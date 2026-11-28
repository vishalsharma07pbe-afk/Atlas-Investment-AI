import tempfile,unittest,io
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from app import global_macro as macro,quote_recovery as recovery

class GlobalPublisherRecoveryTest(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env=patch.dict("os.environ",{"ATLAS_QUOTE_RECOVERY_DB":str(Path(folder.name)/"recovery.sqlite")})
        env.start();self.addCleanup(env.stop)

    def test_fred_rate_limit_blocks_all_fred_series_but_not_eia(self):
        from email.message import Message
        headers=Message();headers["Retry-After"]="86400"
        error=HTTPError("https://api.stlouisfed.org/fred/series?api_key=private",429,"rate",headers,io.BytesIO())
        with patch.object(macro,"build_opener") as opener:
            opener.return_value.open.side_effect=error
            with self.assertRaisesRegex(ValueError,"^GLOBAL_SOURCE_REQUEST_FAILED$"):
                macro._download("https://api.stlouisfed.org/fred/series",{"api_key":"private"})
            with self.assertRaises(macro.GlobalCooldown):
                macro._download("https://api.stlouisfed.org/fred/series/observations",{})
            self.assertEqual(opener.call_count,1)
        status=recovery.status(global_sources=True)
        fred=next(p for p in status["providers"] if p["provider"]=="FRED")
        self.assertEqual(fred["state"],"OPEN")
        self.assertGreater(fred["retry_after_seconds"],86000)
        self.assertIsNotNone(recovery.claim("EIA"))
        self.assertNotIn("private",str(status))
        self.assertEqual([p["provider"] for p in recovery.status()["providers"]],["UPSTOX","POLYGON","DHAN"])

    def test_rejects_unapproved_host_without_network(self):
        with patch.object(macro,"build_opener") as opener:
            with self.assertRaises(ValueError):
                macro._download("https://www.bls.gov.evil.test/feed",{})
            opener.assert_not_called()
