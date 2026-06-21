"""
Unit tests for sagent harness
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from harness import (
    AgentHarness,
    ContextBuilder,
    MemoryEntry,
    MemoryStore,
    MemoryType,
    SessionManager,
)
from harness.context import TimeRange
from harness.memory import (
    _decode_stored_content,
    _encode_stored_content,
    _resolve_memory_type,
)


class TestMemoryEntry:
    def test_create_memory_entry(self):
        entry = MemoryEntry(
            content="Test content",
            type=MemoryType.FACT,
            user_id="user_1",
        )
        assert entry.content == "Test content"
        assert entry.type == MemoryType.FACT
        assert entry.user_id == "user_1"
        assert entry.id is not None

    def test_to_dict(self):
        entry = MemoryEntry(
            id="test-id",
            content="Test",
            type=MemoryType.PREFERENCE,
            user_id="user_1",
        )
        d = entry.to_dict()
        assert d["id"] == "test-id"
        assert d["content"] == "Test"
        assert d["type"] == "preference"
        assert d["user_id"] == "user_1"

    def test_from_dict(self):
        data = {
            "id": "test-id",
            "content": "Test",
            "type": "fact",
            "user_id": "user_1",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        entry = MemoryEntry.from_dict(data)
        assert entry.id == "test-id"
        assert entry.content == "Test"
        assert entry.type == MemoryType.FACT


class TestMemoryEncoding:
    def test_encode_decode_roundtrip(self):
        stored = _encode_stored_content("Hello world", MemoryType.PREFERENCE, "user_1")
        assert stored == "[preference:user_1] Hello world"
        memory_type, user_id, content = _decode_stored_content(stored)
        assert memory_type == MemoryType.PREFERENCE
        assert user_id == "user_1"
        assert content == "Hello world"

    def test_resolve_type_from_metadata(self):
        assert _resolve_memory_type(
            {"memory_type": "event"},
            "[fact:user_1] ignored",
        ) == MemoryType.EVENT


class TestMemoryStore:
    def test_add_memory(self):
        mock_client = MagicMock()
        mock_client.add_memory.return_value = "source-123"

        store = MemoryStore(mock_client)
        entry = MemoryEntry(
            content="Learn Rust",
            type=MemoryType.FACT,
            user_id="user_1",
        )

        entry_id = store.add(entry)
        assert entry_id == entry.id
        mock_client.add_memory.assert_called_once()
        call_kwargs = mock_client.add_memory.call_args.kwargs
        assert call_kwargs["text"].startswith("[fact:user_1]")
        assert call_kwargs["metadata"]["memory_type"] == "fact"

    def test_recall(self):
        mock_client = MagicMock()
        mock_client.recall.return_value = [
            {
                "source_id": "src-1",
                "content": "[fact:user_1] Learning Rust",
                "metadata": {"memory_type": "fact", "memory_id": "mem-1", "user_id": "user_1"},
            }
        ]

        store = MemoryStore(mock_client)
        results = store.recall(query="Rust", user_id="user_1")

        assert len(results) == 1
        assert results[0].content == "Learning Rust"
        assert results[0].type == MemoryType.FACT
        assert results[0].user_id == "user_1"

    def test_get_recent(self):
        mock_client = MagicMock()
        mock_client.get_memories.return_value = [
            {
                "source_id": "src-1",
                "content": "[fact:user_1] Memory 1",
            },
            {
                "source_id": "src-2",
                "content": "[preference:user_2] Other user",
            },
        ]

        store = MemoryStore(mock_client)
        results = store.get_recent(user_id="user_1", limit=10)

        assert len(results) == 1
        assert results[0].content == "Memory 1"
        assert results[0].type == MemoryType.FACT


class TestContextBuilder:
    def test_time_range_last_n_days(self):
        tr = TimeRange(last_n_days=7)
        recent = datetime.utcnow()
        old = datetime(2020, 1, 1)

        assert tr.contains(recent) is True
        assert tr.contains(old) is False

    def test_time_range_date_bounds(self):
        tr = TimeRange(
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 12, 31),
        )

        assert tr.contains(datetime(2026, 6, 15)) is True
        assert tr.contains(datetime(2025, 1, 1)) is False
        assert tr.contains(datetime(2027, 1, 1)) is False

    def test_build_empty_context(self):
        mock_client = MagicMock()
        mock_client.get_memories.return_value = []

        store = MemoryStore(mock_client)
        builder = ContextBuilder(store)

        context = builder.build(
            prompt="What am I working on?",
            user_id="user_1",
        )

        assert "Current Query" in context
        assert "What am I working on?" in context

    def test_build_filters_by_user_id(self):
        mock_client = MagicMock()
        mock_client.get_memories.return_value = [
            {"source_id": "src-1", "content": "[fact:user_1] Rust project"},
            {"source_id": "src-2", "content": "[fact:user_2] Python project"},
        ]

        store = MemoryStore(mock_client)
        builder = ContextBuilder(store)
        context = builder.build(prompt="What am I working on?", user_id="user_1")

        assert "Rust project" in context
        assert "Python project" not in context


class TestSessionManager:
    def test_start_session(self):
        mock_client = MagicMock()
        store = MemoryStore(mock_client)
        manager = SessionManager(store)

        session = manager.start_session(user_id="user_1")

        assert session.user_id == "user_1"
        assert session.active is True
        assert session.id is not None

    def test_end_session(self):
        mock_client = MagicMock()
        store = MemoryStore(mock_client)
        manager = SessionManager(store)

        session = manager.start_session(user_id="user_1")
        ended = manager.end_session(session.id)

        assert ended is not None
        assert ended.active is False
        assert ended.ended_at is not None

    def test_add_memory_to_session(self):
        mock_client = MagicMock()
        store = MemoryStore(mock_client)
        manager = SessionManager(store)

        session = manager.start_session(user_id="user_1")
        manager.add_memory_to_session(session.id, "mem-1")

        session = manager.get_session(session.id)
        assert "mem-1" in session.entry_ids


class TestAgentHarness:
    def test_init_without_llm(self):
        with patch.dict("os.environ", {}, clear=True):
            harness = AgentHarness(
                api_key="test-key",
                tenant_id="test-tenant",
                llm_api_key=None,
            )
            assert harness.llm is None

    def test_init_with_llm(self):
        with patch("harness.harness.OpenAI"):
            harness = AgentHarness(
                api_key="test-key",
                tenant_id="test-tenant",
                llm_api_key="fake-key",
            )
            assert harness.llm is not None

    def test_remember(self):
        with patch("harness.harness.OpenAI"):
            harness = AgentHarness(
                api_key="test-key",
                tenant_id="test-tenant",
            )

            with patch.object(harness.memory_store, "add") as mock_add:
                mock_add.return_value = "mem-123"
                entry_id = harness.remember(
                    content="Learning Rust",
                    user_id="user_1",
                    memory_type=MemoryType.FACT,
                )

                assert entry_id == "mem-123"
                mock_add.assert_called_once()

    def test_profile(self):
        with patch("harness.harness.OpenAI"):
            harness = AgentHarness(
                api_key="test-key",
                tenant_id="test-tenant",
            )

            with patch.object(harness.memory_store, "get_recent") as mock_recent:
                mock_recent.return_value = [
                    MemoryEntry(
                        content="Likes dark mode",
                        type=MemoryType.PREFERENCE,
                        user_id="user_1",
                    ),
                    MemoryEntry(
                        content="Learning Rust",
                        type=MemoryType.FACT,
                        user_id="user_1",
                    ),
                ]

                profile = harness.profile("user_1")
                assert len(profile.preferences) == 1
                assert len(profile.facts) == 1

    def test_start_session(self):
        harness = AgentHarness(api_key="test", tenant_id="test")
        session = harness.start_session("user_1")
        assert session.user_id == "user_1"
        assert session.active is True

    def test_end_session(self):
        harness = AgentHarness(api_key="test", tenant_id="test")
        session = harness.start_session("user_1")
        ended = harness.end_session(session.id)
        assert ended is not None
        assert ended.active is False
        assert ended.ended_at is not None

    def test_get_recent_memories(self):
        harness = AgentHarness(api_key="test", tenant_id="test")
        with patch.object(harness.memory_store, "get_recent") as mock_recent:
            mock_recent.return_value = [
                MemoryEntry(content="Test", type=MemoryType.FACT, user_id="user_1")
            ]
            results = harness.get_recent_memories("user_1")
            assert len(results) == 1
            assert results[0].content == "Test"

    def test_recall(self):
        harness = AgentHarness(api_key="test", tenant_id="test")
        with patch.object(harness.memory_store, "recall") as mock_recall:
            mock_recall.return_value = [
                MemoryEntry(content="Rust", type=MemoryType.FACT, user_id="user_1")
            ]
            results = harness.recall("Rust", "user_1")
            assert len(results) == 1
            mock_recall.assert_called_once_with(query="Rust", user_id="user_1", limit=5)

    def test_call_llm_fallback(self):
        with patch.dict("os.environ", {}, clear=True):
            harness = AgentHarness(
                api_key="test-key",
                tenant_id="test-tenant",
                llm_api_key=None,
            )

            result = harness._call_llm("test prompt")
            assert "not configured" in result
