"""Fixtures for GenLayer Studio integration tests.

The default, reproducible evidence for this repository is the direct-mode
suite under `tests/direct/`. The tests in this package talk to a real
GenLayer network (real consensus, real web retrieval, real LLM evaluation)
and are therefore opt-in.

`deployed_contract` is a real gltest contract handle: it is built from the
contract source and an address you supply. It deliberately does NOT spin up a
fake contract, and it never fakes a consensus result. When nothing is
configured it SKIPS with an explicit reason instead of erroring, so the
default test run stays green and honest.

Required configuration (to actually run these tests):

    RELEASEGUARD_STUDIO_CONTRACT_ADDRESS
        Address of an already-deployed ReleaseGuard contract on the target
        GenLayer network (for example a `0x...` Studio address).

Optional configuration:

    RELEASEGUARD_STUDIO_CONTRACT_FILE
        Path to the contract source used to build the method schema. Either an
        absolute path, or a path relative to the configured contracts
        directory. Defaults to `contracts/release_guard.py` in this repository.

    Network / RPC / accounts are taken from `gltest.config.yaml` and the
    usual gltest options (`--network`, `--rpc-url`, `--contracts-dir`), so the
    tests run against whatever network you configure there.

These tests are never part of the default direct-mode evidence.
"""
import os
from pathlib import Path

import pytest

ADDRESS_ENV = "RELEASEGUARD_STUDIO_CONTRACT_ADDRESS"
CONTRACT_FILE_ENV = "RELEASEGUARD_STUDIO_CONTRACT_FILE"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONTRACT_FILE = _REPO_ROOT / "contracts" / "release_guard.py"

_SKIP_REASON = (
    "GenLayer Studio integration test skipped: no deployed contract is "
    "configured. Set " + ADDRESS_ENV + " to the address of an already-deployed "
    "ReleaseGuard contract (and make sure gltest.config.yaml points at a "
    "reachable network) to run it. Optional: " + CONTRACT_FILE_ENV + " to "
    "override the contract source used for the method schema. These tests "
    "require real GenLayer consensus and are not part of the default "
    "direct-mode test run."
)


@pytest.fixture(scope="session")
def deployed_contract():
    """A real gltest handle for a deployed ReleaseGuard contract.

    Skips with an explicit reason when no contract address is configured.
    """
    address = os.environ.get(ADDRESS_ENV, "").strip()
    if not address:
        pytest.skip(_SKIP_REASON)

    gltest = pytest.importorskip("gltest")
    contract_file = os.environ.get(CONTRACT_FILE_ENV, "").strip()
    contract_path = Path(contract_file) if contract_file else _DEFAULT_CONTRACT_FILE

    factory = gltest.get_contract_factory(contract_file_path=str(contract_path))
    return factory.build_contract(address)
