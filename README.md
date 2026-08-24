# ReleaseGuard

On-chain release attestation for GenLayer. Verifies whether software releases are trustworthy by evaluating them against configurable policies using AI consensus.

## What it does

Takes a release URL + project info → runs multiple checks via GenLayer consensus → returns VERIFIED, REJECTED, or INCONCLUSIVE.

Each check fetches the evidence page, extracts stable facts via LLM, derives a categorical verdict, and reaches consensus across validators. The final verdict is composed deterministically, no LLM involved at the verdict layer.

Key invariant: if we can't check (FETCH_FAILED), we can't approve. That's enforced in code, not left to an LLM.

## Primitives

7 standalone contracts, each usable independently:

| Contract | Checks | Consensus pattern |
|---|---|---|
| `source_attestation.py` | Does URL contain the release? | `run_nondet_unsafe` |
| `version_attestation.py` | Does the version exist? | `run_nondet_unsafe` |
| `license_check.py` | Is the license allowed? | `run_nondet_unsafe` |
| `vulnerability_check.py` | Any critical CVEs? | `run_nondet_unsafe` (structured) |
| `freshness_check.py` | Is evidence recent? | `run_nondet_unsafe` |
| `source_corroboration.py` | Do 2+ sources agree? | `run_nondet_unsafe` |
| `semantic_policy.py` | Custom NL policy check | `prompt_non_comparative` |

The orchestrator (`release_guard.py`) composes all of them.

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
    "source,license,vulnerability"
)

# Run it
verdict = contract.run_verification(vid)
# "VERIFIED" | "REJECTED" | "INCONCLUSIVE"

# Check results
record = contract.get_verification(vid)
# record["failed_checks"] == ""
# record["reason_code"] == ""
```

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
  release_guard.py          ← orchestrator
tests/direct/
  test_source_attestation.py
  test_license_check.py
  test_vulnerability_check.py
  test_release_guard.py
docs/
  ARCHITECTURE.md
  CONSENSUS.md
  SECURITY.md
```

## Running

```bash
pip install -r requirements.txt
genvm-lint contracts/release_guard.py
pytest tests/direct/ -v
```

Direct tests use mocked web/LLM responses. For real consensus, deploy in GenLayer Studio.

## Deployment

| Item | Value |
|---|---|
| Contract | `0x54877FDcf9cae0A995a7D5CFDE656723bE13a2b4` |
| TX hash | `0x05a35eeaa977620816acde5b4c4e52bd2e0d0e96d678270a0227deafa87e979e` |
| Consensus | Accepted (5 validators) |
| Explorer | [View](https://explorer-studio.genlayer.com/tx/0x05a35eeaa977620816acde5b4c4e52bd2e0d0e96d678270a0227deafa87e979e) |
| Studio | [Import](https://studio.genlayer.com/?import-contract=0x54877FDcf9cae0A995a7D5CFDE656723bE13a2b4) |
