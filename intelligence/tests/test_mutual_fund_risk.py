import unittest
from pydantic import ValidationError
from app.mutual_fund_risk import FundRiskRequest,assess_fund_risk

class FundRiskTests(unittest.TestCase):
    def test_weights_and_effective_positions(self):
        request=FundRiskRequest(positions=[
            {"holding_id":1,"label":"A","recorded_value":"75"},
            {"holding_id":2,"label":"B","recorded_value":"25"}])
        result=assess_fund_risk(request)
        self.assertEqual(result["status"],"COMPLETE_RECORDED_WEIGHTS")
        self.assertEqual(result["largest_weight_pct"],"75.00")
        self.assertEqual(result["top_three_weight_pct"],"100.00")
        self.assertEqual(result["hhi"],"6250.00")
        self.assertEqual(result["effective_holdings"],"1.60")
        self.assertFalse(result["stored"])
    def test_incomplete_portfolio_blocks_full_value(self):
        result=assess_fund_risk(FundRiskRequest(positions=[
            {"holding_id":1,"label":"A","recorded_value":"100"},
            {"holding_id":2,"label":"B","recorded_value":None}]))
        self.assertIsNone(result["full_portfolio_value"])
        self.assertEqual(result["status"],"PARTIAL_OR_UNAVAILABLE")
        self.assertIn("INCOMPLETE_VALUATION",[d["code"] for d in result["diagnostics"]])
    def test_zero_value_has_no_fabricated_weights(self):
        result=assess_fund_risk(FundRiskRequest(positions=[
            {"holding_id":1,"label":"A","recorded_value":"0"}]))
        self.assertIsNone(result["hhi"])
        self.assertEqual(result["weights"],[])
    def test_duplicate_and_nonfinite_rejected(self):
        with self.assertRaises(ValidationError):FundRiskRequest(positions=[
            {"holding_id":1,"label":"A","recorded_value":"1"},
            {"holding_id":1,"label":"B","recorded_value":"2"}])
        with self.assertRaises(ValidationError):FundRiskRequest(positions=[
            {"holding_id":1,"label":"A","recorded_value":"Infinity"}])

if __name__=="__main__":unittest.main()
