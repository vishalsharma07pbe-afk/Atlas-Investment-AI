import unittest
from decimal import Decimal
from pydantic import ValidationError
from app.goal_planning import GoalRequest,goal_projection
from app import main

class GoalPlanningTests(unittest.TestCase):
    def test_zero_return_and_required_monthly(self):
        request=GoalRequest(target_amount="1200",initial_amount="0",monthly_contribution="100",months=12,annual_return_percent="0")
        result=goal_projection(request)
        self.assertEqual(result["status"],"TARGET_MET")
        self.assertEqual(result["projected_value"],"1200.00")
        self.assertEqual(result["required_monthly_contribution"],"100.00")
        self.assertEqual(result["hypothetical_growth"],"0.00")
    def test_initial_savings_reduce_required_contribution(self):
        result=goal_projection(GoalRequest(target_amount="1000",initial_amount="1000",monthly_contribution="0",months=12,annual_return_percent="0"))
        self.assertEqual(result["required_monthly_contribution"],"0.00")
    def test_negative_return_and_shortfall(self):
        result=goal_projection(GoalRequest(target_amount="1000",monthly_contribution="100",months=10,annual_return_percent="-12"))
        self.assertEqual(result["status"],"TARGET_SHORTFALL")
        self.assertGreater(Decimal(result["required_monthly_contribution"]),Decimal("100"))
    def test_compounding_and_checkpoints(self):
        result=goal_projection(GoalRequest(target_amount="5000",initial_amount="100",monthly_contribution="100",months=25,annual_return_percent="12"))
        self.assertEqual([c["month"] for c in result["checkpoints"]],[12,24,25])
        self.assertGreater(Decimal(result["hypothetical_growth"]),0)
    def test_invalid_input_rejected(self):
        for kwargs in [{"months":0},{"annual_return_percent":100},{"target_amount":-1},{"monthly_contribution":-1}]:
            with self.assertRaises(ValidationError):GoalRequest(target_amount=1000,months=12,**kwargs)
    def test_api(self):
        result=main.planning_goal_projection(GoalRequest(target_amount=1200,months=12,monthly_contribution=100))
        self.assertEqual(result["status"],"TARGET_MET")
if __name__=="__main__":unittest.main()
