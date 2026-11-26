import unittest
from decimal import Decimal
from types import SimpleNamespace
from pydantic import ValidationError
from unittest.mock import patch
from app import main
from app.portfolio_allocation import PlanRequest,allocation_plan

def holding(id,kind,qty,price):
    return SimpleNamespace(id=id,symbol="SYNTH",asset_type=kind,
        quantity=Decimal(qty),last_price=Decimal(price) if price is not None else None)

class AllocationTests(unittest.TestCase):
    def request(self,contribution="100"):
        return PlanRequest(contribution=contribution,targets=[
            {"asset_type":"EQUITY","weight_percent":"50"},
            {"asset_type":"MUTUAL_FUND","weight_percent":"50"}])
    def test_contribution_only_reduces_underweight_gap(self):
        result=allocation_plan([holding(1,"EQUITY","3","100"),holding(2,"MUTUAL_FUND","1","100")],self.request())
        self.assertEqual(result["recorded_value"],"400.00")
        by_type={a["asset_type"]:a for a in result["allocations"]}
        self.assertEqual(by_type["EQUITY"]["hypothetical_contribution"],"0.00")
        self.assertEqual(by_type["MUTUAL_FUND"]["hypothetical_contribution"],"100.00")
        self.assertEqual(result["unallocated_contribution"],"0.00")
    def test_unpriced_holdings_not_assigned_value(self):
        result=allocation_plan([holding(1,"EQUITY","2","50"),holding(2,"MUTUAL_FUND","5",None)],self.request())
        self.assertEqual(result["status"],"PARTIAL_PRICE_COVERAGE")
        self.assertEqual(result["recorded_value"],"100.00")
        self.assertEqual(len(result["unpriced_holdings"]),1)
    def test_no_prices_fails_closed(self):
        result=allocation_plan([holding(1,"EQUITY","1",None)],self.request())
        self.assertEqual(result["status"],"NO_PRICED_VALUE")
        self.assertEqual(result["allocations"],[])
    def test_invalid_targets_rejected(self):
        with self.assertRaises(ValidationError):
            PlanRequest(targets=[{"asset_type":"EQUITY","weight_percent":90}])
        with self.assertRaises(ValidationError):
            PlanRequest(targets=[{"asset_type":"EQUITY","weight_percent":50},{"asset_type":"EQUITY","weight_percent":50}])
    def test_endpoint_uses_local_portfolio(self):
        with patch.object(main,"_fetch_portfolio_holdings",return_value=[holding(1,"EQUITY","1","100")]):
            result=main.portfolio_allocation_plan(self.request(),None)
        self.assertEqual(result["recorded_value"],"100.00")
if __name__=="__main__":unittest.main()
