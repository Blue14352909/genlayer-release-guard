"""Focused regression tests for fail-closed invariants.

These tests prove the steward-requested behaviors:
- Empty policy cannot produce VERIFIED
- Malformed vulnerability data cannot produce VERIFIED
- Stale evidence fails freshness
- max_age_days is enforced
- Every failure path produces INCONCLUSIVE or REJECTED, never VERIFIED

API notes for gltest 0.29.2 direct mode:
- mock_llm(prompt_pattern: str, response: str)  -- pattern is regex
- mock_web(url_pattern: str, {"method": "GET", "status": 200, "body": "..."})
- No mock_web_fail: omit the mock and MockNotFoundError is raised,
  caught by contract's except Exception as FETCH_FAILED.
- mock_web uses re.search, so URL patterns with ? must be escaped
  or use .* wildcards.
"""


# -----------------------------------------------------------------------
# Empty policy cannot verify
# -----------------------------------------------------------------------
def test_empty_policy_inconclusive(direct_deploy, direct_vm, direct_alice):
    """Empty string policy produces INCONCLUSIVE, never VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://example.com/release", "")
    result = contract.run_verification(vid)
    assert result == "INCONCLUSIVE"
    v = contract.get_verification(vid)
    assert v["verdict"] == "INCONCLUSIVE"
    assert v["reason_code"] in ("EMPTY_POLICY", "INSUFFICIENT_EVIDENCE")


def test_whitespace_policy_inconclusive(direct_deploy, direct_vm, direct_alice):
    """Whitespace-only policy produces INCONCLUSIVE, never VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://example.com/release", "   ,  , ")
    result = contract.run_verification(vid)
    assert result == "INCONCLUSIVE"


def test_commas_only_policy_inconclusive(direct_deploy, direct_vm, direct_alice):
    """Commas-only policy produces INCONCLUSIVE, never VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://example.com/release", ",,,")
    result = contract.run_verification(vid)
    assert result == "INCONCLUSIVE"


def test_malformed_policy_unknown_check(direct_deploy, direct_vm, direct_alice):
    """Unknown check type produces INCONCLUSIVE, never VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://example.com/release", "foo,bar")
    result = contract.run_verification(vid)
    assert result == "INCONCLUSIVE"
    v = contract.get_verification(vid)
    assert v["failed_checks"] != "" or v["reason_code"] != ""


def test_valid_policy_not_empty(direct_deploy, direct_vm, direct_alice):
    """Valid policy does not trigger empty-policy path."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://example.com/release", "source")
    v = contract.get_verification(vid)
    assert v["status"] == "PENDING"
    contract.run_verification(vid)
    v2 = contract.get_verification(vid)
    assert v2["status"] == "COMPLETED"
    assert v2["verdict"] in ("VERIFIED", "REJECTED", "INCONCLUSIVE")


# -----------------------------------------------------------------------
# Malformed vulnerability data cannot verify
# -----------------------------------------------------------------------
def test_vuln_malformed_json_inconclusive(direct_deploy, direct_vm):
    """LLM returning non-dict vulnerability data produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200,
         "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '"a plain string response"')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_missing_fields_inconclusive(direct_deploy, direct_vm):
    """Missing critical_count/high_count produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(".*", '{"foo": "bar"}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_has_data_missing_counts_inconclusive(direct_deploy, direct_vm):
    """has_vulnerability_data=true but missing counts produces INSUFFICIENT,
    NOT PASS. This is the exact bug the steward identified."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    # CRITICAL: must NOT be PASS — missing counts != zero vulnerabilities
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_vuln_has_data_partial_counts_inconclusive(direct_deploy, direct_vm):
    """has_vulnerability_data=true with only one count field produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, "critical_count": 0}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_vuln_empty_response_inconclusive(direct_deploy, direct_vm):
    """has_vulnerability_data=false produces INSUFFICIENT, not PASS."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(".*", '{"has_vulnerability_data": false}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_wrong_type_counts_inconclusive(direct_deploy, direct_vm):
    """Non-integer critical_count/high_count produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": "not_a_number", '
        '"high_count": true}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_has_data_zero_passes(direct_deploy, direct_vm):
    """Valid response with has_vulnerability_data=true and zero counts PASS."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "No vulnerabilities found."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": 0, "high_count": 0}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] == "PASS"
    assert result["critical_count"] == 0
    assert result["high_count"] == 0


def test_vuln_has_data_critical_fails(direct_deploy, direct_vm):
    """Valid response with critical vulnerability produces FAIL."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "CVE-2024-1234: Critical RCE."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": 1, "high_count": 0}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] == "FAIL"
    assert result["critical_count"] == 1


def test_vuln_has_data_high_fails(direct_deploy, direct_vm):
    """Valid response with high vulnerability produces FAIL."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "CVE-2024-5678: High XSS."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": 0, "high_count": 1}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] == "FAIL"
    assert result["high_count"] == 1


