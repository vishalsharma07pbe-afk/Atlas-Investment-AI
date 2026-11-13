import unittest
from decimal import Decimal
from pydantic import ValidationError
from app.mutual_fund_planning import FundPlanningRequest,plan_funds

class FundPlanningTests(unittest.TestCase):
    def payload(self):
        return {"sip":{"monthly_contribution":"1000","annual_return_pct":"0","years":2,"annual_step_up_pct":"10","initial_amount":"500"},
                "positions":[{"holding_id":1,"label":"Fund A","invested":"100","recorded_value":"150"},
                             {"holding_id":2,"label":"Fund B","invested":"100","recorded_value":"50"}]}
    def test_zero_return_step_up_and_weights(self):
        result=plan_funds(FundPlanningRequest(**self.payload()))
        self.assertEqual(result["projection"]["contributed"],"25700.00")
        self.assertEqual(result["projection"]["projected_value"],"25700.00")
        self.assertEqual(result["projection"]["projected_gain"],"0.00")
        self.assertEqual(result["portfolio"]["recorded_total"],"200.00")
        self.assertEqual(result["portfolio"]["largest_holding_weight_pct"],"75.00")
        self.assertEqual(len(result["projection"]["annual_snapshots"]),2)
        self.assertFalse(result["stored"])
    def test_unpriced_portfolio_is_partial(self):
        data=self.payload();data["positions"][1]["recorded_value"]=None
        result=plan_funds(FundPlanningRequest(**data))
        self.assertFalse(result["portfolio"]["complete"])
        self.assertIsNone(result["portfolio"]["recorded_total"])
        self.assertEqual(result["portfolio"]["priced_subset_total"],"150.00")
    def test_negative_return_does_not_invent_profit(self):
        data=self.payload();data["sip"]["annual_return_pct"]="-20"
        result=plan_funds(FundPlanningRequest(**data))
        self.assertLess(Decimal(result["projection"]["projected_value"]),Decimal(result["projection"]["contributed"]))
    def test_nonfinite_and_duplicate_rejected(self):
        data=self.payload();data["sip"]["monthly_contribution"]="NaN"
        with self.assertRaises(ValidationError):FundPlanningRequest(**data)
        data=self.payload();data["positions"][1]["holding_id"]=1
        with self.assertRaises(ValidationError):FundPlanningRequest(**data)

if __name__=="__main__":unittest.main()
