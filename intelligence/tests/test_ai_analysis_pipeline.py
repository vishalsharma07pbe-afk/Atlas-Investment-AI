import asyncio
import json
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from app.sanitizer import build_payload
from app import consensus

def verdict(action="HOLD"):
    return json.dumps({"action":action,"confidence":0.6,"target_1":None,"target_2":None,
                       "stop_loss":None,"holding_horizon":"SWING",
                       "pros":["Observed trend"],"cons":["Uncertainty"]})

class PipelineTests(unittest.TestCase):
    def test_private_fields_rejected(self):
        for field in ("quantity","average_cost","account_id","access_token","portfolio_value"):
            with self.assertRaises(ValidationError):
                build_payload("RELIANCE",{field:"private"})
    def test_safe_indicators(self):
        result=build_payload("RELIANCE",{"market":"NSE","price_change_pct":2.0})
        self.assertEqual(result["symbol"],"RELIANCE")
    def test_parallel_consensus_conflict(self):
        def fake(provider,prompt):
            return verdict("BUY" if provider=="GEMINI" else "HOLD")
        with patch.object(consensus,"_order",return_value=["OLLAMA","GEMINI"]),\
             patch.object(consensus,"_enabled",return_value=True),\
             patch.object(consensus,"reserve",return_value=True),\
             patch.object(consensus,"_generate",side_effect=fake):
            result=asyncio.run(consensus.committee("RELIANCE",{"market":"NSE"}))
        self.assertTrue(result["consensus"]["conflict"])
        self.assertIsNone(result["consensus"]["majority_action"])
        self.assertFalse(result["actionable"])
    def test_budget_skips_provider(self):
        with patch.object(consensus,"_order",return_value=["GROQ"]),\
             patch.object(consensus,"_enabled",return_value=True),\
             patch.object(consensus,"reserve",return_value=False):
            result=asyncio.run(consensus.committee("TCS",{"market":"NSE"}))
        self.assertEqual(result["providers"][0]["status"],"BUDGET_EXHAUSTED")
if __name__=="__main__":
    unittest.main()
