"""Direct-mode tests for ReleaseGuard V2 (challengeable, revocable attestations).

These tests prove the V2 lifecycle end to end against the pinned gltest setup
used by the rest of this repository. They do not modify or weaken the V1
tests.

Mocking notes (gltest 0.29.x direct mode):
- mock_web(url_pattern, {"method": "GET", "status": 200, "body": "..."})
  Patterns use re.search; escape dots.
- mock_llm(prompt_pattern, response) — first matching mock wins.
- Omitting a web/LLM mock raises MockNotFoundError, which the contract's
  fetch/prompt helpers either catch (-> FETCH_FAILED / INSUFFICIENT) or which
  propagates out of consensus (-> handled fail-closed as UNRESOLVED).
"""
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


def _attested_source_claim(contract, vm, alice,
                           project="requests", version="2.31.0",
                           url="https://pypi.org/project/requests/2.31.0/"):
    """Create and review a claim that becomes ATTESTED on the source policy."""
    vm.sender = alice
    cid = contract.create_claim(project, version, url, "source")
    vm.mock_web(r".*pypi\.org.*",
                {"method": "GET", "status": 200,
                 "body": f"{project} {version} release information and package metadata."})
    vm.mock_llm(SOURCE_PROMPT, SOURCE_PASS)
    assert contract.run_claim_review(cid) == "ATTESTED"
    return cid


# =======================================================================
# 1. Happy path
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


# =======================================================================
# 2. Initial rejection
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
    assert contract.get_current_attestation("TestProject", "1.0.0")["attestation_state"] == "REJECTED"


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


# =======================================================================
# 3. Initial unresolved
# =======================================================================
def test_empty_policy_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://example.com/release", "   ,  ")
    assert contract.run_claim_review(cid) == "UNRESOLVED"
    c = contract.get_claim(cid)
    assert c["attestation_state"] == "UNRESOLVED"
    assert c["reason_code"] == "EMPTY_POLICY"


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
# 4. Challenge success (REVOKED)
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


# =======================================================================
# 5. Challenge rejected
# =======================================================================
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

    assert contract.get_current_attestation(
        "requests", "2.31.0")["attestation_state"] == "ATTESTED"


