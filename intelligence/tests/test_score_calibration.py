import unittest,json,tempfile
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from app import score_calibration as s,watch_outcomes as watch,autonomous_research as research
from app.horizon_research import VERSION
TODAY=date(2026,11,27)
ISIN="INE002A01018"
def candidate(day,score=12):
    as_of=(day-timedelta(days=1)).isoformat();first=(day-timedelta(days=30)).isoformat()
    return {"id":1,"isin":ISIN,"symbol":"TEST","exchange":"NSE","as_of":as_of,"close":100,
      "adjustment_status":"ADJUSTED","rank_score":score,"rank_components":{"momentum_percent":score-2,"relative_volume_bonus":4,"atr_penalty":-2},
      "score_window":{"first_date":first,"last_date":as_of,"return_percent":score-2,"source_code":"UPSTOX","dates_digest":"a"*64},
      "score_risk_path":{"first_date":first,"last_date":as_of,"adjustment_status":"ADJUSTED","maximum_close_drawdown_percent":8,"annualized_daily_volatility_percent":30}}
def group(item):return {"methodology":VERSION,"status":"TECHNICAL_WATCH_ONLY","candidates":[item]}
def coverage(day):return {"calendar_status":"PUBLISHED_SESSION","calendar_checked_on":day.isoformat(),"expected_session":(day-timedelta(days=1)).isoformat()}
def row(day,score=12,status="OBSERVED",legacy=False):
    item=candidate(day,score);maturity=day+timedelta(days=14)
    evidence={"isin":ISIN,"methodology":VERSION,"adjustment_status":"ADJUSTED"}
    if not legacy:evidence["score_calibration"]=s.capture(item,"SWING",group(item),coverage(day),day)
    return {"published_at":day.isoformat()+"T10:00:00+00:00","observed_date":item["as_of"],"maturity_date":maturity.isoformat(),"status":status,"evidence":json.dumps(evidence),
      "outcome":json.dumps({"entry_date":(day+timedelta(days=1)).isoformat(),"exit_date":maturity.isoformat(),"entry_close":100,"exit_close":110,"source_code":"UPSTOX",
      "evidence_version":watch.OUTCOME_EVIDENCE_VERSION,"observations":10,"history_fingerprint":"b"*64,"calendar_status":"STORED_SESSIONS_MATCHED",
      "corporate_action_status":"NO_RECORDED_CROSSING_ACTION","action_context_through":maturity.isoformat()})}
class ScoreCalibrationTests(unittest.TestCase):
    def test_capture_reconciles_and_never_assigns_probability(self):
        item=candidate(TODAY);g=group(item);c=coverage(TODAY)
        frozen=s.capture(item,"SWING",g,c,TODAY)
        self.assertEqual(frozen["score_band"],"5_TO_BELOW_15")
        self.assertEqual(frozen["historical_risk"]["band"],"MEDIUM")
        self.assertIsNone(frozen["probability"])
        item["rank_score"]=13
        self.assertIsNone(s.capture(item,"SWING",g,c,TODAY))
    def test_missing_and_legacy_precede_overlapping_winner(self):
        rows=[row(date(2026,7,1),legacy=True),row(date(2026,7,5),20),row(date(2026,8,1),status="EVIDENCE_GAP"),row(date(2026,8,5),20),row(date(2026,9,1))]
        r=s.summarize(rows,"SWING",TODAY)
        self.assertEqual(r["legacy_or_unscored_mature"],1)
        self.assertEqual(r["overlap_excluded"],2)
        self.assertEqual(r["selected_scored_mature"],2)
        b=r["score_bands"][1]
        self.assertEqual(b["mature_count"],2);self.assertEqual(b["observed_count"],1)
        self.assertEqual(b["coverage_percent"],50)
        self.assertFalse(r["calibrated"])
    def test_publication_frozen_and_no_retroactive_backfill(self):
        item=candidate(TODAY);snap={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{"SWING":group(item)},"discovery_coverage":coverage(TODAY)}}]}
        now=datetime(2026,11,27,10,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp,patch.dict("os.environ",{"ATLAS_RESEARCH_SNAPSHOT_DB":tmp+"/research.sqlite"}):
            watch.publish(snap,research._connect,now)
            item["rank_score"]=999
            watch.publish(snap,research._connect,now)
            with research._connect() as db:
                evidence=json.loads(db.execute("SELECT evidence FROM watch_outcomes").fetchone()["evidence"])
            self.assertEqual(evidence["score_calibration"]["score"],12)
            self.assertEqual(s.read(research._connect,now)["horizons"]["SWING"]["immature_excluded"],1)
