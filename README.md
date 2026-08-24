# ReleaseGuard

**On-chain Release Attestation via AI-Adjudicated Consensus**

A GenLayer Intelligent Contract system that evaluates whether software releases satisfy configurable verification policies using nondeterministic AI analysis and consensus-based verification.

---

## Problem

Software supply chain attacks exploit the gap between "a release exists" and "this release is trustworthy." Existing tools check hashes and signatures but cannot evaluate whether a release page actually matches the claimed project, whether the license is acceptable, whether known vulnerabilities exist, or whether the release satisfies arbitrary organizational policies.

Centralized review solves this at the cost of trust, scalability, and speed. ReleaseGuard solves it with decentralized AI consensus: multiple independent validators evaluate the same evidence and must agree on categorical verdicts before any verification is recorded on-chain.

---

## Architecture

```
                    ReleaseGuard
                    ┌──────────────────────────────────────┐
                    │                                      │
  User ────► create_verification()                        │
                    │                                      │
                    │  ┌──────────────────────────────┐    │
                    │  │  Verification Pipeline        │    │
                    │  │                              │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ SourceAttestation    │─────│────│──► Does URL contain release?
                    │  │  └─────────────────────┘     │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ VersionAttestation  │─────│────│──► Does version exist?
                    │  │  └─────────────────────┘     │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ LicenseCheck         │─────│────│──► Is license acceptable?
                    │  │  └─────────────────────┘     │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ VulnerabilityCheck   │─────│────│──► Are there vulns?
                    │  │  └─────────────────────┘     │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ FreshnessCheck       │─────│────│──► Is evidence recent?
                    │  │  └─────────────────────┘     │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ SourceCorroboration  │─────│────│──► Do sources agree?
                    │  │  └─────────────────────┘     │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ SemanticPolicy       │─────│────│──► Custom NL policy?
                    │  │  └─────────────────────┘     │    │
                    │  │                              │    │
                    │  │  ┌─────────────────────┐     │    │
                    │  │  │ Verdict Composer     │─────│────│──► Final VERIFIED/REJECTED/INCONCLUSIVE
                    │  │  └─────────────────────┘     │    │
                    │  └──────────────────────────────┘    │
                    └──────────────────────────────────────┘
```

---

## Verification Primitives

ReleaseGuard is composed of 7 reusable verification primitives, each independently usable by other GenLayer builders.

### SourceAttestation

**Question:** Does this URL actually contain the claimed release?

| Field | Value |
|---|---|
| Consensus | `run_nondet_unsafe` (partial field matching) |
| Standalone use | Verify a release page is legitimate before trusting its contents |
| Input | URL, project name, version |
| Output | PASS / FAIL / FETCH_FAILED / INSUFFICIENT_EVIDENCE |
| Pipeline | Web → LLM extracts facts → derive verdict → compare verdict |

### VersionAttestation

**Question:** Does the claimed version exist and correspond to real artifacts?

| Field | Value |
|---|---|
| Consensus | `run_nondet_unsafe` (partial field matching) |
| Standalone use | Verify a version string exists before trusting it |
| Input | URL, project name, version |
| Output | PASS / FAIL / FETCH_FAILED / INSUFFICIENT_EVIDENCE |
| Pipeline | Web → LLM extracts {version_found} → derive verdict → compare |

### LicenseCheck

**Question:** Does the project use an allowed license?

| Field | Value |
|---|---|
| Consensus | `run_nondet_unsafe` (partial field matching) |
| Standalone use | Check if a project's license is on your allowlist |
| Input | URL, project name, allowed licenses |
| Output | PASS / FAIL / FETCH_FAILED / INSUFFICIENT_EVIDENCE |
| Pipeline | Web → LLM extracts {license_name} → compare against allowlist → compare verdict |

### VulnerabilityCheck

**Question:** Are there known critical/high vulnerabilities?

