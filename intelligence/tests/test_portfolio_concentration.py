import unittest
from decimal import Decimal
from unittest.mock import patch
from app.portfolio_concentration import LimitsRequest,concentration_report
from app.main import PortfolioHolding
from app import main

def holding(id,symbol,kind,quantity,price):
    return PortfolioHolding(id=id,symbol=symbol,asset_type=kind,quantity=Decimal(quantity),
        average_cost=Decimal("1"),last_price=None if price is None else Decimal(price))

class ConcentrationTests(unittest.TestCase):
    def test_single_holding_and_asset_type_breaches(self):
        data=[holding(1,"AAA","EQUITY","8","10"),holding(2,"BBB","MUTUAL_FUND","2","10")]
        result=concentration_report(data,LimitsRequest(max_single_holding_percent=70,max_equity_percent=70,max_mutual_fund_percent=80,max_top_three_percent=90))
        self.assertEqual(result["recorded_value"],"100.00")
        self.assertEqual(result["holdings"][0]["weight_percent"],"80.00")
        self.assertEqual({x["type"] for x in result["breaches"]},{"SINGLE_HOLDING","ASSET_TYPE","TOP_THREE"})
    def test_missing_price_is_excluded_and_flagged(self):
        result=concentration_report([holding(1,"AAA","EQUITY","2","10"),holding(2,"BBB","EQUITY","10",None)],LimitsRequest())
        self.assertEqual(result["status"],"PARTIAL_PRICE_COVERAGE")
        self.assertEqual(len(result["unpriced_holdings"]),1)
    def test_no_priced_value(self):
        result=concentration_report([holding(1,"AAA","EQUITY","2",None)],LimitsRequest())
        self.assertEqual(result["status"],"NO_PRICED_VALUE")
        self.assertEqual(result["breaches"],[])
    def test_empty_portfolio(self):
        self.assertEqual(concentration_report([],LimitsRequest())["status"],"NO_PRICED_VALUE")
    def test_endpoint_uses_recorded_holdings(self):
        with patch.object(main,"_fetch_portfolio_holdings",return_value=[holding(1,"AAA","EQUITY","1","100")]):
            result=main.portfolio_concentration(LimitsRequest(),None)
        self.assertEqual(result["recorded_value"],"100.00")
if __name__=="__main__":unittest.main()
