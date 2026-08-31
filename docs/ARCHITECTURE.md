# Architecture

## Overview

ReleaseGuard is a GenLayer Intelligent Contract system that performs on-chain release attestation. It evaluates software releases against configurable verification policies using nondeterministic AI analysis and consensus-based verification.

The architecture is designed around three principles:

1. **Primitive composition** — Each verification check is a standalone, reusable primitive
2. **Fail-closed defaults** — Uncertainty produces INCONCLUSIVE, never VERIFIED
3. **Consensus-native design** — Every non-deterministic operation uses the Equivalence Principle

---

## System Layers

```
┌──────────────────────────────────────────────┐
│  Application Layer                           │
│  ┌────────────────────────────────────────┐  │
│  │  ReleaseGuard Orchestrator             │  │
│  │  - Manages verification lifecycle      │  │
│  │  - Composes primitives                 │  │
│  │  - Stores results on-chain             │  │
│  └────────────────────────────────────────┘  │
├──────────────────────────────────────────────┤
│  Primitive Layer                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Source   │ │ Version  │ │ License  │    │
│  │ Attest.  │ │ Attest.  │ │ Check    │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Vuln.    │ │ Freshness│ │ Source   │    │
│  │ Check    │ │ Check    │ │ Corrobor.│    │
│  └──────────┘ └──────────┘ └──────────┘    │
│  ┌──────────────────────────────────────┐   │
│  │  SemanticPolicy                      │   │
│  └──────────────────────────────────────┘   │
├──────────────────────────────────────────────┤
│  GenLayer Consensus Layer                    │
│  ┌────────────────────────────────────────┐  │
│  │  Equivalence Principle                 │  │
│  │  - run_nondet_unsafe (6 primitives)    │  │
│  │  - prompt_non_comparative (1 primitive)│  │
│  │  - Leader/Validator pattern            │  │
│  │  - Extraction → Verdict → Compare      │  │
│  └────────────────────────────────────────┘  │
├──────────────────────────────────────────────┤
│  External Evidence Layer                     │
│  ┌────────────────────────────────────────┐  │
│  │  Web Rendering                         │  │
│  │  - gl.nondet.web.render(url, mode)     │  │
│  │  - Independent per-node                │  │
│  └────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────┐  │
│  │  LLM Evaluation                        │  │
│  │  - gl.nondet.exec_prompt()             │  │
│  │  - JSON response format                │  │
│  │  - Independent per-node                │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## Data Flow

### Verification Lifecycle

```
1. User calls create_verification(project, version, url, policy)
   │
   ├─► Validates inputs
   ├─► Creates Verification record (status: PENDING)
   └─► Returns verification ID

2. User calls run_verification(verification_id)
   │
   ├─► Validates status == PENDING
   ├─► Sets status to RUNNING
   │
   ├─► For each check in policy:
   │   ├─► Calls gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
   │   │   ├─► Leader: web render → LLM extracts stable facts → derive verdict
   │   │   └─► Validator: independently re-runs pipeline → compares verdict
   │   ├─► Stores CheckResult
   │   └─► On consensus failure: records INSUFFICIENT (fail closed)
   │
   ├─► Deterministic verdict composition (NO LLM):
   │   ├─► All checks PASS → VERIFIED
   │   ├─► Any check FAIL → REJECTED
   │   └─► Only FETCH_FAILED/INSUFFICIENT → INCONCLUSIVE
   │
   ├─► Stores all results on-chain
   ├─► Sets status to COMPLETED
   └─► Returns final verdict
```

---

## Verdict Composition Rules

The final verdict is determined by the individual check results:

```
All checks PASS
    → VERIFIED

Any check FAIL (not FETCH_FAILED or INSUFFICIENT)
    → REJECTED

No checks FAIL, but some are FETCH_FAILED or INSUFFICIENT
    → INCONCLUSIVE
```

This is a **fail-closed** design:

- `FETCH_FAILED` means "we don't know" — it cannot be treated as `PASS`
- `INSUFFICIENT_EVIDENCE` means "the evidence is too weak" — it cannot be treated as `PASS`
- Only explicit, consensus-verified `PASS` from every required check produces `VERIFIED`

---

## Storage Model

### On-Chain State

```python
class ReleaseGuard(gl.Contract):
    verifications: TreeMap[str, Verification]
    verification_counter: u256
```

### Verification Record

```python
@allow_storage
@dataclass
class Verification:
    id: str                    # "v-1", "v-2", etc.
    requester: Address         # Who created this
    project_name: str          # e.g., "requests"
    version: str               # e.g., "2.31.0"
    evidence_url: str          # URL to evaluate
    policy_text: str           # Comma-separated checks
    status: str                # PENDING | RUNNING | COMPLETED | FAILED
    verdict: str               # VERIFIED | REJECTED | INCONCLUSIVE
    reason_code: str           # "", "CHECK_FAILED", "FETCH_FAILED", "INSUFFICIENT_EVIDENCE"
    failed_checks: str         # comma-separated failed check names
    results_json: str             # Serialized individual check results
```

### Check Result

```python
@allow_storage
@dataclass
class CheckResult:
    check_name: str            # e.g., "source"
    status: str                # PASS | FAIL | FETCH_FAILED | INSUFFICIENT_EVIDENCE
    evidence: str              # Observable evidence
    reason: str                # Human-readable explanation
```

---

## Primitive Independence

Each primitive is a standalone GenLayer Intelligent Contract with its own:
- Clear purpose and public API
- Extraction-before-consensus pipeline
- Correct consensus pattern for its data type
- Direct tests
- Documentation for standalone use

```python
# Standalone usage examples:

# Verify a release page exists
result = SourceAttestation().verify(url, project_name, version)

# Check version exists on registry
result = VersionAttestation().verify(url, project_name, version)

# Verify license compliance
result = LicenseCheck().verify(url, project_name, "MIT,Apache-2.0")

# Check for known CVEs
result = VulnerabilityCheck().verify(url, project_name, version)

# Verify evidence freshness
result = FreshnessCheck().verify(url, project_name, version, "365")

# Cross-reference multiple sources
result = SourceCorroboration().verify(project_name, version, url1, url2)

# Evaluate custom NL policy
result = SemanticPolicy().evaluate(url, project_name, version, policy)
```

The orchestrator composes them inline (not via cross-contract calls) for gas efficiency and to keep all consensus operations within a single transaction context.

---

## Error Handling Strategy

Every primitive follows the same error handling pattern:

```
External failure → FETCH_FAILED (not PASS, not FAIL)
Empty content    → INSUFFICIENT_EVIDENCE (not PASS, not FAIL)
LLM malformed    → INSUFFICIENT_EVIDENCE (fail closed)
Consensus fail   → INSUFFICIENT (fail closed)
```

The orchestrator catches consensus failures at each check and records them as INSUFFICIENT (fail closed). A consensus failure means we could not establish a reliable result — it does not mean the evidence was evaluated and failed.

---

## Extensibility

Adding a new verification primitive requires:

1. Create a new contract file with a `verify()` method
2. Implement `leader_fn` and `validator_fn` following the consensus pattern
3. Add the check name to the orchestrator's check dispatch
4. Add tests

The primitive pattern is intentionally uniform — each check takes a URL and context, returns a structured verdict, and uses the same consensus mechanism.
