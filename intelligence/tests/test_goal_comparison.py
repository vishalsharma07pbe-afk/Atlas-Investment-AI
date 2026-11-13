import unittest
from pydantic import ValidationError
from app.goal_comparison import ComparisonRequest,compare_scenarios
from app import main

def sample(name,monthly,rate=0):
    return {"name":name,"parameters":{"target_amount":"1200","months":12,
        "monthly_contribution":str(monthly),"annual_return_percent":str(rate)}}

class ComparisonTests(unittest.TestCase):
    def test_two_scenarios_compare_without_cross_contamination(self):
        request=ComparisonRequest(scenarios=[sample("A",100),sample("B",50)])
        result=compare_scenarios(request)
        self.assertEqual(result["scenarios"][0]["projected_value"],"1200.00")
        self.assertEqual(result["scenarios"][1]["projected_value"],"600.00")
        self.assertEqual(result["scenarios"][1]["status"],"TARGET_SHORTFALL")
    def test_duplicate_names_rejected(self):
        with self.assertRaises(ValidationError):
            ComparisonRequest(scenarios=[sample("Base",100),sample(" base ",100)])
    def test_bounds_and_invalid_nested_values(self):
        with self.assertRaises(ValidationError):
            ComparisonRequest(scenarios=[sample("A",100)])
        with self.assertRaises(ValidationError):
            ComparisonRequest(scenarios=[sample("A",100),sample("B",100,99)])
    def test_endpoint(self):
        result=main.planning_goal_comparison(ComparisonRequest(scenarios=[sample("A",100),sample("B",50)]))
        self.assertEqual(len(result["scenarios"]),2)
if __name__=="__main__":unittest.main()
