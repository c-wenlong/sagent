"""
Tests for the interactive REPL
"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from repl import Spinner


class TestSpinner:
    def test_spinner_init(self):
        spinner = Spinner("Testing")
        assert spinner.message == "Testing"
        assert spinner.running is False
        assert spinner.index == 0

    def test_spinner_frames(self):
        spinner = Spinner()
        assert len(spinner.frames) == 10
        assert "⠋" in spinner.frames

    def test_stream_print(self):
        from repl import stream_print
        output = StringIO()
        with patch("sys.stdout", output):
            stream_print("Hello", delay=0)
        result = output.getvalue()
        assert result == "Hello\n"


class TestREPLCommands:
    def test_repl_requires_env_vars(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("sys.exit") as mock_exit:
                # Will exit because env vars are missing
                pass  # Can't easily test main() without mocking input


class TestREPLMemoryTypes:
    def test_all_memory_types_available(self):
        from harness import MemoryType
        assert MemoryType.FACT is not None
        assert MemoryType.PREFERENCE is not None
        assert MemoryType.INTERACTION is not None
        assert MemoryType.THOUGHT is not None
        assert MemoryType.EVENT is not None
