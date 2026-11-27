import unittest
from datetime import datetime,timezone,timedelta
from app import valuation_scenarios as v
NOW=datetime(2026,11,27,5,tzinfo=timezone.utc)
ISIN="INE002A01018"
def fixture():
    def block(key,metric,values):
        return {"status":"AVAILABLE","source":{"provider":"UPSTOX","endpoint":f"/v2/fundamentals/{ISIN}/"+key.replace("_","-"),"retrieved_at":NOW.isoformat()},
            "data":{"statement_type":"consolidated","time_period":"yearly","units":"crore","rows":[{"name":metric,
            "history":[{"period":f"Mar {year}","value":value} for year,value in zip(range(2023,2027),values)]}]}}
    return {"isin":ISIN,"retrieved_at":NOW.isoformat(),"sections":{"income_statement":block("income_statement","net_profit",[80,90,100,110]),
            "cash_flow":block("cash_flow","operating",[90,100,110,120])}}
class ValuationScenariosTest(unittest.TestCase):
    def test_constant_perpetuity_and_bad_rates(self):
        self.assertAlmostEqual(v.pv(10,0,.1,0)["hypothetical_cash_stream_pv_cr"],100,places=4)
        with self.assertRaises(ValueError):v.pv(10,.1,.1,.1)
        with self.assertRaises(ValueError):v.pv(float("nan"),0,.1,0)
    def test_history_and_assumptions_are_separate(self):
        result=v.summarize(fixture(),NOW)
        self.assertEqual(result["status"],"HYPOTHETICAL_CASH_STREAM_ONLY")
        self.assertEqual(result["operating_cash_anchor_cr"],105)
        self.assertEqual(len(result["scenarios"]),3)
        self.assertIsNone(result["intrinsic_value"]);self.assertIsNone(result["margin_of_safety_percent"]);self.assertFalse(result["qualified"])
        self.assertLess(result["scenarios"][0]["hypothetical_cash_stream_pv_cr"],result["scenarios"][2]["hypothetical_cash_stream_pv_cr"])
    def test_negative_stale_mismatched_scope_and_source(self):
        report=fixture();report["sections"]["cash_flow"]["data"]["rows"][0]["history"][0]["value"]=-1
        result=v.summarize(report,NOW)
        self.assertEqual(result["status"],"HISTORICAL_DETERIORATION_REVIEW");self.assertFalse(result["scenarios"])
        report=fixture();report["sections"]["cash_flow"]["source"]["retrieved_at"]=(NOW-timedelta(hours=2)).isoformat()
        self.assertFalse(v.summarize(report,NOW)["scenarios"])
        self.assertFalse(v.summarize(fixture(),NOW+timedelta(hours=25))["scenarios"])
        report=fixture();report["sections"]["cash_flow"]["data"]["statement_type"]="standalone"
        self.assertFalse(v.summarize(report,NOW)["scenarios"])
