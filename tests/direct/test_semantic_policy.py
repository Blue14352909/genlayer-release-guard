"""Tests for SemanticPolicy primitive contract."""


def test_semantic_policy_deploy(direct_deploy):
    """Contract deploys successfully."""
    contract = direct_deploy("contracts/semantic_policy.py")
    assert contract is not None


def test_semantic_policy_empty_url(direct_deploy):
    """Empty URL returns INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/semantic_policy.py")
    result = contract.evaluate(
        "", "MyProject", "1.0.0", "Must have README")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_semantic_policy_empty_policy(direct_deploy):
    """Empty policy returns INSUFFICIENT_EVIDENCE."""
    contract = direct_deploy("contracts/semantic_policy.py")
    result = contract.evaluate(
        "https://example.com", "MyProject", "1.0.0", "")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_semantic_policy_pass(direct_deploy, direct_vm):
    """Policy satisfied returns PASS."""
    contract = direct_deploy("contracts/semantic_policy.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0 with CHANGELOG and migration guide."})
    direct_vm.mock_llm(
        ".*",
        '{"status": "PASS", '
        '"reason": "Release includes CHANGELOG and migration guide", '
        '"policy_checks": [{"item": "changelog", "result": "PASS"}]}')
    result = contract.evaluate(
        "https://github.com/test/project/releases/tag/v1.0.0",
        "TestProject", "1.0.0",
        "Release must include CHANGELOG entry")
    assert result["status"] == "PASS"


def test_semantic_policy_fail(direct_deploy, direct_vm):
    """Policy not satisfied returns FAIL."""
    contract = direct_deploy("contracts/semantic_policy.py")
    direct_vm.mock_web(
        ".*github.com.*",
        {"method": "GET", "status": 200,
         "body": "Release v1.0.0. No changelog provided."})
    direct_vm.mock_llm(
        ".*",
        '{"status": "FAIL", '
        '"reason": "No CHANGELOG found", '
        '"policy_checks": [{"item": "changelog", "result": "FAIL"}]}')
    result = contract.evaluate(
        "https://github.com/test/project/releases/tag/v1.0.0",
        "TestProject", "1.0.0",
        "Release must include CHANGELOG entry")
    assert result["status"] == "FAIL"


def test_semantic_policy_fetch_failure(direct_deploy, direct_vm):
    """Unreachable URL returns FETCH_FAILED."""
    contract = direct_deploy("contracts/semantic_policy.py")
    result = contract.evaluate(
        "https://down.example.com",
        "TestProject", "1.0.0",
        "Must have README")
    assert result["status"] == "FETCH_FAILED"
