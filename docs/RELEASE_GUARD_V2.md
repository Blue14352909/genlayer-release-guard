# ReleaseGuard V2 — Challengeable, Revocable On-Chain Release Attestations

This document describes **`contracts/release_guard_v2.py`**, a standalone GenLayer
intelligent contract that adds a public, challengeable release-attestation
registry on top of the verification model already proven by ReleaseGuard V1.

> **Status.** V2 is a new, unlisted contract. It has **not been deployed**, has
> **not been audited**, and is **not production-ready or accepted**. Everything
> below is local direct-mode testing plus a Studio procedure you run yourself.
> Nothing in this document claims V2 is secure, deployed, or accepted.

V1 is preserved unchanged: `contracts/release_guard.py`, its tests, its docs and
its Studio deployment/evidence are untouched. V2 is a separate contract with a
separate test suite and separate storage.

---

## 1. What V2 solves that V1 did not

V1 answers one question once:

> Does this release claim hold up against source / license / vulnerability
> evidence, according to GenLayer consensus?

V1's answer is **terminal and unquestionable**. Once a verification is
`VERIFIED`, nothing can challenge it; a release that later turns out to have a
disclosed critical vulnerability, or a license change, or forged evidence, stays
`VERIFIED` forever.

V2 adds the missing half of a real attestation system:

| Capability | V1 | V2 |
|---|---|---|
| Consensus verification of a release claim | ✅ | ✅ |
| Durable, queryable record | ✅ | ✅ |
| Canonical lookup by exact project + version | ❌ | ✅ `get_current_attestation` |
| Anyone can **challenge** an attested release | ❌ | ✅ `open_challenge` |
| Validators independently re-evaluate the **original + challenge** evidence | ❌ | ✅ |
| Attestation can be **revoked** by substantiated evidence | ❌ | ✅ |
| Contested evidence must not silently stay "safe" | ❌ | ✅ (drops to `UNRESOLVED`) |
| Challenge history per claim | ❌ | ✅ `get_claim_challenges` |

In short: V2 makes an attestation **accountable**. It is a reusable primitive —
not a reputation score, generic AI analysis, wallet app, payment product, or
frontend feature.

---

## 2. Supported policies

V2 deliberately supports **only** the three policies V1 already implements and
advertises:

| Policy | Question it asks |
|---|---|
| `source` | Does the evidence URL genuinely contain the claimed project **and** exact version? |
| `license` | Is the license text observed, and is the license permissive? |
| `vulnerability` | Are there known critical/high vulnerabilities? |

Any other policy name is **unsupported**. An unsupported policy is never
silently accepted and never silently dropped: it poisons the whole claim and the
result is `UNRESOLVED` with `reason_code = "UNSUPPORTED_POLICY"`. No partial
attestation is produced.

`policy_text` is a comma-separated string, e.g. `"source,license,vulnerability"`.
Order is preserved and **duplicates are collapsed deterministically** (first
occurrence wins), so `"source,source"` runs the source check once. A blank,
whitespace-only, or comma-only policy is valid input but fails closed to
`UNRESOLVED` (`EMPTY_POLICY`).

---

## 3. State machine

### 3.1 Claim states

| State | Meaning |
|---|---|
| `PENDING` | Created, not yet reviewed. |
| `RUNNING` | Transient — review in flight (mirrors V1). Never a resting state. |
| `ATTESTED` | Every requested policy explicitly passed. Challengeable. |
| `REJECTED` | At least one requested policy explicitly failed. |
| `UNRESOLVED` | Evidence insufficient/malformed/unreachable/unsupported, or consensus could not agree. |
| `CHALLENGED` | An open challenge exists. The attestation is contested but not yet withdrawn. |
| `REVOKED` | A substantiated challenge showed the attestation can no longer be relied upon. |

`attestation_state` is the safety-relevant projection: `""` while
`PENDING`/`RUNNING`, then `ATTESTED` / `REJECTED` / `REVOKED` / `UNRESOLVED`. It
stays `ATTESTED` while the claim is `CHALLENGED`. Consumers that need certainty
must treat `CHALLENGED` as **contested**.

### 3.2 Challenge states

