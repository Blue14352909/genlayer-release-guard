# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
LicenseCheck — Does the project use an allowed license?

A reusable GenLayer Intelligent Contract primitive that verifies a software
project's license against a configurable allowlist. Fetches license info
from the project's repository or registry and determines compliance.

Standalone use case:
    Any builder who needs to verify license compliance before adopting
    a dependency. For example: a license audit tool, a compliance
    checker, or a dependency policy enforcer.

    contract = LicenseCheck()
    result = contract.verify(
        url="https://github.com/psf/requests/blob/main/LICENSE",
        project_name="requests",
        allowed="MIT,Apache-2.0,BSD-3-Clause"
    )
    # result["status"] == "PASS" | "FAIL" | "FETCH_FAILED" | "INSUFFICIENT_EVIDENCE"
    # result["observed_license"] == "MIT"

Consensus pattern: run_nondet_unsafe with partial field matching.
    The LLM extracts the license name as a stable fact.
    The validator independently extracts and compares the verdict.
    The observed license name may differ slightly between validators
    (e.g., "MIT License" vs "MIT"), so only the verdict is compared.
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
    observed_license: str
    reason: str


DEFAULT_ALLOWED = [
    "MIT", "Apache-2.0", "Apache License 2.0",
    "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "MPL-2.0", "0BSD", "Unlicense",
]


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
_EXTRACTION_PROMPT = """\
Extract the software license from this page.

PROJECT: {project_name}
ALLOWED LICENSES: {allowed_licenses}
URL: {url}

PAGE CONTENT:
{page_content}

Identify the license. Extract ONLY observable facts.

Return a JSON object with these exact fields:
{{
  "license_name": "the license identifier (e.g., MIT, Apache-2.0, GPL-3.0), or empty",
  "license_text_observed": true or false,
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


def _derive_verdict(extracted: dict, allowed_list: list) -> dict:
    """Derive categorical verdict from extracted license."""
    license_text_observed = extracted.get("license_text_observed", False)
    if not isinstance(license_text_observed, bool):
        return {"status": E_INSUFFICIENT,
                "observed_license": "",
                "reason": "license_text_observed must be a boolean"}
    if not license_text_observed:
        return {"status": E_INSUFFICIENT,
                "observed_license": "",
                "reason": "License text not observed on page"}

    license_name = str(extracted.get("license_name", "")).strip()
    if not license_name:
        return {"status": E_INSUFFICIENT,
                "observed_license": "",
                "reason": "No license found on page"}

    # Normalize license name for comparison
    normalized = license_name.lower().replace(" license", "").replace(" ", "")
    allowed_normalized = [a.lower().replace(" license", "").replace(" ", "")
                          for a in allowed_list]

    if normalized in allowed_normalized:
        return {"status": E_PASS,
                "observed_license": license_name,
                "reason": f"License {license_name} is in allowlist"}

    return {"status": E_FAIL,
            "observed_license": license_name,
            "reason": f"License {license_name} not in allowlist"}


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
class LicenseCheck(gl.Contract):
    """
    Verifies that a project uses an allowed license.

    Stateless primitive — no on-chain storage needed.
    Can be used standalone or composed into larger verification pipelines.
    """

    @gl.public.write
    def verify(self, url: str, project_name: str, allowed: str) -> dict:
        """
        Check whether the project at the given URL uses an allowed license.

        Pipeline:
            1. Fetch page content via web rendering
            2. LLM extracts stable fact: {license_name: str}
            3. Compare extracted license against allowlist
            4. Consensus compares derived verdict

        Args:
            url: URL to the project's license page or repository
            project_name: The project name for context
            allowed: Comma-separated allowed licenses.
                     If empty, uses the default allowlist.

        Returns:
            dict with status, observed_license, reason
        """
        if not url or not url.strip():
            return {"status": E_INSUFFICIENT,
                    "observed_license": "", "reason": "Empty URL"}

        allowed_list = (
            [a.strip() for a in allowed.split(",") if a.strip()]
            if allowed and allowed.strip()
            else DEFAULT_ALLOWED
        )
        allowed_str = ", ".join(allowed_list)

        def leader_fn() -> dict:
            try:
                raw_content = gl.nondet.web.render(url, mode="text")
                content_str = _sanitize_content(str(raw_content))
            except Exception:
                return {"status": E_FETCH_FAILED,
                        "observed_license": "",
                        "reason": "Web retrieval failed"}

            if not content_str or len(content_str.strip()) < 10:
                return {"status": E_INSUFFICIENT,
                        "observed_license": "",
                        "reason": "License content too short"}

            prompt = _EXTRACTION_PROMPT.format(
                project_name=project_name,
                allowed_licenses=allowed_str,
                url=url,
                page_content=content_str,
            )
            raw_result = gl.nondet.exec_prompt(prompt, response_format="json")
            extracted = _parse_json_response(raw_result)
            return _derive_verdict(extracted, allowed_list)

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

            return leader_status == validator_status

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
