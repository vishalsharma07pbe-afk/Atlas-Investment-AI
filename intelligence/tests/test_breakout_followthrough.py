import unittest
from datetime import date,timedelta
from dataclasses import replace
from app.technical import Candle
from app.breakout_followthrough import analyze
from app.screener import screen

def fixture():
    start=date(2026,10,1)
    return [Candle((start+timedelta(days=i)).isoformat(),100,102,98,100,1000,"ADJUSTED") for i in range(24)]

def bar(row,v,volume=1000):
    return replace(row,open=v,high=v+1,low=v-1,close=v,volume=volume)

class FollowthroughTests(unittest.TestCase):
    def test_frozen_upside_boundary_and_reentry(self):
        rows=fixture()
        rows[20]=bar(rows[20],105,3000)
        rows[21]=bar(rows[21],106)
        rows[22]=bar(rows[22],101)
        report=analyze(rows,calendar_verified=True)
        event=report["events"][0]
        self.assertEqual(event["status"],"REENTRY_OBSERVED")
        self.assertEqual(event["boundary"],102)
        self.assertEqual(event["reentry_date"],rows[22].date)
        self.assertEqual(event["relative_volume"],3)
        self.assertEqual(event["followup_count"],3)
    def test_downside_reentry_and_pending(self):
        rows=fixture()
        rows[20]=bar(rows[20],95)
        report=analyze(rows,calendar_verified=True)
        self.assertEqual(report["events"][0]["direction"],"DOWNSIDE")
        self.assertEqual(report["events"][0]["status"],"REENTRY_OBSERVED")
        self.assertEqual(report["events"][0]["volume_context"],"BELOW_HIGH_VOLUME_THRESHOLD")
        rows=fixture()
        rows[-1]=bar(rows[-1],105)
        self.assertEqual(analyze(rows,calendar_verified=True)["events"][0]["status"],"PENDING_FOLLOWTHROUGH")
    def test_held_and_inconclusive(self):
        rows=fixture()
        for i in range(20,24):
            rows[i]=bar(rows[i],105)
        self.assertEqual(analyze(rows,calendar_verified=True)["events"][0]["status"],"HELD_BEYOND_BOUNDARY")
        rows[-1]=bar(rows[-1],102)
        self.assertEqual(analyze(rows,calendar_verified=True)["events"][0]["status"],"INCONCLUSIVE_FOLLOWTHROUGH")
    def test_missing_or_raw_evidence_withheld(self):
        rows=fixture()
        self.assertEqual(analyze(rows)["status"],"UNAVAILABLE")
        self.assertEqual(analyze(rows[:-1],calendar_verified=True)["status"],"UNAVAILABLE")
        self.assertEqual(analyze([replace(c,adjustment_status="RAW_UNADJUSTED") for c in rows],calendar_verified=True)["status"],"UNAVAILABLE")
    def test_sample_independent_of_technical_watch(self):
        rows=fixture()
        rows[20]=bar(rows[20],105)
        raw=[{"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,"close":c.close,"volume":c.volume,"adjustment_status":c.adjustment_status} for c in rows]
        result=screen([{"id":1,"symbol":"TEST","exchange":"NSE","isin":"INE002A01018"}],lambda _:{"candles":raw},
            as_of=date(2026,10,25),batch_loaded=True,expected_session=date(2026,10,24),include_horizons=True)
        self.assertEqual(result["breakout_review"]["event_listing_count"],1)
        self.assertEqual(result["breakout_review"]["items"][0]["followthrough"]["events"][0]["status"],"REENTRY_OBSERVED")
        self.assertEqual(result["horizons"]["SWING"]["candidates"],[])
