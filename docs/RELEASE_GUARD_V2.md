# ReleaseGuard V2 - Challengeable, Revocable On-Chain Release Attestations

This document describes `contracts/release_guard_v2.py`, a standalone GenLayer
intelligent contract that adds a public, challengeable, revocable
release-attestation registry on top of the verification model already proven by
ReleaseGuard V1.

> **Status.** V2 is a new, unlisted contract. It has **not been deployed**, has
> **not been audited**, and is **not production-ready or accepted** as a
> GenLayer Project revision or Milestone. Everything below is local direct-mode
> testing plus a Studio procedure you run yourself. Nothing in this document
> claims V2 is secure, deployed, or accepted.

V1 is preserved unchanged: `contracts/release_guard.py`, its tests, its docs and
its Studio deployment/evidence are untouched. V2 is a separate contract with a
separate test suite and separate storage.

---

## 1. Purpose: what V2 adds over V1

V1 answers one question once:

> Does this release claim hold up against source / license / vulnerability
> evidence, according to GenLayer consensus?

V1's answer is **terminal and unquestionable**. Once a verification is
`VERIFIED`, nothing can challenge it. A release that later turns out to have a
disclosed critical vulnerability, or forged evidence, stays `VERIFIED` forever.

V2 adds the missing half of a real attestation system.

| Capability | V1 | V2 |
|---|---|---|
| Consensus verification of a release claim | yes | yes |
| Durable, queryable record | yes | yes |
| Canonical lookup by exact project + version | no | yes (`get_current_attestation`) |
| Anyone can challenge an attested release | no | yes (`open_challenge`) |
| Validators independently re-check original + challenge evidence | no | yes |
| Attestation can be **revoked** by substantiated evidence | no | yes |
| Contested evidence must not silently stay "safe" | no | yes (drops to `DISPUTED`) |
| Unusable challenge evidence can never damage an attestation | n/a | yes (challenge `INVALID`) |
| Challenge history per claim | no | yes (`get_claim_challenges`) |

**V1 vs V2 boundary.** V1 is a one-shot verdict for a single claim. V2 is a
stateful registry: at most one *canonical* claim per exact project + version,
which anyone may challenge and which consensus may revoke. V2 does not modify,
read, or migrate V1 state; the two contracts are independent. V2 is a reusable
primitive - not a reputation score, not a generic AI analysis product, not a
wallet or payment product, and not a frontend feature.

---

## 2. Supported policies

V2 deliberately supports **only** the three policies V1 already implements:

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

## 3. Canonical binding (anti-squatting)

The canonical map answers exactly one question: *which claim is the historical
record for this exact project + version?*

- `create_claim` **never** reserves or writes the canonical mapping. Creating a
  claim is permissionless and cheap, and it has no side effect on canonical
  state.
- A `PENDING`, `RUNNING`, `REJECTED`, or `UNRESOLVED` claim therefore **never
  blocks** another claim for the same normalized project/version. Anyone may
  create as many claims as they like for a version; nothing is reserved.
- The canonical key is bound **only** when a review genuinely reaches
  `ATTESTED`, and only if no other claim is already canonical for that exact
  key.
- If another claim is already canonical, the competing claim is **not**
  overwritten and is **not** mislabelled `REJECTED`. It finishes `UNRESOLVED`
  with `reason_code = "CANONICAL_ATTESTATION_EXISTS"`.
- Once bound, a canonical record stays the historical record for that exact
  version **even after it is `REVOKED`**. A later claim can never silently
  replace it (it again finishes `CANONICAL_ATTESTATION_EXISTS`).

This removes the canonical-claim-squatting attack: no attacker can create a
bad, unfinished, rejected, or unresolved claim for a project/version and
permanently block the legitimate release claim.

Canonical keys are built by `_canonical_key`:
`"<project.strip().lower()>::<version.strip().lower() with leading 'v' removed>"`.
Lookup is an **exact map key**, never a substring search, so version `2` can
never collide with `11.2.0`.

`get_current_attestation(project_name, version)`:
- returns `exists = False` when nothing has been bound for that exact key;
- returns the actual canonical claim only after an `ATTESTED` claim was bound;
- always reports that claim's real current `status` and `attestation_state`, so
  a `REVOKED` or `DISPUTED` canonical record is explicitly not attestable;
- uses exact normalized key matching only.

---

## 4. State machine

### 4.1 Claim states

