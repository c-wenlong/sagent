"""
Tests for the interactive REPL
"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from repl import ThinkingCanceller, CommandPalette, COMMANDS


class TestThinkingCanceller:
    def test_canceller_init(self):
        c = ThinkingCanceller("Thinking")
        assert c.message == "Thinking"
        assert c.running is False
        assert c.cancelled is False

    def test_canceller_was_cancelled_false_initially(self):
        c = ThinkingCanceller()
        assert c.was_cancelled() is False


class TestCommandPalette:
    def test_palette_init(self):
        p = CommandPalette(COMMANDS)
        assert p.visible is False
        assert p.selected == 0
        assert len(p.commands) == 9

    def test_palette_commands_loaded(self):
        p = CommandPalette(COMMANDS)
        assert p.commands[0][0] == "remember <text>"
        assert "Store a fact" in p.commands[0][1]


class TestREPLMemoryTypes:
    def test_all_memory_types_available(self):
        from harness import MemoryType
        assert MemoryType.FACT is not None
        assert MemoryType.PREFERENCE is not None
        assert MemoryType.INTERACTION is not None
        assert MemoryType.THOUGHT is not None
        assert MemoryType.EVENT is not None
