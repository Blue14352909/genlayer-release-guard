# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
ReleaseGuard V2 - Challengeable, Revocable On-Chain Release Attestations

A standalone GenLayer intelligent contract that turns a verified release claim
into a durable, public, *challengeable* attestation.

V1 (contracts/release_guard.py) verifies a single release claim and stores a
terminal verdict (VERIFIED / REJECTED / INCONCLUSIVE). It cannot be questioned
and it cannot be withdrawn.

V2 adds the missing half of real attestation:

    1. A claim is created and reviewed through GenLayer consensus
       (ATTESTED / REJECTED / UNRESOLVED).
    2. Only an ATTESTED claim may be challenged.
    3. Any caller - permissionless - may open a challenge with conflicting
       public evidence and a short reason.
    4. Validators independently re-evaluate the original claim AND the
       challenge evidence through consensus.
    5. The challenge resolves to a final, queryable state:
           INVALID    - the challenge evidence was unusable (unreachable,
                        empty, too short). The original attestation STANDS.
           ATTESTED   - challenge rejected, original attestation stands
           REVOKED    - the challenge established the attestation can no
                        longer be relied upon
           DISPUTED   - the evidence was retrievable and meaningful, but
                        consensus could not safely decide. The release must
                        NOT remain safely attested.
    6. Anyone can read a claim, a challenge, all challenges for a claim, and
       the canonical current attestation for an exact project + version.

Canonical binding (anti-squatting):
    `create_claim` NEVER reserves or writes the canonical project/version
    mapping. A PENDING, RUNNING, REJECTED, or UNRESOLVED claim therefore never
    blocks another claim for the same normalized project/version. The canonical
    key is bound ONLY when a review genuinely reaches ATTESTED, and only if no
    other claim is already canonical for that exact key. A competing claim that
    would otherwise attest finishes UNRESOLVED with
    reason_code = CANONICAL_ATTESTATION_EXISTS instead of overwriting the
    canonical record. Once bound, a canonical record is the historical record
    for that exact version even after it is REVOKED; a later claim can never
    silently replace it.

Scope (deliberately limited to the three V1 policies):
    source, license, vulnerability
    Any other policy name fails closed (UNRESOLVED). It is never silently
    accepted and never silently dropped.

Evidence URLs:
    Both create_claim and open_challenge validate the evidence URL with a
    deterministic, dependency-free HTTPS validator BEFORE any nondeterministic
    retrieval. Only https:// URLs with a plausible public host are accepted.
    This validation is a syntactic/structural guard only: it does not, and
    cannot, prove that a hostname is publicly reachable.

No funds, no wallet, no escrow, no `.payable`: this primitive is about
verifiable attestation and consensus, not token accounting.

Deterministic composition, fail-closed:
    Consensus produces raw evidence outcomes. Final state is composed by pure,
    deterministic code. Uncertainty - missing, malformed, unsupported,
    unreachable, or non-agreeing evidence - collapses to a non-attested state,
    never to ATTESTED. A consensus/runtime failure is NEVER recorded as
    REJECTED and NEVER as ATTESTED; it becomes UNRESOLVED (initial review) or
    DISPUTED (challenge review).
