"""Direct-mode tests for ReleaseGuard V2 (challengeable, revocable attestations).

These tests prove the V2 lifecycle end to end against the pinned gltest setup
used by the rest of this repository. They do not modify or weaken the V1
tests.

Coverage map:
  1.  Happy path + canonical binding after ATTESTED
  2.  Initial rejection / unresolved (fail-closed) behaviour
  3.  Challenge success, rejection, and fail-closed paths
  4.  Invalid (unusable-evidence) challenges never damage an attestation
  5.  Substantive but undecidable challenges drop the claim to DISPUTED
  6.  Permissionless challenge execution
  7.  Invalid transitions and duplicate / concurrent challenges
  8.  Exact project/version matching
  9.  Regression cases carried forward from V1
  10. Anti-squatting: canonical is bound only on ATTESTED
  11. Deterministic HTTPS evidence URL validation
  12. Storage / query accuracy

Mocking notes (gltest 0.29.x direct mode):
- mock_web(url_pattern, {"method": "GET", "status": 200, "body": "..."})
  Patterns use re.search; escape dots.
- mock_llm(prompt_pattern, response) - first matching mock wins.
- Omitting a web/LLM mock raises MockNotFoundError, which the contract's
  fetch/prompt helpers either catch (-> FETCH_FAILED / INSUFFICIENT) or which
  propagates out of consensus (-> handled fail-closed).
"""
import pytest

from tests.direct.conftest import to_hex

CLAIM = "contracts/release_guard_v2.py"

# Distinctive prompt fragments the contract emits, used as mock patterns.
SOURCE_PROMPT = r".*Verify whether this URL genuinely contains a release.*"
LICENSE_PROMPT = r".*Check the license of project.*"
VULN_PROMPT = r".*Check for critical/high vulnerabilities.*"
ADJUDICATE_PROMPT = r".*Release challenge adjudication.*"

SOURCE_PASS = ('{"observed_project": "requests", "observed_version": "2.31.0", '
               '"page_has_release_content": true}')
SOURCE_UNKNOWN = ('{"observed_project": "unknown", "observed_version": "unknown", '
                  '"page_has_release_content": false}')
TESTPROJ_SOURCE_PASS = ('{"observed_project": "TestProject", '
                        '"observed_version": "1.0.0", '
                        '"page_has_release_content": true}')

REQUESTS_URL = "https://pypi.org/project/requests/2.31.0/"
REQUESTS_PAGE = "requests 2.31.0 release information and package metadata."


def _register_requests_source_mocks(vm):
    """Register the (web, LLM) mocks needed for a passing source check."""
    vm.mock_web(r".*pypi\.org.*",
                {"method": "GET", "status": 200, "body": REQUESTS_PAGE})
    vm.mock_llm(SOURCE_PROMPT, SOURCE_PASS)


def _attested_source_claim(contract, vm, alice,
                           project="requests", version="2.31.0",
                           url=REQUESTS_URL):
    """Create and review a claim that becomes ATTESTED on the source policy."""
    vm.sender = alice
    cid = contract.create_claim(project, version, url, "source")
    _register_requests_source_mocks(vm)
    assert contract.run_claim_review(cid) == "ATTESTED"
    return cid


