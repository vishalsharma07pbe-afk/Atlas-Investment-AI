from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

def test_internal_ai_endpoints_reject_anonymous():
    client=TestClient(app)
    with patch.dict("os.environ",{"INTERNAL_SERVICE_TOKEN":"a"*40}):
        assert client.get("/api/v1/ai/providers/health").status_code==401
        assert client.post("/api/v1/ai/analyze/TCS",json={"symbol":"TCS","market":"NSE"}).status_code==401

def test_health_accepts_internal_token():
    client=TestClient(app)
    with patch.dict("os.environ",{"INTERNAL_SERVICE_TOKEN":"a"*40}):
        response=client.get("/api/v1/ai/providers/health",headers={"X-Atlas-Service-Token":"a"*40})
        assert response.status_code==200
