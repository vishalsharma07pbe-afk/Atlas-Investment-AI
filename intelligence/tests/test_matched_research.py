import unittest
from datetime import date,timedelta
from app import relative_strength as rs, governance_review as gr

TODAY=date(2026,11,26)
class MatchedResearchTests(unittest.TestCase):
    def test_relative_strength_exact_session_digest_and_provenance(self):
        days=[TODAY-timedelta(days=i) for i in range(1,500)]
        regular=sorted(d for d in days if d.weekday()<5)[-253:]
        indexed={d:100+i for i,d in enumerate(regular)}
        calendar={"exchange":"NSE","through":days[0].isoformat(),"days":[{"trade_date":d.isoformat(),"state":"REGULAR" if d.weekday()<5 else "CLOSED"} for d in days]}
        windows=rs.benchmark_windows(indexed,calendar,TODAY)
        self.assertEqual(set(windows),{"20","60","120","252"})
        raw=[{"trade_date":d.isoformat(),"open":100,"high":101,"low":99,"close":100,"volume":1000,"adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED","source_code":"TEST","revision":1} for d in regular]
        digests=rs.stock_windows(raw,TODAY)
        self.assertEqual(digests["252"],windows["252"]["dates_digest"])
        as_of=regular[-1].isoformat()
        regime={"status":"OBSERVED_BENCHMARK_REGIME","calendar_checked_on":TODAY.isoformat(),"as_of":as_of,"relative_strength_windows":windows}
        row={"exchange":"NSE","as_of":as_of,"adjustment_status":"ADJUSTED","adjusted_window_dates":digests,
             "momentum_windows":{"252":{"adjustment_status":"ADJUSTED","first_date":regular[0].isoformat(),"last_date":as_of,"return_percent":300}}}
        self.assertEqual(rs.compare(row,regime,TODAY)["windows"]["252"]["difference_pp"],48)
        self.assertFalse(rs.compare({**row,"exchange":"BSE"},regime,TODAY)["windows"])
        self.assertFalse(rs.compare({**row,"adjusted_window_dates":{"252":"x"*64}},regime,TODAY)["windows"])
        self.assertFalse(rs.compare(row,{**regime,"calendar_checked_on":"2026-11-25"},TODAY)["windows"])
        raw[-1]["quality_status"]="VALIDATED_MANUAL"
        self.assertFalse(rs.stock_windows(raw,TODAY))
        calendar["days"][0]["state"]="UNKNOWN"
        self.assertFalse(rs.benchmark_windows(indexed,calendar,TODAY))
    def test_normal_provider_classification_is_not_governance_clearance(self):
        normal=gr.assess({"security_state":"NORMAL"},{},TODAY)
        self.assertFalse(normal["clearance_verified"])
        self.assertIn("OFFICIAL_ASM_GSM_ESM_AND_TRADE_RESTRICTIONS_REQUIRED",normal["blockers"])
        self.assertEqual(normal["status"],"INCOMPLETE_GOVERNANCE_EVIDENCE")
        suspended=gr.assess({"security_state":"SUSPENDED_REPORTED"},{},TODAY)
        self.assertEqual(suspended["status"],"REVIEW_REQUIRED")
        self.assertIn("REPORTED_SUSPENDED_REPORTED_REVIEW",suspended["findings"])
