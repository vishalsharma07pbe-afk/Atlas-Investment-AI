"""Configuration and portfolio transport regression checks (no network calls)."""
import unittest
from unittest.mock import patch, MagicMock

from app import main
from app.config import settings


class CloudRoutingTests(unittest.TestCase):
    def test_portfolio_endpoint_uses_configured_backend(self):
        expected = settings.backend_url.rstrip("/") + "/api/v1/portfolio/holdings"
        self.assertEqual(main._BACKEND_HOLDINGS_URL, expected)

    def test_portfolio_fetch_uses_only_configured_endpoint(self):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b"[]"
        context = MagicMock()
        context.__enter__.return_value = response
        context.__exit__.return_value = False
        with patch.object(main, "urlopen", return_value=context) as open_mock:
            self.assertEqual(main._fetch_portfolio_holdings(), [])
        request = open_mock.call_args.args[0]
        self.assertEqual(request.full_url, settings.backend_url.rstrip("/") + "/api/v1/portfolio/holdings")
        self.assertEqual(open_mock.call_args.kwargs["timeout"], 5)


if __name__ == "__main__":
    unittest.main()
