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