| State | Meaning |
|---|---|
| `OPEN` | Challenge exists; the claim is `CHALLENGED`. |
| `RESOLVED` | Adjudicated to a decision (`outcome` is `ATTESTED` or `REVOKED`). |
| `UNRESOLVED` | Adjudication could not safely resolve; claim dropped to `UNRESOLVED`. |

### 3.3 Transition table

**Claim**

| From | Event | To | Notes |
|---|---|---|---|
| — | `create_claim` | `PENDING` | Reserves the canonical key. |
| `PENDING` | `run_claim_review` → all PASS | `ATTESTED` | |
| `PENDING` | `run_claim_review` → any FAIL | `REJECTED` | FAIL dominates. |
| `PENDING` | `run_claim_review` → anything else | `UNRESOLVED` | Fail closed. |
| `ATTESTED` | `open_challenge` | `CHALLENGED` | Only ATTESTED claims are challengeable. |
| `CHALLENGED` | `run_challenge_review` → `ATTESTED` | `ATTESTED` | Challenge rejected; attestation stands. |
| `CHALLENGED` | `run_challenge_review` → `REVOKED` | `REVOKED` | Terminal; cannot be restored. |
| `CHALLENGED` | `run_challenge_review` → `UNRESOLVED` | `UNRESOLVED` | Contested result cannot stay safe. |

**Challenge**

| From | Event | To | Notes |
|---|---|---|---|
| — | `open_challenge` | `OPEN` | Rejected unless the claim is `ATTESTED`. |
| `OPEN` | `run_challenge_review` → contradiction rejected | `RESOLVED` | `outcome = ATTESTED`. |
| `OPEN` | `run_challenge_review` → contradiction upheld (or original now fails) | `RESOLVED` | `outcome = REVOKED`. |
| `OPEN` | `run_challenge_review` → cannot resolve / consensus failure | `UNRESOLVED` | `outcome = UNRESOLVED`. |

**Forbidden transitions (all rejected):** reviewing a non-`PENDING` claim;
challenging a `PENDING`/`REJECTED`/`REVOKED`/`UNRESOLVED` claim; a second
concurrent challenge; an identical (evidence URL, reason) challenge; a challenge
reusing the claim's own evidence URL; restoring a `REVOKED` claim to `ATTESTED`;
creating a duplicate canonical claim for the same exact project + version.

---

## 4. How consensus is used

V2 has two independent consensus blocks, both using the repository's existing
leader/validator pattern (`gl.vm.run_nondet_unsafe`). All storage values are
copied into local memory before either block; mutable storage is never touched
inside a leader/validator callback.

### 4.1 Initial claim review

For each requested, supported policy, the leader fetches the evidence and asks
the model for a structured verdict. The validator independently re-runs the same
leader function against its own fetch and confirms the **check status** matches.
If the validator cannot confirm — different evidence, unreachable evidence,
unrecognised status — `run_nondet_unsafe` raises and the check is recorded as
`INSUFFICIENT_EVIDENCE`.

Each check returns one of `PASS`, `FAIL`, `FETCH_FAILED`, `INSUFFICIENT_EVIDENCE`.

### 4.2 Challenge adjudication

A single consensus block does two things inside the leader:

1. **Re-evaluates the original claim's policies** against the original evidence,
   producing a fresh set of check results.
2. **Adjudicates the challenge evidence**: fetches the challenge URL and asks
   the model for `{"contradiction_established": bool, "reason": str}`, strictly
   validating that the flag is a real boolean.

The leader composes these into one of `ATTESTED` / `REVOKED` / `UNRESOLVED` and
returns the composed outcome. The validator re-runs the whole block and confirms
the **outcome matches**; any disagreement raises, and the contract records
`UNRESOLVED`.

### 4.3 Deterministic composition (no LLM)

The final state is never chosen by the model. It is produced by pure functions:

- `_compose_claim_state(check_results)` — claim terminal state.
- `_compose_challenge_outcome(recomputed, contradiction, evidence_ok)` — challenge outcome.

These are the only places a terminal state is decided.

---

## 5. Fail-closed behaviour

An attestation is **never** returned because data is missing or a call failed.