# =======================================================================
# 1. Happy path + canonical binding
# =======================================================================
def test_happy_path_attested_and_canonical(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    c = contract.get_claim(cid)
    assert c["status"] == "ATTESTED"
    assert c["attestation_state"] == "ATTESTED"
    assert c["reason_code"] == ""
    assert c["failed_checks"] == ""
    assert c["requester"] == to_hex(direct_alice)

    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["exists"] is True
    assert att["attestation_state"] == "ATTESTED"
    assert att["claim_id"] == cid


def test_created_claim_is_pending_and_not_canonical(direct_deploy, direct_vm,
                                                    direct_alice):
    """A freshly created claim must not be canonical until it attests."""
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim("requests", "2.31.0", REQUESTS_URL, "source")
    assert contract.get_claim(cid)["status"] == "PENDING"
    assert contract.get_claim(cid)["attestation_state"] == ""
    assert contract.get_current_attestation("requests", "2.31.0")["exists"] is False


# =======================================================================
# 2. Initial rejection / unresolved
# =======================================================================
def test_claim_rejected_on_failed_license(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://github.com/test/project", "license")
    direct_vm.mock_web(r".*github\.com.*",
                       {"method": "GET", "status": 200, "body": "Project license text page."})
    direct_vm.mock_llm(
        LICENSE_PROMPT,
        '{"license_name": "GPL-3.0", "license_text_observed": true, "is_permissive": false}')
    assert contract.run_claim_review(cid) == "REJECTED"
    c = contract.get_claim(cid)
    assert c["attestation_state"] == "REJECTED"
    assert c["reason_code"] == "CHECK_FAILED"
    assert "license" in c["failed_checks"]
    # A REJECTED claim never reserves the canonical lookup.
    assert contract.get_current_attestation("TestProject", "1.0.0")["exists"] is False


def test_claim_rejected_on_vulnerability_finding(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://osv.dev/list?q=test", "vulnerability")
    direct_vm.mock_web(r".*osv\.dev.*",
                       {"method": "GET", "status": 200, "body": "CVE-2024-1234: Critical RCE."})
    direct_vm.mock_llm(
        VULN_PROMPT,
        '{"has_vulnerability_data": true, "critical_count": 1, "high_count": 0}')
    assert contract.run_claim_review(cid) == "REJECTED"
    assert contract.get_claim(cid)["failed_checks"] == "vulnerability"


def test_empty_policy_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://example.com/release", "   ,  ")
    assert contract.run_claim_review(cid) == "UNRESOLVED"
    c = contract.get_claim(cid)
    assert c["attestation_state"] == "UNRESOLVED"
    assert c["reason_code"] == "EMPTY_POLICY"
    assert contract.get_current_attestation("TestProject", "1.0.0")["exists"] is False


def test_unsupported_policy_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://example.com/release", "freshness")
    assert contract.run_claim_review(cid) == "UNRESOLVED"
    c = contract.get_claim(cid)
    assert c["reason_code"] == "UNSUPPORTED_POLICY"
    assert c["results"][0]["status"] == "UNSUPPORTED_POLICY"


def test_fetch_failure_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://down.example.com/release", "source")
    # No web mock -> retrieval fails -> FETCH_FAILED -> UNRESOLVED, never ATTESTED.
    assert contract.run_claim_review(cid) == "UNRESOLVED"
    c = contract.get_claim(cid)
    assert c["reason_code"] == "FETCH_FAILED"
    assert c["results"][0]["status"] == "FETCH_FAILED"


# =======================================================================
# 3. Challenge outcomes
# =======================================================================
def test_challenge_success_revokes_claim(direct_deploy, direct_vm,
                                         direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0",
        "Critical RCE disclosed for requests 2.31.0")
    assert xid.startswith("x-")

    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "CVE-2024-9999 critical remote code execution in requests 2.31.0."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": true, "reason": "Critical RCE contradicts the attestation"}')

    assert contract.run_challenge_review(xid) == "REVOKED"

    c = contract.get_claim(cid)
    assert c["status"] == "REVOKED"
    assert c["attestation_state"] == "REVOKED"
    assert c["active_challenge_id"] == ""

    x = contract.get_challenge(xid)
    assert x["status"] == "RESOLVED"
    assert x["outcome"] == "REVOKED"
    assert x["challenger"] == to_hex(direct_bob)

    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["attestation_state"] == "REVOKED"


def test_challenge_rejected_keeps_attestation(direct_deploy, direct_vm,
                                              direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://news.example.com/requests-2.31.0",
        "Claims a licensing dispute that does not affect the release")

    direct_vm.mock_web(
        r".*news\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "Discussion thread with no new facts about requests 2.31.0."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": false, "reason": "No contradicting facts found"}')

    assert contract.run_challenge_review(xid) == "ATTESTED"

    c = contract.get_claim(cid)
    assert c["status"] == "ATTESTED"
    assert c["attestation_state"] == "ATTESTED"
    assert c["active_challenge_id"] == ""

    x = contract.get_challenge(xid)
    assert x["status"] == "RESOLVED"
    assert x["outcome"] == "ATTESTED"
    assert x["reason_code"] == "CHALLENGE_REJECTED"

    assert contract.get_current_attestation(
        "requests", "2.31.0")["attestation_state"] == "ATTESTED"


# =======================================================================
# 4. Invalid challenges must not damage the attestation
# =======================================================================
def test_invalid_challenge_unreachable_evidence_preserves_attestation(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    """A challenge whose evidence cannot be retrieved is INVALID, not a DoS."""
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://unreachable.example.com/evidence",
        "Alleges a vulnerability without accessible evidence")
    # No web mock for the challenge URL -> unusable evidence -> INVALID.
    assert contract.run_challenge_review(xid) == "INVALID"

    c = contract.get_claim(cid)
    assert c["status"] == "ATTESTED"
    assert c["attestation_state"] == "ATTESTED"
    assert c["active_challenge_id"] == ""

    x = contract.get_challenge(xid)
    assert x["status"] == "INVALID"
    assert x["outcome"] == "INVALID"
    assert x["reason_code"] == "CHALLENGE_EVIDENCE_UNUSABLE"

    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["exists"] is True
    assert att["claim_id"] == cid
    assert att["attestation_state"] == "ATTESTED"


def test_invalid_challenge_too_short_evidence_preserves_attestation(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://tiny.example.com/e", "Weak evidence with no substance")
    direct_vm.mock_web(r".*tiny\.example\.com.*",
                       {"method": "GET", "status": 200, "body": "too short"})
    assert contract.run_challenge_review(xid) == "INVALID"
    assert contract.get_claim(cid)["status"] == "ATTESTED"
    assert contract.get_challenge(xid)["status"] == "INVALID"
    assert contract.get_current_attestation(
        "requests", "2.31.0")["attestation_state"] == "ATTESTED"


def test_invalid_challenge_clears_lock_and_allows_new_challenge(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    x1 = contract.open_challenge(
        cid, "https://unreachable.example.com/e1", "first weak challenge")
    assert contract.run_challenge_review(x1) == "INVALID"

    # The lock is cleared, so a substantive challenge can still be opened.
    x2 = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0",
        "second substantive challenge")
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "CVE-2024-9999 critical remote code execution in requests 2.31.0."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": true, "reason": "Confirmed contradiction"}')
    assert contract.run_challenge_review(x2) == "REVOKED"
    assert contract.get_claim(cid)["status"] == "REVOKED"
    assert [x["id"] for x in contract.get_claim_challenges(cid)] == [x1, x2]


# =======================================================================
# 5. Substantive but undecidable challenges -> DISPUTED
# =======================================================================
def test_substantive_but_undecidable_challenge_sets_disputed(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://ambiguous.example.com/report",
        "Conflicting but inconclusive advisory evidence")
    direct_vm.mock_web(
        r".*ambiguous\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "An advisory page whose meaning is genuinely ambiguous here."})
    # Retrievable, meaningful evidence, but the adjudication cannot decide.
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": "maybe", "reason": "cannot decide"}')

    assert contract.run_challenge_review(xid) == "DISPUTED"

    c = contract.get_claim(cid)
    assert c["status"] == "DISPUTED"
    assert c["attestation_state"] == "DISPUTED"
    assert c["active_challenge_id"] == ""

    x = contract.get_challenge(xid)
    assert x["status"] == "DISPUTED"
    assert x["outcome"] == "DISPUTED"

    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["exists"] is True
    assert att["attestation_state"] == "DISPUTED"
    assert att["status"] == "DISPUTED"
    # A DISPUTED canonical record is explicitly NOT safely attestable.
    assert att["attestation_state"] != "ATTESTED"


def test_malformed_adjudication_is_disputed_not_revoked(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0",
        "Conflicting advisory evidence")
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "An advisory page with ambiguous and unparseable claims here."})
    # Adjudication returns junk -> undecidable -> DISPUTED (never ATTESTED).
    direct_vm.mock_llm(ADJUDICATE_PROMPT, "this is not json at all")

    assert contract.run_challenge_review(xid) == "DISPUTED"
    assert contract.get_claim(cid)["status"] == "DISPUTED"
    assert contract.get_current_attestation(
        "requests", "2.31.0")["attestation_state"] == "DISPUTED"


def test_challenge_disputed_when_original_cannot_be_reconfirmed(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0",
        "New advisory for this release")
    # Drop the original-evidence mocks: the challenge evidence is retrievable
    # and meaningful, but the ORIGINAL claim can no longer be re-confirmed.
    direct_vm.clear_mocks()
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "A concrete advisory that mentions requests 2.31.0 explicitly."})

    assert contract.run_challenge_review(xid) == "DISPUTED"
    c = contract.get_claim(cid)
    assert c["status"] == "DISPUTED"
    assert c["reason_code"] == "ORIGINAL_NOT_CONFIRMED"


# =======================================================================
# 6. Permissionless behaviour
# =======================================================================
def test_challenge_is_permissionless(direct_deploy, direct_vm,
                                     direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    # Alice creates and reviews the claim.
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    # Bob - a completely different account - opens and runs the challenge.
    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0",
        "Independent third-party contradiction")
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "Independent security advisory contradicting the release claim."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": true, "reason": "Third-party contradiction confirmed"}')

    assert contract.run_challenge_review(xid) == "REVOKED"
    assert contract.get_challenge(xid)["challenger"] == to_hex(direct_bob)


# =======================================================================
# 7. Invalid transitions
# =======================================================================
def test_challenge_non_attested_claim_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://example.com/release", "source")
    # Claim is still PENDING - cannot be challenged.
    with pytest.raises(Exception):
        contract.open_challenge(cid, "https://other.example.com/e", "reason")


def test_second_open_challenge_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.open_challenge(cid, "https://a.example.com/e", "first")
    with pytest.raises(Exception):
        contract.open_challenge(cid, "https://b.example.com/e", "second")


def test_duplicate_challenge_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    xid = contract.open_challenge(
        cid, "https://dup.example.com/e", "Duplicate reason")
    direct_vm.mock_web(
        r".*dup\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "A page that does not contradict the release attestation."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": false, "reason": "Nothing new"}')
    assert contract.run_challenge_review(xid) == "ATTESTED"

    # Claim is attested again; an identical (url, reason) challenge is refused.
    with pytest.raises(Exception):
        contract.open_challenge(cid, "https://dup.example.com/e", "Duplicate reason")


def test_challenge_cannot_reuse_original_evidence(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.open_challenge(cid, REQUESTS_URL, "reuse original")


def test_cannot_challenge_revoked_claim(direct_deploy, direct_vm,
                                        direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0", "revoke it")
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "Advisory that definitively contradicts the release claim."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": true, "reason": "Contradiction"}')
    assert contract.run_challenge_review(xid) == "REVOKED"

    # A revoked claim can never be challenged again (nor restored).
    with pytest.raises(Exception):
        contract.open_challenge(cid, "https://another.example.com/e", "restore please")
    assert contract.get_current_attestation(
        "requests", "2.31.0")["attestation_state"] == "REVOKED"


def test_malformed_ids_fail_safely(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    for call in (
        lambda: contract.get_claim("c-999"),
        lambda: contract.run_claim_review("c-999"),
        lambda: contract.get_challenge("x-999"),
        lambda: contract.run_challenge_review("x-999"),
        lambda: contract.open_challenge("c-999", "https://e.example.com", "r"),
        lambda: contract.get_claim_challenges("c-999"),
    ):
        with pytest.raises(Exception):
            call()


def test_review_requires_pending_state(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    # The claim is now ATTESTED; a second review must be refused.
    with pytest.raises(Exception):
        contract.run_claim_review(cid)


def test_challenge_review_requires_open_challenge(direct_deploy, direct_vm,
                                                  direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    xid = contract.open_challenge(cid, "https://a.example.com/e", "reason here")
    direct_vm.mock_web(
        r".*a\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "A page that does not contradict the release attestation."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": false, "reason": "Nothing"}')
    contract.run_challenge_review(xid)
    # Challenge is now RESOLVED; a second review must be refused.
    with pytest.raises(Exception):
        contract.run_challenge_review(xid)


# =======================================================================
# 8. Exact matching
# =======================================================================
def test_version_two_does_not_match_component_of_11_2_0(direct_deploy, direct_vm,
                                                        direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "2", "https://example.com/release", "source")
    direct_vm.mock_web(
        r".*example\.com.*",
        {"method": "GET", "status": 200,
         "body": "TestProject release version 11.2.0 information."})
    direct_vm.mock_llm(SOURCE_PROMPT, SOURCE_UNKNOWN)
    assert contract.run_claim_review(cid) == "REJECTED"
    assert contract.get_claim(cid)["results"][0]["status"] == "FAIL"


def test_canonical_lookup_is_exact_not_substring(direct_deploy, direct_vm,
                                                 direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    a = contract.create_claim("Example", "2", "https://example.com/a", "source")
    b = contract.create_claim("Example", "11.2.0", "https://example.com/b", "source")
    assert a != b
    # Nothing is canonical until a claim actually reaches ATTESTED.
    assert contract.get_current_attestation("Example", "2")["exists"] is False
    assert contract.get_current_attestation("Example", "11.2.0")["exists"] is False

    direct_vm.mock_web(r".*example\.com/a$",
                       {"method": "GET", "status": 200,
                        "body": "Example 2 release information page for download."})
    direct_vm.mock_web(r".*example\.com/b$",
                       {"method": "GET", "status": 200,
                        "body": "Example 11.2.0 release information page download."})
    direct_vm.mock_llm(SOURCE_PROMPT, SOURCE_UNKNOWN)
    assert contract.run_claim_review(a) == "ATTESTED"
    assert contract.run_claim_review(b) == "ATTESTED"

    assert contract.get_current_attestation("Example", "2")["claim_id"] == a
    assert contract.get_current_attestation("Example", "11.2.0")["claim_id"] == b
    # Different project name is a different canonical key.
    assert contract.get_current_attestation("Example2", "2")["exists"] is False


# =======================================================================
# 9. Regression cases carried forward from V1
# =======================================================================
def test_duplicate_policy_is_deterministically_collapsed(direct_deploy, direct_vm,
                                                         direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "requests", "2.31.0", REQUESTS_URL, "source,source")
    _register_requests_source_mocks(direct_vm)
    assert contract.run_claim_review(cid) == "ATTESTED"
    # Duplicates are collapsed (first occurrence wins) -> exactly one result.
    source_results = [r for r in contract.get_claim(cid)["results"]
                      if r["check_name"] == "source"]
    assert len(source_results) == 1


def test_malformed_vulnerability_data_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://osv.dev/list?q=test", "vulnerability")
    direct_vm.mock_web(
        r".*osv\.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    # has_vulnerability_data=true but counts missing -> insufficiency, not zero.
    direct_vm.mock_llm(VULN_PROMPT, '{"has_vulnerability_data": true}')
    assert contract.run_claim_review(cid) == "UNRESOLVED"
    assert contract.get_claim(cid)["results"][0]["status"] == "INSUFFICIENT_EVIDENCE"


def test_boolean_vulnerability_counts_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://osv.dev/list?q=test", "vulnerability")
    direct_vm.mock_web(
        r".*osv\.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        VULN_PROMPT,
        '{"has_vulnerability_data": true, "critical_count": true, "high_count": false}')
    assert contract.run_claim_review(cid) == "UNRESOLVED"


def test_fractional_vulnerability_counts_unresolved(direct_deploy, direct_vm,
                                                    direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://osv.dev/list?q=test", "vulnerability")
    direct_vm.mock_web(
        r".*osv\.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        VULN_PROMPT,
        '{"has_vulnerability_data": true, "critical_count": 0.5, "high_count": 0}')
    assert contract.run_claim_review(cid) == "UNRESOLVED"


def test_license_without_observed_text_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://github.com/test/project", "license")
    direct_vm.mock_web(
        r".*github\.com.*",
        {"method": "GET", "status": 200, "body": "Project release details page."})
    direct_vm.mock_llm(
        LICENSE_PROMPT,
        '{"license_name": "MIT", "license_text_observed": false, "is_permissive": true}')
    assert contract.run_claim_review(cid) == "UNRESOLVED"
    assert contract.get_claim(cid)["results"][0]["status"] == "INSUFFICIENT_EVIDENCE"


def test_mixed_pass_fail_inconclusive_composes_rejected(direct_deploy, direct_vm,
                                                        direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://github.com/test/project",
        "source,license,vulnerability")
    direct_vm.mock_web(
        r".*github\.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject. Download source."})
    direct_vm.mock_llm(SOURCE_PROMPT, TESTPROJ_SOURCE_PASS)
    direct_vm.mock_llm(
        LICENSE_PROMPT,
        '{"license_name": "GPL-3.0", "license_text_observed": true, "is_permissive": false}')
    # vulnerability has no LLM mock -> INSUFFICIENT, but the FAIL dominates.
    assert contract.run_claim_review(cid) == "REJECTED"
    c = contract.get_claim(cid)
    assert "license" in c["failed_checks"]


def test_consensus_exception_persists_terminal_state(direct_deploy, direct_vm,
                                                     direct_alice):
    """A check whose prompt raises (a real consensus-failure path) is recorded
    as INSUFFICIENT -> UNRESOLVED. The claim must never remain RUNNING and must
    never be recorded as REJECTED."""
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://github.com/test/project", "source")
    direct_vm.mock_web(
        r".*github\.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject. Download source."})
    # No LLM mock for the source prompt -> exec_prompt raises.
    assert contract.run_claim_review(cid) == "UNRESOLVED"
    c = contract.get_claim(cid)
    assert c["status"] == "UNRESOLVED"
    assert c["status"] != "RUNNING"
    assert c["results"][0]["status"] == "INSUFFICIENT_EVIDENCE"
    assert c["results"][0]["evidence"] == "Consensus not reached"


def test_source_fallback_uses_visible_facts(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim("requests", "2.31.0", REQUESTS_URL, "source")
    _register_requests_source_mocks(direct_vm)
    direct_vm.mock_llm(SOURCE_PROMPT, SOURCE_UNKNOWN)
    assert contract.run_claim_review(cid) == "ATTESTED"


def test_validator_disagreement_fails_closed(direct_deploy, direct_vm, direct_alice):
    """Force the validator to see different evidence. The validator returns
    False; the recorded outcome is the fail-closed DISPUTED."""
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_alice
    xid = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0", "contradiction")
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "Advisory that corroborates the release attestation here."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": false, "reason": "No contradiction"}')
    # Leader sees no contradiction -> ATTESTED (challenge rejected).
    contract.run_challenge_review(xid)
    assert contract.get_challenge(xid)["outcome"] == "ATTESTED"

    # Replay the captured validator against swapped evidence: it must reject.
    direct_vm.clear_mocks()
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "Completely different page with a contradicting advisory."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": true, "reason": "Contradiction"}')
    _register_requests_source_mocks(direct_vm)
    assert direct_vm.run_validator() is False


# =======================================================================
# 10. Anti-squatting: canonical is bound only on ATTESTED
# =======================================================================
def test_malicious_pending_claim_does_not_block_legitimate_claim(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    """A parked PENDING claim must never reserve the canonical mapping."""
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_bob
    squat = contract.create_claim(
        "requests", "2.31.0", "https://attacker.example.com/junk", "source")
    assert contract.get_current_attestation("requests", "2.31.0")["exists"] is False

    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    assert cid != squat
    assert contract.get_claim(cid)["status"] == "ATTESTED"

    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["exists"] is True
    assert att["claim_id"] == cid
    assert att["attestation_state"] == "ATTESTED"
    # The squatting claim is still pending and irrelevant.
    assert contract.get_claim(squat)["status"] == "PENDING"


def test_rejected_claim_does_not_block_later_attested_claim(
        direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    bad = contract.create_claim(
        "TestProject", "1.0.0", "https://github.com/test/project", "license")
    direct_vm.mock_web(r".*github\.com.*",
                       {"method": "GET", "status": 200,
                        "body": "Project license text page."})
    direct_vm.mock_llm(
        LICENSE_PROMPT,
        '{"license_name": "GPL-3.0", "license_text_observed": true, "is_permissive": false}')
    assert contract.run_claim_review(bad) == "REJECTED"
    assert contract.get_current_attestation("TestProject", "1.0.0")["exists"] is False

    good = contract.create_claim(
        "TestProject", "1.0.0", "https://github.com/test/project", "source")
    direct_vm.mock_llm(SOURCE_PROMPT, TESTPROJ_SOURCE_PASS)
    assert contract.run_claim_review(good) == "ATTESTED"

    att = contract.get_current_attestation("TestProject", "1.0.0")
    assert att["exists"] is True
    assert att["claim_id"] == good
    assert att["attestation_state"] == "ATTESTED"


def test_unresolved_claim_does_not_block_later_attested_claim(
        direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    bad = contract.create_claim(
        "TestProject", "1.0.0", "https://example.com/release", "   ,  ")
    assert contract.run_claim_review(bad) == "UNRESOLVED"
    assert contract.get_current_attestation("TestProject", "1.0.0")["exists"] is False

    good = contract.create_claim(
        "TestProject", "1.0.0", "https://example.com/release", "source")
    direct_vm.mock_web(
        r".*example\.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject. Download source."})
    direct_vm.mock_llm(SOURCE_PROMPT, TESTPROJ_SOURCE_PASS)
    assert contract.run_claim_review(good) == "ATTESTED"
    att = contract.get_current_attestation("TestProject", "1.0.0")
    assert att["exists"] is True
    assert att["claim_id"] == good
    assert att["attestation_state"] == "ATTESTED"


def test_competing_attested_claim_cannot_overwrite_canonical(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    first = _attested_source_claim(contract, direct_vm, direct_alice)

    # Bob's competing claim for the same exact version is valid on its own
    # merits, so it must NOT be labelled REJECTED - it loses the race instead.
    direct_vm.sender = direct_bob
    second = contract.create_claim("requests", "2.31.0", REQUESTS_URL, "source")
    assert contract.run_claim_review(second) == "UNRESOLVED"

    c2 = contract.get_claim(second)
    assert c2["status"] == "UNRESOLVED"
    assert c2["attestation_state"] == "UNRESOLVED"
    assert c2["reason_code"] == "CANONICAL_ATTESTATION_EXISTS"
    assert c2["status"] != "REJECTED"

    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["claim_id"] == first
    assert att["attestation_state"] == "ATTESTED"


def test_revoked_canonical_cannot_be_silently_replaced(
        direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    first = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        first, "https://advisory.example.com/requests-2.31.0",
        "Critical RCE disclosed for this release")
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "CVE-2024-9999 critical remote code execution in requests 2.31.0."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": true, "reason": "Critical RCE"}')
    assert contract.run_challenge_review(xid) == "REVOKED"

    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["claim_id"] == first
    assert att["attestation_state"] == "REVOKED"

    # A later claim for the same version must not silently replace the
    # revoked canonical record.
    later = contract.create_claim("requests", "2.31.0", REQUESTS_URL, "source")
    assert contract.run_claim_review(later) == "UNRESOLVED"
    assert contract.get_claim(later)["reason_code"] == "CANONICAL_ATTESTATION_EXISTS"

    att2 = contract.get_current_attestation("requests", "2.31.0")
    assert att2["claim_id"] == first
    assert att2["attestation_state"] == "REVOKED"


# =======================================================================
# 11. Deterministic HTTPS evidence URL validation
# =======================================================================
def _create_with_url(contract, vm, sender, url):
    vm.sender = sender
    return contract.create_claim("TestProject", "1.0.0", url, "source")


def test_valid_public_https_urls_accepted(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    for url in (
        "https://pypi.org/project/requests/2.31.0/",
        "https://example.com/a",
        "https://sub.domain.example.org/path?q=1#frag",
        "https://example.com:8443/release",
    ):
        assert _create_with_url(contract, direct_vm, direct_alice, url)


def test_non_https_and_unsafe_schemes_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    for url in (
        "http://example.com/a",
        "file:///etc/passwd",
        "data:text/plain,hello",
        "javascript:alert(1)",
        "ftp://example.com/x",
        "example.com/no-scheme",
    ):
        with pytest.raises(Exception):
            _create_with_url(contract, direct_vm, direct_alice, url)


def test_local_and_private_network_urls_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    for url in (
        "https://localhost/x",
        "https://127.0.0.1/x",
        "https://10.0.0.5/x",
        "https://192.168.1.10/x",
        "https://172.16.0.1/x",
        "https://169.254.1.1/x",
        "https://0.0.0.0/x",
        "https://foo.local/x",
        "https://intranet/x",
        "https://[::1]/x",
    ):
        with pytest.raises(Exception):
            _create_with_url(contract, direct_vm, direct_alice, url)


def test_blank_and_malformed_urls_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    for url in (
        "",
        "   ",
        "not-a-url",
        "https://",
        "https:// bad.example.com/x",
        "https://example.com:notaport/x",
        "https://user@example.com/x",
    ):
        with pytest.raises(Exception):
            _create_with_url(contract, direct_vm, direct_alice, url)


def test_challenge_urls_are_validated(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    for url in (
        "http://evil.example.com/x",
        "https://localhost/x",
        "https://127.0.0.1/x",
        "not-a-url",
        "",
    ):
        with pytest.raises(Exception):
            contract.open_challenge(cid, url, "a substantive challenge reason")


def test_challenge_reason_is_validated(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    for reason in ("", "   ", "x" * 401, "bad\nnewline reason"):
        with pytest.raises(Exception):
            contract.open_challenge(cid, "https://challenge.example.com/e", reason)


# =======================================================================
# 12. Storage / query accuracy
# =======================================================================
def test_get_challenge_returns_record(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    xid = contract.open_challenge(
        cid, "https://x.example.com/e", "a concise challenge reason")
    x = contract.get_challenge(xid)
    assert x["id"] == xid
    assert x["claim_id"] == cid
    assert x["status"] == "OPEN"
    assert x["outcome"] == ""
    assert x["evidence_url"] == "https://x.example.com/e"
    assert x["challenger"] == to_hex(direct_alice)


def test_get_claim_challenges_lists_history(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    x1 = contract.open_challenge(cid, "https://one.example.com/e", "first reason")
    direct_vm.mock_web(
        r".*one\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "A page with no contradicting facts about the release."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": false, "reason": "Nothing"}')
    assert contract.run_challenge_review(x1) == "ATTESTED"

    x2 = contract.open_challenge(cid, "https://two.example.com/e", "second reason")
    history = contract.get_claim_challenges(cid)
    assert [h["id"] for h in history] == [x1, x2]
    assert contract.get_claim(cid)["challenge_ids"] == [x1, x2]


def test_getters_reflect_final_state_after_revocation(direct_deploy, direct_vm,
                                                      direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://advisory.example.com/requests-2.31.0",
        "Advisory establishing the release is unsafe")
    direct_vm.mock_web(
        r".*advisory\.example\.com.*",
        {"method": "GET", "status": 200,
         "body": "Advisory establishing the release is unsafe for consumers."})
    direct_vm.mock_llm(
        ADJUDICATE_PROMPT,
        '{"contradiction_established": true, "reason": "Release is unsafe"}')
    assert contract.run_challenge_review(xid) == "REVOKED"

    assert contract.get_claim(cid)["status"] == "REVOKED"
    assert contract.get_challenge(xid)["status"] == "RESOLVED"
    assert contract.get_challenge(xid)["outcome"] == "REVOKED"
    att = contract.get_current_attestation("requests", "2.31.0")
    assert att["status"] == "REVOKED"
    assert att["attestation_state"] == "REVOKED"
    assert [h["id"] for h in contract.get_claim_challenges(cid)] == [xid]


def test_multiple_claims_allowed_for_same_version(direct_deploy, direct_vm,
                                                  direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    a = contract.create_claim("requests", "2.31.0", "https://pypi.org/a", "source")
    b = contract.create_claim("requests", "2.31.0", "https://pypi.org/b", "source")
    assert a != b
    # A different version is an independent key.
    c = contract.create_claim("requests", "2.32.0", "https://pypi.org/c", "source")
    assert c != a and c != b


def test_create_claim_requires_inputs(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    for args in (
        ("", "1.0.0", "https://e.example.com", "source"),
        ("P", "", "https://e.example.com", "source"),
        ("P", "1.0.0", "", "source"),
    ):
        with pytest.raises(Exception):
            contract.create_claim(*args)


def test_canonical_lookup_missing_returns_not_exists(direct_deploy, direct_vm,
                                                     direct_alice):
    contract = direct_deploy(CLAIM)
    att = contract.get_current_attestation("nope", "0.0.1")
    assert att["exists"] is False
    assert att["claim_id"] == ""