"""
import json
import re
from dataclasses import dataclass
from genlayer import *


# ---------------------------------------------------------------------------
# Check statuses (produced by consensus or deterministic policy validation)
# ---------------------------------------------------------------------------
E_PASS = "PASS"
E_FAIL = "FAIL"
E_FETCH_FAILED = "FETCH_FAILED"
E_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
E_UNSUPPORTED = "UNSUPPORTED_POLICY"

# Statuses a consensus leader is allowed to return. E_UNSUPPORTED is only ever
# produced deterministically (policy validation), never by consensus.
VALID_CHECK_STATUSES = {E_PASS, E_FAIL, E_FETCH_FAILED, E_INSUFFICIENT}

# ---------------------------------------------------------------------------
# Terminal attestation states (shared by claims and challenge outcomes)
# ---------------------------------------------------------------------------
ATTESTED = "ATTESTED"
REJECTED = "REJECTED"
REVOKED = "REVOKED"
UNRESOLVED = "UNRESOLVED"
INVALID = "INVALID"
DISPUTED = "DISPUTED"

# ---------------------------------------------------------------------------
# Claim lifecycle states
# ---------------------------------------------------------------------------
CLAIM_PENDING = "PENDING"
CLAIM_RUNNING = "RUNNING"        # transient: review in flight
CLAIM_ATTESTED = "ATTESTED"
CLAIM_REJECTED = "REJECTED"
CLAIM_CHALLENGED = "CHALLENGED"
CLAIM_DISPUTED = "DISPUTED"
CLAIM_REVOKED = "REVOKED"
CLAIM_UNRESOLVED = "UNRESOLVED"

# ---------------------------------------------------------------------------
# Challenge lifecycle states
# ---------------------------------------------------------------------------
CHALLENGE_OPEN = "OPEN"
CHALLENGE_INVALID = "INVALID"        # evidence unusable; attestation untouched
CHALLENGE_RESOLVED = "RESOLVED"      # decided: ATTESTED or REVOKED
CHALLENGE_DISPUTED = "DISPUTED"      # credible but undecidable; claim DISPUTED

# Outcomes a decided/classified challenge can carry in `outcome`.
CHALLENGE_OUTCOMES = (INVALID, ATTESTED, REVOKED, DISPUTED)

SUPPORTED_POLICIES = ("source", "license", "vulnerability")

MAX_CHALLENGE_REASON_LEN = 400
MIN_CHALLENGE_EVIDENCE_LEN = 20
MAX_STORED_RESULTS = 64


# ---------------------------------------------------------------------------
# Storage types
# ---------------------------------------------------------------------------
@allow_storage
@dataclass
class Claim:
    id: str
    requester: Address
    project_name: str
    version: str
    evidence_url: str
    policy_text: str
    status: str                # claim lifecycle state
    attestation_state: str     # "" | ATTESTED | REJECTED | REVOKED | UNRESOLVED | DISPUTED
    reason_code: str
    failed_checks: str         # comma-separated failed check names
    active_challenge_id: str   # "" when no challenge is open
    # Results stored as JSON string (DynArray cannot be user-initialized),
    # mirroring V1's storage pattern.
    results_json: str
    # Ordered list of every challenge id ever opened for this claim, JSON-encoded.
    challenge_ids_json: str


@allow_storage
@dataclass
class Challenge:
    id: str
    claim_id: str
    challenger: Address
    evidence_url: str
    reason: str
    status: str                # OPEN | INVALID | RESOLVED | DISPUTED
    outcome: str               # "" | INVALID | ATTESTED | REVOKED | DISPUTED
    reason_code: str
    results_json: str          # recomputed original-policy check results


# ---------------------------------------------------------------------------
# Evidence URL validation - deterministic, no new dependency, no network.
# ---------------------------------------------------------------------------
_HTTPS_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):")
_URL_BAD_CHARS_RE = re.compile(r"[\s\x00-\x1f\x7f]")
_REASON_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_IPV4_LITERAL_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
# A conservative public hostname: labels of [a-z0-9-] that start/end alnum,
# at least one dot, and an alphabetic TLD of length >= 2.
_HOSTNAME_RE = re.compile(
    r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?"
    r"(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)*\.[a-z]{2,}$"
)
# Host suffixes that name local / non-public networks.
_LOCAL_HOST_SUFFIXES = (
    ".localhost", ".local", ".internal", ".lan", ".home.arpa", ".localdomain",
)


def _validate_evidence_url(url) -> str:
    """Return "" when the URL is an acceptable public HTTPS evidence URL.

    Otherwise return a short, stable reason code. Deterministic and
    dependency-free. This is a structural guard only: passing it does NOT
    prove that the host is actually reachable.

    Rejected: blank/whitespace, control characters, non-HTTPS schemes
    (http/file/data/javascript/...), missing "//", userinfo, malformed port,
    IPv4/IPv6 literals, localhost and local-network suffixes, single-label
    hosts, and hosts that are not plausible public DNS names.
    """
    if url is None:
        return "URL_MISSING"
    if not isinstance(url, str):
        return "URL_INVALID_TYPE"
    if not url.strip():
        return "URL_BLANK"
    if url != url.strip():
        return "URL_WHITESPACE"
    if _URL_BAD_CHARS_RE.search(url):
        return "URL_WHITESPACE"

    scheme_match = _HTTPS_SCHEME_RE.match(url)
    if scheme_match is None:
        return "URL_MALFORMED"
    if scheme_match.group(1).lower() != "https":
        return "URL_SCHEME_NOT_HTTPS"
    remainder = url[len(scheme_match.group(0)):]
    if not remainder.startswith("//"):
        return "URL_MALFORMED"
    rest = remainder[2:]

    authority = re.split(r"[/?#]", rest, maxsplit=1)[0]
    if not authority:
        return "URL_MALFORMED"
    if "@" in authority:
        return "URL_USERINFO_NOT_ALLOWED"

    host = authority
    if ":" in authority:
        host, _, port = authority.partition(":")
        if not port.isdigit():
            return "URL_MALFORMED"
        if not 1 <= int(port) <= 65535:
            return "URL_MALFORMED"
    host = host.lower()
    if not host:
        return "URL_MALFORMED"

    # Bracketed IPv6 literals are out of scope: reject them all.
    if host.startswith("[") or host.endswith("]"):
        return "URL_HOST_NOT_PUBLIC"
    if host == "localhost" or host.endswith(_LOCAL_HOST_SUFFIXES):
        return "URL_HOST_NOT_PUBLIC"
    # Any bare IPv4 literal is rejected (covers loopback/private/link-local).
    if _IPV4_LITERAL_RE.match(host):
        return "URL_HOST_NOT_PUBLIC"
    # Single-label hosts are local network names.
    if "." not in host:
        return "URL_HOST_NOT_PUBLIC"
    if not _HOSTNAME_RE.match(host):
        return "URL_MALFORMED"
    return ""


def _validate_reason(reason) -> str:
    """Return "" for an acceptable challenge reason, else a reason code."""
    if reason is None:
        return "REASON_MISSING"
    if not isinstance(reason, str):
        return "REASON_INVALID_TYPE"
    if not reason.strip():
        return "REASON_BLANK"
    if _REASON_CONTROL_RE.search(reason):
        return "REASON_CONTROL_CHARS"
    if len(reason) > MAX_CHALLENGE_REASON_LEN:
        return "REASON_TOO_LONG"
    return ""


# ---------------------------------------------------------------------------
# Extraction helpers - shared across checks (ported from V1, unchanged in
# meaning so V2 inherits V1's safety fixes)
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


def _fetch_page_text(url: str) -> str:
    """Fetch browser-rendered text first, fall back to static HTML."""
    try:
        raw = gl.nondet.web.render(url, mode="text")
        content = _sanitize_content(str(raw))
        if content:
            return content
    except Exception:
        pass

    try:
        response = gl.nondet.web.get(url)
        body = response.body
        text = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        content = _sanitize_content(text)
        if content:
            return content
    except Exception:
        pass

    return ""


def _parse_json_response(raw) -> dict:
    """Parse LLM JSON output. Raises on malformed output (fail closed)."""
    if isinstance(raw, dict):
        return raw
    text = str(raw)
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1:
        raise gl.vm.UserError("No JSON object found in response")
    text = text[first: last + 1]
    text = re.sub(r",(\s*[}\]]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise gl.vm.UserError(f"Invalid JSON from evaluator: {e}")


def _inconclusive(check_name: str, evidence: str, reason: str) -> dict:
    """Build a fail-closed result for malformed evaluator output."""
    return {"check_name": check_name, "status": E_INSUFFICIENT,
            "evidence": evidence, "reason": reason}


def _normalized_version(value: str) -> str:
    """Normalize the common leading `v` release-tag convention."""
    normalized = value.strip().lower()
    return normalized[1:] if normalized.startswith("v") else normalized


def _page_contains_claim(content: str, project_name: str, version: str) -> bool:
    """Check exact release facts visible in the fetched source text.

    Uses strict token boundaries so a requested version such as "2" cannot
    match the "2" in "11.2.0" (the exact bug fixed in V1).
    """
    project = re.escape(project_name.strip())
    normalized_version = re.escape(_normalized_version(version))
    boundary = r"(?<![A-Za-z0-9_-])"
    end_boundary = r"(?![A-Za-z0-9_-])"
    version_boundary = r"(?<![A-Za-z0-9_.-])"
    version_end_boundary = r"(?![A-Za-z0-9_.-])"
    project_present = re.search(
        boundary + project + end_boundary, content, flags=re.IGNORECASE)
    version_present = re.search(
        version_boundary + r"v?" + normalized_version + version_end_boundary,
        content, flags=re.IGNORECASE)
    return bool(project_present and version_present)


def _missing_observation(value: str) -> bool:
    return value.strip().lower() in ("", "unknown", "n/a", "none")


# ---------------------------------------------------------------------------
# Individual check implementations (identical semantics to V1)
# ---------------------------------------------------------------------------
def _check_source(url: str, project_name: str, version: str) -> dict:
    """Source policy: does the evidence genuinely contain the claimed release?"""
    prompt = (
        f"Verify whether this URL genuinely contains a release for "
        f"{project_name} version {version}.\n"
        f"URL: {url}\n"
        "Return JSON: {\"observed_project\": \"name\", "
        "\"observed_version\": \"ver\", "
        "\"page_has_release_content\": true/false}"
    )
    content = _fetch_page_text(url)
    if not content:
        return {"check_name": "source", "status": E_FETCH_FAILED,
                "evidence": "Web retrieval failed",
                "reason": "Could not retrieve usable page content"}
    if not content or len(content.strip()) < 20:
        return {"check_name": "source", "status": E_INSUFFICIENT,
                "evidence": "Page too short", "reason": "Insufficient evidence"}
    raw_result = gl.nondet.exec_prompt(
        prompt + f"\n\nPage content:\n{content}", response_format="json")
    parsed = _parse_json_response(raw_result)
    if not isinstance(parsed, dict):
        return _inconclusive("source", "Response is not a dict",
                             "Malformed source response")
    has_content = parsed.get("page_has_release_content", False)
    if not isinstance(has_content, bool):
        return _inconclusive("source", "Invalid page_has_release_content",
                             "Source content flag must be a boolean")
    obs_project = str(parsed.get("observed_project", "")).strip()
    obs_version = str(parsed.get("observed_version", "")).strip()
    project_match = obs_project.lower() == project_name.lower()
    version_match = _normalized_version(version) == _normalized_version(obs_version)
    page_claim_present = _page_contains_claim(content, project_name, version)

    # Some registries expose stable release facts in page text but an LLM may
    # still return placeholders such as "unknown". Use only exact, visible
    # project/version matches as a fallback; explicit non-matching facts still
    # fail rather than being overridden.
    if (_missing_observation(obs_project) or _missing_observation(obs_version)):
        if page_claim_present:
            return {"check_name": "source", "status": E_PASS,
                    "evidence": f"{project_name} {version}",
                    "reason": "Exact project and version found in page text"}
    status = E_PASS if (has_content and project_match and version_match) else E_FAIL
    return {"check_name": "source", "status": status,
            "evidence": f"{obs_project} {obs_version}",
            "reason": f"Project match={project_match}, version match={version_match}"}


def _check_license(url: str, project_name: str) -> dict:
    """License policy: is the license observed and permissive?"""
    prompt = (
        f"Check the license of project {project_name}.\n"
        f"URL: {url}\n"
        "Return JSON: {\"license_name\": \"MIT\", "
        "\"license_text_observed\": true/false, "
        "\"is_permissive\": true/false}"
    )
    content = _fetch_page_text(url)
    if not content:
        return {"check_name": "license", "status": E_FETCH_FAILED,
                "evidence": "Web retrieval failed",
                "reason": "Could not retrieve usable page content"}
    raw_result = gl.nondet.exec_prompt(
        prompt + f"\n\nPage content:\n{content}", response_format="json")
    parsed = _parse_json_response(raw_result)
    if not isinstance(parsed, dict):
        return _inconclusive("license", "Response is not a dict",
                             "Malformed license response")
    license_text_observed = parsed.get("license_text_observed", False)
    if not isinstance(license_text_observed, bool):
        return _inconclusive("license", "Invalid license_text_observed value",
                             "License-observed flag must be a boolean")
    if not license_text_observed:
        return {"check_name": "license", "status": E_INSUFFICIENT,
                "evidence": "License text not observed",
                "reason": "Cannot verify license without observed license text"}
    is_permissive = parsed.get("is_permissive", False)
    if not isinstance(is_permissive, bool):
        return _inconclusive("license", "Invalid is_permissive value",
                             "License permissiveness must be a boolean")
    license_name = str(parsed.get("license_name", ""))
    status = E_PASS if is_permissive else E_FAIL
    return {"check_name": "license", "status": status,
            "evidence": license_name,
            "reason": f"License: {license_name}, permissive: {is_permissive}"}


def _check_vulnerability(url: str, project_name: str, version: str) -> dict:
    """Vulnerability policy: are there known critical/high vulnerabilities?"""
    prompt = (
        f"Check for critical/high vulnerabilities in {project_name} {version}.\n"
        f"URL: {url}\n"
        "Return JSON: {\"has_vulnerability_data\": true/false, "
        "\"critical_count\": 0, \"high_count\": 0}"
    )
    content = _fetch_page_text(url)
    if not content:
        return {"check_name": "vulnerability", "status": E_FETCH_FAILED,
                "evidence": "Advisory unreachable",
                "reason": "Cannot retrieve vulnerability evidence"}
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
    if not isinstance(has_data, bool):
        return _inconclusive("vulnerability", "Invalid has_vulnerability_data",
                             "Vulnerability-data flag must be a boolean")
    if not has_data:
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": "No vulnerability data reported",
                "reason": "Evaluator reported no vulnerability data"}
    # Explicit field presence check: missing counts are NOT zero.
    if "critical_count" not in parsed or "high_count" not in parsed:
        missing = []
        if "critical_count" not in parsed:
            missing.append("critical_count")
        if "high_count" not in parsed:
            missing.append("high_count")
        return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                "evidence": f"Missing fields: {', '.join(missing)}",
                "reason": "Vulnerability data incomplete: " + ", ".join(missing) + " missing"}
    # Reject booleans: int(True)==1 would silently accept them.
    for field_name in ("critical_count", "high_count"):
        val = parsed[field_name]
        if isinstance(val, bool):
            return {"check_name": "vulnerability", "status": E_INSUFFICIENT,
                    "evidence": f"Boolean {field_name}: {val}",
                    "reason": f"Boolean {field_name} is not a valid count"}
        if not isinstance(val, int):
            return _inconclusive("vulnerability", f"Non-integer {field_name}: {val}",
                                 f"{field_name} must be an integer")
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
# Deterministic composition - NO LLM. Fail closed.
# ---------------------------------------------------------------------------
def _parse_policies(policy_text: str):
    """Split a comma-separated policy string.

    Returns (supported, unsupported). Order is preserved and duplicates are
    collapsed (first occurrence wins) so a repeated policy does not consume
    extra consensus rounds. Duplicate handling is deterministic.
    """
    supported = []
    unsupported = []
    seen = set()
    for raw in policy_text.split(","):
        name = raw.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        if name in SUPPORTED_POLICIES:
            supported.append(name)
        else:
            unsupported.append(name)
    return supported, unsupported


def _compose_claim_state(check_results: list) -> dict:
    """Compose a claim's terminal attestation state from check results.

    Invariants:
        * Every check PASS            -> ATTESTED
        * Any check FAIL              -> REJECTED
        * Anything else / nothing ran -> UNRESOLVED (never ATTESTED)
    """
    if len(check_results) == 0:
        return {"attestation_state": UNRESOLVED, "reason_code": "EMPTY_POLICY",
                "failed_checks": ""}

    failed = []
    inconclusive = []
    unsupported = []

    for r in check_results:
        status = r.get("status", E_FAIL)
        name = r.get("check_name", "unknown")
        if status == E_FAIL:
            failed.append(name)
        elif status == E_UNSUPPORTED:
            unsupported.append(name)
            inconclusive.append(name)
        elif status in (E_FETCH_FAILED, E_INSUFFICIENT):
            inconclusive.append(name)
        elif status not in VALID_CHECK_STATUSES:
            inconclusive.append(name)

    if len(failed) > 0:
        return {"attestation_state": REJECTED, "reason_code": "CHECK_FAILED",
                "failed_checks": ",".join(failed)}
    if len(unsupported) > 0:
        return {"attestation_state": UNRESOLVED, "reason_code": "UNSUPPORTED_POLICY",
                "failed_checks": ",".join(unsupported)}
    if len(inconclusive) > 0:
        reason = "FETCH_FAILED" if any(
            r.get("status") == E_FETCH_FAILED for r in check_results
        ) else "INSUFFICIENT_EVIDENCE"
        return {"attestation_state": UNRESOLVED, "reason_code": reason,
                "failed_checks": ",".join(inconclusive)}
    return {"attestation_state": ATTESTED, "reason_code": "", "failed_checks": ""}


def _compose_challenge_outcome(recomputed: list, contradiction, evidence_ok: bool) -> dict:
    """Compose a challenge outcome from recomputed checks + adjudication.

    ``contradiction`` is True, False, or None (unknown/malformed).

    Invariants (fail closed):
        * Unusable challenge evidence         -> INVALID  (attestation STANDS)
        * Original policy now explicitly FAILs-> REVOKED  (no longer valid)
        * Original policy now inconclusive    -> DISPUTED (cannot confirm)
        * Adjudication says contradiction=True -> REVOKED
        * Adjudication says contradiction=False-> ATTESTED (challenge rejected)
        * Adjudication undecidable (None)     -> DISPUTED (cannot affirm)
    """
    if not evidence_ok:
        return {"outcome": INVALID,
                "reason_code": "CHALLENGE_EVIDENCE_UNUSABLE"}
    if len(recomputed) == 0:
        return {"outcome": DISPUTED, "reason_code": "ORIGINAL_NOT_CONFIRMED"}

    failed = [r.get("check_name", "unknown") for r in recomputed
              if r.get("status") == E_FAIL]
    inconclusive = [r.get("check_name", "unknown") for r in recomputed
                    if r.get("status") in (E_FETCH_FAILED, E_INSUFFICIENT)
                    or r.get("status") not in VALID_CHECK_STATUSES]

    if len(failed) > 0:
        return {"outcome": REVOKED, "reason_code": "ORIGINAL_NO_LONGER_VALID"}
    if len(inconclusive) > 0:
        return {"outcome": DISPUTED, "reason_code": "ORIGINAL_NOT_CONFIRMED"}
    if contradiction is True:
        return {"outcome": REVOKED, "reason_code": "CHALLENGE_UPHELD"}
    if contradiction is False:
        return {"outcome": ATTESTED, "reason_code": "CHALLENGE_REJECTED"}
    return {"outcome": DISPUTED, "reason_code": "CHALLENGE_UNDECIDED"}


def _canonical_key(project_name: str, version: str) -> str:
    """Deterministic canonical key for an exact project + version.

    Project and version are normalized the same way everywhere (strip +
    lowercase, leading `v` removed from the version). Because lookup uses an
    exact map key - never substring search - version "2" can never collide
    with "11.2.0".
    """
    project = project_name.strip().lower()
    ver = _normalized_version(version)
    return f"{project}::{ver}"


def _normalize_url(url: str) -> str:
    """Normalize a URL for equality comparison only (not for fetching)."""
    return url.strip().lower()


def _normalize_reason(reason: str) -> str:
    return re.sub(r"\s+", " ", reason.strip().lower())


def _address_hex(addr) -> str:
    try:
        return addr.as_hex
    except Exception:
        return str(addr)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
class ReleaseGuardV2(gl.Contract):
    """
    Challengeable, revocable on-chain release attestations.

    At most one canonical claim per exact project + version. The canonical
    key is bound only when a review reaches ATTESTED, so a PENDING, RUNNING,
    REJECTED, or UNRESOLVED claim can never block a legitimate release claim.
    Attested claims can be challenged by anyone:

        * unusable challenge evidence   -> challenge INVALID, attestation stands
        * substantiated contradiction   -> claim REVOKED (terminal)
        * rejected contradiction        -> claim stays ATTESTED
        * credible but undecidable      -> claim DISPUTED (not safely attested)

    No attestation can ever be silently restored to ATTESTED once revoked,
    and a canonical record is never silently overwritten.
    """

    claims: TreeMap[str, Claim]
    challenges: TreeMap[str, Challenge]
    canonical: TreeMap[str, str]
    claim_counter: u256
    challenge_counter: u256

    def __init__(self):
        self.claim_counter = u256(0)
        self.challenge_counter = u256(0)

    # ------------------------------------------------------------------
    # Claim lifecycle
    # ------------------------------------------------------------------
    @gl.public.write
    def create_claim(self, project_name: str, version: str,
                     evidence_url: str, policy_text: str) -> str:
        """Register a release claim. Permissionless.

        This does NOT reserve any canonical mapping. Any number of claims may
        exist for the same project/version; the canonical key is bound only
        by a review that reaches ATTESTED. Blank inputs and invalid evidence
        URLs are rejected.

        Returns the new claim id ("c-<n>").
        """
        if not project_name or not project_name.strip():
            raise gl.vm.UserError("Project name required")
        if not version or not version.strip():
            raise gl.vm.UserError("Version required")
        url_problem = _validate_evidence_url(evidence_url)
        if url_problem:
            raise gl.vm.UserError(f"Invalid evidence URL ({url_problem})")
        # Empty policy is allowed - it fails closed (UNRESOLVED) at review time,
        # exactly as in V1. Do NOT silently default to a policy here.

        self.claim_counter = self.claim_counter + 1
        claim_id = f"c-{self.claim_counter}"

        claim = Claim(
            id=claim_id,
            requester=gl.message.sender_address,
            project_name=project_name,
            version=version,
            evidence_url=evidence_url,
            policy_text=policy_text,
            status=CLAIM_PENDING,
            attestation_state="",
            reason_code="",
            failed_checks="",
            active_challenge_id="",
            results_json="",
            challenge_ids_json="",
        )
        self.claims[claim_id] = claim
        return claim_id

    @gl.public.write
    def run_claim_review(self, claim_id: str) -> str:
        """Run consensus review of a pending claim.

        Permissionless: anyone may trigger it. The result is a deterministic
        function of the consensus evidence, so permissionless execution does
        not weaken security.

        The canonical key is bound ONLY if this review reaches ATTESTED and no
        other claim is already canonical for that exact project/version. A
        competing claim that would otherwise attest finishes UNRESOLVED with
        reason_code CANONICAL_ATTESTATION_EXISTS.

        Returns the terminal state: ATTESTED | REJECTED | UNRESOLVED.
        """
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        claim = self.claims[claim_id]
        if claim.status != CLAIM_PENDING:
            raise gl.vm.UserError(f"Claim is {claim.status}, not PENDING")

        claim.status = CLAIM_RUNNING

        # Copy storage values to memory before any nondeterministic work.
        mem_url = claim.evidence_url
        mem_project = claim.project_name
        mem_version = claim.version
        mem_policy = claim.policy_text

        supported, unsupported = _parse_policies(mem_policy)

        check_results = []

        if len(unsupported) > 0:
            # Unsupported policy poisons the whole claim: no partial attestation.
            for name in unsupported:
                check_results.append({
                    "check_name": name,
                    "status": E_UNSUPPORTED,
                    "evidence": "Unsupported policy",
                    "reason": f"Policy '{name}' is not supported by ReleaseGuard V2",
                })
        else:
            for check_name in supported:
                if check_name == "source":
                    def leader_fn() -> dict:
                        return _check_source(mem_url, mem_project, mem_version)
                elif check_name == "license":
                    def leader_fn() -> dict:
                        return _check_license(mem_url, mem_project)
                elif check_name == "vulnerability":
                    def leader_fn() -> dict:
                        return _check_vulnerability(mem_url, mem_project, mem_version)
                else:
                    # Unreachable: _parse_policies only returns supported names
                    # here. Fail closed anyway.
                    check_results.append({
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
                    check_results.append({
                        "check_name": check_name,
                        "status": str(result.get("status", E_INSUFFICIENT)),
                        "evidence": str(result.get("evidence", "")),
                        "reason": str(result.get("reason", "")),
                    })
                except Exception:
                    # Consensus failure -> INSUFFICIENT (fail closed), never FAIL.
                    check_results.append({
                        "check_name": check_name,
                        "status": E_INSUFFICIENT,
                        "evidence": "Consensus not reached",
                        "reason": "Validator disagreed or execution failed",
                    })

        # --- Deterministic composition (no LLM). Never leave a stale RUNNING. ---
        try:
            composed = _compose_claim_state(check_results)
            state = composed["attestation_state"]
            reason_code = composed["reason_code"]
            failed_checks = composed["failed_checks"]
        except Exception:
            state = UNRESOLVED
            reason_code = "COMPOSITION_ERROR"
            failed_checks = ""
            check_results = [{
                "check_name": "composition",
                "status": E_INSUFFICIENT,
                "evidence": "Result composition failed",
                "reason": "Deterministic composition failed; fail closed",
            }]

        # --- Canonical binding: ONLY on a genuine ATTESTED, and never an
        # --- overwrite of an existing canonical record for the same key.
        if state == ATTESTED:
            key = _canonical_key(mem_project, mem_version)
            existing = self.canonical[key] if key in self.canonical else ""
            if existing == "" or existing == claim_id:
                self.canonical[key] = claim_id
            else:
                # Another claim already owns this exact version. Never
                # overwrite it, and never label a valid competing claim
                # REJECTED just for losing the race.
                state = UNRESOLVED
                reason_code = "CANONICAL_ATTESTATION_EXISTS"
                failed_checks = ""

        claim.attestation_state = state
        claim.reason_code = reason_code
        claim.failed_checks = failed_checks
        claim.results_json = json.dumps(check_results[:MAX_STORED_RESULTS])
        claim.status = state  # terminal lifecycle state

        return claim.attestation_state

    @gl.public.view
    def get_claim(self, claim_id: str) -> dict:
        """Return the complete stored claim record."""
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        c = self.claims[claim_id]
        return {
            "id": c.id,
            "requester": _address_hex(c.requester),
            "project_name": c.project_name,
            "version": c.version,
            "evidence_url": c.evidence_url,
            "policy_text": c.policy_text,
            "status": c.status,
            "attestation_state": c.attestation_state,
            "reason_code": c.reason_code,
            "failed_checks": c.failed_checks,
            "active_challenge_id": c.active_challenge_id,
            "results": json.loads(c.results_json) if c.results_json else [],
            "challenge_ids": json.loads(c.challenge_ids_json) if c.challenge_ids_json else [],
        }

    # ------------------------------------------------------------------
    # Challenge lifecycle
    # ------------------------------------------------------------------
    @gl.public.write
    def open_challenge(self, claim_id: str, evidence_url: str,
                       reason: str) -> str:
        """Open a challenge against an ATTESTED claim. Permissionless.

        Rejected (transaction reverts, nothing stored) when: the claim is not
        ATTESTED; a challenge is already open; the evidence URL is invalid or
        identical to the claim's own evidence URL; the reason is blank, too
        long, or contains control characters; or this exact (evidence URL,
        reason) challenge already exists.

        The challenge starts OPEN. Whether its evidence is usable is decided
        deterministically at review time, so an unusable challenge becomes
        INVALID instead of damaging the attestation.

        Returns the new challenge id ("x-<n>").
        """
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        url_problem = _validate_evidence_url(evidence_url)
        if url_problem:
            raise gl.vm.UserError(f"Invalid challenge evidence URL ({url_problem})")
        reason_problem = _validate_reason(reason)
        if reason_problem:
            raise gl.vm.UserError(f"Invalid challenge reason ({reason_problem})")

        claim = self.claims[claim_id]
        if claim.status != CLAIM_ATTESTED:
            raise gl.vm.UserError(
                f"Only an ATTESTED claim can be challenged (claim is {claim.status})")
        if claim.active_challenge_id:
            raise gl.vm.UserError("A challenge is already open for this claim")
        if _normalize_url(evidence_url) == _normalize_url(claim.evidence_url):
            raise gl.vm.UserError(
                "Challenge evidence must differ from the original evidence")

        new_url = _normalize_url(evidence_url)
        new_reason = _normalize_reason(reason)
        existing_ids = json.loads(claim.challenge_ids_json) if claim.challenge_ids_json else []
        for existing_id in existing_ids:
            if existing_id in self.challenges:
                prev = self.challenges[existing_id]
                if (_normalize_url(prev.evidence_url) == new_url
                        and _normalize_reason(prev.reason) == new_reason):
                    raise gl.vm.UserError("Duplicate challenge")

        self.challenge_counter = self.challenge_counter + 1
        challenge_id = f"x-{self.challenge_counter}"

        challenge = Challenge(
            id=challenge_id,
            claim_id=claim_id,
            challenger=gl.message.sender_address,
            evidence_url=evidence_url,
            reason=reason,
            status=CHALLENGE_OPEN,
            outcome="",
            reason_code="",
            results_json="",
        )
        self.challenges[challenge_id] = challenge

        existing_ids.append(challenge_id)
        claim.challenge_ids_json = json.dumps(existing_ids)
        claim.active_challenge_id = challenge_id
        claim.status = CLAIM_CHALLENGED
        return challenge_id

    @gl.public.write
    def run_challenge_review(self, challenge_id: str) -> str:
        """Run consensus adjudication of an open challenge.

        Validators independently re-evaluate the original claim's policies AND
        the challenge evidence, then the outcome is composed deterministically:

            INVALID    - challenge evidence unusable. The claim returns to
                         ATTESTED and the canonical attestation is preserved.
            ATTESTED   - challenge rejected, claim returns to ATTESTED.
            REVOKED    - claim is revoked; canonical state becomes REVOKED.
            DISPUTED   - retrievable but undecidable; the claim can no longer
                         remain safely attested and becomes DISPUTED.

        Returns the challenge outcome.
        """
        if challenge_id not in self.challenges:
            raise gl.vm.UserError("Challenge not found")
        challenge = self.challenges[challenge_id]
        if challenge.status != CHALLENGE_OPEN:
            raise gl.vm.UserError(f"Challenge is {challenge.status}, not OPEN")

        if challenge.claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        claim = self.claims[challenge.claim_id]
        if claim.status != CLAIM_CHALLENGED:
            raise gl.vm.UserError(
                f"Claim is {claim.status}, not CHALLENGED")

        # Copy storage values to memory before nondeterministic work.
        mem_claim_url = claim.evidence_url
        mem_project = claim.project_name
        mem_version = claim.version
        mem_policy = claim.policy_text
        mem_challenge_url = challenge.evidence_url
        mem_reason = challenge.reason

        def leader_fn() -> dict:
            # Re-evaluate the original claim's supported policies. A check that
            # cannot be re-run is recorded as INSUFFICIENT (fail closed) rather
            # than raising, so the outcome stays deterministic.
            supported, _ = _parse_policies(mem_policy)
            recomputed = []
            for name in supported:
                try:
                    if name == "source":
                        recomputed.append(
                            _check_source(mem_claim_url, mem_project, mem_version))
                    elif name == "license":
                        recomputed.append(_check_license(mem_claim_url, mem_project))
                    elif name == "vulnerability":
                        recomputed.append(
                            _check_vulnerability(mem_claim_url, mem_project, mem_version))
                except Exception:
                    recomputed.append({
                        "check_name": name,
                        "status": E_INSUFFICIENT,
                        "evidence": "Re-evaluation failed",
                        "reason": "Original check could not be re-evaluated",
                    })

            # Fetch and adjudicate the challenge evidence.
            challenge_text = _fetch_page_text(mem_challenge_url)
            evidence_ok = (len(challenge_text.strip()) >= MIN_CHALLENGE_EVIDENCE_LEN)
            contradiction = None
            contradiction_reason = ""
            if evidence_ok:
                prompt = (
                    "Release challenge adjudication.\n"
                    f"Original claim: {mem_project} {mem_version}\n"
                    f"Original evidence URL: {mem_claim_url}\n"
                    f"Requested policies: {mem_policy}\n"
                    f"Challenge evidence URL: {mem_challenge_url}\n"
                    f"Challenge reason: {mem_reason}\n\n"
                    "Decide whether the challenge evidence establishes a "
                    "contradiction with the original release attestation.\n"
                    "Return JSON: {\"contradiction_established\": true/false, "
                    "\"reason\": \"...\"}"
                )
                try:
                    raw = gl.nondet.exec_prompt(
                        prompt + f"\n\nChallenge evidence:\n{challenge_text}",
                        response_format="json")
                    parsed = _parse_json_response(raw)
                    if isinstance(parsed, dict) and isinstance(
                            parsed.get("contradiction_established"), bool):
                        contradiction = parsed["contradiction_established"]
                        contradiction_reason = str(parsed.get("reason", ""))
                    else:
                        contradiction = None
                        contradiction_reason = "Malformed adjudication response"
                except Exception:
                    # Undecidable adjudication -> contradiction None -> DISPUTED
                    # (fail closed). Never treated as ATTESTED.
                    contradiction = None
                    contradiction_reason = "Adjudication could not be completed"

            composed = _compose_challenge_outcome(
                recomputed, contradiction, evidence_ok)
            return {
                "outcome": composed["outcome"],
                "reason_code": composed["reason_code"],
                "checks": recomputed[:MAX_STORED_RESULTS],
                "contradiction_established": contradiction,
                "contradiction_reason": contradiction_reason,
                "evidence_ok": evidence_ok,
            }

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            leader_data = leader_result.calldata
            if not isinstance(leader_data, dict):
                return False
            leader_outcome = leader_data.get("outcome", "")
            if leader_outcome not in CHALLENGE_OUTCOMES:
                return False
            try:
                validator_data = leader_fn()
            except Exception:
                return False
            if not isinstance(validator_data, dict):
                return False
            return validator_data.get("outcome", "") == leader_outcome

        try:
            result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
            if not isinstance(result, dict):
                raise gl.vm.UserError("Malformed challenge consensus result")
            outcome = str(result.get("outcome", DISPUTED))
            reason_code = str(result.get("reason_code", ""))
            checks = result.get("checks", [])
            if not isinstance(checks, list):
                checks = []
        except Exception:
            # Consensus failure -> DISPUTED (fail closed). Never REJECTED,
            # never silently ATTESTED.
            outcome = DISPUTED
            reason_code = "CONSENSUS_FAILED"
            checks = [{
                "check_name": "challenge",
                "status": E_INSUFFICIENT,
                "evidence": "Consensus not reached",
                "reason": "Validator disagreed or execution failed",
            }]

        if outcome not in CHALLENGE_OUTCOMES:
            outcome = DISPUTED
            reason_code = "MALFORMED_CHALLENGE_RESPONSE"

        # --- Deterministic state transition. REVOKED is terminal. ---
        challenge.results_json = json.dumps(checks[:MAX_STORED_RESULTS])
        challenge.outcome = outcome
        challenge.reason_code = reason_code
        claim.active_challenge_id = ""

        if outcome == REVOKED:
            challenge.status = CHALLENGE_RESOLVED
            claim.status = CLAIM_REVOKED
            claim.attestation_state = REVOKED
            claim.reason_code = reason_code or "CHALLENGE_UPHELD"
        elif outcome == ATTESTED:
            challenge.status = CHALLENGE_RESOLVED
            # A revoked claim can never be restored to ATTESTED; this is only
            # reachable from CHALLENGED, but guard defensively anyway.
            if claim.attestation_state == REVOKED:
                claim.status = CLAIM_REVOKED
                claim.attestation_state = REVOKED
            else:
                claim.status = CLAIM_ATTESTED
                claim.attestation_state = ATTESTED
                claim.reason_code = ""
        elif outcome == INVALID:
            # Unusable challenge evidence must NOT damage a valid attestation.
            challenge.status = CHALLENGE_INVALID
            if claim.attestation_state == ATTESTED:
                claim.status = CLAIM_ATTESTED
                claim.attestation_state = ATTESTED
                claim.reason_code = ""
            else:
                # Defensive: never leave a non-attested claim looking attested.
                claim.status = CLAIM_DISPUTED
                claim.attestation_state = DISPUTED
                claim.reason_code = "CHALLENGE_INVALID_UNEXPECTED_STATE"
        else:  # DISPUTED
            challenge.status = CHALLENGE_DISPUTED
            claim.status = CLAIM_DISPUTED
            claim.attestation_state = DISPUTED
            claim.reason_code = reason_code or "CHALLENGE_UNDECIDED"

        return outcome

    @gl.public.view
    def get_challenge(self, challenge_id: str) -> dict:
        """Return the complete stored challenge record."""
        if challenge_id not in self.challenges:
            raise gl.vm.UserError("Challenge not found")
        x = self.challenges[challenge_id]
        return {
            "id": x.id,
            "claim_id": x.claim_id,
            "challenger": _address_hex(x.challenger),
            "evidence_url": x.evidence_url,
            "reason": x.reason,
            "status": x.status,
            "outcome": x.outcome,
            "reason_code": x.reason_code,
            "results": json.loads(x.results_json) if x.results_json else [],
        }

    # ------------------------------------------------------------------
    # Canonical queries
    # ------------------------------------------------------------------
    @gl.public.view
    def get_current_attestation(self, project_name: str, version: str) -> dict:
        """Return the canonical current attestation for an exact project+version.

        `exists` is False until a review has genuinely bound this exact
        project/version to an ATTESTED claim. After binding, `status` and
        `attestation_state` always reflect the claim's real current state, so a
        REVOKED or DISPUTED canonical record is explicitly not attestable.
        No substring matching is ever used.
        """
        key = _canonical_key(project_name, version)
        if key not in self.canonical:
            return {
                "exists": False,
                "project_name": project_name,
                "version": version,
                "claim_id": "",
                "status": "",
                "attestation_state": "",
                "reason_code": "",
            }
        claim_id = self.canonical[key]
        c = self.claims[claim_id]
        return {
            "exists": True,
            "project_name": c.project_name,
            "version": c.version,
            "claim_id": c.id,
            "status": c.status,
            "attestation_state": c.attestation_state,
            "reason_code": c.reason_code,
        }

    @gl.public.view
    def get_claim_challenges(self, claim_id: str) -> list:
        """Return every challenge opened for a claim, oldest first."""
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        c = self.claims[claim_id]
        ids = json.loads(c.challenge_ids_json) if c.challenge_ids_json else []
        out = []
        for cid in ids:
            if cid in self.challenges:
                out.append(self.get_challenge(cid))
        return out