| Situation | Result |
|---|---|
| Blank / whitespace / comma-only policy | `UNRESOLVED` (`EMPTY_POLICY`) |
| Unsupported policy | `UNRESOLVED` (`UNSUPPORTED_POLICY`) |
| Malformed consensus/LLM response | `UNRESOLVED` |
| Evidence missing / unreachable | `UNRESOLVED` (`FETCH_FAILED`) |
| Empty challenge reason | rejected at `open_challenge` |
| Consensus exception / no validator agreement | `UNRESOLVED` (`CONSENSUS_FAILED`) |
| Missing `critical_count`/`high_count` when vuln data exists | `UNRESOLVED` |
| Boolean or fractional vulnerability counts | `UNRESOLVED` |
| Negative vulnerability counts | `UNRESOLVED` |
| License permissive without observed license text | `UNRESOLVED` |
| Non-boolean semantic flags (`is_permissive`, `page_has_release_content`, …) | `UNRESOLVED` |
| Invalid project/version input | rejected at `create_claim` |
| Challenge on a non-`ATTESTED` claim | rejected at `open_challenge` |
| Duplicate / concurrent / invalid challenge | rejected at `open_challenge` |
| Deterministic composition unexpectedly fails | persisted `UNRESOLVED` (`COMPOSITION_ERROR`), never stale `RUNNING` |

A consensus or runtime failure is **never** recorded as `REJECTED` and **never**
as `ATTESTED`. It becomes `UNRESOLVED`.

Additional carried-forward safety fixes from V1:

- Empty parsed policy fails closed.
- Missing vulnerability counts are *insufficient evidence*, not zero findings.
- Booleans are not valid counts; fractional values are not truncated to zero.
- Source project/version comparison uses exact normalized matching with strict
  token boundaries — a requested version `2` cannot match the `2` in `11.2.0`.
- License passes only when license evidence was actually observed.

The canonical lookup key is `f"{project.strip().lower()}::{version.lower().lstrip('v')}"`
and is used as an **exact map key** — there is no substring matching, so `2` and
`11.2.0` can never collide.

---

## 6. Public method reference

### `create_claim(project_name, version, evidence_url, policy_text) -> str`
Registers a claim and reserves the canonical key. Permissionless. Blank inputs
and duplicate canonical claims are rejected. Returns `"c-<n>"`.

### `run_claim_review(claim_id) -> str`
Runs consensus review of a `PENDING` claim. Returns terminal state
`ATTESTED` | `REJECTED` | `UNRESOLVED`. Permissionless.

### `get_claim(claim_id) -> dict`
Full record: `id`, `requester`, `project_name`, `version`, `evidence_url`,
`policy_text`, `status`, `attestation_state`, `reason_code`, `failed_checks`,
`active_challenge_id`, `results`, `challenge_ids`.

### `open_challenge(claim_id, evidence_url, reason) -> str`
Opens a challenge against an `ATTESTED` claim. Permissionless. Rejects non-attested
claims, concurrent challenges, duplicate (URL, reason) challenges, and evidence
equal to the claim's own URL. Returns `"x-<n>"`.

### `run_challenge_review(challenge_id) -> str`
Runs consensus adjudication of an `OPEN` challenge. Returns
`ATTESTED` | `REVOKED` | `UNRESOLVED` and applies the matching claim transition.
Permissionless.

### `get_challenge(challenge_id) -> dict`
Full record: `id`, `claim_id`, `challenger`, `evidence_url`, `reason`, `status`,
`outcome`, `reason_code`, `results`.

### `get_current_attestation(project_name, version) -> dict`
Canonical current record for an exact project + version: `exists`,
`project_name`, `version`, `claim_id`, `status`, `attestation_state`,
`reason_code`. Returns `exists = False` when no claim exists.

### `get_claim_challenges(claim_id) -> list`
Every challenge opened for a claim, oldest first.

**No funds, no wallet, no escrow, no `.payable`.** There is no payment path.

---

## 7. Local test commands

Run from the repository root, in the project's pinned environment
(`requirements.txt`; `python 3.12`).

