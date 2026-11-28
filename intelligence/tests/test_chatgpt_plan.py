import unittest
from unittest.mock import patch
from app import chatgpt_plan as p, ai_failover as ai

class ChatGPTPlanTest(unittest.TestCase):
    def test_stream_requires_completed_and_handles_limit(self):
        self.assertEqual(p.parse_stream(['data: {"type":"response.output_text.delta","delta":"ok"}','data: {"type":"response.completed"}']),"ok")
        with self.assertRaisesRegex(p.PlanError,"PLAN_INCOMPLETE"):
            p.parse_stream(['data: {"type":"response.output_text.delta","delta":"partial"}'])
        with self.assertRaisesRegex(p.PlanError,"PLAN_USAGE_LIMIT"):
            p.parse_stream(['data: {"type":"response.failed","response":{"error":{"code":"subscription_sharing_usage_limit_exceeded"}}}'])
    def test_identity_only_not_enough(self):
        with self.assertRaisesRegex(p.PlanError,"PLAN_PERMISSION_REQUIRED"):
            p.token_record({"scope":"openid email"})
    def test_router_uses_plan_not_paid_api(self):
        with patch.object(p,"generate",return_value="{}") as generate:
            self.assertEqual(ai._generate("CHATGPT_PLAN","public prompt"),"{}")
            generate.assert_called_once()
        with patch.dict("os.environ",{"ATLAS_CHATGPT_PLAN_ENABLED":"true","ATLAS_CHATGPT_PLAN_INCLUDED_ONLY_CONFIRMED":"false","ATLAS_EXTERNAL_AI_ALLOWED":"true","ATLAS_PAID_AI_ALLOWED":"false"}):
            self.assertEqual(ai._configuration_status("CHATGPT_PLAN"),"PLAN_USAGE_CONFIRMATION_REQUIRED")
