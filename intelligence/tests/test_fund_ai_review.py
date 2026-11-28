import unittest,json
from app import fund_ai_review as f,automatic_ai_review as ai
class FundAIReviewTests(unittest.TestCase):
    def test_public_pack_excludes_arbitrary_fields_and_never_promotes(self):
        row={"identifier":"123456","name":"PRIVATE_MARKER","portfolio_date":"2026-10-31","quarter":"2026-09-30","nav_date":"2026-11-26",
             "joint_coverage_weight_percent":80,"joint_growth_weight_percent":70,"review_weight_percent":10,
             "qualified":False,"forecast_return_percent":None,"private_marker":"DO_NOT_FORWARD"}
        snapshot={"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":"2026-11-27","sections":[
          {"section":"LARGE_CAP","status":"READY","result":{"category":"LARGE_CAP","growth_driver_review":{
            "methodology":"MF-QUARTERLY-DRIVERS-1","status":"MATCHED_HISTORICAL_DRIVERS","items":[row]}}}]}
        _,pack,_=next(f.candidates(snapshot,["OLLAMA"]))
        supplied=ai._supplied(pack)
        self.assertNotIn("PRIVATE_MARKER",str(supplied));self.assertNotIn("DO_NOT_FORWARD",str(supplied))
        def runner(prompt,ids,providers):
            self.assertNotIn("PRIVATE_MARKER",prompt)
            return {"status":"MODEL_GROUNDED","provider":"OLLAMA","response":{"findings":[
                {"statement":json.dumps({"path":"/OBS/joint_growth_weight_percent","value":70}),"evidence_ids":["OBS"]}]}}
        self.assertEqual(ai._review(pack,"OLLAMA",runner)["claim_audit"]["claims"][0]["status"],"MATCHED")
        row["qualified"]=True
        self.assertFalse(list(f.candidates(snapshot)))
