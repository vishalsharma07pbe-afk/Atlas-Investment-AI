import importlib.util
import json
from pathlib import Path
from datetime import datetime,timezone
import unittest

SPEC=importlib.util.spec_from_file_location("local_acceptance",Path(__file__).resolve().parents[2]/"scripts"/"local_research_acceptance.py")
a=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(a)
NOW=datetime(2026,11,28,4,tzinfo=timezone.utc)

class RecoveryAcceptanceTests(unittest.TestCase):
    def fixture(self):
        row={"exchange":"NSE","target_session":"2026-11-27","calendar_status":"VERIFIED_PRIOR_REGULAR_SESSION",
            **dict.fromkeys(a.RECOVERY_COUNTS,0),**dict.fromkeys(a.RECOVERY_FIELDS,0)}
        row.update(mapped_listings=10,mapped_companies=9,current_listings=4,recoverable_missing=6,due_missing=3,deep_listings=2)
        unknown={**row,"exchange":"BSE","target_session":None,"calendar_status":"UNVERIFIED",**dict.fromkeys(a.RECOVERY_FIELDS,None)}
        h={"generated_at":NOW.isoformat(),"configured":True,"provider_blocked":False,"depth_target":253,
           "distinct_mapped_companies":12,"exchanges":[row,unknown]}
        readiness={"research_jobs":{"company_acquisition":{"status":"DISABLED_OR_NOT_AUTHORIZED"},
            "fund_disclosure_acquisition":{"status":"NO_SNAPSHOT"},
            "global_source_recovery":{"status":"PERSISTED_GLOBAL_RECOVERY","providers":[{"provider":key,"state":"NOT_OBSERVED","retry_after_seconds":0} for key in a.GLOBAL_PUBLISHERS]}}}
        overview={"enabled":True,"sections":[{"section":"NSE","status":"FAILED"}],"historical_display":[{
            "section":"NSE","status":"HISTORICAL_DISPLAY_ONLY","generated_at":"2026-11-27T04:00:00+00:00",
            "current_status":"FAILED","metric":"20_SESSION_PRICE_CHANGE","qualification_eligible":False,
            "observations":[{"label":"PRIVATE_MARKER","observed_date":"2026-11-26","value_percent":2}]}]}
        providers={"automatic_fallback_available":False,"streaming_verified":False,"same_market_fallback_configured":False,
            "fallback_observation":{"status":"NOT_OBSERVED","route":"UPSTOX_TO_DHAN","observation_count":0,"last_observed_at":None}}
        return h,readiness,overview,providers
    def test_unknown_calendar_and_disabled_sources_not_certified(self):
        result=a.recovery_audit(*self.fixture(),instant=NOW)
        self.assertEqual(result["status"],"PASS")
        self.assertIsNone(result["observed_evidence"]["history"]["exchanges"]["BSE"]["current_listings"])
        self.assertEqual(result["product_acceptance"],"NOT_CERTIFIED")
        self.assertNotIn("PRIVATE_MARKER",json.dumps(result))
    def test_unknown_calendar_cannot_report_zero_and_due_cannot_exceed_backlog(self):
        args=self.fixture();args[0]["exchanges"][1]["current_listings"]=0
        self.assertEqual(a.recovery_audit(*args,instant=NOW)["checks"]["history_recovery_contract"],"BLOCKED")
        args=self.fixture();args[0]["exchanges"][0]["due_missing"]=7
        self.assertEqual(a.recovery_audit(*args,instant=NOW)["checks"]["history_recovery_contract"],"BLOCKED")
    def test_archive_cannot_be_qualified_or_contain_extra_fields(self):
        for changed in ({"qualification_eligible":True},{"observations":[{"label":"PRIVATE_MARKER","observed_date":"2026-11-26","value_percent":2,"target":123}]}):
            args=self.fixture();args[2]["historical_display"][0].update(changed)
            result=a.recovery_audit(*args,instant=NOW)
            self.assertEqual(result["checks"]["historical_display_isolation_contract"],"BLOCKED")
            self.assertNotIn("PRIVATE_MARKER",json.dumps(result))
    def test_missing_contract_is_blocked(self):
        self.assertEqual(a.recovery_audit({}, {}, {}, {},instant=NOW)["status"],"BLOCKED")

    def test_opportunity_audit_counts_outputs_without_certifying(self):
        row={"exchange":"NSE","id":1,"isin":"INE002A01018","symbol":"PRIVATE_MARKER"}
        overview={"steady_momentum":{"matched_count":3,"strict_suggestions":{
            "status":"JOINT_SCREEN_MATCHES","qualification_eligible":False,"matched_count":1,"items":[row]}}}
        result=a.qualification_audit(overview)
        self.assertEqual(result["elite"]["displayed_strict_suggestion_count"],1)
        self.assertEqual(result["elite"]["preliminary_business_match_count"],3)
        self.assertNotIn("PRIVATE_MARKER",json.dumps(result))
        self.assertIsNone(result["stocks"]["SWING"]["strict_watch_count"])
        overview["steady_momentum"]["strict_suggestions"]["items"]=[row,row]
        self.assertIsNone(a.qualification_audit(overview)["elite"]["displayed_strict_suggestion_count"])

    def test_result_acceptance_requires_current_populated_outputs_not_contracts(self):
        stock={"id":1,"isin":"INE002A01018","symbol":"PRIVATE_MARKER","exchange":"NSE",
               "as_of":"2026-11-27","status":"SCREEN_MATCH_ONLY","adjustment_status":"ADJUSTED",
               "strict_fip_evidence":{"status":"FIP_PRICE_MATCH","calendar_status":"STORED_SESSIONS_MATCHED","as_of":"2026-11-27","adjustment_status":"ADJUSTED"}}
        sections=[{"section":"NSE","status":"READY","result":{"discovery_coverage":{"calendar_checked_on":"2026-11-28",
            "calendar_status":"PUBLISHED_SESSION","expected_session":"2026-11-27"}}}]
        for cat in ("LARGE_CAP","MID_CAP","SMALL_CAP"):
            sections.append({"section":cat,"status":"READY","result":{"historical_coverage":{"comparison_date":"2026-11-27"},
                "historical_research_shortlist":{"methodology":"MF-MATCHED-PEER-1","category":cat,"status":"HISTORICAL_SHORTLIST_AVAILABLE",
                "last_date":"2026-11-27","items":[{"identifier":"123456","qualified":False,"status":"HISTORICAL_RESEARCH_ONLY","nav_date":"2026-11-27"}]}}})
        overview={"enabled":True,"sections":sections,"steady_momentum":{"strict_suggestions":{"status":"JOINT_SCREEN_MATCHES",
            "qualification_eligible":False,"matched_count":1,"items":[stock]}}}
        review={"holding_count":0,"holdings":[]}
        result=a.result_acceptance(overview,review,NOW)
        self.assertEqual(result["status"],"POPULATED_RESEARCH_OBSERVED")
        self.assertEqual(result["final_investment_qualification"],"NOT_CERTIFIED")
        self.assertNotIn("PRIVATE_MARKER",json.dumps(result))
        stock["strict_fip_evidence"]["adjustment_status"]="RAW_UNADJUSTED"
        self.assertEqual(a.result_acceptance(overview,review,NOW)["status"],"AWAITING_POPULATED_RESEARCH")
        stock["strict_fip_evidence"]["adjustment_status"]="ADJUSTED"
        stock["governance_review"]={"findings":["REVIEW"]}
        self.assertEqual(a.result_acceptance(overview,review,NOW)["status"],"AWAITING_POPULATED_RESEARCH")
        del stock["governance_review"]
        stock["as_of"]="2026-11-25"
        self.assertEqual(a.result_acceptance(overview,review,NOW)["status"],"AWAITING_POPULATED_RESEARCH")
        stock["as_of"]="2026-11-27"
        sections[3]["status"]="STALE"
        self.assertEqual(a.result_acceptance(overview,review,NOW)["status"],"AWAITING_POPULATED_RESEARCH")
        self.assertEqual(a.result_acceptance({}, {},NOW)["status"],"AWAITING_POPULATED_RESEARCH")
