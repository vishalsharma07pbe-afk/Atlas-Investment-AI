import unittest
from datetime import date,timedelta
from app import sector_benchmarks as s,relative_strength as rel
TODAY=date(2026,11,27)
ISIN="INE002A01018"
def fixture():
    days=[TODAY-timedelta(days=i) for i in range(1,100)]
    regular=sorted(d for d in days if d.weekday()<5)[-61:]
    rows=[{"trade_date":d.isoformat(),"close":100+i,"source_code":"UPSTOX","revision":1} for i,d in enumerate(regular)]
    calendar={"exchange":"NSE","through":(TODAY-timedelta(days=1)).isoformat(),"days":[{"trade_date":d.isoformat(),"state":"REGULAR" if d.weekday()<5 else "CLOSED"} for d in days]}
    return {"benchmark_key":s.KEYS[0],"kind":"PRICE_INDEX","candles":rows},calendar
class SectorBenchmarkTests(unittest.TestCase):
    def test_exact_calendar_and_narrow_classification(self):
        item,calendar=fixture()
        indexed=s.analyze({"items":[item]},calendar,TODAY)
        index=indexed[s.KEYS[0]]
        self.assertIn("60",index["windows"])
        point={**index["windows"]["60"],"return_percent":80,"source_code":"UPSTOX"}
        row={"id":1,"isin":ISIN,"exchange":"NSE","as_of":index["as_of"],"comparative_price_windows":{"60":point}}
        report=s.compare(row,("financial services","banks"),indexed,TODAY)
        self.assertEqual(report["windows"]["60"]["difference_pp"],20)
        self.assertIsNone(s.compare(row,("financial services","insurance"),indexed,TODAY))
        self.assertIsNone(s.compare({**row,"exchange":"BSE"},("banks","banks"),indexed,TODAY))
        point["dates_digest"]="b"*64
        self.assertIsNone(s.compare(row,("banks","banks"),indexed,TODAY))
    def test_duplicate_and_unpublished_session_rejected(self):
        item,calendar=fixture()
        self.assertEqual(s.analyze({"items":[item,item]},calendar,TODAY),{})
        calendar["days"][0]["state"]="UNKNOWN"
        self.assertEqual(s.analyze({"items":[item]},calendar,TODAY),{})