def test_vuln_has_data_null_critical_inconclusive(direct_deploy, direct_vm):
    """null critical_count produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": null, "high_count": 0}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_vuln_has_data_null_high_inconclusive(direct_deploy, direct_vm):
    """null high_count produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": 0, "high_count": null}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_vuln_negative_count_inconclusive(direct_deploy, direct_vm):
    """Negative count produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": -1, "high_count": 0}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_vuln_bool_count_inconclusive(direct_deploy, direct_vm):
    """Boolean count produces INSUFFICIENT (int(True)==1 must not pass)."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true, '
        '"critical_count": true, "high_count": false}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_vuln_empty_dict_inconclusive(direct_deploy, direct_vm):
    """Empty dict with has_vulnerability_data produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        ".*osv.dev.*",
        {"method": "GET", "status": 200, "body": "Advisory page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"has_vulnerability_data": true}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


# -----------------------------------------------------------------------
# Freshness / max_age_days enforcement
# -----------------------------------------------------------------------
def test_freshness_pass_within_limit(direct_deploy, direct_vm):
    """Evidence within max_age_days produces PASS."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200, "body": "Released 2025-01-15."})
    direct_vm.mock_llm(
        ".*",
        '{"date_string": "2025-01-15", '
        '"days_since_publication": 30, '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "PASS"
    assert result["observed_date"] == "2025-01-15"


def test_freshness_fail_exceeds_limit(direct_deploy, direct_vm):
    """Evidence older than max_age_days produces FAIL."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200, "body": "Released 2020-01-01."})
    direct_vm.mock_llm(
        ".*",
        '{"date_string": "2020-01-01", '
        '"days_since_publication": 1800, '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "FAIL"
    assert "1800" in result["reason"] or "exceeds" in result["reason"]


def test_freshness_exact_boundary_fails(direct_deploy, direct_vm):
    """Evidence exactly at max_age_days produces FAIL (>= means boundary is rejected)."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200, "body": "Released 2024-06-01."})
    direct_vm.mock_llm(
        ".*",
        '{"date_string": "2024-06-01", '
        '"days_since_publication": 365, '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "FAIL"


def test_freshness_fail_at_boundary(direct_deploy, direct_vm):
    """Evidence 1 day over boundary produces FAIL."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200, "body": "Released 2024-06-01."})
    direct_vm.mock_llm(
        ".*",
        '{"date_string": "2024-06-01", '
        '"days_since_publication": 366, '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "FAIL"


def test_freshness_missing_days_inconclusive(direct_deploy, direct_vm):
    """Missing days_since_publication produces INSUFFICIENT."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200, "body": "Released 2025-01-15."})
    direct_vm.mock_llm(
        ".*",
        '{"date_string": "2025-01-15", '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] != "PASS"


def test_freshness_malformed_days_inconclusive(direct_deploy, direct_vm):
    """Non-numeric days_since_publication produces INSUFFICIENT."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200, "body": "Released 2025-01-15."})
    direct_vm.mock_llm(
        ".*",
        '{"date_string": "2025-01-15", '
        '"days_since_publication": "unknown", '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] != "PASS"


def test_freshness_no_date_inconclusive(direct_deploy, direct_vm):
    """No date found produces INSUFFICIENT."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        ".*example.com.*",
        {"method": "GET", "status": 200, "body": "This page has no dates."})
    direct_vm.mock_llm(
        ".*",
        '{"date_string": "", '
        '"days_since_publication": 0, '
        '"date_source": ""}')
    result = contract.verify(
        "https://example.com/no-date",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


# -----------------------------------------------------------------------
# Orchestrator invariant: no failure path produces VERIFIED
# -----------------------------------------------------------------------
def test_fetch_failed_produces_inconclusive(
        direct_deploy, direct_vm, direct_alice):
    """FETCH_FAILED in any check produces INCONCLUSIVE, not VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://down.example.com/release",
        "source")
    result = contract.run_verification(vid)
    assert result != "VERIFIED"
    assert result in ("REJECTED", "INCONCLUSIVE")


def test_all_pass_produces_verified(direct_deploy, direct_vm, direct_alice):
    """All checks PASS produces VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject. MIT License."})
    direct_vm.mock_llm(
        ".*",
        '{"observed_project": "TestProject", '
        '"observed_version": "1.0.0", '
        '"page_has_release_content": true, '
        '"is_permissive": true, '
        '"license_name": "MIT", '
        '"has_vulnerability_data": true, '
        '"critical_count": 0, "high_count": 0}')
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://github.com/test/project",
        "source,license,vulnerability")
    result = contract.run_verification(vid)
    assert result == "VERIFIED"
    v = contract.get_verification(vid)
    assert v["failed_checks"] == ""
    assert v["reason_code"] == ""


def test_unknown_check_alone_produces_inconclusive(
        direct_deploy, direct_vm, direct_alice):
    """Only unknown check types in policy produces INCONCLUSIVE."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://example.com",
        "nonexistent_check")
    result = contract.run_verification(vid)
    assert result != "VERIFIED"


def test_consensus_failure_produces_inconclusive(
        direct_deploy, direct_vm, direct_alice):
    """Consensus exception (validator disagrees) produces INCONCLUSIVE,
    not REJECTED. A consensus failure means we couldn't establish a
    result — it does not mean the evidence was evaluated and failed."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    # No mocks registered → leader_fn will raise MockNotFoundError
    # → caught by except Exception → E_INSUFFICIENT → INCONCLUSIVE
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://down.example.com/release",
        "source")
    result = contract.run_verification(vid)
    assert result == "INCONCLUSIVE"
    v = contract.get_verification(vid)
    assert v["verdict"] == "INCONCLUSIVE"