| State | Meaning |
|---|---|
| `PENDING` | Created, not yet reviewed. Not canonical, blocks nothing. |
| `RUNNING` | Transient - review in flight. Never a resting state. |
| `ATTESTED` | Every requested policy explicitly passed. Challengeable. |
| `REJECTED` | At least one requested policy explicitly failed. |
| `UNRESOLVED` | Evidence insufficient/malformed/unreachable/unsupported, consensus could not agree, or the claim lost the canonical race. |
| `CHALLENGED` | An open challenge exists. The attestation is contested but not withdrawn. |
| `DISPUTED` | A challenge's evidence was credible but consensus could not decide, so the release is no longer safely attestable. |
| `REVOKED` | A substantiated challenge showed the attestation can no longer be relied upon. Terminal. |

`attestation_state` is the safety-relevant projection: `""` while
`PENDING`/`RUNNING`, otherwise one of `ATTESTED`, `REJECTED`, `UNRESOLVED`,
`DISPUTED`, `REVOKED`. It stays `ATTESTED` while the claim is `CHALLENGED`
(contested but not withdrawn); consumers that need certainty must treat
`status == "CHALLENGED"` as **contested**.

### 4.2 Challenge states

| State | Meaning |
|---|---|
| `OPEN` | Challenge exists; the claim is `CHALLENGED`. |
| `INVALID` | The challenge evidence was unusable (unreachable/empty/too short). The original attestation stands unchanged. |
| `RESOLVED` | Decided: `outcome` is `ATTESTED` (challenge rejected) or `REVOKED` (challenge upheld). |
| `DISPUTED` | The evidence was retrievable and meaningful, but consensus could not safely decide; the claim dropped to `DISPUTED`. |

`outcome` mirrors the classification: `INVALID`, `ATTESTED`, `REVOKED`, or
`DISPUTED` (empty while `OPEN`).

### 4.3 Challenge outcomes and their reasons

| Outcome | reason_code | Meaning |
|---|---|---|
| `INVALID` | `CHALLENGE_EVIDENCE_UNUSABLE` | Challenge evidence could not be retrieved, was empty, or was shorter than the 20-character minimum. The attestation is **preserved**. |
| `REVOKED` | `ORIGINAL_NO_LONGER_VALID` | The original policy now explicitly fails on re-evaluation. |
| `REVOKED` | `CHALLENGE_UPHELD` | Consensus established the contradiction. |
| `ATTESTED` | `CHALLENGE_REJECTED` | Consensus rejected the contradiction; the attestation stands. |
| `DISPUTED` | `ORIGINAL_NOT_CONFIRMED` | The original claim could not be re-confirmed. |
| `DISPUTED` | `CHALLENGE_UNDECIDED` | Adjudication returned no usable yes/no (malformed or non-boolean). |
| `DISPUTED` | `CONSENSUS_FAILED` | Consensus could not be reached at all. |
| `DISPUTED` | `MALFORMED_CHALLENGE_RESPONSE` | The consensus result was not a usable outcome. |

### 4.4 Transition table

**Claim**

| From | Event | To | Notes |
|---|---|---|---|
| - | `create_claim` | `PENDING` | No canonical reservation. |
| `PENDING` | `run_claim_review` -> all PASS, no canonical conflict | `ATTESTED` | Canonical key bound to this claim. |
| `PENDING` | `run_claim_review` -> all PASS, canonical already held | `UNRESOLVED` | `CANONICAL_ATTESTATION_EXISTS`; canonical untouched. |
| `PENDING` | `run_claim_review` -> any FAIL | `REJECTED` | FAIL dominates. |
| `PENDING` | `run_claim_review` -> anything else | `UNRESOLVED` | Fail closed. |
| `ATTESTED` | `open_challenge` | `CHALLENGED` | Only `ATTESTED` claims are challengeable. |
| `CHALLENGED` | `run_challenge_review` -> `INVALID` | `ATTESTED` | Unusable evidence; attestation preserved, lock cleared. |
| `CHALLENGED` | `run_challenge_review` -> `ATTESTED` | `ATTESTED` | Challenge rejected; attestation stands. |
| `CHALLENGED` | `run_challenge_review` -> `REVOKED` | `REVOKED` | Terminal; can never be restored. |
| `CHALLENGED` | `run_challenge_review` -> `DISPUTED` | `DISPUTED` | No longer safely attestable. |

**Challenge**

| From | Event | To | Notes |
|---|---|---|---|
| - | `open_challenge` | `OPEN` | Rejected unless the claim is `ATTESTED`. |
| `OPEN` | `run_challenge_review` -> evidence unusable | `INVALID` | `outcome = INVALID`. |
| `OPEN` | `run_challenge_review` -> contradiction rejected | `RESOLVED` | `outcome = ATTESTED`. |
| `OPEN` | `run_challenge_review` -> contradiction upheld, or original now fails | `RESOLVED` | `outcome = REVOKED`. |
| `OPEN` | `run_challenge_review` -> credible but undecidable | `DISPUTED` | `outcome = DISPUTED`. |

