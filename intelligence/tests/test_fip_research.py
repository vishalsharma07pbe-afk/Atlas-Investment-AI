import unittest,tempfile,json
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from app import fip_research as f,watch_outcomes as watch,autonomous_research as research
TODAY=date(2026,11,27)
NOW=datetime(2026,11,27,10,tzinfo=timezone.utc)
ISIN="INE002A01018"
def fixture(n=253):
    days=[TODAY-timedelta(days=i) for i in range(1,800)]
    dates=sorted(d for d in days if d.weekday()<5)[-n:]
    prices=[100.]
    for i in range(1,n):prices.append(prices[-1]*(1.004 if i%5 else .997))
    raw=[{"trade_date":d.isoformat(),"open":p,"high":p,"low":p,"close":p,"volume":1000000,
        "adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED","source_code":"UPSTOX","revision":1} for d,p in zip(dates,prices)]
    calendar={"exchange":"NSE","through":(TODAY-timedelta(days=1)).isoformat(),"days":[{"trade_date":d.isoformat(),"state":"REGULAR" if d.weekday()<5 else "CLOSED"} for d in days]}
    return raw,calendar
class FipTests(unittest.TestCase):
    def test_full_calendar_and_smoothness(self):
        raw,c=fixture();dates=f.calendar_suffix(c,"NSE",TODAY)
        report=f.observe(raw,dates,TODAY)
        self.assertEqual(report["status"],"FIP_PRICE_MATCH")
        self.assertEqual(set(report["windows"]),{"20","60","120","252"})
        self.assertGreater(report["score"],65)
        self.assertIsNone(f.observe(raw[:-1],dates,TODAY))
        c["days"][0]["state"]="UNKNOWN";self.assertEqual(f.calendar_suffix(c,"NSE",TODAY),())
        raw[0]["adjustment_status"]="RAW_UNADJUSTED";self.assertIsNone(f.observe(raw,dates,TODAY))
    def test_concentrated_gain_rejected_and_replay_disjoint(self):
        p=[100.]*253;p[-1]=120.
        self.assertEqual(f.metrics(p,[1000000]*253)["status"],"FIP_FILTER_NOT_MET")
        raw,_=fixture(500);report=f.replay(raw,TODAY)
        self.assertEqual(report["status"],"DESCRIPTIVE_FIXED_RULE_REPLAY")
        for w in report["windows"]:
            self.assertLess(w["folds"][0]["last_date"],w["folds"][1]["first_date"])
    def test_broad_rank_and_immutable_prospective_publication(self):
        raw,c=fixture();report=f.observe(raw,f.calendar_suffix(c,"NSE",TODAY),TODAY)
        identity={"id":1,"isin":ISIN,"exchange":"NSE","as_of":report["as_of"],"security_state":"NORMAL","fip_research":report}
        venue={**identity,"symbol":"TEST","close":100}
        snap={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"discovery_coverage":{"calendar_checked_on":TODAY.isoformat(),"calendar_status":"PUBLISHED_SESSION","expected_session":report["as_of"]},"company_research_universe":[identity],"venue_observations":[venue]}}]}
        ranked=f.rank(snap,NOW);self.assertEqual(ranked["matched_companies"],1)
        with tempfile.TemporaryDirectory() as tmp,patch.dict("os.environ",{"ATLAS_RESEARCH_SNAPSHOT_DB":tmp+"/r.sqlite"}):
            f.publish(snap,research._connect,NOW)
            report["score"]=99
            f.publish(snap,research._connect,NOW)
            with research._connect() as db:
                row=db.execute("SELECT * FROM watch_outcomes WHERE horizon='FIP'").fetchone()
            self.assertEqual(json.loads(row["evidence"])["fip_score"],ranked["items"][0]["score"])
            self.assertEqual(f.prospective(research._connect,NOW)["immature"],1)
            # Venue switch on the same observed session does not duplicate
            # the frozen company publication.
            other={**identity,"id":2,"exchange":"BSE"}
            snap["sections"]=[{"section":"BSE","status":"READY","result":{"discovery_coverage":{"calendar_checked_on":TODAY.isoformat(),"calendar_status":"PUBLISHED_SESSION","expected_session":report["as_of"]},"company_research_universe":[other],"venue_observations":[{**other,"symbol":"TEST","close":101}]}}]
            f.publish(snap,research._connect,NOW)
            with research._connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM watch_outcomes WHERE horizon='FIP'").fetchone()[0],1)

    def test_acquisition_intersection_precedes_price_only_top_ten(self):
        from app import automatic_company_evidence as company
        raw,c=fixture();report=f.observe(raw,f.calendar_suffix(c,"NSE",TODAY),TODAY)
        rows=[]
        for i in range(12):
            rows.append({"id":i+1,"isin":f"INE000A{i:05d}","exchange":"NSE","as_of":report["as_of"],
                "security_state":"NORMAL","fip_research":{**report,"score":90-i},"symbol":f"T{i}","close":100})
        technical={**rows[-1],"adjustment_status":"ADJUSTED"}
        snap={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{
            "discovery_coverage":{"calendar_checked_on":TODAY.isoformat(),"calendar_status":"PUBLISHED_SESSION","expected_session":report["as_of"]},
            "company_research_universe":rows,"venue_observations":rows,"steady_momentum_candidates":[technical]}}]}
        self.assertNotIn(rows[-1]["isin"],[x["isin"] for x in f.rank(snap,NOW)["items"]])
        priority=list(company.identify_fip_priority(snap,NOW))
        self.assertEqual(priority[0][1],rows[-1]["isin"])
        self.assertEqual(len(priority),10)
        self.assertEqual(len({i for _,i in priority}),10)
        technical["as_of"]="2026-11-25"
        self.assertEqual(list(company.identify_fip_priority(snap,NOW))[0][1],rows[0]["isin"])

    def test_reported_history_observations_preserve_unverified_adjustment_boundary(self):
        raw,c=fixture()
        dates=f.calendar_suffix(c,"NSE",TODAY)
        raw=[{**r,"adjustment_status":"RAW_UNADJUSTED"} for r in raw]
        result=f.observe_reported(raw,dates,TODAY)
        self.assertEqual(result["status"],"REPORTED_PRICE_MATCH")
        self.assertFalse(result["qualification_eligible"])
        self.assertFalse(result["adjustment_verified"])
        self.assertNotIn("replay_evidence_hash",result)
        self.assertIsNone(f.observe(raw,dates,TODAY))
        raw[-1]["source_code"]="DIFFERENT"
        self.assertIsNone(f.observe_reported(raw,dates,TODAY))
