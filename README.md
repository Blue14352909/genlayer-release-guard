# ReleaseGuard

On-chain release attestation for GenLayer. Verifies whether software releases are trustworthy by evaluating them against configurable policies using AI consensus.

## What it does

Takes a release URL + project info, runs checks via GenLayer consensus, returns VERIFIED, REJECTED, or INCONCLUSIVE.

Each check fetches the evidence page, extracts stable facts via LLM, derives a categorical verdict, and reaches consensus across validators. The final verdict is composed deterministically, no LLM involved at the verdict layer.

Key invariant: if we can't check (FETCH_FAILED), we can't approve. That's enforced in code, not left to an LLM.

## Supported policies

The orchestrator (`release_guard.py`) currently wires three checks:

| Policy name | What it checks |
|---|---|
| `source` | Does the URL actually contain the claimed release? |
| `license` | Is the project license on the allowlist? |
| `vulnerability` | Are there known critical/high CVEs? |

Pass these as a comma-separated string: `"source,license,vulnerability"`.

The evidence URL must contain evidence for every requested policy. A PyPI
release page is appropriate for `source,license`; request `vulnerability`
only with an advisory page containing version-specific vulnerability data.
Unavailable evidence returns `INCONCLUSIVE`, never VERIFIED.

For registry and other static pages, the orchestrator first attempts an HTTP
fetch and falls back to rendered text when needed. It accepts a source claim
only when the required facts are explicit and validated.

Empty or invalid policies fail closed (INCONCLUSIVE, never VERIFIED).

## Standalone primitives (not wired into orchestrator)

7 standalone contracts, each usable independently. These are NOT executed by the ReleaseGuard orchestrator — they are reusable building blocks only:

| Contract | Checks | Consensus pattern |
|---|---|---|
| `source_attestation.py` | Does URL contain the release? | `run_nondet_unsafe` |
| `version_attestation.py` | Does the version exist? | `run_nondet_unsafe` |
| `license_check.py` | Is the license allowed? | `run_nondet_unsafe` |
| `vulnerability_check.py` | Any critical CVEs? | `run_nondet_unsafe` (structured) |
| `freshness_check.py` | Is evidence recent? | `run_nondet_unsafe` |
| `source_corroboration.py` | Do 2+ sources agree? | `run_nondet_unsafe` |
| `semantic_policy.py` | Custom NL policy check | `prompt_non_comparative` |

## Evidence status

Every check returns one of:

- **PASS** - evidence confirms the claim
- **FAIL** - evidence contradicts the claim
- **FETCH_FAILED** - couldn't retrieve evidence (fail closed)
- **INSUFFICIENT_EVIDENCE** - evidence too weak to decide

## API

```python
# Create a verification
vid = contract.create_verification(
    "requests", "2.31.0",
    "https://pypi.org/project/requests/2.31.0/",
    "source,license"
)

# Run it
verdict = contract.run_verification(vid)
# "VERIFIED" | "REJECTED" | "INCONCLUSIVE"

# Check results
record = contract.get_verification(vid)
# record["failed_checks"] == ""
# record["reason_code"] == ""
```

## Fail-closed invariants

- Empty policy -> INCONCLUSIVE (never VERIFIED)
- Malformed vulnerability response -> INSUFFICIENT (never VERIFIED)
- FETCH_FAILED -> INCONCLUSIVE (never VERIFIED)
- Unknown check type -> INSUFFICIENT (never VERIFIED)
- Consensus failure -> INSUFFICIENT -> INCONCLUSIVE

## Structure

```
contracts/
  source_attestation.py
  version_attestation.py
  license_check.py
  vulnerability_check.py
  freshness_check.py
  source_corroboration.py
  semantic_policy.py
  release_guard.py          # orchestrator
tests/direct/
  test_source_attestation.py
  test_license_check.py
  test_vulnerability_check.py
  test_release_guard.py
  test_fail_closed.py       # focused regression tests
tests/integration/
  test_release_guard_studio.py
docs/
  ARCHITECTURE.md
  CONSENSUS.md
  SECURITY.md
```

## Setup

Requires Python 3.10+ and Docker (for GenLayer Studio integration tests).

```bash
# Clone the repository
git clone https://github.com/Blue14352909/genlayer-release-guard.git
cd genlayer-release-guard

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Linting

```bash
genvm-lint contracts/release_guard.py
genvm-lint contracts/source_attestation.py
genvm-lint contracts/version_attestation.py
genvm-lint contracts/license_check.py
genvm-lint contracts/vulnerability_check.py
genvm-lint contracts/freshness_check.py
genvm-lint contracts/source_corroboration.py
genvm-lint contracts/semantic_policy.py
```

## Running tests

Direct-mode tests use mocked web/LLM responses and run against the local GenLayer VM:

```bash
pytest tests/direct/ -v
```

This runs 89 tests covering:
- Empty/malformed policy fail-closed behavior
- Vulnerability data validation (missing fields, booleans, nulls, negatives)
- Freshness max_age_days enforcement
- Orchestrator verdict composition
- Individual check primitives (source, license, vulnerability)

Integration tests require GenLayer Studio running (`genlayer up`):

```bash
gltest tests/integration/test_release_guard_studio.py
```

## Reproducible setup

**Python:** 3.12  
**OS:** Linux (CI), Windows (local, with conftest.py patch)  
**Dependencies:** genlayer-py v0.18, genlayer-test v0.29, genvm-linter v0.11.0  
**Test command:** `pytest tests/direct/ -v`  
**Lint command:** `genvm-lint contracts/<name>.py`

A `conftest.py` at the repo root patches a known gltest Windows temp-file issue (WinError 32 in `_inject_message_to_fd0`). This is not present on Linux/CI.

GitHub Actions CI runs on `ubuntu-latest` with Python 3.12 to provide a reproducible passing environment.

## Deployment

| Item | Value |
|---|---|
| Contract | `0x54877FDcf9cae0A995a7D5CFDE656723bE13a2b4` |
| TX hash | `0x05a35eeaa977620816acde5b4c4e52bd2e0d0e96d678270a0227deafa87e979e` |
| Consensus | Accepted (5 validators) |
| Explorer | [View](https://explorer-studio.genlayer.com/tx/0x05a35eeaa977620816acde5b4c4e52bd2e0d0e96d678270a0227deafa87e979e) |
| Studio | [Import](https://studio.genlayer.com/?import-contract=0x54877FDcf9cae0A995a7D5CFDE656723bE13a2b4) |
