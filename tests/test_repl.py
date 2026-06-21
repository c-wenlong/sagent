"""
Tests for the interactive REPL.

Uses mocked curses to test TUI logic without a terminal.
"""

import pytest
from unittest.mock import MagicMock, patch
from io import StringIO

from repl import (
    ThinkingCanceller,
    REPLSession,
    handle_command,
    COMMANDS,
    COMPLETIONS,
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

    def remember(self, content, user_id, memory_type):
        self.remembered.append({"content": content, "user_id": user_id, "memory_type": memory_type})

    def get_recent_memories(self, user_id, limit=10):
        return self.recent_memories

    def profile(self, user_id):
        return self.profile_data


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


class TestREPLSession:
    """Tests for REPLSession state management."""

    def test_session_init(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        assert session.user_id == "user1"
        assert session.input_buffer == ""
        assert session.is_thinking() is False
        assert session.is_cancelled() is False

    def test_handle_key_backspace(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        session.input_buffer = "hello"
        result = session.handle_key(127)
        assert result == "backspace"
        assert session.input_buffer == "hell"

    def test_handle_key_tab_with_slash_completes(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        session.input_buffer = "/"
        result = session.handle_key(9)
        assert result == "tab"
        assert session.input_buffer == "remember <text>"

    def test_handle_key_tab_empty_completes_to_slash(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        result = session.handle_key(9)
        assert result == "tab"
        assert session.input_buffer == "/"

    def test_handle_key_escape_clears_buffer(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        session.input_buffer = "hello"
        result = session.handle_key(27)
        assert result == "escape"
        assert session.input_buffer == ""

    def test_handle_key_char(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        result = session.handle_key(ord("h"))
        assert result == "char"
        assert session.input_buffer == "h"

    def test_handle_key_enter(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        result = session.handle_key(10)
        assert result == "enter"

    def test_handle_key_ctrl_c(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        result = session.handle_key(3)
        assert result == "eof"

    def test_cancel_thinking(self):
        harness = MockHarness()
        session = REPLSession(harness, "user1")
        session.canceller = ThinkingCanceller()
        session.canceller.start()
        assert session.is_thinking() is True
        session.cancel_thinking()
        assert session.is_cancelled() is True


class TestCommandsList:
    """Tests for command constants."""

    def test_all_commands_present(self):
        expected = ["remember", "pref", "interact", "think", "event", "memories", "profile", "clear", "help"]
        for cmd in expected:
            found = any(c.startswith(cmd) for c in COMPLETIONS)
            assert found, f"Command {cmd} not found"

    def test_completions_match_commands(self):
        cmd_texts = [cmd for cmd, _ in COMMANDS]
        assert sorted(COMPLETIONS) == sorted(cmd_texts)
