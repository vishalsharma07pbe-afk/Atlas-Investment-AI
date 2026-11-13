import unittest
from datetime import date,timedelta
from decimal import Decimal
from pydantic import ValidationError
from app.institutional_flows import FlowRecord,analyze_flows

def record(participant="FII",buy="125.50",sell="100.25"):
    return FlowRecord(trade_date=date.today()-timedelta(days=1),market="NSE",
        participant=participant,buy_crore_inr=Decimal(buy),sell_crore_inr=Decimal(sell),
        source_name="User research note")

class FlowTests(unittest.TestCase):
    def test_exact_net_and_provenance(self):
        result=analyze_flows([record()])
        self.assertEqual(result["records"][0]["net_crore_inr"],"25.25")
        self.assertEqual(result["records"][0]["verification"],"USER_REPORTED")
        self.assertFalse(result["independent_verification"])

    def test_negative_net(self):
        result=analyze_flows([record("DII","5","10")])
        self.assertEqual(result["records"][0]["direction"],"NET_SELL")

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            analyze_flows([record(),record()])

    def test_future_date_and_negative_amount_rejected(self):
        with self.assertRaises(ValidationError):
            FlowRecord(trade_date=date.today()+timedelta(days=1),market="NSE",
                participant="FII",buy_crore_inr=1,sell_crore_inr=1,source_name="Source")
        with self.assertRaises(ValidationError):
            FlowRecord(trade_date=date.today(),market="NSE",
                participant="FII",buy_crore_inr=-1,sell_crore_inr=1,source_name="Source")

if __name__=="__main__":
    unittest.main()
