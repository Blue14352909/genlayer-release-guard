# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
SourceCorroboration — Do multiple independent sources agree?

A reusable GenLayer Intelligent Contract primitive that fetches data from
multiple URLs and checks whether they provide consistent information
about a release. Defends against single-source manipulation.

Standalone use case:
    Any builder who needs to verify a claim isn't just from one source.
    For example: a fact-checking tool, a multi-source reputation system,
    or a cross-reference validator.

    contract = SourceCorroboration()
    result = contract.verify(
        project_name="requests",
        version="2.31.0",
        url1="https://pypi.org/project/requests/2.31.0/",
        url2="https://github.com/psf/requests/releases/tag/v2.31.0"
    )
    # result["status"] == "PASS" | "FAIL" | "FETCH_FAILED" | "INSUFFICIENT_EVIDENCE"
    # result["sources_confirming"] == 2

Consensus pattern: run_nondet_unsafe with partial field matching.
    Each source is independently fetched and evaluated.
    The LLM compares sources and produces a categorical verdict.
    The validator independently re-checks and compares the verdict.
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
    sources_confirming: u32
    sources_total: u32
    reason: str


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
_EXTRACTION_PROMPT = """\
Cross-reference multiple sources about a software release.

CLAIMED PROJECT: {project_name}
CLAIMED VERSION: {version}

SOURCE 1 ({source1_url}):
{source1_content}

SOURCE 2 ({source2_url}):
{source2_content}

Determine whether these independent sources corroborate each other. \
Extract ONLY observable facts.

Return a JSON object with these exact fields:
{{
  "sources_confirming": 0,
  "sources_total": 2,
  "corroboration_holds": true or false,
  "reason": "one sentence summarizing cross-reference findings"
}}

It is mandatory that you respond only using the JSON format above, \
nothing else. Your output must be only JSON without any formatting \
prefix or suffix.
"""


def _sanitize_content(raw: str, max_len: int = 2000) -> str:
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


def _fetch_source(url: str) -> str:
    """Fetch and sanitize a single source URL."""
    try:
        raw = gl.nondet.web.render(url, mode="text")
        return _sanitize_content(str(raw))
    except Exception:
        return ""


def _derive_verdict(extracted: dict) -> dict:
    """Derive categorical verdict from extracted corroboration data."""
    holds = extracted.get("corroboration_holds", False)
    if not isinstance(holds, bool):
        holds = str(holds).lower() == "true"

    for field_name in ("sources_confirming", "sources_total"):
        val = extracted.get(field_name, 0)
        if isinstance(val, bool):
            return {"status": E_INSUFFICIENT,
                    "sources_confirming": 0, "sources_total": 0,
                    "reason": f"Boolean {field_name} is not valid"}
        if isinstance(val, float) and val != int(val):
            return {"status": E_INSUFFICIENT,
                    "sources_confirming": 0, "sources_total": 0,
                    "reason": f"Fractional {field_name}: {val}"}
    try:
        confirming = int(extracted.get("sources_confirming", 0))
    except (ValueError, TypeError):
        return {"status": E_INSUFFICIENT,
                "sources_confirming": 0, "sources_total": 0,
                "reason": "Non-integer sources_confirming"}
    try:
        total = int(extracted.get("sources_total", 0))
    except (ValueError, TypeError):
        return {"status": E_INSUFFICIENT,
                "sources_confirming": 0, "sources_total": 0,
                "reason": "Non-integer sources_total"}
    if confirming < 0 or total < 0:
        return {"status": E_INSUFFICIENT,
                "sources_confirming": confirming, "sources_total": total,
                "reason": f"Negative counts: confirming={confirming}, total={total}"}
    if confirming > total and total > 0:
        return {"status": E_INSUFFICIENT,
                "sources_confirming": confirming, "sources_total": total,
                "reason": f"Confirming ({confirming}) > total ({total})"}
    if total == 0:
        return {"status": E_INSUFFICIENT,
                "sources_confirming": 0, "sources_total": 0,
                "reason": "No sources total"}

    if holds and confirming >= 2:
        return {"status": E_PASS,
                "sources_confirming": confirming,
                "sources_total": total,
                "reason": f"{confirming}/{total} sources corroborate"}

    return {"status": E_FAIL,
            "sources_confirming": confirming,
            "sources_total": total,
            "reason": f"Only {confirming}/{total} sources confirm"}


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
class SourceCorroboration(gl.Contract):
    """
    Cross-references multiple independent sources to verify a release claim.

    Stateless primitive — no on-chain storage needed.
    Requires at least 2 source URLs.
    """

    @gl.public.write
    def verify(self, project_name: str, version: str,
               url1: str, url2: str) -> dict:
        """
        Cross-reference two sources for release corroboration.

        Pipeline:
            1. Independently fetch both source pages
            2. LLM cross-references and extracts: {sources_confirming, holds}
            3. Derive verdict (2+ confirming → PASS)
            4. Consensus compares derived verdict

        Args:
            project_name: The claimed project name
            version: The claimed version
            url1: First source URL
            url2: Second source URL

        Returns:
            dict with status, sources_confirming, sources_total, reason
        """
        if not url1 or not url1.strip() or not url2 or not url2.strip():
            return {"status": E_INSUFFICIENT,
                    "sources_confirming": 0, "sources_total": 0,
                    "reason": "Need at least 2 source URLs"}

        def leader_fn() -> dict:
            content1 = _fetch_source(url1)
            content2 = _fetch_source(url2)

            if not content1 and not content2:
                return {"status": E_FETCH_FAILED,
                        "sources_confirming": 0, "sources_total": 0,
                        "reason": "Both sources unreachable"}

            if not content1 or not content2:
                return {"status": E_INSUFFICIENT,
                        "sources_confirming": 0, "sources_total": 1,
                        "reason": "Only one source loaded"}

            prompt = _EXTRACTION_PROMPT.format(
                project_name=project_name,
                version=version,
                source1_url=url1,
                source1_content=content1[:2000],
                source2_url=url2,
                source2_content=content2[:2000],
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

            return leader_status == validator_status

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
