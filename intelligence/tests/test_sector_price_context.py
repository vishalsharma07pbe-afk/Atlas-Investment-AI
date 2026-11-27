import unittest
from datetime import date,timedelta
from app import sector_price_context as s
TODAY=date(2026,11,27)
LAST="2026-11-26"
def isin(i):return "INE"+str(i).zfill(9)
def point(value,digest="a"*64):
    return {"first_date":"2026-10-28","last_date":LAST,"dates_digest":digest,"return_percent":value,"source_code":"UPSTOX"}
def row(i,value,market="NSE",digest="a"*64):
    return {"id":i,"isin":isin(i),"exchange":market,"as_of":LAST,"security_state":"NORMAL","comparative_price_windows":{"20":point(value,digest)}}
def section(rows,market="NSE"):
    return {"section":market,"status":"READY","result":{"discovery_coverage":{"calendar_checked_on":TODAY.isoformat(),"expected_session":LAST,"calendar_status":"PUBLISHED_SESSION"},"company_research_universe":rows}}
class SectorPriceTests(unittest.TestCase):
    def test_broad_cohort_excludes_self_and_uses_midrank_ties(self):
        rows=[row(i,v) for i,v in enumerate([12,1,5,12,15,20],1)]
        labels={r["isin"]:("finance","banks") for r in rows}
        result,coverage=s.analyze({"sections":[section(rows)]},labels,TODAY)
        report=result[("NSE",isin(1),1,LAST)]
        w=report["sector_windows"]["20"]
        self.assertEqual(w["peer_count"],5)
        self.assertEqual(w["peer_median_return_percent"],12)
        self.assertEqual(w["peer_percentile"],50)
        self.assertEqual(w["peers_equal"],1)
        self.assertEqual(coverage["comparable_identities"],6)
        self.assertEqual(w["calendar_status"],"MATCHED_OBSERVED_DATES_ONLY")
    def test_window_source_exchange_duplicate_and_special_separation(self):
        rows=[row(i,i) for i in range(1,7)]
        labels={r["isin"]:("finance","banks") for r in rows}
        rows[1]["comparative_price_windows"]["20"]["dates_digest"]="b"*64
        rows[2]["comparative_price_windows"]["20"]["source_code"]="OTHER"
        rows[3]["security_state"]="PCA"
        result,_=s.analyze({"sections":[section(rows),section([row(i,i,"BSE") for i in range(1,7)],"BSE")]},labels,TODAY)
        self.assertNotIn(("NSE",isin(1),1,LAST),result)
        self.assertIn(("BSE",isin(1),1,LAST),result)
        b=[row(i,i) for i in range(1,7)]
        b.append({**b[0],"id":999})
        result,_=s.analyze({"sections":[section(b)]},labels,TODAY)
        self.assertFalse(any(k[1]==isin(1) for k in result))
    def test_validated_window_and_raw_or_future_refusal(self):
        raw=[]
        for i in range(21):
            day=TODAY-timedelta(days=21-i)
            price=100+i
            raw.append({"trade_date":day.isoformat(),"open":price,"high":price,"low":price,"close":price,"volume":100,
                "adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED","source_code":"UPSTOX","revision":1})
        result=s.windows(raw,TODAY)
        self.assertEqual(result["20"]["return_percent"],20)
        raw[-1]["trade_date"]=TODAY.isoformat()
        self.assertEqual(s.windows(raw,TODAY),{})
        raw[-1]["trade_date"]=LAST
        raw[-1]["adjustment_status"]="RAW_UNADJUSTED"
        self.assertEqual(s.windows(raw,TODAY),{})
    def test_calendar_match_is_explicit_not_implicit_for_bse(self):
        rows=[row(i,i) for i in range(1,7)]
        labels={r["isin"]:("finance","banks") for r in rows}
        regime={"status":"OBSERVED_BENCHMARK_REGIME","as_of":LAST,"calendar_checked_on":TODAY.isoformat(),"relative_strength_windows":{"20":point(10)}}
        results,_=s.analyze({"sections":[section(rows),section([row(i,i,"BSE") for i in range(1,7)],"BSE")],"market_regime":regime},labels,TODAY)
        self.assertEqual(results[("NSE",isin(1),1,LAST)]["sector_windows"]["20"]["calendar_status"],"MATCHED_STORED_NSE_INDEX_SESSIONS")
        self.assertEqual(results[("BSE",isin(1),1,LAST)]["sector_windows"]["20"]["calendar_status"],"MATCHED_OBSERVED_DATES_ONLY")