**Forbidden transitions (all rejected with a revert):** reviewing a
non-`PENDING` claim; challenging a claim that is not `ATTESTED`; a second
concurrent challenge; an identical `(evidence URL, reason)` challenge; a
challenge reusing the claim's own evidence URL; a challenge with an invalid
reason or evidence URL; restoring a `REVOKED` claim to `ATTESTED`.

---

## 5. HTTPS evidence URL requirements

Both `create_claim` and `open_challenge` run a **deterministic, dependency-free**
validator before any nondeterministic retrieval. Accepted URLs must:

- be non-blank and contain no leading/trailing whitespace, whitespace, or
  control characters;
- use the `https` scheme followed by `//` (so `http`, `file`, `data`,
  `javascript`, `ftp`, and every other scheme are rejected);
- have a non-empty authority with no userinfo (`user@host`);
- have a numeric port in `1..65535` when a port is present;
- have a plausible public host: not `localhost` or a local suffix
  (`.localhost`, `.local`, `.internal`, `.lan`, `.home.arpa`,
  `.localdomain`), not an IPv4/IPv6 literal, and not a single-label host;
- match a conservative public-hostname shape (alphanumeric labels with
  internal hyphens, at least one dot, alphabetic TLD of length >= 2).

`reason` for `open_challenge` must be non-blank, at most 400 characters, and
free of control characters.

> **This is a structural guard only.** Passing URL validation does **not** prove
> that a hostname is publicly reachable or that its content is meaningful.
> Reachability is decided separately, and a challenge whose evidence turns out
> to be unusable is classified `INVALID` (see section 4.3).

---

## 6. How consensus is used

V2 has two independent consensus blocks, both using the repository's existing
leader/validator pattern (`gl.vm.run_nondet_unsafe`). All storage values are
copied into local memory before either block; mutable storage is never touched
inside a leader/validator callback.

### 6.1 Initial claim review

For each requested, supported policy, the leader fetches the evidence and asks
the model for a structured verdict. The validator independently re-runs the same
leader function against its own fetch and confirms the **check status** matches.
If the validator cannot confirm - different evidence, unreachable evidence,
unrecognised status - `run_nondet_unsafe` raises and the check is recorded as
`INSUFFICIENT_EVIDENCE`.

Each check returns one of `PASS`, `FAIL`, `FETCH_FAILED`, `INSUFFICIENT_EVIDENCE`.

### 6.2 Challenge adjudication

A single consensus block does two things inside the leader:

1. **Re-evaluates the original claim's policies** against the original evidence,
   producing a fresh set of check results. A check that cannot be re-run is
   recorded as `INSUFFICIENT_EVIDENCE` inside the leader (not raised), so the
   outcome stays deterministic.
2. **Adjudicates the challenge evidence**: fetches the challenge URL and asks
   the model for `{"contradiction_established": bool, "reason": str}`, strictly
   validating that the flag is a real boolean. A malformed or failed
   adjudication becomes "undecided" (`contradiction = None`), never a silent
   pass.

The leader composes these into one of `INVALID` / `ATTESTED` / `REVOKED` /
`DISPUTED` and returns the composed outcome. The validator re-runs the whole
block and confirms the **outcome matches**; any disagreement raises, and the
contract records `DISPUTED`.

### 6.3 Deterministic composition (no LLM)

The final state is never chosen by the model. It is produced by pure functions:

- `_compose_claim_state(check_results)` - claim terminal state.
- `_compose_challenge_outcome(recomputed, contradiction, evidence_ok)` - challenge outcome.

These are the only places a terminal state is decided.

---

## 7. Fail-closed rules

An attestation is **never** returned because data is missing or a call failed.

