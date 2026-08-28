# Consensus Design

## Overview

Every non-deterministic operation in ReleaseGuard uses GenLayer's Equivalence Principle to reach consensus. This document explains which consensus pattern each primitive uses, why, and how the patterns differ.

---

## Consensus Pattern Reference

| Primitive | Pattern | What's Compared | Why |
|---|---|---|---|
| SourceAttestation | `run_nondet_unsafe` (partial field matching) | Categorical verdict | LLM evaluates page content; two LLMs may differ in prose but should agree on the verdict |
| VersionAttestation | `run_nondet_unsafe` (partial field matching) | Categorical verdict | Same as above — version existence requires semantic judgment |
| LicenseCheck | `run_nondet_unsafe` (partial field matching) | Categorical verdict | License identification requires semantic judgment; verdict is stable |
| VulnerabilityCheck | `run_nondet_unsafe` (structured comparison) | Verdict + numeric counts | Vulnerability counts are more objective — both verdict AND counts must match |
| FreshnessCheck | `run_nondet_unsafe` (partial field matching) | Categorical verdict | Date extraction involves LLM; verdict comparison is stable |
| SourceCorroboration | `run_nondet_unsafe` (partial field matching) | Categorical verdict | Cross-referencing requires semantic judgment |
| SemanticPolicy | `prompt_non_comparative` | Leader's evaluation judged | Validator judges leader output against criteria, doesn't reproduce |
| Orchestrator verdict | **Deterministic** (no consensus) | N/A — pure code | Fail-closed rules are deterministic; no LLM needed |

---

## Why Not strict_eq?

The user suggested `strict_eq` for Version and Freshness. However, every primitive in ReleaseGuard involves:

1. **Web rendering** — `gl.nondet.web.render()` — content varies between nodes (caching, dynamic content)
2. **LLM extraction** — `gl.nondet.exec_prompt()` — outputs are non-deterministic

Since both the web fetch and LLM call are non-deterministic, the extracted facts will differ between leader and validator. `strict_eq` requires identical outputs, which is impossible when the inputs vary.

The correct pattern is: **extract stable facts → derive categorical verdict → compare verdict via `run_nondet_unsafe`**.

If a primitive could use purely deterministic computation (no web, no LLM), then `strict_eq` would be appropriate. But ReleaseGuard's primitives all require external evidence evaluation.

---

## The Extraction Pipeline

Every primitive follows the same architecture:

```
URL
 ↓
gl.nondet.web.render(url, mode="text")     ← independent per node
 ↓
LLM extraction: prompt → structured JSON    ← independent per node
 ↓
{
  "observed_project": "requests",
  "observed_version": "2.31.0",
  "page_has_release_content": true
}
 ↓
Derive categorical verdict from facts       ← deterministic
 ↓
Consensus compares verdict                  ← run_nondet_unsafe
```

The key insight from the GenLayer docs:

> *"Always extract before comparing. Raw web data varies between nodes and is expensive to write to the chain."*

By extracting stable facts first, we:
- Reduce what needs consensus (categorical verdict, not raw HTML)
- Make comparison more reliable (structured facts, not prose)
- Keep on-chain storage efficient (small extracted facts, not full pages)

---

## Pattern Details

### run_nondet_unsafe with Partial Field Matching

**Used by:** SourceAttestation, VersionAttestation, LicenseCheck, FreshnessCheck, SourceCorroboration

```python
def leader_fn() -> dict:
    content = gl.nondet.web.render(url, mode="text")
    extracted = gl.nondet.exec_prompt(extraction_prompt, response_format="json")
    return derive_verdict(extracted)  # categorical verdict from facts

def validator_fn(leader_result) -> bool:
    # Independently re-run the full pipeline
    validator_data = leader_fn()
    # Compare only the categorical verdict
    return leader_data["status"] == validator_data["status"]
```

**When to use:** The output is a categorical decision derived from semantic analysis of external data. Two independent evaluations should agree on the verdict even if reasoning differs.

### run_nondet_unsafe with Structured Comparison

**Used by:** VulnerabilityCheck

```python
def validator_fn(leader_result) -> bool:
    validator_data = leader_fn()
    # Compare verdict AND numeric counts
    if leader_data["status"] != validator_data["status"]:
        return False
    # If both PASS, counts must be consistent
    if leader_data["status"] == "PASS":
        return (validator_data["critical_count"] == 0
                and validator_data["high_count"] == 0)
    return True
```

**When to use:** The output includes both categorical decisions and structured numeric data. Numeric fields are more reproducible than prose, so comparing them strengthens consensus.

### prompt_non_comparative

**Used by:** SemanticPolicy

```python
def leader_fn() -> dict:
    content = gl.nondet.web.render(url, mode="text")
    # Leader evaluates evidence against policy
    return gl.nondet.exec_prompt(evaluation_prompt, response_format="json")

def validator_fn(leader_result) -> bool:
    content = gl.nondet.web.render(url, mode="text")
    # Validator JUDGES leader's output (does NOT reproduce)
    verdict = gl_call.gl_call_generic({
        'ExecPromptTemplate': {
            'template': 'EqNonComparativeValidator',
            'task': task,
            'input': content,
            'output': leader_result.calldata,
            'criteria': criteria,
        }
    }, _decode_nondet).get()
    return verdict
```

**When to use:** The evaluation is open-ended and two evaluators might legitimately produce different valid conclusions. The validator judges whether the leader's conclusion is defensible, not whether it matches its own.

### Deterministic Verdict Composition

**Used by:** ReleaseGuard orchestrator (final verdict)

```python
def _compose_verdict_deterministic(check_results):
    failed = [r for r in check_results if r["status"] == "FAIL"]
    inconclusive = [r for r in check_results
                    if r["status"] in ("FETCH_FAILED", "INSUFFICIENT_EVIDENCE")]

    if not failed and not inconclusive:
        return "VERIFIED"
    if failed:
        return "REJECTED"
    return "INCONCLUSIVE"  # fail closed
```

**When to use:** The composition logic is deterministic and well-defined. No LLM judgment needed — pure code with explicit invariants.

---

## Fetch Failed Is Never Safe

```
FETCH_FAILED ≠ PASS
FETCH_FAILED → INCONCLUSIVE → NEVER VERIFIED
```

This is enforced as **deterministic code** in `_compose_verdict_deterministic()`, not as an LLM judgment. The invariant cannot be bypassed by LLM hallucination or prompt injection.

---

## Fail-Closed Decision Tree (Deterministic)

```
All checks explicitly PASS?
├── YES → VERIFIED
└── NO
    ├── Any check explicitly FAIL?
    │   └── YES → REJECTED
    └── NO (only FETCH_FAILED or INSUFFICIENT_EVIDENCE)
        └── INCONCLUSIVE
```

---

## Consensus Failure → INCONCLUSIVE

If `run_nondet_unsafe` throws (validator disagrees):

1. Exception is caught by the orchestrator
2. Check is recorded as INSUFFICIENT (not FAIL — the check was never evaluated, so we cannot claim the evidence failed)
3. Deterministic composition sees INSUFFICIENT → INCONCLUSIVE
4. Verification continues with remaining checks
5. Final verdict: INCONCLUSIVE (unless another check returns FAIL → REJECTED)

This means a consensus failure cannot produce VERIFIED — it is a fail-closed property. A consensus failure does not cascade to REJECTED because the check was never actually evaluated.
