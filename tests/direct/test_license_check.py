"""Tests for LicenseCheck primitive contract."""


def test_license_check_deploy(direct_deploy):
    """Contract deploys successfully."""
    contract = direct_deploy("contracts/license_check.py")
    assert contract is not None


def test_license_check_empty_url(direct_deploy):
    """Empty URL returns INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/license_check.py")
    result = contract.verify("", "MyProject", "MIT")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_license_check_pass_mit(direct_deploy, direct_vm):
    """MIT license returns PASS."""
    contract = direct_deploy("contracts/license_check.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "MIT License - Copyright 2024"})
    direct_vm.mock_llm(
        ".*",
        '{"license_name": "MIT", "license_text_observed": true, '
        '"reason": "MIT license found"}')
    result = contract.verify(
        "https://github.com/test/project",
        "TestProject", "MIT")
    assert result["status"] == "PASS"
    assert result["observed_license"] == "MIT"


def test_license_check_fail_gpl(direct_deploy, direct_vm):
    """GPL license returns FAIL."""
    contract = direct_deploy("contracts/license_check.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "GNU General Public License v3.0"})
    direct_vm.mock_llm(
        ".*",
        '{"license_name": "GPL-3.0", "license_text_observed": true, '
        '"reason": "GPL license found"}')
    result = contract.verify(
        "https://github.com/test/project",
        "TestProject", "MIT")
    assert result["status"] == "FAIL"


def test_license_check_custom_allowlist(direct_deploy, direct_vm):
    """Custom allowlist accepts specified licenses."""
    contract = direct_deploy("contracts/license_check.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Apache License 2.0"})
    direct_vm.mock_llm(
        ".*",
        '{"license_name": "Apache-2.0", "license_text_observed": true, '
        '"reason": "Apache license found"}')
    result = contract.verify(
        "https://github.com/test/project",
        "TestProject", "MIT,Apache-2.0")
    assert result["status"] == "PASS"


def test_license_check_fetch_failure(direct_deploy, direct_vm):
    """Unreachable URL returns FETCH_FAILED."""
    contract = direct_deploy("contracts/license_check.py")
    result = contract.verify(
        "https://down.example.com/license",
        "TestProject", "MIT")
    assert result["status"] == "FETCH_FAILED"