| Field | Value |
|---|---|
| Consensus | `run_nondet_unsafe` (structured comparison) |
| Standalone use | Check for known CVEs before adopting a dependency |
| Input | URL, project name, version |
| Output | PASS / FAIL / FETCH_FAILED / INSUFFICIENT_EVIDENCE |
| Pipeline | Web → LLM extracts {critical_count, high_count} → compare verdict AND counts |
| Critical | FETCH_FAILED ≠ SAFE — fail closed |

### FreshnessCheck

**Question:** Is the evidence recent enough?

| Field | Value |
|---|---|
| Consensus | `run_nondet_unsafe` (partial field matching) |
| Standalone use | Verify data sources aren't stale |
| Input | URL, project name, version, max_age_days |
| Output | PASS / FAIL / FETCH_FAILED / INSUFFICIENT_EVIDENCE |
| Pipeline | Web → LLM extracts {date_string} → derive freshness → compare verdict |

### SourceCorroboration

**Question:** Do multiple independent sources agree?

| Field | Value |
|---|---|
| Consensus | `run_nondet_unsafe` (partial field matching) |
| Standalone use | Verify a claim isn't just from one source |
| Input | project name, version, 2+ source URLs |
| Output | PASS / FAIL / FETCH_FAILED / INSUFFICIENT_EVIDENCE |
| Pipeline | Fetch both sources → LLM cross-references → 2+ confirming → PASS |

### SemanticPolicy

**Question:** Does a natural-language policy match the evidence?

| Field | Value |
|---|---|
| Consensus | `prompt_non_comparative` |
| Standalone use | Evaluate evidence against any custom requirement |
| Input | URL, project name, version, natural-language policy |
| Output | PASS / FAIL / FETCH_FAILED / INSUFFICIENT_EVIDENCE |
| Pipeline | Leader evaluates policy; validator judges leader's evaluation against criteria |

---

## Consensus Design

ReleaseGuard uses four distinct consensus patterns, each chosen for its specific use case. See [CONSENSUS.md](docs/CONSENSUS.md) for the complete analysis.

| Pattern | Used By | Why |
|---|---|---|
| `run_nondet_unsafe` (partial field matching) | SourceAttestation, VersionAttestation, LicenseCheck, FreshnessCheck, SourceCorroboration | LLM extracts stable facts; validators compare categorical verdict |
| `run_nondet_unsafe` (structured comparison) | VulnerabilityCheck | Verdict AND numeric counts must match |
| `prompt_non_comparative` | SemanticPolicy | Validator judges leader output, doesn't reproduce |
| Deterministic (no LLM) | Orchestrator verdict | Fail-closed rules are pure code — no consensus needed |

### Evidence Status Model

Every check returns one of four statuses:

```
PASS                 Evidence confirms the claim
FAIL                 Evidence contradicts the claim
FETCH_FAILED         Could not retrieve evidence (fail closed — NOT equivalent to PASS)
INSUFFICIENT_EVIDENCE  Evidence available but too weak to decide
```

**Hard invariant (enforced in code):** `FETCH_FAILED` → `INCONCLUSIVE` → `NEVER VERIFIED`. This is deterministic logic, not LLM judgment.

---

## State Machine

```
                  create_verification()
                         │
                         ▼
                      PENDING
                         │
                         │ run_verification()
                         ▼
                      RUNNING
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
         COMPLETED              FAILED
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
VERIFIED  REJECTED  INCONCLUSIVE
```

---

## Security Model

See [SECURITY.md](docs/SECURITY.md) for the complete threat model.

### Key Security Properties

| Property | Mechanism |
|---|---|
| Fail closed | FETCH_FAILED → INCONCLUSIVE → NEVER VERIFIED (deterministic, not LLM) |
| Prompt injection defense | Evidence treated as untrusted; evaluator instructed to ignore embedded instructions |
| No single-source trust | SourceCorroboration requires 2+ independent sources |
| Consensus-gated | Verdicts require majority validator agreement |
| Immutable record | Completed verifications cannot be modified |
| Deterministic composition | Final verdict uses pure code — no LLM judgment in verdict layer |

