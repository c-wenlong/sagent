"""
Integration tests for sagent harness (requires real API keys)
"""

import pytest
import os
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def hydra_api_key():
    key = os.getenv("HYDRA_DB_API_KEY")
    if not key or key == "your-api-key":
        pytest.skip("HYDRA_DB_API_KEY not configured")
    return key


@pytest.fixture
def tenant_id():
    tid = os.getenv("HYDRA_DB_TENANT_ID")
    if not tid or tid == "your-tenant-id":
        pytest.skip("HYDRA_DB_TENANT_ID not configured")
    return tid


@pytest.fixture
def nebius_api_key():
    key = os.getenv("NEBIUS_API_KEY")
    if not key or key == "your-nebius-key":
        pytest.skip("NEBIUS_API_KEY not configured")
    return key


@pytest.fixture
def harness(hydra_api_key, tenant_id, nebius_api_key):
    from harness import AgentHarness
    return AgentHarness(
        api_key=hydra_api_key,
        tenant_id=tenant_id,
        sub_tenant_id="test-integration",
        llm_api_key=nebius_api_key,
    )


@pytest.mark.integration
class TestHydraDBIntegration:
    def test_add_and_recall_memory(self, harness):
        user_id = "test_integration_user"

        entry_id = harness.remember(
            content=f"Test memory at 2026",
            user_id=user_id,
        )
        assert entry_id is not None

        results = harness.recall(
            query="2026",
            user_id=user_id,
            limit=5,
        )
        assert len(results) >= 1

    def test_session_tracking(self, harness):
        user_id = "test_session_user"

        session = harness.start_session(user_id)
        assert session.user_id == user_id
        assert session.active is True

        harness.remember(
            content="Session test memory",
            user_id=user_id,
            session_id=session.id,
        )

        ended = harness.end_session(session.id)
        assert ended is not None
        assert ended.active is False

    def test_profile(self, harness):
        user_id = "test_profile_user"

        harness.remember(
            content="I prefer concise responses",
            user_id=user_id,
            memory_type="PREFERENCE",
        )
        harness.remember(
            content="I am a software engineer",
            user_id=user_id,
            memory_type="FACT",
        )

        profile = harness.profile(user_id)
        assert len(profile.preferences) >= 1
        assert len(profile.facts) >= 1


@pytest.mark.integration
class TestNebiusIntegration:
    def test_llm_call(self, harness):
        harness.llm_api_key  # ensure configured

        response = harness._call_llm("Say 'hello' in exactly one word")
        assert response.lower() == "hello"

    def test_think_with_context(self, harness):
        user_id = "test_think_user"

        harness.remember(
            content="My name is Test User",
            user_id=user_id,
        )

        response = harness.think(
            prompt="What is my name?",
            user_id=user_id,
            store_interaction=False,
        )
        assert "test user" in response.lower() or "name" in response.lower()
