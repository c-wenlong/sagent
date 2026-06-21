"""Tests for the sagent CLI entry point."""

from unittest.mock import patch

from sagent_cli import main


class TestCLI:
    def test_repl_tui_is_packaged(self):
        import repl_tui  # noqa: F401 — must be a top-level install module

        assert hasattr(repl_tui, "print_landing_screen")

    def test_default_runs_repl(self):
        with patch("repl.main") as mock_repl:
            main([])
            mock_repl.assert_called_once()

    def test_repl_subcommand(self):
        with patch("repl.main") as mock_repl:
            main(["repl"])
            mock_repl.assert_called_once()

    def test_demo_subcommand(self):
        with patch("demo.demo") as mock_demo:
            main(["demo"])
            mock_demo.assert_called_once()
