import io
import unittest
from datetime import date
from unittest.mock import patch
from app.providers.upstox import UpstoxHistoricalProvider

class HistoricalIdentityTests(unittest.TestCase):
    def test_daily_request_identifies_atlas_and_retains_authorization(self):
        class Response(io.BytesIO):
            status=200
        with patch("app.providers.upstox.urlopen",return_value=Response(
            b'{"status":"success","data":{"candles":[]}}')) as request:
            provider=UpstoxHistoricalProvider("synthetic-token",retries=0)
            self.assertEqual(provider.daily("NSE_EQ|INE002A01018",date(2026,11,24),date(2026,11,25)),[])
        req=request.call_args.args[0]
        self.assertEqual(req.get_header("User-agent"),"ATLAS/2.0")
        self.assertEqual(req.get_header("Authorization"),"Bearer synthetic-token")
        self.assertEqual(req.get_header("Accept"),"application/json")
        self.assertEqual(req.full_url,"https://api.upstox.com/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/2026-11-25/2026-11-24")
