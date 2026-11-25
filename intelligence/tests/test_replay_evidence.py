import unittest
from copy import deepcopy
from datetime import date,timedelta
from app.replay_evidence import fingerprint,exact_isin

TODAY=date(2026,11,24)

def history(n=500):
    return [{"trade_date":(TODAY-timedelta(days=n-i)).isoformat(),"open":100,
        "high":102,"low":99,"close":101,"volume":100000,
        "adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED",
        "source_code":"UPSTOX","revision":1} for i in range(n)]

class ReplayEvidenceTests(unittest.TestCase):
    def test_recent_shared_window_matches_and_revisions_invalidate(self):
        data=history()
        expected=fingerprint(data,TODAY)
        self.assertIsNotNone(expected)
        self.assertEqual(expected,fingerprint(data[-250:],TODAY))
        data[0]["revision"]=2
        self.assertEqual(expected,fingerprint(data,TODAY))
        data[-250]["revision"]=2
        self.assertNotEqual(expected,fingerprint(data,TODAY))
        data[-250]["revision"]=1
        data[-1]["close"]=100.5
        self.assertNotEqual(expected,fingerprint(data,TODAY))

    def test_numeric_representation_does_not_change_evidence(self):
        data=history(50)
        expected=fingerprint(data,TODAY)
        data[0]["close"]="101.0000"
        data[1]["volume"]=100000.0
        self.assertEqual(expected,fingerprint(data,TODAY))

    def test_invalid_source_adjustment_quality_revision_or_volume_withheld(self):
        original=history(50)
        for field,value in (("source_code","OTHER"),("adjustment_status","RAW_UNADJUSTED"),
            ("quality_status","VALIDATED_MANUAL"),("revision",0),("revision",True),
            ("volume",1.5),("close",float("nan"))):
            data=deepcopy(original)
            data[-1][field]=value
            self.assertIsNone(fingerprint(data,TODAY),field)
        self.assertTrue(exact_isin("INE002A01018"))
        for value in ("INF002A01018","INE002A0101","TEST",None):
            self.assertFalse(exact_isin(value))

    def test_full_manifest_detects_older_changes_and_retains_shared_hash(self):
        from app.replay_evidence import full_manifest,revision_audit
        data=history()
        old=full_manifest(data,TODAY)
        shared=fingerprint(data,TODAY)
        data[0]["revision"]=2
        new=full_manifest(data,TODAY)
        self.assertEqual(shared,fingerprint(data,TODAY))
        self.assertNotEqual(old["digest"],new["digest"])
        audit=revision_audit(new,old)
        self.assertEqual(audit["status"],"REVISIONS_DETECTED")
        self.assertEqual(audit["changed_dates"],[data[0]["trade_date"]])
        self.assertEqual(audit["overlap_observations"],500)
        self.assertEqual(revision_audit(new,None)["status"],"NO_COMPARABLE_PRIOR_CAPTURE")
        self.assertEqual(revision_audit(full_manifest(data[1:],TODAY),new)["status"],"OVERLAP_UNCHANGED")
        data[0]["revision"]=0
        self.assertIsNone(full_manifest(data,TODAY))
        self.assertIsNotNone(fingerprint(data,TODAY))

    def test_recorded_action_context_does_not_certify_crossing_history(self):
        import json
        from app.replay_evidence import full_manifest,corporate_action_status
        manifest=full_manifest(history(),TODAY)
        empty={"latest_action_date":None,"corporate_action_context":"[]"}
        self.assertEqual(corporate_action_status(empty,manifest),"NO_RECORDED_CROSSING_ACTION")
        self.assertEqual(corporate_action_status({},manifest),"ACTION_CONTEXT_UNAVAILABLE")
        for kind in ("SPLIT","BONUS","DIVIDEND","RIGHTS"):
            action={"ex_date":manifest["last_date"],"action_type":kind}
            record={"latest_action_date":action["ex_date"],"corporate_action_context":json.dumps([action])}
            self.assertEqual(corporate_action_status(record,manifest),"RECORDED_ACTION_RECONCILIATION_REQUIRED")
            self.assertEqual(corporate_action_status({**record,"latest_action_date":None},manifest),"ACTION_CONTEXT_UNAVAILABLE")
        action={"ex_date":manifest["first_date"],"action_type":"SPLIT"}
        self.assertEqual(corporate_action_status({"latest_action_date":action["ex_date"],"corporate_action_context":json.dumps([action])},manifest),"NO_RECORDED_CROSSING_ACTION")
        self.assertEqual(corporate_action_status({"latest_action_date":action["ex_date"],"corporate_action_context":json.dumps([action]*33)},manifest),"ACTION_CONTEXT_UNAVAILABLE")

    def test_session_audit_detects_internal_and_trailing_gaps_and_unknowns(self):
        from app.replay_evidence import full_manifest,session_audit
        data=history(5)
        manifest=full_manifest(data,TODAY)
        rows=[{"trade_date":r["trade_date"],"state":"REGULAR"} for r in data]
        calendar={"exchange":"NSE","through":data[-1]["trade_date"],"days":rows}
        self.assertEqual(session_audit(manifest,calendar,"NSE",TODAY)["status"],"STORED_SESSIONS_MATCHED")
        for index in (2,4):
            gap=full_manifest(data[:index]+data[index+1:],TODAY)
            audit=session_audit(gap,calendar,"NSE",TODAY)
            self.assertEqual(audit["status"],"HISTORICAL_SESSION_MISMATCH")
            self.assertEqual(audit["missing_dates"],[data[index]["trade_date"]])
        for state,key,status in (("CLOSED","unexpected_observations","HISTORICAL_SESSION_MISMATCH"),
            ("UNKNOWN","unknown_days","HISTORICAL_CALENDAR_INCOMPLETE"),
            ("SPECIAL_SESSION_UNSUPPORTED","special_days","HISTORICAL_CALENDAR_INCOMPLETE")):
            changed=[{**r,"state":state} if i==2 else r for i,r in enumerate(rows)]
            audit=session_audit(manifest,{**calendar,"days":changed},"NSE",TODAY)
            self.assertEqual(audit[key],1)
            self.assertEqual(audit["status"],status)
        self.assertEqual(session_audit(manifest,{**calendar,"days":rows[:-1]},"NSE",TODAY)["unknown_days"],1)
        self.assertEqual(session_audit(manifest,{**calendar,"days":rows+[rows[0]]},"NSE",TODAY)["status"],"HISTORICAL_CALENDAR_UNAVAILABLE")
        self.assertEqual(session_audit(manifest,calendar,"BSE",TODAY)["status"],"HISTORICAL_CALENDAR_UNAVAILABLE")

    def test_session_audit_accepts_known_closure_without_candle(self):
        from app.replay_evidence import full_manifest,session_audit
        data=history(5)
        rows=[{"trade_date":r["trade_date"],"state":"CLOSED" if i==2 else "REGULAR"} for i,r in enumerate(data)]
        calendar={"exchange":"BSE","through":data[-1]["trade_date"],"days":rows}
        audit=session_audit(full_manifest(data[:2]+data[3:],TODAY),calendar,"BSE",TODAY)
        self.assertEqual(audit["status"],"STORED_SESSIONS_MATCHED")
        self.assertEqual(audit["regular_sessions"],4)

    def test_listing_audit_checks_recorded_dates_without_certifying_universe(self):
        from app.replay_evidence import full_manifest,listing_audit
        manifest=full_manifest(history(50),TODAY)
        identity={"id":1,"exchange":"NSE","symbol":"TEST","isin":"INE002A01018","series":"EQ",
                  "instrument_type":"EQUITY","active":True,"listing_status":"ACTIVE",
                  "listed_on":manifest["first_date"],"delisted_on":None,
                  "registry_source":"TEST","registry_revision":"r1"}
        result=listing_audit(identity,identity,manifest,TODAY)
        self.assertEqual(result["status"],"RECORDED_LISTING_DATES_CONSISTENT")
        self.assertFalse(result["historical_universe_verified"])
        for field,value in (("listed_on",None),("registry_revision",None),("listed_on","invalid")):
            changed={**identity,field:value}
            self.assertEqual(listing_audit(changed,changed,manifest,TODAY)["status"],"LISTING_EVIDENCE_UNAVAILABLE")
        for field,value in (("listed_on",manifest["last_date"]),("delisted_on",manifest["last_date"]),("active",False)):
            changed={**identity,field:value}
            self.assertEqual(listing_audit(changed,changed,manifest,TODAY)["status"],"LISTING_CONTEXT_CONTRADICTION")
        self.assertEqual(listing_audit(identity,{**identity,"registry_revision":"r2"},manifest,TODAY)["status"],"LISTING_CONTEXT_CHANGED")

    def test_scoped_action_context_checks_only_the_actual_outcome_interval(self):
        import json
        from app.replay_evidence import full_manifest,corporate_action_status
        manifest=full_manifest(history(20)[:10],TODAY)
        def record(day):
            return {"action_context_through":(TODAY-timedelta(days=1)).isoformat(),
                    "latest_action_date":day,"corporate_action_context":json.dumps([{"ex_date":day,"action_type":"DIVIDEND"}])}
        later=record(history(20)[-1]["trade_date"])
        self.assertEqual(corporate_action_status(later,manifest,require_scope=True,today=TODAY),"NO_RECORDED_CROSSING_ACTION")
        self.assertEqual(corporate_action_status(record(manifest["last_date"]),manifest,require_scope=True,today=TODAY),"RECORDED_ACTION_RECONCILIATION_REQUIRED")
        self.assertEqual(corporate_action_status({**later,"action_context_through":manifest["last_date"]},manifest,require_scope=True,today=TODAY),"ACTION_CONTEXT_UNAVAILABLE")
        self.assertEqual(corporate_action_status({"latest_action_date":None,"corporate_action_context":"[]"},manifest,require_scope=True,today=TODAY),"ACTION_CONTEXT_UNAVAILABLE")
