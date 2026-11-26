import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

from app import quote_recovery as recovery, multi_provider_quotes as multi


class QuoteRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path=Path(directory.name)/"recovery.sqlite"
        env=patch.dict("os.environ",{"ATLAS_QUOTE_RECOVERY_DB":str(self.path)})
        env.start()
        self.addCleanup(env.stop)

    def state(self,provider,now):
        return next(r for r in recovery.status(now)["providers"] if r["provider"]==provider)

    def test_no_observation_does_not_create_storage(self):
        self.assertEqual(self.state("UPSTOX",100)["state"],"NOT_OBSERVED")
        self.assertFalse(self.path.exists())

    def test_persisted_access_cooldown_and_single_recovery_probe(self):
        claim=recovery.claim("UPSTOX",100)
        self.assertTrue(claim)
        self.assertIsNone(recovery.claim("UPSTOX",101))
        self.assertTrue(recovery.finish("UPSTOX",claim,"PROVIDER_ACCESS_REJECTED",now=102))
        self.assertEqual(self.state("UPSTOX",103)["state"],"OPEN")
        self.assertIsNone(recovery.claim("UPSTOX",1001))
        self.assertEqual(self.state("UPSTOX",1002)["state"],"RECOVERY_PROBE_DUE")
        probe=recovery.claim("UPSTOX",1002)
        self.assertTrue(probe)
        self.assertIsNone(recovery.claim("UPSTOX",1003))
        self.assertFalse(recovery.finish("UPSTOX",claim,now=1004))
        self.assertTrue(recovery.finish("UPSTOX",probe,now=1004))
        self.assertEqual(self.state("UPSTOX",1004)["state"],"CLOSED")

    def test_rate_limit_honors_retry_after_and_isolated_provider(self):
        token=recovery.claim("UPSTOX",100)
        recovery.finish("UPSTOX",token,"PROVIDER_RATE_LIMITED",retry_after=120,now=101)
        self.assertIsNone(recovery.claim("UPSTOX",220))
        self.assertTrue(recovery.claim("POLYGON",220))
        self.assertTrue(recovery.claim("UPSTOX",221))

    def test_expired_lease_rejects_late_completion(self):
        token=recovery.claim("UPSTOX",100)
        replacement=recovery.claim("UPSTOX",100+recovery.LEASE)
        self.assertNotEqual(token,replacement)
        self.assertFalse(recovery.finish("UPSTOX",token,now=131))
        self.assertTrue(recovery.finish("UPSTOX",replacement,now=132))

    def test_http_rejection_shared_across_quote_and_fundamentals(self):
        response=Mock(status_code=429,headers={"Retry-After":"120"})
        with patch.object(multi.httpx,"get",return_value=response) as request:
            with self.assertRaisesRegex(multi.ProviderFailure,"PROVIDER_RATE_LIMITED"):
                multi._request("https://api.upstox.com/v3/market-quote/quotes",{"Authorization":"Bearer secret"})
            with self.assertRaisesRegex(multi.ProviderFailure,"PROVIDER_RECOVERY_COOLDOWN"):
                multi._request("https://api.upstox.com/v2/fundamentals/test",{"Authorization":"Bearer secret"})
            request.assert_called_once()
        self.assertNotIn(b"secret",self.path.read_bytes())

    def test_storage_error_blocks_external_request(self):
        self.path.write_bytes(b"not sqlite")
        with patch.object(multi.httpx,"get") as request:
            with self.assertRaisesRegex(multi.ProviderFailure,"RECOVERY_STORAGE_UNAVAILABLE"):
                multi._request("https://api.upstox.com/v3/market-quote/quotes",{})
            request.assert_not_called()

    def test_dhan_success_respects_minimum_request_interval(self):
        token=recovery.claim("DHAN",100)
        self.assertTrue(token)
        self.assertTrue(recovery.finish("DHAN",token,now=101))
        self.assertIsNone(recovery.claim("DHAN",101.5))
        self.assertTrue(recovery.claim("UPSTOX",101.5))
        self.assertTrue(recovery.claim("DHAN",102))
