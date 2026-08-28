# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
ReleaseGuard — On-chain Release Attestation System

A GenLayer Intelligent Contract that composes multiple verification primitives
into a coherent release verification pipeline. Projects define verification
policies specifying which checks to run, and ReleaseGuard orchestrates the
evaluation using GenLayer's nondeterministic consensus.

Standalone use case:
    This is the complete orchestration layer. Use it when you need to
    run multiple verification checks against a release and produce a
    single, structured, fail-closed verdict.

    contract = ReleaseGuard()
    vid = contract.create_verification(
        "requests", "2.31.0",
        "https://pypi.org/project/requests/2.31.0/",
        "source,license,vulnerability"
    )
    verdict = contract.run_verification(vid)
    # verdict == "VERIFIED" | "REJECTED" | "INCONCLUSIVE"

    record = contract.get_verification(vid)
    # record["failed_checks"] == []
    # record["reason_code"] == ""

Verification primitives composed:
    - SourceAttestation: Does the URL contain the claimed release?
    - VersionAttestation: Does the claimed version exist?
    - LicenseCheck: Is the license acceptable?
    - VulnerabilityCheck: Are there disallowed vulnerabilities?
    - FreshnessCheck: Is the evidence recent enough?
    - SourceCorroboration: Do multiple sources agree?
    - SemanticPolicy: Does a custom NL policy match?

Final verdict composition: DETERMINISTIC (no LLM).
    All checks PASS → VERIFIED
    Any check FAIL → REJECTED
    Otherwise → INCONCLUSIVE

Hard invariant enforced in code:
    FETCH_FAILED → INCONCLUSIVE → NEVER VERIFIED
