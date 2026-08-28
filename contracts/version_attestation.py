# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
VersionAttestation — Does the claimed version exist?

A reusable GenLayer Intelligent Contract primitive that verifies whether
a specific software version actually exists on an authoritative source
(GitHub releases, npm registry, PyPI, etc.).

Standalone use case:
    Any builder who needs to verify a version string exists before
    trusting it. For example: a dependency pinning tool, a release
    tracker, or a version conflict detector.

    contract = VersionAttestation()
    result = contract.verify(
        url="https://pypi.org/project/requests/2.31.0/",
        project_name="requests",
        version="2.31.0"
    )
    # result["status"] == "PASS" | "FAIL" | "FETCH_FAILED" | "INSUFFICIENT_EVIDENCE"

Consensus pattern: run_nondet_unsafe with partial field matching.
    The LLM extracts a normalized fact: {version_found: bool}.
    The validator independently extracts the same fact and compares.
    Both the web fetch and LLM extraction are non-deterministic,
    so strict_eq cannot be used directly.
"""
import json
import re
from dataclasses import dataclass
from genlayer import *


# ---------------------------------------------------------------------------
# Evidence status constants
# ---------------------------------------------------------------------------
E_PASS = "PASS"
E_FAIL = "FAIL"
E_FETCH_FAILED = "FETCH_FAILED"
E_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

VALID_VERDICTS = {E_PASS, E_FAIL, E_FETCH_FAILED, E_INSUFFICIENT}


@allow_storage
@dataclass
class Verdict:
    status: str
    version_found: bool
    observed_versions: str
    reason: str


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
_EXTRACTION_PROMPT = """\
Extract factual information about software versions from this page.

CLAIMED PROJECT: {project_name}
CLAIMED VERSION: {version}
URL: {url}

PAGE CONTENT:
{page_content}

Determine whether the claimed version exists on this page. \
Extract ONLY observable facts.

Return a JSON object with these exact fields:
{{
  "version_found": true or false,
  "observed_versions": "comma-separated list of versions you see, or empty",
  "reason": "one sentence explaining what you observed"
}}

It is mandatory that you respond only using the JSON format above, \
nothing else. Your output must be only JSON without any formatting \
prefix or suffix.
"""


def _sanitize_content(raw: str, max_len: int = 3000) -> str:
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


def _derive_verdict(extracted: dict) -> dict:
    """Derive categorical verdict from extracted facts."""
    version_found = extracted.get("version_found", False)
    if not isinstance(version_found, bool):
        return {"status": E_INSUFFICIENT,
                "version_found": False,
                "observed_versions": str(extracted.get("observed_versions", "")),
                "reason": f"Invalid version_found type: {type(version_found).__name__}"}

    return {
        "status": E_PASS if version_found else E_FAIL,
        "version_found": version_found,
        "observed_versions": str(extracted.get("observed_versions", "")),
        "reason": str(extracted.get("reason", "")),
    }


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
class VersionAttestation(gl.Contract):
    """
    Verifies that a claimed software version exists on an authoritative source.

    Stateless primitive — no on-chain storage needed.
    Can be used standalone or composed into larger verification pipelines.
    """

    @gl.public.write
    def verify(self, url: str, project_name: str, version: str) -> dict:
        """
        Verify that the claimed version exists at the given source URL.

        Pipeline:
            1. Fetch page content via web rendering
            2. LLM extracts stable fact: {version_found: bool}
            3. Derive verdict from extracted fact
            4. Consensus compares derived verdict

        Args:
            url: Authoritative source URL (releases page, registry, etc.)
            project_name: The claimed project name
            version: The claimed version string

        Returns:
            dict with status, version_found, observed_versions, reason
        """
        if not url or not url.strip():
            return {"status": E_INSUFFICIENT, "version_found": False,
                    "observed_versions": "", "reason": "Empty URL"}
        if not version or not version.strip():
            return {"status": E_INSUFFICIENT, "version_found": False,
                    "observed_versions": "", "reason": "Empty version"}

        def leader_fn() -> dict:
            try:
                raw_content = gl.nondet.web.render(url, mode="text")
                content_str = _sanitize_content(str(raw_content))
            except Exception:
                return {"status": E_FETCH_FAILED, "version_found": False,
                        "observed_versions": "",
                        "reason": "Web retrieval failed"}

            if not content_str or len(content_str.strip()) < 10:
                return {"status": E_INSUFFICIENT, "version_found": False,
                        "observed_versions": "",
                        "reason": "Page content too short"}

            prompt = _EXTRACTION_PROMPT.format(
                project_name=project_name,
                version=version,
                url=url,
                page_content=content_str,
            )
            raw_result = gl.nondet.exec_prompt(prompt, response_format="json")
            extracted = _parse_json_response(raw_result)
            return _derive_verdict(extracted)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader_data = leader_result.calldata
            if not isinstance(leader_data, dict):
                return False
            leader_status = leader_data.get("status", "")
            if leader_status not in VALID_VERDICTS:
                return False

            try:
                validator_data = leader_fn()
            except Exception:
                return False
            if not isinstance(validator_data, dict):
                return False
            validator_status = validator_data.get("status", "")
            if validator_status not in VALID_VERDICTS:
                return False

            # Compare categorical verdict (partial field matching)
            return leader_status == validator_status

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
