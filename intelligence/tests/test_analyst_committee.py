import unittest
from app import analyst_committee as c
from app import investment_analyst as a
from datetime import date
class CommitteeTest(unittest.TestCase):
    def test_model_cannot_invent_evidence_or_promote_adverse_fund(self):
        e={"S1":{"tier":"ADJUSTED_JOINT","allowed_reasons":["JOINT_SCREEN","LIMITED_EVIDENCE"]},
           "F1":{"tier":"DRIVER_REVIEW","allowed_reasons":["HISTORICAL_PEERS","DRIVER_RISK"]}}
        import json
        def row(k,decision,reason):
            return {"statement":json.dumps({"candidate":k,"decision":decision,"reason":reason}),"evidence_ids":[k]}
        r=c.validate({"findings":[row("S1","PRIORITIZE_REVIEW","JOINT_SCREEN"),row("F1","PRIORITIZE_REVIEW","HISTORICAL_PEERS"),row("S2","PRIORITIZE_REVIEW","JOINT_SCREEN")]},e)
        self.assertEqual(set(r),{"S1"})
        self.assertEqual(c.validate({"findings":[row("S1","PRIORITIZE_REVIEW","POSITIVE_SCENARIO")]},e),{})
        self.assertEqual(c.validate({"findings":[row("S1","PRIORITIZE_REVIEW","JOINT_SCREEN"),row("S1","DEFER_REVIEW","LIMITED_EVIDENCE")]},e),{})
    def test_fund_growth_is_original_weight_scenario_not_nav_forecast(self):
        d={"quarter":"2026-09-30","experimental_forward":{"status":"UNCALIBRATED_PERSISTENCE_EXPERIMENT","qualified":False,
          "observed_quarter":"2026-09-30","target_quarter":"2026-12-31","covered_weight_percent":80,
          "positive_joint_growth_weight_percent":65,"covered_subset_revenue_persistence_percent":10,"covered_subset_profit_persistence_percent":15}}
        v=a.fund_growth(d,date(2026,11,28))
        self.assertEqual(v["coverage_percent"],80)
        self.assertEqual(v["profit_yoy_percent"],15)
        self.assertIsNone(a.fund_growth(d,date(2027,1,1)))
