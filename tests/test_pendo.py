"""
Tests for the Pendo server-side track event utility.
"""

import json
import urllib.request
from unittest.mock import MagicMock, patch

from harness.pendo import PENDO_INTEGRATION_KEY, PENDO_TRACK_URL, track


class TestPendoTrack:
    """Tests for the track() function."""

    @patch("harness.pendo.urllib.request.urlopen")
    def test_sends_correct_payload(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        track("test_event", visitor_id="user_1", account_id="acct_1")

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))

        assert payload["type"] == "track"
        assert payload["event"] == "test_event"
        assert payload["visitorId"] == "user_1"
        assert payload["accountId"] == "acct_1"
        assert isinstance(payload["timestamp"], int)
        assert "properties" not in payload

    @patch("harness.pendo.urllib.request.urlopen")
    def test_includes_properties(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        track(
            "test_event",
            visitor_id="user_1",
            account_id="acct_1",
            properties={"key": "value", "count": 42},
        )

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))

        assert payload["properties"] == {"key": "value", "count": 42}

    @patch("harness.pendo.urllib.request.urlopen")
    def test_sends_correct_headers(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        track("test_event")

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("X-pendo-integration-key") == PENDO_INTEGRATION_KEY
        assert req.full_url == PENDO_TRACK_URL
        assert req.method == "POST"

    @patch("harness.pendo.urllib.request.urlopen")
    def test_default_visitor_and_account(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        track("test_event")

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))

        assert payload["visitorId"] == "system"
        assert payload["accountId"] == "system"

    @patch("harness.pendo.urllib.request.urlopen")
    def test_does_not_raise_on_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.request.URLError("connection refused")

        track("test_event", visitor_id="user_1", account_id="acct_1")

    @patch("harness.pendo.urllib.request.urlopen")
    def test_does_not_raise_on_generic_exception(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("unexpected error")

        track("test_event", visitor_id="user_1", account_id="acct_1")

    @patch("harness.pendo.urllib.request.urlopen")
    def test_boolean_properties(self, mock_urlopen):
        mock_urlopen.return_value.__enter__ = MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        track(
            "test_event",
            visitor_id="user_1",
            account_id="acct_1",
            properties={"enabled": True, "has_data": False},
        )

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))

        assert payload["properties"]["enabled"] is True
        assert payload["properties"]["has_data"] is False
