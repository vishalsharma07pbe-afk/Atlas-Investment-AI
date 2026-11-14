import unittest
from unittest.mock import patch
from app import ai_failover as ai

class AIFailoverTests(unittest.TestCase):
    def test_default_is_offline(self):
        with patch.dict("os.environ",{"ATLAS_OLLAMA_ENABLED":"false","ATLAS_EXTERNAL_AI_ALLOWED":"false",
                                      "ATLAS_AI_PROVIDER_ORDER":"OLLAMA,GEMINI,GROQ"},clear=False):
            result=ai.analyze_market({"symbol":"RELIANCE","price_change_pct":1.2})
            self.assertEqual(result["status"],"UNAVAILABLE")
            self.assertTrue(all(a["status"]=="DISABLED" for a in result["attempts"]))
    def test_rejects_sensitive_fields(self):
        for data in ({"symbol":"AAPL","account_id":"123"},
                     {"symbol":"AAPL","news_summary":"access_token=secret"},
                     {"symbol":"AAPL","price_change_pct":float("nan")}):
            with self.assertRaises(ValueError):
                ai.analyze_market(data)
    def test_local_fallback_to_groq(self):
        env={"ATLAS_AI_PROVIDER_ORDER":"OLLAMA,GROQ","ATLAS_OLLAMA_ENABLED":"true",
             "ATLAS_EXTERNAL_AI_ALLOWED":"true","ATLAS_GROQ_ENABLED":"true","GROQ_API_KEY":"test"}
        def fake_generate(provider,prompt):
            if provider=="OLLAMA":
                raise ai.AIProviderError("UNAVAILABLE")
            self.assertNotIn("account_id",prompt)
            return "{\"action\":\"HOLD\",\"confidence\":0.6,\"target_1\":null,\"target_2\":null,\"stop_loss\":null,\"holding_horizon\":\"SWING\",\"pros\":[\"Market liquidity\"],\"cons\":[\"Trend uncertain\"]}"
        with patch.dict("os.environ",env,clear=False),patch.object(ai,"_generate",side_effect=fake_generate):
            result=ai.analyze_market({"symbol":"AAPL","sector":"Technology"})
            self.assertEqual(result["provider"],"GROQ")
            self.assertEqual(result["attempts"][0]["status"],"FAILED")
    def test_paid_providers_blocked(self):
        env={"ATLAS_EXTERNAL_AI_ALLOWED":"true","ATLAS_OPENAI_ENABLED":"true",
             "OPENAI_API_KEY":"test","ATLAS_PAID_AI_ALLOWED":"false"}
        with patch.dict("os.environ",env,clear=False):
            self.assertFalse(ai._enabled("OPENAI"))
if __name__=="__main__":
    unittest.main()
