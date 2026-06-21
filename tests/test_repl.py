"""
Tests for the interactive REPL
"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from repl import Spinner, load_avatar_pixels


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
            stream_print("Hello")
        result = output.getvalue()
        assert result == "Hello\n"


class TestAvatarPixels:
    def test_load_avatar_pixels(self):
        pixels = load_avatar_pixels("assets/icons/human.png", 20, 12)
        assert len(pixels) == 12
        assert len(pixels[0]) == 20

    def test_avatar_colors_are_integers(self):
        pixels = load_avatar_pixels("assets/icons/agent.png", 10, 5)
        for row in pixels:
            for color in row:
                assert isinstance(color, int)
                assert 0 <= color <= 255


class TestREPLCommands:
    def test_repl_requires_env_vars(self):
        pass


class TestREPLMemoryTypes:
    def test_all_memory_types_available(self):
        from harness import MemoryType
        assert MemoryType.FACT is not None
        assert MemoryType.PREFERENCE is not None
        assert MemoryType.INTERACTION is not None
        assert MemoryType.THOUGHT is not None
        assert MemoryType.EVENT is not None