"""
import json
import re
from dataclasses import dataclass
from genlayer import *


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------
E_PASS = "PASS"
E_FAIL = "FAIL"
E_FETCH_FAILED = "FETCH_FAILED"
E_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

VERIFIED = "VERIFIED"
REJECTED = "REJECTED"
INCONCLUSIVE = "INCONCLUSIVE"

VALID_CHECK_STATUSES = {E_PASS, E_FAIL, E_FETCH_FAILED, E_INSUFFICIENT}
VALID_FINAL_VERDICTS = {VERIFIED, REJECTED, INCONCLUSIVE}
VALID_CHECK_NAMES = {"source", "license", "vulnerability"}


# ---------------------------------------------------------------------------
# Storage types
# ---------------------------------------------------------------------------
@allow_storage
@dataclass
class CheckResult:
    check_name: str
    status: str
    evidence: str
    reason: str


@allow_storage
@dataclass
class Verification:
    id: str
    requester: Address
    project_name: str
    version: str
    evidence_url: str
    policy_text: str
    status: str          # PENDING | RUNNING | COMPLETED | FAILED
    verdict: str         # VERIFIED | REJECTED | INCONCLUSIVE
    reason_code: str     # e.g., "FETCH_FAILED", "CHECK_FAILED"
    failed_checks: str   # comma-separated list of failed check names
    created_at: str
    # Results stored as JSON string (DynArray cannot be user-initialized)
    results_json: str


DEFAULT_POLICY = "source,license,vulnerability"


# ---------------------------------------------------------------------------
# Extraction helpers — shared across checks
# ---------------------------------------------------------------------------
def _sanitize_content(raw: str, max_len: int = 4000) -> str:
    """Sanitize page content."""
    if not raw:
        return ""
    cleaned = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def _parse_json_response(raw) -> dict:
    """Parse LLM JSON output."""
    if isinstance(raw, dict):
        return raw
    text = str(raw)
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1:
        raise gl.vm.UserError("No JSON object found in response")
    text = text[first : last + 1]
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise gl.vm.UserError(f"Invalid JSON from evaluator: {e}")


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------
def _check_source(url: str, project_name: str, version: str) -> dict:
    """SourceAttestation check: does URL contain the claimed release?"""
    prompt = (
        f"Verify whether this URL genuinely contains a release for "
        f"{project_name} version {version}.\n"
        f"URL: {url}\n"
        "Return JSON: {{\"observed_project\": \"name\", "
        "\"observed_version\": \"ver\", "
        "\"page_has_release_content\": true/false}}"
    )
    try:
        raw = gl.nondet.web.render(url, mode="text")
        content = _sanitize_content(str(raw))
    except Exception:
        return {"check_name": "source", "status": E_FETCH_FAILED,
                "evidence": "Web retrieval failed",
                "reason": "Could not render URL"}
    if not content or len(content.strip()) < 20:
        return {"check_name": "source", "status": E_INSUFFICIENT,
                "evidence": "Page too short", "reason": "Insufficient evidence"}
    raw_result = gl.nondet.exec_prompt(
        prompt + f"\n\nPage content:\n{content}", response_format="json")
    parsed = _parse_json_response(raw_result)
    has_content = parsed.get("page_has_release_content", False)
    obs_project = str(parsed.get("observed_project", "")).strip()
    obs_version = str(parsed.get("observed_version", "")).strip()
    project_match = obs_project.lower() == project_name.lower()
    version_match = version.lower() in obs_version.lower()
    status = E_PASS if (has_content and project_match and version_match) else E_FAIL
    return {"check_name": "source", "status": status,
            "evidence": f"{obs_project} {obs_version}",
            "reason": f"Project match={project_match}, version match={version_match}"}


def _check_license(url: str, project_name: str) -> dict:
    """LicenseCheck: is the license acceptable?"""
    prompt = (
        f"Check the license of project {project_name}.\n"
        f"URL: {url}\n"
        "Return JSON: {{\"license_name\": \"MIT\", "
        "\"is_permissive\": true/false}}"
    )
    try:
        raw = gl.nondet.web.render(url, mode="text")
        content = _sanitize_content(str(raw))
    except Exception:
        return {"check_name": "license", "status": E_FETCH_FAILED,
                "evidence": "Web retrieval failed",
                "reason": "Could not render URL"}
    if not content:
        return {"check_name": "license", "status": E_INSUFFICIENT,
                "evidence": "No content", "reason": "Insufficient evidence"}
    raw_result = gl.nondet.exec_prompt(
        prompt + f"\n\nPage content:\n{content}", response_format="json")
    parsed = _parse_json_response(raw_result)
    is_permissive = parsed.get("is_permissive", False)
    license_name = str(parsed.get("license_name", ""))
    status = E_PASS if is_permissive else E_FAIL
    return {"check_name": "license", "status": status,
            "evidence": license_name,
            "reason": f"License: {license_name}, permissive: {is_permissive}"}


def _check_vulnerability(url: str, project_name: str,
                         version: str) -> dict:
    """VulnerabilityCheck: are there known critical/high vulns?"""
    prompt = (
        f"Check for critical/high vulnerabilities in {project_name} {version}.\n"
        f"URL: {url}\n"
        "Return JSON: {{\"critical_count\": 0, \"high_count\": 0}}"
    )
    try:
        raw = gl.nondet.web.render(url, mode="text")
        content = _sanitize_content(str(raw))
    except Exception:
        return {"check_name": "vulnerability", "status": E_FETCH_FAILED,
                "evidence": "Advisory unreachable",
                "reason": "Cannot verify vulnerability status"}
    if not content:
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": "No vulnerability data",
                "reason": "Insufficient evidence"}
    raw_result = gl.nondet.exec_prompt(
        prompt + f"\n\nPage content:\n{content}", response_format="json")
    parsed = _parse_json_response(raw_result)
    # Validate response structure before interpreting counts.
    # Malformed or missing data must NOT silently become "0 vulns".
    if not isinstance(parsed, dict):
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": "Response is not a dict",
                "reason": "Malformed vulnerability response"}
    has_data = parsed.get("has_vulnerability_data", False)
    if not has_data:
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": "No vulnerability data reported",
                "reason": "Evaluator reported no vulnerability data"}
    # Explicit field presence check: missing counts are NOT zero.
    # Missing critical_count or high_count must produce INSUFFICIENT, never PASS.
    if "critical_count" not in parsed or "high_count" not in parsed:
        missing = []
        if "critical_count" not in parsed:
            missing.append("critical_count")
        if "high_count" not in parsed:
            missing.append("high_count")
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": f"Missing fields: {', '.join(missing)}",
                "reason": "Vulnerability data incomplete: " + ", ".join(missing) + " missing"}
    # Reject booleans: int(True)==1 would silently accept them
    for field_name in ("critical_count", "high_count"):
        val = parsed[field_name]
        if isinstance(val, bool):
            return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                    "evidence": f"Boolean {field_name}: {val}",
                    "reason": f"Boolean {field_name} is not a valid count"}
    try:
        critical = int(parsed["critical_count"])
    except (ValueError, TypeError):
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": f"Non-integer critical_count: {parsed['critical_count']}",
                "reason": "Malformed critical_count in vulnerability data"}
    try:
        high = int(parsed["high_count"])
    except (ValueError, TypeError):
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": f"Non-integer high_count: {parsed['high_count']}",
                "reason": "Malformed high_count in vulnerability data"}
    if critical < 0 or high < 0:
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": f"Negative count: critical={critical}, high={high}",
                "reason": "Negative vulnerability counts are invalid"}
    status = E_PASS if (critical == 0 and high == 0) else E_FAIL
    return {"check_name": "vulnerability", "status": status,
            "evidence": f"{critical} critical, {high} high",
            "reason": f"Critical: {critical}, High: {high}"}


# ---------------------------------------------------------------------------
# Deterministic verdict composition — NO LLM
# ---------------------------------------------------------------------------
def _compose_verdict_deterministic(check_results: list) -> dict:
    """Compose final verdict from check results using deterministic logic.

    Hard invariants enforced:
        1. All checks must PASS for VERIFIED
        2. Any check FAIL → REJECTED
        3. FETCH_FAILED or INSUFFICIENT → INCONCLUSIVE (never VERIFIED)
        4. Consensus failure (exception during check) → INSUFFICIENT → INCONCLUSIVE
    """
    # Empty check list: no checks ran → INCONCLUSIVE (fail closed)
    if len(check_results) == 0:
        return {"verdict": INCONCLUSIVE,
                "reason_code": "EMPTY_POLICY",
                "failed_checks": "",
                "reason": "No checks executed"}

    failed_checks = []
    inconclusive_checks = []
    all_pass = True

    for r in check_results:
        status = r.get("status", E_FAIL)
        name = r.get("check_name", "unknown")

        if status == E_FAIL:
            failed_checks.append(name)
            all_pass = False
        elif status in (E_FETCH_FAILED, E_INSUFFICIENT):
            inconclusive_checks.append(name)
            all_pass = False
        elif status not in VALID_CHECK_STATUSES:
            # Unknown status — fail closed, treat as inconclusive
            inconclusive_checks.append(name)
            all_pass = False

    # Hard invariant: FETCH_FAILED → INCONCLUSIVE → NEVER VERIFIED
    if all_pass and len(failed_checks) == 0 and len(inconclusive_checks) == 0:
        return {"verdict": VERIFIED,
                "reason_code": "",
                "failed_checks": "",
                "reason": "All checks passed"}

    if len(failed_checks) > 0:
        return {"verdict": REJECTED,
                "reason_code": "CHECK_FAILED",
                "failed_checks": ",".join(failed_checks),
                "reason": f"Failed: {','.join(failed_checks)}"}

    # Only inconclusive checks remain — fail closed
    return {"verdict": INCONCLUSIVE,
            "reason_code": "FETCH_FAILED" if any(
                r.get("status") == E_FETCH_FAILED for r in check_results
            ) else "INSUFFICIENT_EVIDENCE",
            "failed_checks": ",".join(inconclusive_checks),
            "reason": f"Inconclusive: {','.join(inconclusive_checks)}"}


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
class ReleaseGuard(gl.Contract):
    """
    On-chain Release Attestation System.

    Composes verification primitives with deterministic, fail-closed
    verdict composition. No LLM is used for the final verdict — the
    composition logic is pure code with explicit invariants.

    Supported orchestrator policies: {"source", "license", "vulnerability"}.
    No other policies are wired. Unknown policy names fail closed.
    Other standalone primitives (freshness, version, corroboration,
    semantic) exist in this repository but are NOT executed by this
    orchestrator.
    """

    verifications: TreeMap[str, Verification]
    verification_counter: u256

    def __init__(self):
        self.verification_counter = u256(0)

    @gl.public.write.payable
    def create_verification(
        self, project_name: str, version: str,
        evidence_url: str, policy_text: str
    ) -> str:
        """
        Create a new release verification request.

        Args:
            project_name: The project name
            version: The release version
            evidence_url: URL containing release evidence
            policy_text: Comma-separated checks: "source,license,vulnerability"

        Returns:
            Verification ID string
        """
        if not project_name or not project_name.strip():
            raise gl.vm.UserError("Project name required")
        if not version or not version.strip():
            raise gl.vm.UserError("Version required")
        if not evidence_url or not evidence_url.strip():
            raise gl.vm.UserError("Evidence URL required")
        # Empty policy is valid — the orchestrator handles it as a fail-closed
        # path (no checks = INCONCLUSIVE). Do NOT default to a policy here.

        self.verification_counter = self.verification_counter + 1
        vid = f"v-{self.verification_counter}"

        verification = Verification(
            id=vid,
            requester=gl.message.sender_address,
            project_name=project_name,
            version=version,
            evidence_url=evidence_url,
            policy_text=policy_text,
            status="PENDING",
            verdict="",
            reason_code="",
            failed_checks="",
            created_at="",
            results_json="",
        )
        self.verifications[vid] = verification
        return vid

    @gl.public.write
    def run_verification(self, verification_id: str) -> str:
        """
        Execute the verification pipeline for a pending verification.

        Runs each check via consensus, then composes the final verdict
        using deterministic fail-closed logic (no LLM).

        Args:
            verification_id: The verification to run

        Returns:
            Final verdict: "VERIFIED", "REJECTED", or "INCONCLUSIVE"
        """
        if verification_id not in self.verifications:
            raise gl.vm.UserError("Verification not found")

        v = self.verifications[verification_id]
        if v.status != "PENDING":
            raise gl.vm.UserError(f"Verification is {v.status}, not PENDING")

        v.status = "RUNNING"
        checks = [c.strip() for c in v.policy_text.split(",") if c.strip()]
        check_results_list = []

        # --- Fail-closed: empty policy must not produce VERIFIED ---
        if len(checks) == 0:
            check_results_list.append({
                "check_name": "policy",
                "status": E_INSUFFICIENT,
                "evidence": "Empty or whitespace-only policy",
                "reason": "No checks to run",
            })

        # --- Run individual checks via consensus ---
        for check_name in checks:
            if check_name == "source":
                def leader_fn() -> dict:
                    return _check_source(
                        v.evidence_url, v.project_name, v.version)
            elif check_name == "license":
                def leader_fn() -> dict:
                    return _check_license(v.evidence_url, v.project_name)
            elif check_name == "vulnerability":
                def leader_fn() -> dict:
                    return _check_vulnerability(
                        v.evidence_url, v.project_name, v.version)
            else:
                check_results_list.append({
                    "check_name": check_name,
                    "status": E_INSUFFICIENT,
                    "evidence": "Unknown check type",
                    "reason": f"Check '{check_name}' not recognized",
                })
                continue

            def validator_fn(leader_result) -> bool:
                if not isinstance(leader_result, gl.vm.Return):
                    return False
                leader_data = leader_result.calldata
                if not isinstance(leader_data, dict):
                    return False
                leader_status = leader_data.get("status", "")
                if leader_status not in VALID_CHECK_STATUSES:
                    return False
                try:
                    validator_data = leader_fn()
                except Exception:
                    return False
                if not isinstance(validator_data, dict):
                    return False
                validator_status = validator_data.get("status", "")
                if validator_status not in VALID_CHECK_STATUSES:
                    return False
                return leader_status == validator_status

            try:
                result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
                check_results_list.append({
                    "check_name": check_name,
                    "status": str(result.get("status", E_FAIL)),
                    "evidence": str(result.get("evidence", "")),
                    "reason": str(result.get("reason", "")),
                })
            except Exception:
                # Consensus failure → INSUFFICIENT (fail closed)
                # Not E_FAIL: the check was never evaluated, so we cannot
                # claim the evidence failed. We simply couldn't establish
                # a result, which is the definition of INSUFFICIENT.
                check_results_list.append({
                    "check_name": check_name,
                    "status": E_INSUFFICIENT,
                    "evidence": "Consensus not reached",
                    "reason": "Validator disagreed or execution failed",
                })

        # --- Deterministic verdict composition (NO LLM) ---
        verdict_data = _compose_verdict_deterministic(check_results_list)

        # --- Store results ---
        v.results_json = json.dumps(check_results_list)

        v.verdict = verdict_data["verdict"]
        v.reason_code = verdict_data["reason_code"]
        v.failed_checks = verdict_data["failed_checks"]
        v.status = "COMPLETED"
        return v.verdict

    @gl.public.view
    def get_verification(self, verification_id: str) -> dict:
        """Retrieve the full verification record."""
        if verification_id not in self.verifications:
            raise gl.vm.UserError("Verification not found")
        v = self.verifications[verification_id]
        return {
            "id": v.id,
            "project_name": v.project_name,
            "version": v.version,
            "evidence_url": v.evidence_url,
            "policy_text": v.policy_text,
            "status": v.status,
            "verdict": v.verdict,
            "reason_code": v.reason_code,
            "failed_checks": v.failed_checks,
            "results": json.loads(v.results_json) if v.results_json else [],
        }

    @gl.public.view
    def get_verdict(self, verification_id: str) -> str:
        """Retrieve just the final verdict."""
        if verification_id not in self.verifications:
            raise gl.vm.UserError("Verification not found")
        v = self.verifications[verification_id]
        if v.status != "COMPLETED":
            return "PENDING"
        return v.verdict

    @gl.public.view
    def get_check_results(self, verification_id: str) -> list:
        """Retrieve individual check results."""
        if verification_id not in self.verifications:
            raise gl.vm.UserError("Verification not found")
        v = self.verifications[verification_id]
        return [
            {"check_name": r["check_name"], "status": r["status"],
             "evidence": r["evidence"], "reason": r["reason"]}
            for r in (json.loads(v.results_json) if v.results_json else [])
        ]
