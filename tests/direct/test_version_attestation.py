"""Tests for VersionAttestation primitive contract."""


def test_version_attestation_deploy(direct_deploy):
    """Contract deploys successfully."""
    contract = direct_deploy("contracts/version_attestation.py")
    assert contract is not None


def test_version_attestation_empty_url(direct_deploy):
    """Empty URL returns INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/version_attestation.py")
    result = contract.verify("", "MyProject", "1.0.0")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_version_attestation_empty_version(direct_deploy):
    """Empty version returns INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/version_attestation.py")
    result = contract.verify("https://example.com", "MyProject", "")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_version_attestation_pass(direct_deploy, direct_vm):
    """Valid version found returns PASS."""
    contract = direct_deploy("contracts/version_attestation.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject. Download v1.0.0 binaries."})
    direct_vm.mock_llm(
        ".*",
        '{"version_found": true, '
        '"observed_versions": "v1.0.0, v0.9.0", '
        '"reason": "Version 1.0.0 found on page"}')
    result = contract.verify(
        "https://github.com/test/project/releases",
        "TestProject", "1.0.0")
    assert result["status"] == "PASS"
    assert result["version_found"] is True


def test_version_attestation_fail(direct_deploy, direct_vm):
    """Missing version returns FAIL."""
    contract = direct_deploy("contracts/version_attestation.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v0.9.0 of TestProject."})
    direct_vm.mock_llm(
        ".*",
        '{"version_found": false, '
        '"observed_versions": "v0.9.0", '
        '"reason": "Version 1.0.0 not found"}')
    result = contract.verify(
        "https://github.com/test/project/releases",
        "TestProject", "1.0.0")
    assert result["status"] == "FAIL"
    assert result["version_found"] is False


def test_version_attestation_fetch_failure(direct_deploy, direct_vm):
    """Unreachable URL returns FETCH_FAILED."""
    contract = direct_deploy("contracts/version_attestation.py")
    result = contract.verify(
        "https://down.example.com",
        "TestProject", "1.0.0")
    assert result["status"] == "FETCH_FAILED"


def test_version_attestation_string_true_rejected(direct_deploy, direct_vm):
    """String 'true' for version_found returns INSUFFICIENT, not PASS."""
    contract = direct_deploy("contracts/version_attestation.py")
    direct_vm.mock_web(
        ".*example.com.*",
        {"method": "GET", "status": 200,
         "body": "Release page content here."})
    direct_vm.mock_llm(
        ".*",
        '{"version_found": "true", '
        '"observed_versions": "1.0.0", '
        '"reason": "Found"}')
    result = contract.verify(
        "https://example.com/releases",
        "TestProject", "1.0.0")
    assert result["status"] != "PASS"
