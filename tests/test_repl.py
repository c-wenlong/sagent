"""
Tests for the interactive REPL.
"""

from unittest.mock import MagicMock

import pytest
from prompt_toolkit.document import Document

from repl import (
    _RUNTIME,
    COMMANDS,
    COMPLETIONS,
    REPLSession,
    SlashCommandCompleter,
    ThinkingCanceller,
    _interaction_content,
    chat_with_spinner,
    complete_slash_command,
    filter_slash_commands,
    handle_command,
    normalize_user_input,
    run_think_in_thread,
)


class TestThinkingCanceller:
    """Tests for ThinkingCanceller cancellation logic."""

    def test_init(self):
        c = ThinkingCanceller("Thinking")
        assert c.message == "Thinking"
        assert c.running is False
        assert c.was_cancelled() is False

    def test_cancel_sets_event(self):
        c = ThinkingCanceller()
        c.cancel()
        assert c.was_cancelled() is True

    def test_start_and_cancel(self):
        c = ThinkingCanceller()
        c.start()
        assert c.running is True
        assert c.was_cancelled() is False
        c.cancel()
        assert c.was_cancelled() is True

    def test_cancel_twice_is_idempotent(self):
        c = ThinkingCanceller()
        c.cancel()
        c.cancel()
        assert c.was_cancelled() is True


class MockHarness:
    """Mock harness for testing command handling."""

    def __init__(self):
        self.remembered = []
        self.recent_memories = []
        self.profile_data = MagicMock()
        self.think_response = "Hello from agent"
        self.think_error = None

    def remember(self, content, user_id, memory_type):
        self.remembered.append({"content": content, "user_id": user_id, "memory_type": memory_type})

    def get_recent_memories(self, user_id, limit=10):
        return self.recent_memories

    def profile(self, user_id):
        return self.profile_data

    def think(self, prompt, user_id, store_interaction=False):
        self.last_store_interaction = store_interaction
        if self.think_error:
            raise self.think_error
        return self.think_response


class TestHandleCommand:
    """Tests for handle_command function."""

    def test_empty_input_returns_true(self):
        harness = MockHarness()
        result = handle_command("", harness, "user1")
        assert result is True

    def test_remember_command(self):
        harness = MockHarness()
        result = handle_command("remember my name is kai", harness, "user1")
        assert result is True
        assert len(harness.remembered) == 1
        assert harness.remembered[0]["content"] == "my name is kai"

    def test_slash_remember_command(self):
        harness = MockHarness()
        result = handle_command("/remember my name is kai", harness, "user1")
        assert result is True
        assert harness.remembered[0]["content"] == "my name is kai"

    def test_pref_command(self):
        harness = MockHarness()
        result = handle_command("pref I like coffee", harness, "user1")
        assert result is True
        assert "I like coffee" in harness.remembered[0]["content"]

    def test_interact_command(self):
        harness = MockHarness()
        result = handle_command("interact talked to john yesterday", harness, "user1")
        assert result is True

    def test_think_command(self):
        harness = MockHarness()
        result = handle_command("think about the meaning of life", harness, "user1")
        assert result is True

    def test_event_command(self):
        harness = MockHarness()
        result = handle_command("event meeting at 3pm", harness, "user1")
        assert result is True

    def test_memories_command(self):
        harness = MockHarness()
        result = handle_command("memories", harness, "user1")
        assert result is True

    def test_profile_command(self):
        harness = MockHarness()
        result = handle_command("profile", harness, "user1")
        assert result is True

    def test_help_command(self):
        harness = MockHarness()
        result = handle_command("help", harness, "user1")
        assert result is True

    def test_clear_command(self):
        harness = MockHarness()
        result = handle_command("clear", harness, "user1")
        assert result is True

    def test_save_command_stores_last_exchange(self):
        harness = MockHarness()
        _RUNTIME["last_exchange"] = {"prompt": "hello", "response": "hi there"}
        result = handle_command("save", harness, "user1")
        assert result is True
        assert len(harness.remembered) == 1
        assert "hello" in harness.remembered[0]["content"]
        assert "hi there" in harness.remembered[0]["content"]

    def test_save_custom_text(self):
        harness = MockHarness()
        result = handle_command("save met with team about roadmap", harness, "user1")
        assert result is True
        assert harness.remembered[0]["content"] == "met with team about roadmap"

    def test_save_without_exchange_shows_message(self, capsys):
        harness = MockHarness()
        _RUNTIME["last_exchange"] = None
        handle_command("save", harness, "user1")
        assert len(harness.remembered) == 0
        assert "Nothing to save" in capsys.readouterr().out

    def test_autosave_toggle(self, capsys):
        harness = MockHarness()
        _RUNTIME["auto_store"] = False
        handle_command("autosave on", harness, "user1")
        assert _RUNTIME["auto_store"] is True
        handle_command("autosave off", harness, "user1")
        assert _RUNTIME["auto_store"] is False

    def test_exit_command_raises_systemexit(self):
        harness = MockHarness()
        with pytest.raises(SystemExit):
            handle_command("exit", harness, "user1")

    def test_quit_command_raises_systemexit(self):
        harness = MockHarness()
        with pytest.raises(SystemExit):
            handle_command("quit", harness, "user1")

    def test_chat_input_returns_false(self):
        harness = MockHarness()
        result = handle_command("hello there", harness, "user1")
        assert result is False
        assert len(harness.remembered) == 0