| Situation | Result |
|---|---|
| Blank / whitespace / comma-only policy | `UNRESOLVED` (`EMPTY_POLICY`) |
| Unsupported policy | `UNRESOLVED` (`UNSUPPORTED_POLICY`) |
| Malformed consensus/LLM response | `UNRESOLVED` |
| Evidence missing / unreachable (initial review) | `UNRESOLVED` (`FETCH_FAILED`) |
| Missing `critical_count`/`high_count` when vuln data exists | `UNRESOLVED` |
| Boolean or fractional vulnerability counts | `UNRESOLVED` |
| Negative vulnerability counts | `UNRESOLVED` |
| License permissive without observed license text | `UNRESOLVED` |
| Non-boolean semantic flags (`is_permissive`, `page_has_release_content`, ...) | `UNRESOLVED` |
| Consensus exception / no validator agreement (initial review) | `UNRESOLVED` (`CONSENSUS_FAILED`) |
| Deterministic composition unexpectedly fails | `UNRESOLVED` (`COMPOSITION_ERROR`), never a stale `RUNNING` |
| Claim would attest but another claim is already canonical | `UNRESOLVED` (`CANONICAL_ATTESTATION_EXISTS`) |
| Challenge evidence unusable | challenge `INVALID`; claim stays `ATTESTED` |
| Original claim cannot be re-confirmed during a challenge | claim `DISPUTED` (`ORIGINAL_NOT_CONFIRMED`) |
| Challenge adjudication undecidable / malformed | claim `DISPUTED` |
| Challenge consensus failure | claim `DISPUTED` (`CONSENSUS_FAILED`) |
| Invalid project/version/evidence URL input | rejected at `create_claim` |
| Non-`ATTESTED` claim, concurrent, duplicate, or same-URL challenge | rejected at `open_challenge` |
| Blank / too-long / control-character challenge reason | rejected at `open_challenge` |

A consensus or runtime failure during an **initial review** is never `REJECTED`
and never `ATTESTED`; it becomes `UNRESOLVED`. During a **challenge review** it
becomes `DISPUTED` - a state that is explicitly not safely attestable.

Additional carried-forward safety fixes from V1:

- Empty parsed policy fails closed.
- Missing vulnerability counts are *insufficient evidence*, not zero findings.
- Booleans are not valid counts; fractional values are not truncated to zero.
- Source project/version comparison uses exact normalized matching with strict
  token boundaries - a requested version `2` cannot match the `2` in `11.2.0`.
- License passes only when license evidence was actually observed.

---

## 8. Public method reference

### `create_claim(project_name, version, evidence_url, policy_text) -> str`
Registers a claim. Permissionless. Rejects blank inputs and invalid evidence
URLs. Never touches canonical state. Returns `"c-<n>"`.

### `run_claim_review(claim_id) -> str`
Runs consensus review of a `PENDING` claim and binds the canonical key only on a
genuine `ATTESTED`. Returns `ATTESTED` | `REJECTED` | `UNRESOLVED`.
Permissionless.

### `get_claim(claim_id) -> dict`
Full record: `id`, `requester`, `project_name`, `version`, `evidence_url`,
`policy_text`, `status`, `attestation_state`, `reason_code`, `failed_checks`,
`active_challenge_id`, `results`, `challenge_ids`.

### `open_challenge(claim_id, evidence_url, reason) -> str`
Opens a challenge against an `ATTESTED` claim. Permissionless. Rejects
non-attested claims, concurrent challenges, duplicate `(URL, reason)`
challenges, evidence equal to the claim's own URL, invalid URLs, and invalid
reasons. Returns `"x-<n>"`.

### `run_challenge_review(challenge_id) -> str`
Runs consensus adjudication of an `OPEN` challenge. Returns `INVALID` |
`ATTESTED` | `REVOKED` | `DISPUTED` and applies the matching claim transition.
Permissionless.

### `get_challenge(challenge_id) -> dict`
Full record: `id`, `claim_id`, `challenger`, `evidence_url`, `reason`, `status`,
`outcome`, `reason_code`, `results`.

### `get_current_attestation(project_name, version) -> dict`
Canonical record for an exact project + version: `exists`, `project_name`,
`version`, `claim_id`, `status`, `attestation_state`, `reason_code`.
`exists = False` until an `ATTESTED` claim has been bound.

### `get_claim_challenges(claim_id) -> list`
Every challenge opened for a claim, oldest first.

**No funds, no wallet, no escrow, no `.payable`.** There is no payment path.

---

## 9. Local test commands

Run from the repository root, in the project's pinned environment
(`requirements.txt`; Python 3.12).

```bash
# V2 direct tests only
python -m pytest tests/direct/test_release_guard_v2.py -q --tb=short

# Entire direct suite (V1 + V2) - the default, reproducible evidence
python -m pytest tests/direct -q

# Full suite: direct tests pass, Studio-only tests skip with a reason
python -m pytest -q

# Lint the V2 contract the same way CI does
PYTHONIOENCODING=utf-8 genvm-lint contracts/release_guard_v2.py
```

`gltest.config.yaml` selects `localnet`; direct tests do not require a running
node or any network access, and they are the only tests used as reproducible
evidence.

---

## 10. Studio-only integration test requirement

`tests/integration/test_release_guard_studio.py` talks to a **real** GenLayer
network (real consensus, real web retrieval, real LLM evaluation). It is opt-in
and is **never** part of the default direct-mode evidence. It does not fake a
deployed contract or a consensus result.