```bash
# V2 direct tests only
python -m pytest tests/direct/test_release_guard_v2.py -v --tb=short

# Entire direct suite (V1 + V2)
python -m pytest tests/direct/ -v --tb=short

# Lint the V2 contract the same way CI does
PYTHONIOENCODING=utf-8 genvm-lint contracts/release_guard_v2.py
```

`gltest.config.yaml` selects `localnet`; direct tests do not require a running
node or any network access.

---

## 8. GenLayer Studio deployment and test procedure

> This is the procedure **you** run. V2 is not deployed by this document, and
> no new deployment has been made.

### 8.1 Deploy

1. Open GenLayer Studio and connect to **Studionet**.
2. Create a new file and paste the **entire** contents of
   `contracts/release_guard_v2.py`, keeping the first line dependant header
   (`# { "Depends": "py-genlayer:…" }`) intact.
3. Deploy the contract. Note the deployed **contract address**.
4. (Optional) In the Studio UI, call the read method
   `get_current_attestation("requests","2.31.0")` — it should return
   `exists: false` before any claim is created.

### 8.2 Example scenario: one ATTESTED claim, then one REVOKED/UNRESOLVED challenge

This mirrors the direct tests and uses a real, public evidence URL.

**Step 1 — create a claim.**

Call `create_claim` with:

| Argument | Value |
|---|---|
| `project_name` | `requests` |
| `version` | `2.31.0` |
| `evidence_url` | `https://pypi.org/project/requests/2.31.0/` |
| `policy_text` | `source` |

Expect a return value like `c-1`.

**Step 2 — run the initial review.**

Call `run_claim_review("c-1")`. Expect `ATTESTED`.

**Step 3 — inspect the ATTESTED state.**

Call `get_claim("c-1")`. Confirm `status == "ATTESTED"`,
`attestation_state == "ATTESTED"`, `reason_code == ""`, and
`results[0].status == "PASS"`.
Then call `get_current_attestation("requests","2.31.0")` and confirm
`exists == true` and `attestation_state == "ATTESTED"`.

**Step 4 — open a genuine conflicting-evidence challenge.**

Call `open_challenge` with:

| Argument | Value |
|---|---|
| `claim_id` | `c-1` |
| `evidence_url` | a real page that **contradicts** the original claim, e.g. a security advisory page for `requests` that discloses a critical/high issue, or an equally concrete contradicting source |
| `reason` | a short, concrete sentence describing the contradiction |

Expect a return value like `x-1`. The claim is now `CHALLENGED`.

**Step 5 — run the challenge review.**

Call `run_challenge_review("x-1")`.

**Step 6 — inspect the final result.**

- Call `get_challenge("x-1")`: expect `status` in
  (`RESOLVED`, `UNRESOLVED`) and `outcome` in (`ATTESTED`, `REVOKED`, `UNRESOLVED`).
- Call `get_claim("c-1")`: expect the claim to be `REVOKED` when the challenge is
  upheld, or `UNRESOLVED` when the evidence could not be safely resolved.
- Call `get_current_attestation("requests","2.31.0")`: expect
  `attestation_state` to be `REVOKED` (or `UNRESOLVED`), **not** `ATTESTED`.

If the challenge evidence turns out not to establish a contradiction, the
challenge resolves `ATTESTED` and the claim **stays** `ATTESTED` — the challenge
result is still recorded in `get_claim_challenges("c-1")`.

### 8.3 Interpreting results

- A challenge that cannot be fetched, parsed, or agreed upon yields
  `UNRESOLVED` — the claim does **not** remain safely attested. This is
  intentional and is not a failure of the contract.
- A `REVOKED` claim is **terminal**. `open_challenge` will refuse further
  challenges, and no code path can restore `ATTESTED`.

---

## 9. Scope and honesty

- V2 is **not deployed**. The example above is a Studionet procedure, not a
  record of a completed deployment.
- V2 is **not audited**, **not production-ready**, and **not accepted** as a
  GenLayer Project Milestone. This document is a description of the code and its
  tests, not a claim of endorsement.
- The contract is intentionally limited to three policies. Broader policy
  coverage is out of scope for V2.
- Direct tests run against mocks; they prove contract logic and fail-closed
  behaviour, not the real-world accuracy of any model.
