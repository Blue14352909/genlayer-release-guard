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
    """MIT license returns PASS with default allowlist."""
    contract = direct_deploy("contracts/license_check.py")
    direct_vm.mock_web(
        "https://github.com/test/project/blob/main/LICENSE",
        "MIT License\n\nCopyright (c) 2024 Test Project\n\n"
        "Permission is hereby granted, free of charge, to any person "
        "obtaining a copy of this software...",
    )
    direct_vm.mock_llm(
        '{"status": "PASS", "reason": "MIT license detected", '
        '"observed_license": "MIT"}'
    )
    result = contract.verify(
        "https://github.com/test/project/blob/main/LICENSE",
        "TestProject", "")
    assert result["status"] == "PASS"
    assert result["evidence"] == "MIT"


def test_license_check_fail_gpl(direct_deploy, direct_vm):
    """GPL license returns FAIL with default allowlist."""
    contract = direct_deploy("contracts/license_check.py")
    direct_vm.mock_web(
        "https://github.com/test/project/blob/main/LICENSE",
        "GNU GENERAL PUBLIC LICENSE Version 3",
    )
    direct_vm.mock_llm(
        '{"status": "FAIL", "reason": "GPL v3 not in allowlist", '
        '"observed_license": "GPL-3.0"}'
    )
    result = contract.verify(
        "https://github.com/test/project/blob/main/LICENSE",
        "TestProject", "")
    assert result["status"] == "FAIL"


def test_license_check_custom_allowlist(direct_deploy, direct_vm):
    """Custom allowlist is respected."""
    contract = direct_deploy("contracts/license_check.py")
    direct_vm.mock_web(
        "https://github.com/test/project/blob/main/LICENSE",
        "MIT License\n\nPermission is hereby granted...",
    )
    direct_vm.mock_llm(
        '{"status": "PASS", "reason": "MIT in custom allowlist", '
        '"observed_license": "MIT"}'
    )
    result = contract.verify(
        "https://github.com/test/project/blob/main/LICENSE",
        "TestProject", "MIT,Apache-2.0")
    assert result["status"] == "PASS"


def test_license_check_fetch_failure(direct_deploy, direct_vm):
    """Unreachable URL returns FETCH_FAILED."""
    contract = direct_deploy("contracts/license_check.py")
    direct_vm.mock_web_fail("https://down.example.com/license")
    result = contract.verify(
        "https://down.example.com/license",
        "TestProject", "")
    assert result["status"] == "FETCH_FAILED"