By default it **SKIPS** with an explicit reason rather than erroring:

```
SKIPPED ... GenLayer Studio integration test skipped: no deployed contract is
configured. Set RELEASEGUARD_STUDIO_CONTRACT_ADDRESS to the address of an
already-deployed ReleaseGuard contract (and make sure gltest.config.yaml points
at a reachable network) to run it. ...
```

Required setting to actually run it:

| Setting | Required | Meaning |
|---|---|---|
| `RELEASEGUARD_STUDIO_CONTRACT_ADDRESS` | yes | Address of an already-deployed ReleaseGuard contract on the target network. |
| `RELEASEGUARD_STUDIO_CONTRACT_FILE` | no | Contract source used to build the method schema. Absolute, or relative to the contracts directory. Defaults to `contracts/release_guard.py`. |
| Network / RPC / accounts | inherited | Taken from `gltest.config.yaml` and the usual gltest options (`--network`, `--rpc-url`, `--contracts-dir`). |

The `deployed_contract` fixture (in `tests/integration/conftest.py`) builds a
real gltest contract handle from that address. If the address or network is
wrong, the tests fail for real - they do not fall back to a fake contract.

Honest limitation: the full Studio lifecycle below has **not** been executed as
part of this change, because no live deployment and network were available. Only
the fixture's skip behaviour, its real (non-mock) build path, and the direct
suite were verified locally.

---

## 11. GenLayer Studio lifecycle (for you to run)

> This is the procedure **you** run. V2 is not deployed by this document, and no
> new deployment has been made.

1. **Deploy V2.** Open GenLayer Studio on **Studionet**, paste the entire
   `contracts/release_guard_v2.py` (keeping the first `# { "Depends": ... }`
   header), and deploy. Note the contract address.
2. **Create a claim.** `create_claim("requests", "2.31.0",
   "https://pypi.org/project/requests/2.31.0/", "source")`. Expect `c-1`.
   Calling `get_current_attestation("requests","2.31.0")` now must return
   `exists: false` - creation reserves nothing.
3. **Run the claim review.** `run_claim_review("c-1")`. Expect `ATTESTED`.
4. **Inspect the current attestation.** `get_claim("c-1")` should show
   `status == "ATTESTED"` and `results[0].status == "PASS"`, and
   `get_current_attestation("requests","2.31.0")` should now return
   `exists: true` with `claim_id == "c-1"` and `attestation_state == "ATTESTED"`.
5. **Open a challenge.** `open_challenge("c-1", <a real page that contradicts
   the claim>, <a short concrete reason>)`. Expect `x-1`; the claim is now
   `CHALLENGED`.
6. **Run the challenge review.** `run_challenge_review("x-1")`.
7. **Inspect the final canonical result.**
   - `get_challenge("x-1")`: expect `status` in (`RESOLVED`, `INVALID`,
     `DISPUTED`) and `outcome` in (`ATTESTED`, `REVOKED`, `INVALID`,
     `DISPUTED`).
   - `get_claim("c-1")`: expect `REVOKED` when the challenge is upheld,
     `ATTESTED` when it is rejected or invalid, and `DISPUTED` when consensus
     could not decide.
   - `get_current_attestation("requests","2.31.0")`: expect `REVOKED`,
     `DISPUTED`, or `ATTESTED` consistent with the above - and **not** a
     silently unchanged `ATTESTED` after a substantiated or undecidable
     challenge.

Interpreting results:

- A challenge that cannot be fetched, parsed, or agreed upon does **not** leave
  a false sense of safety. Unreachable/empty/tiny evidence is `INVALID` and the
  attestation survives; credible-but-undecidable evidence is `DISPUTED`.
- A `REVOKED` claim is **terminal**. `open_challenge` refuses further
  challenges, and no code path can restore `ATTESTED`.
- A `DISPUTED` claim is not challengeable again (only `ATTESTED` claims are),
  and it is never reported as safely attested. Resolving a `DISPUTED` state
  would require a future revision.

---

## 12. Scope and honesty

- V2 is **not deployed**. The procedure above is a Studionet procedure, not a
  record of a completed deployment.
- V2 is **not audited**, **not production-ready**, and **not accepted** as a
  GenLayer Project revision or Milestone. This document describes the code and
  its tests, not an endorsement.
- The contract is intentionally limited to three policies. Broader policy
  coverage is out of scope for V2.
- Direct tests run against mocks. They prove contract logic and fail-closed
  behaviour, not the real-world accuracy of any model.
- The Studio integration tests are opt-in and skip by default; they were not
  executed against a live network as part of this change.