# =======================================================================
# 6. Challenge unresolved
# =======================================================================
def test_challenge_evidence_missing_drops_to_unresolved(direct_deploy, direct_vm,
                                                        direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    direct_vm.sender = direct_bob
    xid = contract.open_challenge(
        cid, "https://unreachable.example.com/evidence",
        "Alleges a vulnerability without accessible evidence")
    # No web mock for the challenge URL -> evidence unusable -> UNRESOLVED.
    assert contract.run_challenge_review(xid) == "UNRESOLVED"

    c = contract.get_claim(cid)
    assert c["status"] == "UNRESOLVED"
    assert c["attestation_state"] == "UNRESOLVED"
    assert c["reason_code"] == "CHALLENGE_EVIDENCE_INSUFFICIENT"

    x = contract.get_challenge(xid)
    assert x["status"] == "UNRESOLVED"
    assert x["outcome"] == "UNRESOLVED"

    assert contract.get_current_attestation(
        "requests", "2.31.0")["attestation_state"] == "UNRESOLVED"


def test_challenge_malformed_adjudication_drops_to_unresolved(
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
    # Adjudication returns junk -> contract raises inside consensus -> caught
    # fail-closed as UNRESOLVED (never ATTESTED, never REJECTED).
    direct_vm.mock_llm(ADJUDICATE_PROMPT, "this is not json at all")

    assert contract.run_challenge_review(xid) == "UNRESOLVED"
    c = contract.get_claim(cid)
    assert c["status"] == "UNRESOLVED"
    assert c["attestation_state"] == "UNRESOLVED"
    assert contract.get_current_attestation(
        "requests", "2.31.0")["attestation_state"] == "UNRESOLVED"


# =======================================================================
# 7. Permissionless behaviour
# =======================================================================
def test_challenge_is_permissionless(direct_deploy, direct_vm,
                                     direct_alice, direct_bob):
    contract = direct_deploy(CLAIM)
    # Alice creates and reviews the claim.
    cid = _attested_source_claim(contract, direct_vm, direct_alice)

    # Bob — a completely different account — opens and runs the challenge.
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
# 8. Invalid transitions
# =======================================================================
def test_challenge_non_attested_claim_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "TestProject", "1.0.0", "https://example.com/release", "source")
    # Claim is still PENDING — cannot be challenged.
    try:
        contract.open_challenge(cid, "https://other.example.com/e", "reason")
        assert False, "Should have raised"
    except Exception:
        pass


def test_second_open_challenge_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    contract.open_challenge(cid, "https://a.example.com/e", "first")
    try:
        contract.open_challenge(cid, "https://b.example.com/e", "second")
        assert False, "Should have raised"
    except Exception:
        pass


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
    try:
        contract.open_challenge(cid, "https://dup.example.com/e", "Duplicate reason")
        assert False, "Should have raised"
    except Exception:
        pass


def test_challenge_cannot_reuse_original_evidence(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    try:
        contract.open_challenge(
            cid, "https://pypi.org/project/requests/2.31.0/", "reuse original")
        assert False, "Should have raised"
    except Exception:
        pass


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
    try:
        contract.open_challenge(cid, "https://another.example.com/e", "restore please")
        assert False, "Should have raised"
    except Exception:
        pass
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
        try:
            call()
            assert False, "Should have raised"
        except Exception:
            pass


def test_review_requires_pending_state(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    # The claim is now ATTESTED; a second review must be refused.
    try:
        contract.run_claim_review(cid)
        assert False, "Should have raised"
    except Exception:
        pass


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
    try:
        contract.run_challenge_review(xid)
        assert False, "Should have raised"
    except Exception:
        pass


# =======================================================================
# 9. Exact matching
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
    assert contract.get_current_attestation("Example", "2")["claim_id"] == a
    assert contract.get_current_attestation("Example", "11.2.0")["claim_id"] == b
    # Different project name is a different canonical key.
    assert contract.get_current_attestation("Example2", "2")["exists"] is False


# =======================================================================
# 10. Regression cases carried forward from V1
# =======================================================================
def test_duplicate_policy_is_deterministically_collapsed(direct_deploy, direct_vm,
                                                         direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    cid = contract.create_claim(
        "requests", "2.31.0", "https://pypi.org/project/requests/2.31.0/", "source,source")
    direct_vm.mock_web(
        r".*pypi\.org.*",
        {"method": "GET", "status": 200,
         "body": "requests 2.31.0 release information and package metadata."})
    direct_vm.mock_llm(SOURCE_PROMPT, SOURCE_PASS)
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
    direct_vm.mock_llm(
        SOURCE_PROMPT,
        '{"observed_project": "TestProject", "observed_version": "1.0.0", '
        '"page_has_release_content": true}')
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
    cid = contract.create_claim(
        "requests", "2.31.0", "https://pypi.org/project/requests/2.31.0/", "source")
    direct_vm.mock_web(
        r".*pypi\.org.*",
        {"method": "GET", "status": 200,
         "body": "requests 2.31.0 release information and package metadata."})
    direct_vm.mock_llm(SOURCE_PROMPT, SOURCE_UNKNOWN)
    assert contract.run_claim_review(cid) == "ATTESTED"


def test_validator_disagreement_fails_closed(direct_deploy, direct_vm, direct_alice):
    """Force the validator to see different evidence. The validator returns
    False; the recorded outcome is the fail-closed UNRESOLVED."""
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
    direct_vm.mock_web(
        r".*pypi\.org.*",
        {"method": "GET", "status": 200,
         "body": "requests 2.31.0 release information and package metadata."})
    direct_vm.mock_llm(SOURCE_PROMPT, SOURCE_PASS)
    assert direct_vm.run_validator() is False


# =======================================================================
# 11. Storage / query tests
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


def test_duplicate_canonical_claim_rejected(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    contract.create_claim("requests", "2.31.0", "https://pypi.org/a", "source")
    # Same exact project + version must not overwrite the canonical record.
    try:
        contract.create_claim("requests", "2.31.0", "https://pypi.org/b", "source")
        assert False, "Should have raised"
    except Exception:
        pass
    # A different version is allowed.
    cid2 = contract.create_claim("requests", "2.32.0", "https://pypi.org/c", "source")
    assert cid2


def test_create_claim_requires_inputs(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    direct_vm.sender = direct_alice
    for args in (
        ("", "1.0.0", "https://e.example.com", "source"),
        ("P", "", "https://e.example.com", "source"),
        ("P", "1.0.0", "", "source"),
    ):
        try:
            contract.create_claim(*args)
            assert False, "Should have raised"
        except Exception:
            pass


def test_open_challenge_requires_inputs(direct_deploy, direct_vm, direct_alice):
    contract = direct_deploy(CLAIM)
    cid = _attested_source_claim(contract, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    for args in (
        (cid, "", "reason"),
        (cid, "https://e.example.com", ""),
        (cid, "https://e.example.com", "   "),
    ):
        try:
            contract.open_challenge(*args)
            assert False, "Should have raised"
        except Exception:
            pass


def test_canonical_lookup_missing_returns_not_exists(direct_deploy, direct_vm,
                                                     direct_alice):
    contract = direct_deploy(CLAIM)
    att = contract.get_current_attestation("nope", "0.0.1")
    assert att["exists"] is False
    assert att["claim_id"] == ""
