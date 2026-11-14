import unittest
import tempfile
from pathlib import Path
from app import ai_budgets
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

class InternalAuthTests(unittest.TestCase):
    def test_internal_ai_endpoints_reject_anonymous(self):
        client=TestClient(app)
        with patch.dict("os.environ",{"INTERNAL_SERVICE_TOKEN":"a"*40}):
            self.assertEqual(client.get("/api/v1/ai/providers/health").status_code,401)
            self.assertEqual(client.post("/api/v1/ai/analyze/TCS",json={"symbol":"TCS","market":"NSE"}).status_code,401)

    def test_health_accepts_internal_token(self):
        client=TestClient(app)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ai_budgets,"DB_PATH",Path(directory)/"ai_budgets.sqlite3"), patch.dict("os.environ",{"INTERNAL_SERVICE_TOKEN":"a"*40}):
                response=client.get("/api/v1/ai/providers/health",headers={"X-Atlas-Service-Token":"a"*40})
                self.assertEqual(response.status_code,200)
