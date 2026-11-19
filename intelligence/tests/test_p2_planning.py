import unittest
from pydantic import ValidationError

from app.p2_planning import PlanningRequest, personalized_plan


class PersonalizedPlanningTests(unittest.TestCase):
    def test_returns_risk_and_three_explicit_scenarios(self):
        request = PlanningRequest(target_amount=1000000, initial_amount=100000,
                                  monthly_contribution=10000, years=5,
                                  assumed_return_percent=8, inflation_percent=5,
                                  estimated_tax_drag_percent=1, emergency_months=6,
                                  income_stability=3, loss_tolerance=3, horizon_tolerance=3)
        result = personalized_plan(request)
        self.assertEqual(result["risk_profile"], "BALANCED")
        self.assertEqual([row["name"] for row in result["scenarios"]],
                         ["STRESS", "BASE_ASSUMPTION", "FAVOURABLE"])
        self.assertGreater(float(result["inflation_adjusted_target"]), 1000000)

    def test_flags_insufficient_emergency_reserve(self):
        request = PlanningRequest(target_amount=500000, initial_amount=1000,
                                  monthly_contribution=5000, years=3, emergency_months=1)
        result = personalized_plan(request)
        self.assertIn("EMERGENCY_RESERVE_BELOW_THREE_MONTHS", result["capacity_flags"])

    def test_rejects_unfunded_plan(self):
        with self.assertRaises(ValidationError):
            PlanningRequest(target_amount=500000, initial_amount=0,
                            monthly_contribution=0, years=3)


if __name__ == "__main__":
    unittest.main()
