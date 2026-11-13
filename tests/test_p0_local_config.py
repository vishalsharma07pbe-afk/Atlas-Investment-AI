"""Regression coverage for P0 local configuration gate."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_p0_local_config.py"
spec = importlib.util.spec_from_file_location("p0_config_gate", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class LocalConfigurationGateTests(unittest.TestCase):
    def test_rejects_placeholder_password(self):
        self.assertTrue(module.validate({"POSTGRES_PASSWORD": "replace_with_a_unique_random_password"}))

    def test_accepts_safe_manual_local_configuration(self):
        self.assertEqual(module.validate({"POSTGRES_PASSWORD": "a-unique-local-secret", "MARKET_DATA_PROVIDER": "MANUAL_CSV"}), [])

    def test_blocks_auto_refresh_without_rights(self):
        issues = module.validate({"POSTGRES_PASSWORD": "unique", "MARKET_DATA_AUTO_REFRESH": "true"})
        self.assertTrue(any("rights" in issue for issue in issues))
        self.assertTrue(any("token" in issue for issue in issues))

    def test_blocks_feed_without_entitlement(self):
        issues = module.validate({"POSTGRES_PASSWORD": "unique", "ATLAS_UPSTOX_FEED_ENABLED": "true", "MARKET_DATA_USAGE_RIGHTS_CONFIRMED": "true", "UPSTOX_ACCESS_TOKEN": "private"})
        self.assertTrue(any("entitlement" in issue for issue in issues))
        self.assertFalse(any("private" in issue for issue in issues))

    def test_rejects_unknown_provider(self):
        self.assertTrue(any("Unknown" in issue for issue in module.validate({"POSTGRES_PASSWORD": "unique", "MARKET_DATA_PROVIDER": "UNKNOWN"})))

    def test_parses_comments_without_echoing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("# secret config\\nPOSTGRES_PASSWORD=unique\\nMARKET_DATA_PROVIDER=MANUAL_CSV\\n", encoding="utf-8")
            self.assertEqual(module.parse_env(path)["POSTGRES_PASSWORD"], "unique")


if __name__ == "__main__":
    unittest.main()
