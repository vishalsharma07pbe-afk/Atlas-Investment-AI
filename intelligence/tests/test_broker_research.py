import unittest
from datetime import date,timedelta
from pydantic import ValidationError
from app.broker_research import ConsensusRequest,consensus,SOURCES

TODAY=date.today()
def record(source,days=2,rating="BUY",target="120",report_id="a",analyst=None):
    return {"source":source,"analyst":analyst,"instrument_id":"INE848E01016",
        "symbol":"EXAMPLE","published_on":(TODAY-timedelta(days=days)).isoformat(),
        "rating":rating,"target_price":target,"horizon_months":12,
        "report_url":"https://example.org/research/"+report_id,
        "report_title":"Example research report","report_id":report_id}

class BrokerResearchTests(unittest.TestCase):
    def test_cross_provider_targets_and_ratings(self):
        request=ConsensusRequest(instrument_id="INE848E01016",records=[
            record("GROWW",rating="BUY",target="120"),
            record("ZERODHA",rating="HOLD",target="100"),
            record("ICICI_DIRECT",rating="SELL",target="80")])
        result=consensus(request)
        self.assertEqual(result["fresh_provider_count"],3)
        self.assertEqual(result["targets"]["median"],"100")
        self.assertEqual(result["targets"]["range"],"40")
        self.assertEqual(result["rating_counts"]["BUY"],1)
        self.assertFalse(result["actionable"])

    def test_superseded_and_stale_reports_not_counted(self):
        request=ConsensusRequest(instrument_id="INE848E01016",max_age_days=30,records=[
            record("GROWW",days=1,rating="HOLD",report_id="new"),
            record("GROWW",days=20,rating="BUY",report_id="old"),
            record("UPSTOX",days=80,report_id="stale")])
        result=consensus(request)
        self.assertEqual(result["fresh_records"],1)
        self.assertEqual(result["excluded_stale_or_superseded"],2)
        self.assertEqual(result["rating_counts"]["HOLD"],1)
        self.assertEqual(result["rating_counts"]["BUY"],0)

    def test_no_reports_does_not_invent_consensus(self):
        result=consensus(ConsensusRequest(instrument_id="INE848E01016",records=[]))
        self.assertEqual(result["fresh_provider_count"],0)
        self.assertIsNone(result["targets"]["median"])

    def test_forged_verification_and_mixed_instruments_rejected(self):
        forged=record("GROWW")
        forged["evidence_status"]="SOURCE_VERIFIED"
        with self.assertRaises(ValidationError):
            ConsensusRequest(instrument_id="INE848E01016",records=[forged])
        mixed=record("GROWW")
        mixed["instrument_id"]="DIFFERENT"
        with self.assertRaises(ValidationError):
            ConsensusRequest(instrument_id="INE848E01016",records=[mixed])

    def test_all_named_providers_supported(self):
        for broker in ("GROWW","ZERODHA","UPSTOX","ANGEL_ONE","MOTILAL_OSWAL","NUVAMA","JM_FINANCIAL"):
            self.assertIn(broker,SOURCES)

if __name__=="__main__":unittest.main()
