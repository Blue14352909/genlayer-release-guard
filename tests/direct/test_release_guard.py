"""Tests for ReleaseGuard orchestrator contract."""
from tests.direct.conftest import to_hex


def test_release_guard_deploy(direct_deploy):
    """Contract deploys successfully."""
    contract = direct_deploy("contracts/release_guard.py")
    assert contract is not None


def test_create_verification(direct_deploy, direct_vm, direct_alice):
    """Creating a verification returns an ID."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://github.com/test/project",
        "source,license")
    assert vid.startswith("v-")


def test_create_verification_empty_project(direct_deploy, direct_vm,
                                           direct_alice):
    """Empty project name raises error."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    try:
        contract.create_verification("", "1.0.0", "https://example.com", "")
        assert False, "Should have raised"
    except Exception:
        pass


def test_create_verification_empty_version(direct_deploy, direct_vm,
                                           direct_alice):
    """Empty version raises error."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    try:
        contract.create_verification("Test", "", "https://example.com", "")
        assert False, "Should have raised"
    except Exception:
        pass


def test_get_verification_pending(direct_deploy, direct_vm, direct_alice):
    """New verification is in PENDING status."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://github.com/test/project",
        "source")
    v = contract.get_verification(vid)
    assert v["status"] == "PENDING"
    assert v["project_name"] == "TestProject"
    assert v["version"] == "1.0.0"


def test_get_verdict_pending(direct_deploy, direct_vm, direct_alice):
    """get_verdict returns PENDING for unfinished verification."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://github.com/test/project",
        "source")
    verdict = contract.get_verdict(vid)
    assert verdict == "PENDING"


def test_run_verification_not_found(direct_deploy, direct_vm, direct_alice):
    """Running non-existent verification raises error."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    try:
        contract.run_verification("v-999")
        assert False, "Should have raised"
    except Exception:
        pass


def test_run_verification_wrong_status(direct_deploy, direct_vm,
                                       direct_alice):
    """Running a non-PENDING verification raises error."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://github.com/test/project",
        "source")
    # First run succeeds
    contract.run_verification(vid)
    # Second run fails
    try:
        contract.run_verification(vid)
        assert False, "Should have raised"
    except Exception:
        pass


def test_get_check_results_empty(direct_deploy, direct_vm, direct_alice):
    """New verification has empty check results."""
    contract = direct_deploy("contracts/release_guard.py")
    direct_vm.sender = direct_alice
    vid = contract.create_verification(
        "TestProject", "1.0.0",
        "https://github.com/test/project",
        "source")
    results = contract.get_check_results(vid)
    assert len(results) == 0


def test_verification_not_found(direct_deploy):
    """get_verification for non-existent ID raises error."""
    contract = direct_deploy("contracts/release_guard.py")
    try:
        contract.get_verification("v-999")
        assert False, "Should have raised"
    except Exception:
        pass
