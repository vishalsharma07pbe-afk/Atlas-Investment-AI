"""Configuration and portfolio transport regression checks (no network calls)."""
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from starlette.requests import Request
from fastapi import HTTPException

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
        caller=Request({"type":"http","method":"GET","path":"/","headers":[
            (b"authorization",b"Bearer synthetic-session"),(b"x-atlas-owner",b"spoofed"),
            (b"x-atlas-service-token",b"not-forwarded")]})
        with patch.object(main, "build_opener") as build:
            open_mock=build.return_value.open
            open_mock.return_value=context
            self.assertEqual(main._fetch_portfolio_holdings(caller), [])
        request = open_mock.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"),"Bearer synthetic-session")
        self.assertEqual(set(k.lower() for k in request.headers),{"authorization","accept"})
        self.assertEqual(request.full_url, settings.backend_url.rstrip("/") + "/api/v1/portfolio/holdings")
        self.assertEqual(open_mock.call_args.kwargs["timeout"], 5)


    def test_cookie_and_revoked_session_fail_closed(self):
        caller=Request({"type":"http","method":"GET","path":"/","headers":[(b"cookie",b"ATLAS_SESSION=synthetic")]})
        with patch.object(main,"build_opener") as build:
            opened=build.return_value.open
            opened.side_effect=HTTPError(main._BACKEND_HOLDINGS_URL,401,"",{},None)
            with self.assertRaises(HTTPException) as ctx:
                main._fetch_portfolio_holdings(caller)
            self.assertEqual(ctx.exception.status_code,401)
            self.assertEqual(opened.call_args.args[0].get_header("Authorization"),"Bearer synthetic")
        anonymous=Request({"type":"http","method":"GET","path":"/","headers":[]})
        with patch.object(main,"build_opener") as build:
            with self.assertRaises(HTTPException) as ctx:
                main._fetch_portfolio_holdings(anonymous)
            self.assertEqual(ctx.exception.status_code,401)
            build.assert_not_called()

if __name__ == "__main__":
    unittest.main()
