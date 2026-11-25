import os
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app import automatic_company_evidence as company, autonomous_research as research

class CompanyEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":temp.name+"/research.sqlite3",
            "ATLAS_AUTOMATIC_COMPANY_RESEARCH_ENABLED":"true","MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true",
            "MARKET_DATA_ENTITLEMENT_CONFIRMED":"true","UPSTOX_ACCESS_TOKEN":"test-only"})
        env.start()
        self.addCleanup(env.stop)
        self.now=datetime(2026,11,24,10,tzinfo=timezone.utc)
        self.isin="INE002A01018"
        self.item={"isin":self.isin,"exchange":"NSE","symbol":"TEST"}
        self.snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{"LONG_TERM":{"candidates":[self.item]}}}}]}

    def report(self,isin,key):
        self.assertEqual(key,"NSE_EQ|"+self.isin)
        return {"isin":isin,"sections":{"ratios":{"status":"AVAILABLE","data":[{"name":"P/E","company_value":20,"sector_value":10,"unit":"RATIO","sector_unit":"RATIO"},{"name":"bad","company_value":"NaN"}]},"income_statement":{"status":"AVAILABLE","data":{"units_in":"crore","income_statement":[{"category":"Revenue","history":[{"period":"FY2025","value":100}]}]}}}}

    def test_cached_partial_evidence_and_expiry(self):
        company.refresh(self.snapshot,research._connect,self.report,self.now)
        company.refresh(self.snapshot,research._connect,lambda *a:self.fail("duplicate call"),self.now)
        company.attach(self.snapshot,research._connect,self.now)
        r=self.item["company_evidence"]
        self.assertEqual(r["available_sections"],2)
        self.assertEqual(len(r["sections"]["ratios"]["data"]),1)
        self.assertEqual(r["fundamental_quality"]["valuation"]["comparisons"][0]["premium_discount_percent"],100)
        self.assertIsNone(r["fundamental_quality"]["valuation"]["fair_value"])
        self.assertEqual(r["sections"]["income_statement"]["data"]["rows"][0]["history"][0]["period"],"FY2025")
        self.assertEqual(r["sections"]["cash_flow"]["status"],"UNAVAILABLE")
        self.item.pop("company_evidence")
        company.attach(self.snapshot,research._connect,self.now+timedelta(hours=25))
        self.assertNotIn("company_evidence",self.item)

    def test_cached_statement_trends_are_derived_without_new_provider_call(self):
        def report(isin,key):
            result=self.report(isin,key)
            result["sections"]["income_statement"]["data"]["income_statement"][0]["history"].append({"period":"FY2024","value":80})
            return result
        company.refresh(self.snapshot,research._connect,report,self.now)
        company.attach(self.snapshot,research._connect,self.now)
        self.assertEqual(self.item["company_evidence"]["financial_trends"]["items"][0]["change_percent"],25)
        company.attach(self.snapshot,research._connect,self.now)
        self.assertEqual(self.item["company_evidence"]["financial_trends"]["items"][0]["latest_year"],2025)

    def test_rights_required_and_identity_mismatch_rejected(self):
        with patch.dict(os.environ,{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}):
            company.refresh(self.snapshot,research._connect,lambda *a:self.fail("unauthorized"),self.now)
        company.refresh(self.snapshot,research._connect,lambda *a:{"isin":"WRONG","sections":{}},self.now)
        company.attach(self.snapshot,research._connect,self.now)
        self.assertNotIn("company_evidence",self.item)
        company.refresh(self.snapshot,research._connect,lambda *a:self.fail("cooldown"),self.now)

    def test_no_failed_snapshot_enrichment(self):
        self.snapshot["sections"][0]["status"]="FAILED"
        company.refresh(self.snapshot,research._connect,lambda *a:self.fail("failed snapshot"),self.now)
