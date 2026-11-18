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
        with patch.dict("os.environ",env,clear=False),patch.object(ai,"_generate",side_effect=fake_generate),patch.object(ai.ai_budgets,"reserve",return_value=True):
            result=ai.analyze_market({"symbol":"AAPL","sector":"Technology"})
            self.assertEqual(result["provider"],"GROQ")
            self.assertEqual(result["attempts"][0]["status"],"FAILED")
    def test_paid_providers_blocked(self):
        env={"ATLAS_EXTERNAL_AI_ALLOWED":"true","ATLAS_OPENAI_ENABLED":"true",
             "OPENAI_API_KEY":"test","ATLAS_PAID_AI_ALLOWED":"false"}
        with patch.dict("os.environ",env,clear=False):
            self.assertFalse(ai._enabled("OPENAI"))
    def test_ollama_endpoint_is_local_and_configurable_for_docker(self):
        with patch.dict("os.environ",{"ATLAS_OLLAMA_URL":"http://host.docker.internal:11434"},clear=False):
            self.assertEqual(ai._ollama_url(),"http://host.docker.internal:11434")
        with patch.dict("os.environ",{"ATLAS_OLLAMA_URL":"https://example.test/ollama"},clear=False):
            with self.assertRaises(ai.AIProviderError):
                ai._ollama_url()
    def test_openai_uses_responses_api_without_storage(self):
        response={"output":[{"type":"message","content":[
            {"type":"output_text","text":"safe result"}]}]}
        env={"OPENAI_API_KEY":"test","ATLAS_OPENAI_MODEL":"gpt-4.1-mini"}
        with patch.dict("os.environ",env,clear=False),patch.object(ai,"_post",return_value=response) as post:
            self.assertEqual(ai._generate("OPENAI","prompt"),"safe result")
        self.assertEqual(post.call_args.args[0],"https://api.openai.com/v1/responses")
        self.assertFalse(post.call_args.args[2]["store"])
        self.assertNotIn("messages",post.call_args.args[2])
        self.assertEqual(post.call_args.args[2]["text"]["format"]["type"],"json_schema")
        self.assertTrue(post.call_args.args[2]["text"]["format"]["strict"])
    def test_gemini_requests_structured_json(self):
        response={"candidates":[{"content":{"parts":[{"text":"{}"}]}}]}
        env={"GEMINI_API_KEY":"test","ATLAS_GEMINI_MODEL":"gemini-3.5-flash-lite"}
        with patch.dict("os.environ",env,clear=False),patch.object(ai,"_post",return_value=response) as post:
            self.assertEqual(ai._generate("GEMINI","prompt"),"{}")
        config=post.call_args.args[2]["generationConfig"]
        self.assertEqual(config["responseMimeType"],"application/json")
        self.assertEqual(config["responseJsonSchema"],ai.VERDICT_SCHEMA)
    def test_groq_requests_json_object(self):
        response={"choices":[{"message":{"content":"{}"}}]}
        env={"GROQ_API_KEY":"test","ATLAS_GROQ_MODEL":"llama-3.3-70b-versatile"}
        with patch.dict("os.environ",env,clear=False),patch.object(ai,"_post",return_value=response) as post:
            self.assertEqual(ai._generate("GROQ","prompt"),"{}")
        self.assertEqual(post.call_args.args[2]["response_format"],{"type":"json_object"})
    def test_health_distinguishes_configuration_from_verified_connection(self):
        env={"ATLAS_GEMINI_ENABLED":"true","ATLAS_EXTERNAL_AI_ALLOWED":"true",
             "GEMINI_API_KEY":"test","ATLAS_GEMINI_RPM":"2","ATLAS_GEMINI_RPD":"30"}
        with patch.dict("os.environ",env,clear=False),patch.object(ai.ai_budgets,"usage",return_value={}),patch.object(ai,"_LAST_SUCCESS",{}):
            health=ai.provider_health()
        gemini=next(p for p in health["providers"] if p["name"]=="GEMINI")
        self.assertEqual(gemini["configuration_status"],"READY_TO_CALL")
        self.assertFalse(health["active_connection_verified"])
if __name__=="__main__":
    unittest.main()
