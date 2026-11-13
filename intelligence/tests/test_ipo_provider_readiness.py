import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app.ipo_provider_readiness import inspect_provider

class ReadinessTests(unittest.TestCase):
    def test_missing_config_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=inspect_provider(Path(tmp)/"missing.json")
            self.assertEqual(result["status"],"NOT_CONFIGURED")
            self.assertFalse(result["ready"])
            self.assertFalse(result["network_requested"])
    def test_invalid_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"config.json";path.write_text('{"endpoint":"http://localhost"}')
            self.assertEqual(inspect_provider(path)["status"],"INVALID_CONFIG")
    def test_permissions_and_token_are_required_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"config.json"
            config={"name":"Licensed source","endpoint":"https://example.org/ipo",
                "token_env":"ATLAS_PROVIDER_IPO_TOKEN","enabled":False,
                "collection_authorized":False,"redistribution_authorized":False}
            path.write_text(json.dumps(config))
            with patch.dict(os.environ,{"ATLAS_PROVIDER_IPO_TOKEN":"top-secret"}),patch("socket.getaddrinfo",side_effect=AssertionError("No network")):
                blocked=inspect_provider(path)
                self.assertEqual(blocked["status"],"BLOCKED")
                self.assertNotIn("top-secret",json.dumps(blocked))
                config.update(enabled=True,collection_authorized=True,redistribution_authorized=True)
                path.write_text(json.dumps(config))
                ready=inspect_provider(path)
                self.assertEqual(ready["status"],"READY_FOR_CONNECTION_TEST")
                self.assertTrue(ready["ready"])
                self.assertEqual(ready["endpoint_host"],"example.org")
                self.assertFalse(ready["network_requested"])
    def test_missing_token_blocks_enabled_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"config.json"
            path.write_text(json.dumps({"name":"Licensed source","endpoint":"https://example.org/ipo",
                "token_env":"ATLAS_PROVIDER_IPO_TOKEN","enabled":True,
                "collection_authorized":True,"redistribution_authorized":True}))
            with patch.dict(os.environ,{},clear=True):
                result=inspect_provider(path)
                self.assertEqual(result["checks"]["token_environment"],"MISSING")
                self.assertFalse(result["ready"])
if __name__=="__main__":unittest.main()
