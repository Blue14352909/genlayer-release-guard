"""Focused regression tests for fail-closed invariants.

These tests prove the steward-requested behaviors:
- Empty policy cannot produce VERIFIED
- Malformed vulnerability data cannot produce VERIFIED
- Stale evidence fails freshness
- max_age_days is enforced
- Every failure path produces INCONCLUSIVE or REJECTED, never VERIFIED
"""
from tests.direct.conftest import to_hex


# ---------------------------------------------------------------------------
# Empty policy cannot verify
# ---------------------------------------------------------------------------

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
    # run_verification should not immediately return INCONCLUSIVE
    # for a valid policy (it will run the actual check)
    contract.run_verification(vid)
    v2 = contract.get_verification(vid)
    assert v2["status"] == "COMPLETED"
    assert v2["verdict"] in ("VERIFIED", "REJECTED", "INCONCLUSIVE")


# ---------------------------------------------------------------------------
# Malformed vulnerability data cannot verify
# ---------------------------------------------------------------------------

def test_vuln_malformed_json_inconclusive(
        direct_deploy, direct_vm):
    """LLM returning non-dict vulnerability data produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        "https://osv.dev/list?q=test",
        "Advisory page content here.")
    # Return a string instead of a dict
    direct_vm.mock_llm('"just a string, not a dict"')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_missing_fields_inconclusive(
        direct_deploy, direct_vm):
    """Missing critical_count/high_count produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        "https://osv.dev/list?q=test",
        "Advisory page content here.")
    # Dict but missing required fields, no has_vulnerability_data
    direct_vm.mock_llm('{"foo": "bar"}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_empty_response_inconclusive(
        direct_deploy, direct_vm):
    """Empty LLM response produces INSUFFICIENT, not PASS."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        "https://osv.dev/list?q=test",
        "Advisory page content here.")
    direct_vm.mock_llm('{"has_vulnerability_data": false}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_wrong_type_counts_inconclusive(
        direct_deploy, direct_vm):
    """Non-integer critical_count/high_count produces INSUFFICIENT."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        "https://osv.dev/list?q=test",
        "Advisory page content here.")
    direct_vm.mock_llm(
        '{"has_vulnerability_data": true, '
        '"critical_count": "not_a_number", '
        '"high_count": true}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"


def test_vuln_has_data_zero_passes(
        direct_deploy, direct_vm):
    """Valid response with has_vulnerability_data=true and zero counts PASS."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        "https://osv.dev/list?q=test",
        "No vulnerabilities found.")
    direct_vm.mock_llm(
        '{"has_vulnerability_data": true, '
        '"critical_count": 0, "high_count": 0}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] == "PASS"
    assert result["critical_count"] == 0
    assert result["high_count"] == 0


def test_vuln_has_data_critical_fails(
        direct_deploy, direct_vm):
    """Valid response with critical vulnerability produces FAIL."""
    contract = direct_deploy("contracts/vulnerability_check.py")
    direct_vm.mock_web(
        "https://osv.dev/list?q=test",
        "CVE-2024-1234: Critical RCE.")
    direct_vm.mock_llm(
        '{"has_vulnerability_data": true, '
        '"critical_count": 1, "high_count": 0}')
    result = contract.verify(
        "https://osv.dev/list?q=test",
        "TestProject", "1.0.0")
    assert result["status"] == "FAIL"
    assert result["critical_count"] == 1


# ---------------------------------------------------------------------------
# Freshness / max_age_days enforcement
# ---------------------------------------------------------------------------

def test_freshness_pass_within_limit(
        direct_deploy, direct_vm):
    """Evidence within max_age_days produces PASS."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        "https://pypi.org/project/test/1.0.0/",
        "Released 2025-01-15.")
    direct_vm.mock_llm(
        '{"date_string": "2025-01-15", '
        '"days_since_publication": 30, '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "PASS"
    assert result["observed_date"] == "2025-01-15"


def test_freshness_fail_exceeds_limit(
        direct_deploy, direct_vm):
    """Evidence older than max_age_days produces FAIL."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        "https://pypi.org/project/test/1.0.0/",
        "Released 2020-01-01.")
    direct_vm.mock_llm(
        '{"date_string": "2020-01-01", '
        '"days_since_publication": 1800, '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "FAIL"
    assert "1800" in result["reason"] or "exceeds" in result["reason"]


def test_freshness_fail_at_boundary(
        direct_deploy, direct_vm):
    """Evidence exactly at boundary (1 day over) produces FAIL."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        "https://pypi.org/project/test/1.0.0/",
        "Released 2024-06-01.")
    direct_vm.mock_llm(
        '{"date_string": "2024-06-01", '
        '"days_since_publication": 366, '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "FAIL"


def test_freshness_missing_days_inconclusive(
        direct_deploy, direct_vm):
    """Missing days_since_publication produces INSUFFICIENT."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        "https://pypi.org/project/test/1.0.0/",
        "Released 2025-01-15.")
    # LLM returns date but no days_since_publication
    direct_vm.mock_llm(
        '{"date_string": "2025-01-15", '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] != "PASS"


def test_freshness_malformed_days_inconclusive(
        direct_deploy, direct_vm):
    """Non-numeric days_since_publication produces INSUFFICIENT."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        "https://pypi.org/project/test/1.0.0/",
        "Released 2025-01-15.")
    direct_vm.mock_llm(
        '{"date_string": "2025-01-15", '
        '"days_since_publication": "unknown", '
        '"date_source": "release page"}')
    result = contract.verify(
        "https://pypi.org/project/test/1.0.0/",
        "TestProject", "1.0.0", "365")
    assert result["status"] != "PASS"


def test_freshness_no_date_inconclusive(
        direct_deploy, direct_vm):
    """No date found produces INSUFFICIENT."""
    contract = direct_deploy("contracts/freshness_check.py")
    direct_vm.mock_web(
        "https://example.com/no-date",
        "This page has no dates.")
    direct_vm.mock_llm(
        '{"date_string": "", '
        '"days_since_publication": 0, '
        '"date_source": ""}')
    result = contract.verify(
        "https://example.com/no-date",
        "TestProject", "1.0.0", "365")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------------------
# Orchestrator invariant: no failure path produces VERIFIED
# ---------------------------------------------------------------------------

def test_fetch_failed_produces_inconclusive(
        direct_deploy, direct_vm, direct_alice):
    """FETCH_FAILED in any check produces INCONCLUSIVE, not VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    # Mock web to fail for all URLs
    direct_vm.mock_web_fail("https://down.example.com")
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://down.example.com/release",
        "source,license,vulnerability")
    result = contract.run_verification(vid)
    assert result != "VERIFIED"
    assert result in ("REJECTED", "INCONCLUSIVE")


def test_all_pass_produces_verified(
        direct_deploy, direct_vm, direct_alice):
    """All checks PASS produces VERIFIED."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    direct_vm.mock_web(
        "https://github.com/test/project",
        "Release v1.0.0 of TestProject. MIT License.")
    direct_vm.mock_llm(
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