class TestCompleteSlashCommand:
    """Tests for slash command helpers."""

    def test_normalize_strips_slash(self):
        assert normalize_user_input("/memories") == "memories"
        assert normalize_user_input("hello") == "hello"

    def test_filter_by_prefix(self):
        matches = filter_slash_commands("mem")
        assert any(cmd["name"] == "memories" for cmd in matches)

    def test_empty_returns_slash(self):
        assert complete_slash_command("") == ""

    def test_slash_returns_first_command(self):
        assert complete_slash_command("/") == f"/{COMPLETIONS[0]}"

    def test_partial_match(self):
        result = complete_slash_command("/mem")
        assert result == "/memories"

    def test_completer_suggests_memories(self):
        completer = SlashCommandCompleter()
        doc = Document("/mem", 4)
        values = [c.text for c in completer.get_completions(doc, None)]
        assert "memories" in values


class TestREPLSession:
    """Tests for REPLSession state management."""

    def test_session_init(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        assert session.user_id == "user1"
        assert session.is_thinking() is False
        assert session.is_cancelled() is False

    def test_cancel_thinking(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        session.canceller = ThinkingCanceller()
        session.canceller.start()
        session.cancel_thinking()
        assert session.is_cancelled() is True

    def test_wait_for_result_returns_queue_item(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        session.result_queue.put(("success", "hello"))
        session.think_thread = MagicMock()
        session.think_thread.is_alive.return_value = False
        result = session.wait_for_result()
        assert result == ("success", "hello")

    def test_wait_for_result_returns_none_when_cancelled(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        session.canceller.cancel()
        session.think_thread = MagicMock()
        session.think_thread.is_alive.return_value = False
        result = session.wait_for_result()
        assert result is None


class TestRunThinkInThread:
    def test_respects_cancel_event(self):
        import queue
        import threading

        harness = MockHarness()
        result_queue = queue.Queue()
        cancel_event = threading.Event()
        cancel_event.set()

        run_think_in_thread(harness, "hello", "user1", result_queue, cancel_event)
        assert result_queue.empty()

    def test_passes_store_interaction_flag(self):
        import queue
        import threading

        harness = MockHarness()
        result_queue = queue.Queue()
        cancel_event = threading.Event()

        run_think_in_thread(
            harness, "hello", "user1", result_queue, cancel_event, store_interaction=True
        )
        status, _ = result_queue.get_nowait()
        assert status == "success"
        assert harness.last_store_interaction is True


class TestInteractionContent:
    def test_truncates_long_response(self):
        content = _interaction_content("hi", "x" * 300)
        assert len(content) < 300
        assert content.endswith("...")


class TestChatWithSpinner:
    def test_chat_stores_last_exchange(self, capsys):
        harness = MockHarness()
        _RUNTIME["auto_store"] = False
        _RUNTIME["last_exchange"] = None
        chat_with_spinner(harness, "user1", "hello there")
        assert _RUNTIME["last_exchange"]["prompt"] == "hello there"
        assert "/save" in capsys.readouterr().out

    def test_prints_error_on_failure(self, capsys):
        harness = MockHarness()
        harness.think_error = RuntimeError("LLM down")
        chat_with_spinner(harness, "user1", "hello there")
        output = capsys.readouterr().out
        assert "LLM down" in output


class TestCommandsList:
    """Tests for command constants."""

    def test_all_commands_present(self):
        expected = [
            "remember", "pref", "interact", "think", "event",
            "save", "autosave", "memories", "profile", "clear", "help",
        ]
        for cmd in expected:
            found = any(c.startswith(cmd) for c in COMPLETIONS)
            assert found, f"Command {cmd} not found"

    def test_completions_match_commands(self):
        cmd_names = [cmd.split()[0] for cmd, _ in COMMANDS]
        assert sorted(COMPLETIONS) == sorted(cmd_names)
