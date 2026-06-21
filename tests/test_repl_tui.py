"""Tests for REPL landing screen and TUI helpers."""

from unittest.mock import MagicMock

from repl_tui import (
    SAGENT_LOGO,
    build_landing_lines,
    memory_count,
    terminal_width,
)


class TestLandingScreen:
    def test_logo_present(self):
        assert "SAGENT" in SAGENT_LOGO or "████" in SAGENT_LOGO

    def test_build_landing_contains_key_sections(self):
        harness = MagicMock()
        harness.get_recent_memories.return_value = [MagicMock(), MagicMock()]
        lines = build_landing_lines(
            harness=harness,
            user_id="demo_user",
            model="test-model",
            session_id="session-12345678",
            width=100,
        )
        text = "\n".join(lines)
        assert "Memory Types" in text
        assert "Slash Commands" in text
        assert "demo_user" in text
        assert "test-model" in text
        assert "Welcome to sagent" in text
        assert "/remember" in text

    def test_terminal_width_has_sane_bounds(self):
        width = terminal_width(fallback=100)
        assert 72 <= width <= 120

    def test_memory_count_times_out(self):
        harness = MagicMock()

        def slow_fetch(*_args, **_kwargs):
            import time

            time.sleep(5)
            return []

        harness.get_recent_memories.side_effect = slow_fetch
        assert memory_count(harness, "user1", timeout=0.1) is None

    def test_box_rows_have_consistent_width(self):
        harness = MagicMock()
        harness.get_recent_memories.return_value = []
        width = 100
        lines = build_landing_lines(
            harness=harness,
            user_id="demo_user",
            model="test-model",
            session_id="session-12345678",
            width=width,
        )
        box_rows = [line for line in lines if line.startswith("\x1b[94m│")]
        assert box_rows
        from repl_tui import _display_width

        for row in box_rows:
            assert _display_width(row) == width
