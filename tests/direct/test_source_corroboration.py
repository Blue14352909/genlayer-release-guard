"""Tests for SourceCorroboration primitive contract."""


def test_source_corroboration_deploy(direct_deploy):
    """Contract deploys successfully."""
    contract = direct_deploy("contracts/source_corroboration.py")
    assert contract is not None


def test_source_corroboration_empty_urls(direct_deploy):
    """Empty URLs return INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/source_corroboration.py")
    result = contract.verify("MyProject", "1.0.0", "", "")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_source_corroboration_pass(direct_deploy, direct_vm):
    """Two corroborating sources return PASS."""
    contract = direct_deploy("contracts/source_corroboration.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject on PyPI."})
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject on GitHub."})
    direct_vm.mock_llm(
        ".*",
        '{"sources_confirming": 2, "sources_total": 2, '
        '"corroboration_holds": true, '
        '"reason": "Both sources confirm v1.0.0"}')
    result = contract.verify(
        "TestProject", "1.0.0",
        "https://pypi.org/project/testproject/1.0.0/",
        "https://github.com/test/project/releases/tag/v1.0.0")
    assert result["status"] == "PASS"
    assert result["sources_confirming"] == 2


def test_source_corroboration_fail(direct_deploy, direct_vm):
    """Conflicting sources return FAIL."""
    contract = direct_deploy("contracts/source_corroboration.py")
    direct_vm.mock_web(
        ".*pypi.org.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 of TestProject."})
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v0.9.0 of OtherProject."})
    direct_vm.mock_llm(
        ".*",
        '{"sources_confirming": 1, "sources_total": 2, '
        '"corroboration_holds": false, '
        '"reason": "Sources conflict"}')
    result = contract.verify(
        "TestProject", "1.0.0",
        "https://pypi.org/project/testproject/1.0.0/",
        "https://github.com/test/project/releases")
    assert result["status"] == "FAIL"


def test_source_corroboration_fetch_failure(direct_deploy, direct_vm):
    """Both URLs unreachable returns FETCH_FAILED."""
    contract = direct_deploy("contracts/source_corroboration.py")
    result = contract.verify(
        "TestProject", "1.0.0",
        "https://down1.example.com",
        "https://down2.example.com")
    assert result["status"] == "FETCH_FAILED"


def test_source_corroboration_inconsistent_counts(direct_deploy, direct_vm):
    """confirming > total returns INSUFFICIENT."""
    contract = direct_deploy("contracts/source_corroboration.py")
    direct_vm.mock_web(
        ".*example.com.*",
        {"method": "GET", "status": 200,
         "body": "Release page content."})
    direct_vm.mock_web(
        ".*example.org.*",
        {"method": "GET", "status": 200,
         "body": "Another release page."})
    direct_vm.mock_llm(
        ".*",
        '{"sources_confirming": 5, "sources_total": 2, '
        '"corroboration_holds": true, '
        '"reason": "Inconsistent counts"}')
    result = contract.verify(
        "TestProject", "1.0.0",
        "https://example.com/release",
        "https://example.org/release")
    assert result["status"] != "PASS"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_source_corroboration_rejects_string_holds_flag(direct_deploy, direct_vm):
    """A string boolean cannot establish corroboration."""
    contract = direct_deploy("contracts/source_corroboration.py")
    direct_vm.mock_web(
        ".*example.com.*",
        {"method": "GET", "status": 200, "body": "Release v1.0.0 TestProject"})
    direct_vm.mock_web(
        ".*example.org.*",
        {"method": "GET", "status": 200, "body": "Release v1.0.0 TestProject"})
    direct_vm.mock_llm(
        ".*", '{"sources_confirming": 2, "sources_total": 2, '
        '"corroboration_holds": "true"}')
    result = contract.verify(
        "TestProject", "1.0.0", "https://example.com/release", "https://example.org/release")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
