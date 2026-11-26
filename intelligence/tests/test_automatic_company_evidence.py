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

    def test_existing_cached_shareholding_is_enriched_without_extra_provider_call(self):
        def report(isin,key):
            result=self.report(isin,key)
            result["sections"]["shareholding"]={"status":"AVAILABLE","data":[
                {"category":name,"history":[{"period":"Sep 2026","value":current},{"period":"Jun 2026","value":previous}]}
                for name,current,previous in zip(
                    ("promoters","fii","other_dii","mutual_funds","retail_and_other"),
                    (48,20,11,10,11),(50,19,10,10,11))]}
            return result
        company.refresh(self.snapshot,research._connect,report,self.now)
        company.attach(self.snapshot,research._connect,self.now)
        ownership=self.item["company_evidence"]["ownership_research"]
        self.assertEqual(ownership["status"],"COMPARABLE_QUARTERS")
        self.assertEqual(ownership["review_prompts"][0]["category"],"promoters")

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

    def test_documented_provider_annual_response_is_consumed_end_to_end(self):
        from datetime import datetime,timezone
        def report(isin,key):
            def block(data):
                return {"status":"AVAILABLE","data":{"type":"consolidated","time_period":"yearly","units_in":"crore",**data}}
            def row(category,a,b):
                return {"category":category,"history":[{"period":"Mar 2026","value":b},{"period":"Mar 2025","value":a}]}
            return {"isin":isin,"sections":{
                "income_statement":block({"income_statement":[row("revenue",100,120),row("operating_profit",20,30),row("net_profit",10,12)],
                    "full_statement":[{"particular":"EPS - Diluted","history":[{"period":"Mar 2026","value":12},{"period":"Mar 2025","value":10}]}]}),
                "cash_flow":block({"cash_flow":[row("operating",15,18)]}),
                "balance_sheet":block({"history":[{"period":"Mar 2026","total_asset":200,"total_liability":100},{"period":"Mar 2025","total_asset":150,"total_liability":60}]})}}
        company.refresh(self.snapshot,research._connect,report,self.now)
        company.attach(self.snapshot,research._connect,self.now)
        evidence=self.item["company_evidence"]
        self.assertEqual(evidence["financial_trends"]["status"],"AVAILABLE")
        rows={r["metric"]:r for r in evidence["fundamental_quality"]["derived_metrics"]}
        self.assertEqual(rows["OPERATING_MARGIN"]["latest_value"],25)
        self.assertEqual(rows["OPERATING_CASH_TO_PROFIT"]["latest_value"],1.5)
        self.assertEqual(rows["REPORTED_LIABILITIES_TO_ASSETS"]["latest_period"],"2026-03")
        self.assertEqual(evidence["reported_earnings"]["items"][0]["observations"][-1]["reported_value"],12)
        self.assertFalse(evidence["reported_earnings"]["valuation_eligible"])

    def test_peer_collection_reuses_existing_rotation_and_cache(self):
        peers=["INE242A01010","INE009A01021","INE467B01029"]
        calls=[]
        def report(isin,key):
            calls.append(isin)
            return {"isin":isin,"sections":{
                "profile":{"status":"AVAILABLE","data":{"sector":"Refineries","company_profile":"Business description"}},
                "competitors":{"status":"AVAILABLE","data":[{"instrument_key":"NSE_EQ|"+p,"sector":"Refineries"} for p in peers]},
                "income_statement":{"status":"AVAILABLE","data":{"type":"consolidated","time_period":"yearly","units_in":"crore",
                    "income_statement":[{"category":"revenue","history":[{"period":"Mar 2025","value":100},{"period":"Mar 2026","value":120}]}]}}}}
        for _ in range(5):
            company.refresh(self.snapshot,research._connect,report,self.now)
        self.assertEqual(calls,[self.isin]+sorted(peers))
        company.attach(self.snapshot,research._connect,self.now)
        evidence=self.item["company_evidence"]
        self.assertEqual(evidence["peer_research"]["status"],"SAMPLED_PEER_COMPARISON")
        self.assertEqual(evidence["peer_research"]["cached_same_sector_count"],3)
        self.assertEqual(evidence["sections"]["competitors"]["data"][0]["instrument_key"],"NSE_EQ|"+peers[0])

    def test_public_fund_rotation_reuses_cache_and_isin_only_loader(self):
        calls=[]
        def loader(isin,key):
            calls.append((isin,key))
            return {"isin":isin,"sections":{"profile":{"status":"AVAILABLE","data":{"sector":"Example"}}}}
        ids=["INE009A01021",self.isin]
        for _ in range(3):
            company.refresh({"enabled":True,"sections":[]},research._connect,loader,self.now,explicit_isins=ids)
        self.assertEqual(calls,[(ids[0],None),(ids[1],None)])

    def test_documented_actions_are_preserved_and_never_promoted(self):
        def loader(isin,key):
            return {"isin":isin,"sections":{"corporate_actions":{"status":"AVAILABLE","source":{"endpoint":"/v2/fundamentals/"+isin+"/corporate-actions"},
                "data":[{"name":"Dividend","expiry_date":"14 Aug 2025","amount":5.5,"ratio":None,
                    "event_details":[{"name":"Announcement date","value":"25 Apr 2025"}]},
                    {"name":"Bonus","expiry_date":"20 Nov 2026","ratio":"1:1"},
                    {"name":"Split","expiry_date":"31 Feb 2026"}]}}}
        company.refresh(self.snapshot,research._connect,loader,self.now)
        reports=company.cached_action_reports(research._connect,[self.isin],self.now)
        actions=reports[self.isin]["sections"]["corporate_actions"]["data"]
        self.assertEqual(len(actions),2)
        self.assertEqual(actions[0]["date"],"2025-08-14")
        self.assertEqual(actions[0]["amount"],5.5)
        self.assertEqual(actions[1]["reported_ratio"],"1:1")
        self.assertEqual(actions[1]["ratio_basis"],"UNVERIFIED")
        self.assertFalse(actions[1]["adjustment_eligible"])
        self.assertEqual(company.cached_action_reports(research._connect,[self.isin],self.now+timedelta(hours=25)),{})

    def test_broad_discovery_rotation_preserves_watch_priority_and_budget(self):
        other="INE009A01021"
        third="INE242A01010"
        result=self.snapshot["sections"][0]["result"]
        result["eligible_count"]=2
        result["company_research_universe"]=[
            {"id":1,"exchange":"NSE","isin":other,"as_of":"2026-11-23"},
            {"id":2,"exchange":"NSE","isin":third,"as_of":"2026-11-23"}]
        calls=[]
        def load(isin,key):
            calls.append((isin,key))
            return {"isin":isin,"sections":{"profile":{"status":"AVAILABLE","data":{"sector":"Example"}}}}
        company.refresh(self.snapshot,research._connect,load,self.now)
        self.assertEqual(calls,[(self.isin,"NSE_EQ|"+self.isin)])
        company.refresh(self.snapshot,research._connect,load,self.now)
        self.assertEqual(calls[-1],(other,"NSE_EQ|"+other))
        company.attach(self.snapshot,research._connect,self.now)
        coverage=result["company_research_coverage"]
        self.assertEqual(coverage["distinct_eligible_isins"],2)
        self.assertEqual(coverage["fresh_cached_reports"],1)
        self.assertEqual(coverage["section_counts"]["profile"],1)
        company.refresh(self.snapshot,research._connect,load,self.now)
        self.assertEqual(calls[-1],(third,"NSE_EQ|"+third))
        company.refresh(self.snapshot,research._connect,load,self.now)
        self.assertEqual(len(calls),3)
        result["company_research_universe"][0]["as_of"]="2026-11-01"
        self.assertEqual(list(company.identify_sample(self.snapshot,self.now)),[("NSE",third)])
        result["company_research_universe"][1]["id"]=1
        self.assertEqual(list(company.identify_sample(self.snapshot,self.now)),[])
