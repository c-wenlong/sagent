"""Tests for the sagent CLI entry point."""

from unittest.mock import patch

from sagent_cli import main


class TestCLI:
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
