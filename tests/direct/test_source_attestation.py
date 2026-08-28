"""Tests for SourceAttestation primitive contract."""


def test_source_attestation_deploy(direct_deploy):
    """Contract deploys successfully."""
    contract = direct_deploy("contracts/source_attestation.py")
    assert contract is not None


def test_source_attestation_empty_url(direct_deploy):
    """Empty URL returns INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/source_attestation.py")
    result = contract.verify("", "MyProject", "1.0.0")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_source_attestation_empty_project(direct_deploy):
    """Empty project name returns INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/source_attestation.py")
    result = contract.verify("https://example.com", "", "1.0.0")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_source_attestation_pass(direct_deploy, direct_vm):
    """Valid source page returns PASS."""
    contract = direct_deploy("contracts/source_attestation.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject. "
         "Download source code and binaries."})
    direct_vm.mock_llm(
        ".*",
        '{"observed_project": "TestProject", '
        '"observed_version": "v1.0.0", '
        '"page_has_release_content": true, '
        '"reason": "Release page confirmed"}')
    result = contract.verify(
        "https://github.com/test/project/releases/tag/v1.0.0",
        "TestProject", "1.0.0")
    assert result["status"] == "PASS"


def test_source_attestation_fail(direct_deploy, direct_vm):
    """Non-matching page returns FAIL."""
    contract = direct_deploy("contracts/source_attestation.py")
    direct_vm.mock_web(
        ".*example.com.*",
        {"method": "GET", "status": 200,
         "body": "404 - Page Not Found"})
    direct_vm.mock_llm(
        ".*",
        '{"observed_project": "none", '
        '"observed_version": "", '
        '"page_has_release_content": false, '
        '"reason": "Page is a 404 error"}')
    result = contract.verify(
        "https://example.com/missing",
        "TestProject", "1.0.0")
    assert result["status"] == "FAIL"


def test_source_attestation_fetch_failure(direct_deploy, direct_vm):
    """Unreachable URL returns FETCH_FAILED."""
    contract = direct_deploy("contracts/source_attestation.py")
    result = contract.verify(
        "https://down.example.com",
        "TestProject", "1.0.0")
    assert result["status"] == "FETCH_FAILED"
