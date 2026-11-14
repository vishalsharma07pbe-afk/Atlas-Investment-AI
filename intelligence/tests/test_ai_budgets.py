import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from app import ai_budgets

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=patch.object(ai_budgets,"DB_PATH",Path(self.tmp.name)/"budgets.sqlite3")
        self.path.start()
    def tearDown(self):
        self.path.stop()
        self.tmp.cleanup()
    def test_minute_limit_and_new_minute(self):
        now=datetime(2026,11,14,8,0,tzinfo=timezone.utc)
        with patch.dict("os.environ",{"ATLAS_GEMINI_RPM":"2","ATLAS_GEMINI_RPD":"3"},clear=False):
            self.assertTrue(ai_budgets.reserve("GEMINI",now))
            self.assertTrue(ai_budgets.reserve("GEMINI",now))
            self.assertFalse(ai_budgets.reserve("GEMINI",now))
            self.assertTrue(ai_budgets.reserve("GEMINI",now+timedelta(minutes=1)))
            self.assertFalse(ai_budgets.reserve("GEMINI",now+timedelta(minutes=2)))
            self.assertTrue(ai_budgets.reserve("GEMINI",now+timedelta(days=1)))
    def test_disabled_paid_by_default(self):
        with patch.dict("os.environ",{"ATLAS_OPENAI_RPM":"0","ATLAS_OPENAI_RPD":"0"},clear=False):
            self.assertFalse(ai_budgets.reserve("OPENAI"))
    def test_invalid_config(self):
        with patch.dict("os.environ",{"ATLAS_GROQ_RPM":"unlimited"},clear=False):
            with self.assertRaisesRegex(ValueError,"INVALID_AI_BUDGET"):
                ai_budgets.reserve("GROQ")
    def test_usage(self):
        now=datetime(2026,11,14,8,0,tzinfo=timezone.utc)
        self.assertTrue(ai_budgets.reserve("OLLAMA",now))
        self.assertEqual(ai_budgets.usage("OLLAMA",now)["day_used"],1)
if __name__=="__main__":
    unittest.main()