---

## API

### `create_verification(project_name, version, evidence_url, policy_text) -> str`

Create a new release verification request. Returns a verification ID.

| Parameter | Type | Description |
|---|---|---|
| `project_name` | str | The project name |
| `version` | str | The release version |
| `evidence_url` | str | URL containing release evidence |
| `policy_text` | str | Comma-separated checks: `"source,version,license,vulnerability,freshness"` |

### `run_verification(verification_id) -> str`

Execute the verification pipeline. Returns the final verdict.

### `get_verification(verification_id) -> dict`

Retrieve the full verification record with all check results.

```json
{
  "id": "v-1",
  "project_name": "requests",
  "version": "2.31.0",
  "status": "COMPLETED",
  "verdict": "VERIFIED",
  "reason_code": "",
  "failed_checks": "",
  "results": [
    {"check_name": "source", "status": "PASS", ...},
    {"check_name": "license", "status": "PASS", ...},
    {"check_name": "vulnerability", "status": "PASS", ...}
  ]
}
```

When checks fail:

```json
{
  "verdict": "REJECTED",
  "reason_code": "CHECK_FAILED",
  "failed_checks": "vulnerability"
}
```

When evidence is unavailable:

```json
{
  "verdict": "INCONCLUSIVE",
  "reason_code": "FETCH_FAILED",
  "failed_checks": "vulnerability"
}
```

### `get_verdict(verification_id) -> str`

Retrieve just the final verdict string.

### `get_check_results(verification_id) -> list`

Retrieve individual check results.

---

## Project Structure

```
ReleaseGuard/
├── README.md
├── requirements.txt
├── pyproject.toml
├── gltest.config.yaml
├── .gitignore
├── contracts/
│   ├── source_attestation.py    # Primitive: URL verification
│   ├── version_attestation.py   # Primitive: Version existence
│   ├── license_check.py         # Primitive: License compliance
│   ├── vulnerability_check.py   # Primitive: Security advisory check
│   ├── freshness_check.py       # Primitive: Evidence recency
│   ├── source_corroboration.py  # Primitive: Multi-source verification
│   ├── semantic_policy.py       # Primitive: Custom NL policy evaluation
│   └── release_guard.py         # Orchestrator: Composes all primitives
├── tests/
│   ├── __init__.py
│   ├── direct/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_source_attestation.py
│   │   ├── test_license_check.py
│   │   ├── test_vulnerability_check.py
│   │   └── test_release_guard.py
│   └── integration/
│       ├── __init__.py
│       └── test_release_guard_studio.py
└── docs/
    ├── ARCHITECTURE.md
    ├── CONSENSUS.md
    └── SECURITY.md
```

---

## Installation

```bash
git clone <repository-url>
cd ReleaseGuard
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

---

## Linting

```bash
genvm-lint contracts/release_guard.py
```

---

## Running Tests

### Direct Mode (fast, no Studio)

```bash
pytest tests/direct/ -v
```

### Integration Mode (requires GenLayer Studio)

```bash
gltest tests/integration/ -v -s
```

---

## Deployment

| Item | Value |
|---|---|
| Contract address | `0x54877FDcf9cae0A995a7D5CFDE656723bE13a2b4` |
| Transaction hash | `0x05a35eeaa977620816acde5b4c4e52bd2e0d0e96d678270a0227deafa87e979e` |
| Consensus result | Accepted (5 validators) |
| Explorer | [View on Explorer](https://explorer-studio.genlayer.com/tx/0x05a35eeaa977620816acde5b4c4e52bd2e0d0e96d678270a0227deafa87e979e) |
| Studio | [Import Contract](https://studio.genlayer.com/?import-contract=0x54877FDcf9cae0A995a7D5CFDE656723bE13a2b4) |

---

## License

MIT
