import os
import tempfile
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import portfolio_thesis as thesis, automatic_company_evidence as company
from app.main import app

class PortfolioThesisTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":tmp.name+"/research.sqlite",
            "ATLAS_AUTONOMOUS_RESEARCH_ENABLED":"true","ATLAS_PORTFOLIO_THESIS_ENABLED":"true",
            "INTERNAL_SERVICE_TOKEN":"test-service-token-"+"x"*32})
        env.start()
        self.addCleanup(env.stop)
        self.rows=[{"isin":"INE002A01018","exchange":"NSE","quantity":123,"owner":"private-owner"}]

    def test_selection_strips_private_fields_and_rejects_unmapped_identity(self):
        selection=thesis.selection(self.rows+[{"isin":"bad","exchange":"NSE"}])
        self.assertNotIn("private-owner",str(selection))
        self.assertNotIn("quantity",str(selection))
        self.assertEqual(len(thesis._items(selection)),1)

    def test_local_model_only_and_evidence_hash(self):
        item=thesis._items(thesis.selection(self.rows))[0]
        item["company_evidence"]={"sections":{"ratios":{"data":[{"name":"P/E","company_value":20,"sector_value":15,"unit":"RATIO"},{"name":"Unknown ratio","company_value":999}]}}}
        def runner(prompt,ids,providers):
            self.assertEqual(providers,["OLLAMA"])
            self.assertNotIn("private-owner",prompt)
            self.assertNotIn("999",prompt)
            return {"status":"MODEL_GROUNDED","provider":"OLLAMA","response":{"findings":[{"statement":"Company ratio exceeds the sector ratio.","evidence_ids":["RATIOS"]}]}}
        with patch.object(thesis,"_local_enabled",return_value=True):
            thesis._review([item],thesis.connect,runner,datetime.now(timezone.utc))
            with thesis.connect() as db:
                self.assertEqual(db.execute("SELECT status FROM portfolio_local_ai").fetchone()[0],"AVAILABLE")

    def test_internal_read_requires_token_and_rejects_private_fields(self):
        client=TestClient(app)
        payload={"identities":[{"isin":"INE002A01018","exchange":"NSE"}]}
        self.assertEqual(client.post("/api/v1/internal/portfolio-thesis",json=payload).status_code,401)
        headers={"X-Atlas-Service-Token":os.environ["INTERNAL_SERVICE_TOKEN"]}
        self.assertEqual(client.post("/api/v1/internal/portfolio-thesis",json={"identities":self.rows},headers=headers).status_code,422)
        with patch.object(thesis,"read",return_value={"items":{}}) as read:
            self.assertEqual(client.post("/api/v1/internal/portfolio-thesis",json=payload,headers=headers).status_code,200)
            read.assert_called_once_with(payload["identities"])

    def test_cache_path_is_not_public_snapshot_db(self):
        from app import autonomous_research
        with thesis.connect() as private,autonomous_research._connect() as public:
            self.assertNotEqual(private.execute("PRAGMA database_list").fetchone()[2],public.execute("PRAGMA database_list").fetchone()[2])
