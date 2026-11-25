import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import automatic_institutional as flows, autonomous_research as research

class AutomaticInstitutionalTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":tmp.name+"/research.sqlite",
            "ATLAS_AUTOMATIC_INSTITUTIONAL_ENABLED":"true","MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true",
            "MARKET_DATA_ENTITLEMENT_CONFIRMED":"true","UPSTOX_ACCESS_TOKEN":"test-only"})
        env.start()
        self.addCleanup(env.stop)
        self.now=datetime(2026,11,24,12,tzinfo=timezone.utc)

    def report(self,interval):
        self.assertEqual(interval,"1D")
        rows=[{"observed_at":(self.now-timedelta(days=i,hours=1)).isoformat(),
               "buy_amount":120,"sell_amount":100,"secret":"do-not-persist"} for i in range(5)]
        return {"market":"NSE_CASH","unit":"PROVIDER_REPORTED","interval":"1D",
                "participants":{"fii":{"status":"AVAILABLE","data":rows},"dii":{"status":"AVAILABLE","data":rows}}}

    def test_automatic_dedupe_paired_dates_and_no_sensitive_fields(self):
        flows.refresh(research._connect,self.report,self.now)
        flows.refresh(research._connect,lambda *_:self.fail("duplicate request"),self.now)
        result=flows.read(research._connect,self.now)
        self.assertEqual(result["status"],"RECENT_PROVIDER_EVIDENCE")
        self.assertEqual(result["paired_five_date_window"]["fii_net"],"100")
        self.assertEqual(len(result["participants"]["FII"]["records"]),5)
        self.assertNotIn("do-not-persist",str(result))
        self.assertEqual(flows.read(research._connect,self.now+timedelta(hours=3))["participants"]["FII"]["records"],[])

    def test_failed_refresh_suppresses_old_records_and_partial_is_not_paired(self):
        flows.refresh(research._connect,self.report,self.now)
        def partial(interval):
            report=self.report(interval)
            report["participants"]["dii"]={"status":"UNAVAILABLE"}
            return report
        later=self.now+timedelta(hours=1)
        flows.refresh(research._connect,partial,later)
        result=flows.read(research._connect,later)
        self.assertEqual(result["status"],"PARTIAL_PROVIDER_EVIDENCE")
        self.assertIsNone(result["paired_five_date_window"])
        self.assertEqual(result["participants"]["DII"]["records"],[])

    def test_invalid_future_and_conflicting_records_are_excluded(self):
        report=self.report("1D")
        rows=report["participants"]["fii"]["data"]
        rows.append({**rows[0],"buy_amount":999})
        rows.append({"observed_at":(self.now+timedelta(hours=1)).isoformat(),"buy_amount":100,"sell_amount":90})
        rows[1]["buy_amount"]="NaN"
        self.assertEqual(len(flows.normalize(report,"FII",self.now)),3)

    def test_permission_gate(self):
        with patch.dict(os.environ,{"MARKET_DATA_ENTITLEMENT_CONFIRMED":"false"}):
            flows.refresh(research._connect,lambda *_:self.fail("unauthorized"),self.now)
            self.assertEqual(flows.read(research._connect,self.now)["status"],"DISABLED_OR_NOT_AUTHORIZED")

    def test_flow_context_reports_matched_date_persistence_and_opposition(self):
        def report(interval):
            result=self.report(interval)
            for participant in ("fii","dii"):
                rows=[]
                for i in range(20):
                    buying=participant=="dii" or i>=15
                    rows.append({"observed_at":(self.now-timedelta(days=i,hours=1)).isoformat(),
                        "buy_amount":120 if buying else 80,"sell_amount":80 if buying else 120})
                result["participants"][participant]["data"]=rows
            return result
        flows.refresh(research._connect,report,self.now)
        context=flows.read(research._connect,self.now)["flow_context"]
        self.assertEqual(context["status"],"MATCHED_PROVIDER_DATES_ONLY")
        five,twenty=context["windows"]
        self.assertEqual(five["observation_count"],5)
        self.assertEqual(twenty["observation_count"],20)
        self.assertEqual(twenty["fii_selling_dii_buying_dates"],15)
        self.assertEqual(twenty["both_buying_dates"],5)
        self.assertEqual(twenty["participants"]["FII"]["net_selling_dates"],15)
        self.assertEqual(twenty["participants"]["FII"]["net_to_gross_percent"],-10)
        self.assertEqual(twenty["participants"]["FII"]["direction_consistency"],"NET_SELLING_MAJORITY")
        self.assertEqual(twenty["participants"]["DII"]["direction_consistency"],"NET_BUYING_MAJORITY")
        self.assertTrue(twenty["latest_date_is_today"])

    def test_context_withholds_missing_latest_dates_and_handles_zero_gross(self):
        flows.refresh(research._connect,self.report,self.now)
        result=flows.read(research._connect,self.now)
        fii={r["trade_date"]:r for r in result["participants"]["FII"]["records"]}
        dii={r["trade_date"]:r for r in result["participants"]["DII"]["records"]}
        today=self.now.astimezone(flows.IST).date()
        self.assertEqual(flows._paired_context(fii,{k:v for k,v in dii.items() if k!=max(dii)},today)["windows"],[])
        zero={k:{**v,"buy_amount":"0","sell_amount":"0","net_amount":"0"} for k,v in fii.items()}
        window=flows._paired_context(zero,dii,today)["windows"][0]
        self.assertIsNone(window["participants"]["FII"]["net_to_gross_percent"])
        self.assertEqual(window["one_or_both_balanced_dates"],5)
        invalid={k:{**v,"net_amount":"999"} for k,v in fii.items()}
        self.assertEqual(flows._paired_context(invalid,dii,today)["windows"],[])
