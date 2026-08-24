"""Integration tests for ReleaseGuard (requires GenLayer Studio)."""
import pytest


@pytest.mark.integration
class TestReleaseGuardIntegration:
    """Integration tests that deploy to GenLayer Studio and test with
    real consensus, actual web retrieval, and LLM evaluation."""

    def test_deploy_contract(self, deployed_contract):
        """Contract deploys successfully to Studio."""
        assert deployed_contract is not None

    def test_full_verification_flow(self, deployed_contract):
        """Create, run, and retrieve a complete verification."""
        contract = deployed_contract

        # Create verification
        vid = contract.create_verification(
            "requests",
            "2.31.0",
            "https://pypi.org/project/requests/2.31.0/",
            "source,license",
        )
        assert vid is not None
        assert vid.startswith("v-")

        # Run verification
        verdict = contract.run_verification(vid)
        assert verdict in ("VERIFIED", "REJECTED", "INCONCLUSIVE")

        # Retrieve full record
        v = contract.get_verification(vid)
        assert v["status"] == "COMPLETED"
        assert v["verdict"] == verdict
        assert len(v["results"]) > 0

    def test_get_verdict(self, deployed_contract):
        """get_verdict returns the final verdict after verification."""
        contract = deployed_contract

        vid = contract.create_verification(
            "requests",
            "2.31.0",
            "https://pypi.org/project/requests/2.31.0/",
            "source,license",
        )
        contract.run_verification(vid)

        verdict = contract.get_verdict(vid)
        assert verdict in ("VERIFIED", "REJECTED", "INCONCLUSIVE")
