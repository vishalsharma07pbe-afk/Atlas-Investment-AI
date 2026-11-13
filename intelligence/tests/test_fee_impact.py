import unittest
from decimal import Decimal
from pydantic import ValidationError
from app.fee_impact import FeeRequest,fee_impact
from app import main

class FeeImpactTests(unittest.TestCase):
    def test_zero_fees_match_no_fee_baseline(self):
        result=fee_impact(FeeRequest(initial_amount=1000,monthly_contribution=100,months=12,annual_return_percent=8))
        self.assertEqual(result["without_fees"],result["after_fees"])
        self.assertEqual(result["fee_drag"],"0.00")
        self.assertEqual(result["total_charges"],"0.00")
    def test_flat_fee_and_contribution_load_at_zero_return(self):
        result=fee_impact(FeeRequest(monthly_contribution=100,months=12,contribution_fee_percent=1,monthly_flat_fee=2))
        self.assertEqual(result["without_fees"],"1200.00")
        self.assertEqual(result["after_fees"],"1164.00")
        self.assertEqual(result["contribution_charges"],"12.00")
        self.assertEqual(result["flat_charges"],"24.00")
        self.assertEqual(result["fee_drag"],"36.00")
    def test_expense_ratio_compounds(self):
        result=fee_impact(FeeRequest(initial_amount=1000,monthly_contribution=0,months=24,annual_return_percent=0,annual_expense_ratio_percent=1))
        self.assertLess(Decimal(result["after_fees"]),Decimal("1000"))
        self.assertEqual([p["month"] for p in result["checkpoints"]],[12,24])
    def test_fee_cannot_make_balance_negative(self):
        result=fee_impact(FeeRequest(monthly_contribution=0,months=12,monthly_flat_fee=100))
        self.assertEqual(result["after_fees"],"0.00")
    def test_invalid_fees_rejected(self):
        with self.assertRaises(ValidationError):FeeRequest(monthly_contribution=100,months=12,annual_expense_ratio_percent=7)
        with self.assertRaises(ValidationError):FeeRequest(monthly_contribution=100,months=0)
    def test_api(self):
        result=main.planning_fee_impact(FeeRequest(monthly_contribution=100,months=12))
        self.assertEqual(result["after_fees"],"1200.00")
if __name__=="__main__":unittest.main()
