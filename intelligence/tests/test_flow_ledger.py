import tempfile
import unittest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch

from app import flow_ledger
from app.institutional_flows import FlowRecord, FlowRequest

def record(buy="100",sell="80",market="NSE",participant="FII",day=None):
    return FlowRecord(trade_date=day or date.today(),market=market,participant=participant,
                      buy_crore_inr=Decimal(buy),sell_crore_inr=Decimal(sell),
                      source_name="Manual official report",verification="USER_REPORTED")

class FlowLedgerTests(unittest.TestCase):
    def test_persistence_idempotency_and_net(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(flow_ledger,"DB_PATH",flow_ledger.Path(tmp)/"flows.db"):
                request=FlowRequest(records=[record()])
                self.assertEqual(flow_ledger.import_evidence(request)["inserted"],1)
                self.assertEqual(flow_ledger.import_evidence(request)["unchanged"],1)
                result=flow_ledger.list_evidence()
                self.assertEqual(result["total"],1)
                self.assertEqual(Decimal(result["records"][0]["net_crore_inr"]),Decimal("20"))
                self.assertFalse(result["live_feed_connected"])
                self.assertFalse(result["independently_verified"])

    def test_conflicts_rejected_without_partial_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(flow_ledger,"DB_PATH",flow_ledger.Path(tmp)/"flows.db"):
                flow_ledger.import_evidence(FlowRequest(records=[record()]))
                with self.assertRaisesRegex(ValueError,"CONFLICTING_FLOW_EVIDENCE"):
                    flow_ledger.import_evidence(FlowRequest(records=[
                        record(buy="300",market="BSE"),record(buy="101")]))
                self.assertEqual(flow_ledger.list_evidence()["total"],1)

    def test_freshness_and_market_scope_not_aggregated(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(flow_ledger,"DB_PATH",flow_ledger.Path(tmp)/"flows.db"):
                flow_ledger.import_evidence(FlowRequest(records=[
                    record(day=date.today()-timedelta(days=10)),
                    record(market="INDIA_COMBINED",day=date.today())]))
                result=flow_ledger.list_evidence()
                self.assertEqual(result["total"],2)
                self.assertEqual({r["freshness"] for r in result["records"]},{"RECENT","OLD"})
                self.assertNotIn("aggregate_net",result)

if __name__=="__main__":
    unittest.main()
