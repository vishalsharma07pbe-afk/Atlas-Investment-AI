import unittest
from copy import deepcopy
from datetime import date,timedelta
from app.replay_evidence import fingerprint,exact_isin

TODAY=date(2026,11,24)

def history(n=500):
    return [{"trade_date":(TODAY-timedelta(days=n-i)).isoformat(),"open":100,
        "high":102,"low":99,"close":101,"volume":100000,
        "adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED",
        "source_code":"UPSTOX","revision":1} for i in range(n)]

class ReplayEvidenceTests(unittest.TestCase):
    def test_recent_shared_window_matches_and_revisions_invalidate(self):
        data=history()
        expected=fingerprint(data,TODAY)
        self.assertIsNotNone(expected)
        self.assertEqual(expected,fingerprint(data[-250:],TODAY))
        data[0]["revision"]=2
        self.assertEqual(expected,fingerprint(data,TODAY))
        data[-250]["revision"]=2
        self.assertNotEqual(expected,fingerprint(data,TODAY))
        data[-250]["revision"]=1
        data[-1]["close"]=100.5
        self.assertNotEqual(expected,fingerprint(data,TODAY))

    def test_numeric_representation_does_not_change_evidence(self):
        data=history(50)
        expected=fingerprint(data,TODAY)
        data[0]["close"]="101.0000"
        data[1]["volume"]=100000.0
        self.assertEqual(expected,fingerprint(data,TODAY))

    def test_invalid_source_adjustment_quality_revision_or_volume_withheld(self):
        original=history(50)
        for field,value in (("source_code","OTHER"),("adjustment_status","RAW_UNADJUSTED"),
            ("quality_status","VALIDATED_MANUAL"),("revision",0),("revision",True),
            ("volume",1.5),("close",float("nan"))):
            data=deepcopy(original)
            data[-1][field]=value
            self.assertIsNone(fingerprint(data,TODAY),field)
        self.assertTrue(exact_isin("INE002A01018"))
        for value in ("INF002A01018","INE002A0101","TEST",None):
            self.assertFalse(exact_isin(value))
