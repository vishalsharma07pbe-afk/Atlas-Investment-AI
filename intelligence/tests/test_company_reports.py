import tempfile
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from app import company_reports as reports,automatic_ai_review as ai,autonomous_research as research

NOW=datetime(2026,11,27,10,tzinfo=timezone.utc)
ISIN="INE002A01018"
def fixture():
    shared={"isin":ISIN,"retrieved_at":NOW.isoformat(),"sections":{}}
    def item(exchange,id):
        return {"id":id,"symbol":"TEST","isin":ISIN,"exchange":exchange,"as_of":"2026-11-26","close":100+id,
           "history_count":220,"atr_percent":2,"adjustment_status":"ADJUSTED","company_evidence":shared,"private_balance":123456789}
    n,b=item("NSE",1),item("BSE",2)
    def section(exchange,row):
        return {"section":exchange,"status":"READY","result":{"discovery_coverage":{"calendar_status":"PUBLISHED_SESSION",
            "calendar_checked_on":"2026-11-27","expected_session":"2026-11-26"},"horizons":{
            "SWING":{"status":"TECHNICAL_WATCH_ONLY","candidates":[row]},
            "LONG_TERM":{"status":"TECHNICAL_WATCH_ONLY","candidates":[dict(row)]}}}}
    elite={**n,"status":"SCREEN_MATCH_ONLY"}
    return {"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":"2026-11-27",
            "sections":[section("NSE",n),section("BSE",b)],"steady_momentum":{"items":[elite],"category_items":{"LARGE_CAP":[elite]}}}

class CompanyReportTests(unittest.TestCase):
    def test_one_company_pack_all_scoped_observations_no_private_fields(self):
        data=fixture()
        entries=list(ai.candidates(data,["OLLAMA"]))
        self.assertEqual(len({key for _,_,key in entries}),1)
        pack=entries[0][1]
        self.assertEqual(pack["company_isin"],ISIN)
        self.assertEqual(len(pack["listing_observations"]),5)
        self.assertNotIn("123456789",str(pack))
        self.assertEqual({v["exchange"] for v in pack["listing_observations"]},{"NSE","BSE"})
        self.assertIn("COMPANY",ai._supplied(pack))
        reports.attach(data,NOW)
        result=data["company_reports"]["items"][ISIN]
        self.assertEqual(len(result["observations"]),5)
        self.assertFalse(result["qualified"])
        self.assertEqual(result["company_evidence"]["isin"],ISIN)
    def test_one_provider_review_reused_and_changes_invalidate_all(self):
        data=fixture()
        calls=[]
        def runner(prompt,ids,providers):
            calls.append(prompt)
            return {"status":"MODEL_GROUNDED","provider":"OLLAMA","response":{"findings":[
                {"statement":'{"path":"/COMPANY/isin","value":"INE002A01018"}',"evidence_ids":["COMPANY"]}]}}
        with tempfile.TemporaryDirectory() as tmp,patch.dict("os.environ",{"ATLAS_RESEARCH_SNAPSHOT_DB":tmp+"/research.sqlite"}),patch.object(ai,"enabled",return_value=True),patch.object(ai,"providers",return_value=["OLLAMA"]):
            ai.refresh(data,research._connect,runner)
            ai.refresh(data,research._connect,runner)
            self.assertEqual(len(calls),1)
            ai.attach(data,research._connect)
            self.assertTrue(all(r.get("ai_review",{}).get("company_isin")==ISIN for _,r in reports.entries(data)))
            reports.attach(data,NOW)
            self.assertIsNotNone(data["company_reports"]["items"][ISIN]["ai_review"])
            data["sections"][1]["result"]["horizons"]["SWING"]["candidates"][0]["close"]=105
            ai.attach(data,research._connect)
            self.assertTrue(all("ai_review" not in r for _,r in reports.entries(data)))
    def test_stale_and_conflicting_sources_not_unified(self):
        data=fixture()
        data["sections"][1]["status"]="STALE"
        reports.attach(data,NOW)
        self.assertEqual(data["company_reports"]["items"][ISIN]["observed_venues"],["NSE"])
        data["sections"][0]["result"]["horizons"]["SWING"]["candidates"].append(
            {**data["sections"][0]["result"]["horizons"]["SWING"]["candidates"][0],"close":999})
        self.assertEqual(list(ai.candidates(data,["OLLAMA"])),[])
        reports.attach(data,NOW)
        self.assertEqual(data["company_reports"]["items"],{})
