import unittest
from datetime import date
from pydantic import ValidationError
from app.broker_reports import ReportRequest,report

def position(broker,quantity,price=120):
    return {"broker":broker,"account_label":"Personal","asset_type":"EQUITY",
        "instrument_id":"INE848E01016","display_name":"Example Equity",
        "quantity":quantity,"average_cost":100,"last_price":price,
        "price_as_of":"2026-11-12","source_type":"MANUAL"}

class BrokerReportTests(unittest.TestCase):
    def test_consolidates_same_isin_across_brokers(self):
        data=ReportRequest(report_date=date(2026,11,13),
            positions=[position("GROWW",2),position("ZERODHA",3)])
        result=report(data)
        self.assertEqual(len(result["broker_accounts"]),2)
        self.assertEqual(len(result["consolidated_instruments"]),1)
        self.assertEqual(result["consolidated_instruments"][0]["total_quantity"],"5")
        self.assertEqual(result["portfolio"]["invested"],"500")
        self.assertEqual(result["portfolio"]["recorded_market_value"],"600")
        self.assertEqual(result["portfolio"]["unrealized_pnl"],"100")

    def test_stale_prices_fail_closed_without_partial_pnl(self):
        stale=position("UPSTOX",1)
        stale["price_as_of"]="2026-10-01"
        result=report(ReportRequest(report_date=date(2026,11,13),
            positions=[position("GROWW",2),stale]))
        self.assertFalse(result["portfolio"]["valuation_complete"])
        self.assertIsNone(result["portfolio"]["unrealized_pnl"])
        self.assertIn("PORTFOLIO_VALUATION_INCOMPLETE",result["warnings"])

    def test_missing_valuation_date_rejected(self):
        item=position("GROWW",1)
        item.pop("price_as_of")
        with self.assertRaises(ValidationError):
            ReportRequest(report_date=date(2026,11,13),positions=[item])

    def test_unknown_broker_rejected(self):
        with self.assertRaises(ValidationError):
            ReportRequest(report_date=date(2026,11,13),positions=[position("UNKNOWN",1)])

if __name__=="__main__":unittest.main()
