import tempfile
import unittest
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from app import market_regime as regime, autonomous_research as research

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
TODAY=NOW.date()
def fixture():
    days=[TODAY-timedelta(days=i) for i in range(1,110)]
    regular=sorted(d for d in days if d.weekday()<5)[-61:]
    benchmark={"benchmark_key":"NSE_INDEX|Nifty 50","kind":"PRICE_INDEX","candles":[
        {"trade_date":d.isoformat(),"close":100+i,"source_code":"UPSTOX","revision":1} for i,d in enumerate(regular)]}
    calendar={"exchange":"NSE","through":(TODAY-timedelta(days=1)).isoformat(),"days":[
        {"trade_date":d.isoformat(),"state":"REGULAR" if d.weekday()<5 else "CLOSED"} for d in days]}
    return benchmark,calendar

class MarketRegimeTests(unittest.TestCase):
    def test_calendar_matched_trend_and_volatility(self):
        benchmark,calendar=fixture()
        result=regime.analyze(benchmark,calendar,TODAY)
        self.assertEqual(result["status"],"OBSERVED_BENCHMARK_REGIME")
        self.assertEqual(result["trend"],"RISING")
        self.assertEqual(result["benchmark_change_60_percent"],60)
        self.assertEqual(result["volatility_regime"],"BELOW_HIGH_THRESHOLD")
        missing={**benchmark,"candles":benchmark["candles"][:-1]}
        self.assertNotEqual(regime.analyze(missing,calendar,TODAY)["status"],"OBSERVED_BENCHMARK_REGIME")
        calendar["days"][0]["state"]="UNKNOWN"
        self.assertNotEqual(regime.analyze(benchmark,calendar,TODAY)["status"],"OBSERVED_BENCHMARK_REGIME")
    def test_matched_breadth_and_stale_snapshot(self):
        benchmark,calendar=fixture()
        with tempfile.TemporaryDirectory() as root,patch.dict("os.environ",{"ATLAS_RESEARCH_SNAPSHOT_DB":root+"/research.sqlite"}):
            self.assertTrue(regime.refresh(research._connect,lambda p:benchmark if p.endswith("strategy-benchmark") else calendar,NOW))
            result=regime.read(research._connect,NOW)
            snap={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{
                "discovery_coverage":{"calendar_checked_on":TODAY.isoformat(),"expected_session":result["as_of"],"selected_count":60},
                "sample_breadth":{"as_of":result["as_of"],"adjustment_status":"ADJUSTED","pairs":[
                    {"previous_session":result["previous_session"],"advancing":10,"declining":40,"unchanged":0}]}}}]}
            regime.attach(snap,research._connect,NOW)
            self.assertEqual(snap["market_regime"]["agreement"],"OPPOSING_DAILY_BREADTH_REVIEW")
            self.assertEqual(regime.read(research._connect,NOW+timedelta(hours=3))["status"],"STALE_CAPTURE")
            snap["sections"][0]["result"]["sample_breadth"]["pairs"][0]["previous_session"]="2026-01-01"
            regime.attach(snap,research._connect,NOW)
            self.assertEqual(snap["market_regime"]["breadth"]["status"],"UNAVAILABLE")
