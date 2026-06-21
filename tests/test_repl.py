"""
Tests for the interactive REPL
"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from repl import ThinkingCanceller, COMMANDS, COMPLETIONS


class TestThinkingCanceller:
    def test_canceller_init(self):
        c = ThinkingCanceller("Thinking")
        assert c.message == "Thinking"
        assert c.running is False
        assert c.cancelled is False

    def test_canceller_was_cancelled_false_initially(self):
        c = ThinkingCanceller()
        assert c.was_cancelled() is False


class TestCommandCompletion:
    def test_commands_loaded(self):
        assert len(COMMANDS) == 9
        assert len(COMPLETIONS) == 9

    def test_completions_list(self):
        assert "remember <text>" in COMPLETIONS
        assert "help" in COMPLETIONS


class TestREPLMemoryTypes:
    def test_all_memory_types_available(self):
        from harness import MemoryType
        assert MemoryType.FACT is not None
        assert MemoryType.PREFERENCE is not None
        assert MemoryType.INTERACTION is not None
        assert MemoryType.THOUGHT is not None
        assert MemoryType.EVENT is not None
