import unittest
from app.provider_readiness import ProviderConfig,provider_readiness

def config(**kwargs):
    base=dict(provider="UPSTOX",access_token="super-secret-test-token",
        automatic_refresh=True,licensed_data_access=True,
        entitlement_confirmed=True,rate_per_second=1.0)
    base.update(kwargs)
    return ProviderConfig(**base)

class ProviderReadinessTests(unittest.TestCase):
    def test_all_flags_still_block_without_verified_adapter(self):
        result=provider_readiness(config())
        self.assertEqual(result["status"],"NOT_READY")
        self.assertFalse(result["automatic_collection_enabled"])
        self.assertIn("LIVE_PROVIDER_ADAPTER_NOT_VERIFIED",result["blockers"])
        self.assertNotIn("super-secret-test-token",str(result))

    def test_missing_entitlements_and_credentials_block(self):
        result=provider_readiness(config(access_token=None,licensed_data_access=False,
            entitlement_confirmed=False))
        self.assertIn("MISSING_ACCESS_TOKEN",result["blockers"])
        self.assertIn("DATA_USAGE_RIGHTS_NOT_CONFIRMED",result["blockers"])
        self.assertIn("MARKET_DATA_ENTITLEMENT_NOT_CONFIRMED",result["blockers"])

    def test_manual_mode_never_collects(self):
        result=provider_readiness(config(provider="MANUAL_CSV",access_token=None))
        self.assertIn("MANUAL_IMPORT_ONLY",result["blockers"])
        self.assertFalse(result["automatic_collection_enabled"])

    def test_invalid_rate_and_disabled_refresh(self):
        result=provider_readiness(config(rate_per_second=0,automatic_refresh=False))
        self.assertIn("INVALID_RATE_LIMIT",result["blockers"])
        self.assertIn("AUTOMATIC_REFRESH_DISABLED",result["blockers"])

if __name__=="__main__":
    unittest.main()
