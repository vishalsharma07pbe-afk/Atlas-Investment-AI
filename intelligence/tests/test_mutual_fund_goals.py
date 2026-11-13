import unittest
from decimal import Decimal
from pydantic import ValidationError
from app.mutual_fund_goals import FundGoalRequest,goal_plan

class GoalPlanningTests(unittest.TestCase):
    def test_zero_return_exact_goal(self):
        result=goal_plan(FundGoalRequest(target_amount="12000",years=1,annual_return_pct="0"))
        self.assertEqual(result["required_monthly_sip"],"1000.00")
        self.assertEqual(result["current_shortfall"],"12000.00")
        self.assertFalse(result["stored"])
    def test_existing_sip_reduces_shortfall(self):
        result=goal_plan(FundGoalRequest(target_amount="12000",years=1,annual_return_pct="0",current_monthly_sip="500"))
        self.assertEqual(result["current_shortfall"],"6000.00")
        self.assertEqual(result["additional_monthly_sip"],"500.00")
    def test_initial_amount_covers_goal(self):
        result=goal_plan(FundGoalRequest(target_amount="1000",years=1,annual_return_pct="0",initial_amount="2000"))
        self.assertEqual(result["required_monthly_sip"],"0.00")
        self.assertEqual(result["current_shortfall"],"0.00")
    def test_step_up_and_negative_return(self):
        result=goal_plan(FundGoalRequest(target_amount="100000",years=3,annual_return_pct="-10",annual_step_up_pct="10"))
        self.assertGreater(Decimal(result["required_monthly_sip"]),0)
        self.assertGreaterEqual(Decimal(result["required_plan"]["projected_value"]),Decimal("100000"))
    def test_invalid_inputs(self):
        with self.assertRaises(ValidationError):FundGoalRequest(target_amount="NaN",years=2,annual_return_pct="10")

if __name__=="__main__":unittest.main()
