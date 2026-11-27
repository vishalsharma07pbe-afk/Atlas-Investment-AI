import csv,io,tempfile,unittest
from datetime import date,datetime,timezone,timedelta
from unittest.mock import patch
from app import nse_surveillance as s,autonomous_research as research,governance_review

NOW=datetime(2026,11,27,10,tzinfo=timezone.utc)
ISIN="INE002A01018"
def payload(bad=False):
    stream=io.StringIO()
    writer=csv.writer(stream)
    for i in range(100):
        row=[""]*29
        row[:5]=["0","TEST" if i==0 else "TEST"+str(i),"Y","A","EQ"]
        for pos in s.INDICATORS:row[pos]="100"
        if i==0:row[5]="2";row[14]="1";row[18]="1"
        if bad and i==99:row[5]="999"
        writer.writerow(row)
    return stream.getvalue().encode()
def calendar(_):
    return {"exchange":"NSE","through":"2026-11-26","days":[{"trade_date":"2026-11-26","state":"REGULAR"}]}
def snapshot():
    row={"id":1,"isin":ISIN,"symbol":"TEST","exchange":"NSE","as_of":"2026-11-26"}
    return {"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{
      "discovery_coverage":{"calendar_checked_on":"2026-11-27","calendar_status":"PUBLISHED_SESSION","expected_session":"2026-11-26"},
      "venue_observations":[dict(row)],"steady_momentum_candidates":[row],"horizons":{}}}]}

class SurveillanceTests(unittest.TestCase):
    def test_strict_legacy_schema_positive_only(self):
        rows=s.parse(payload())
        self.assertEqual(rows[0]["findings"],["NSE_REPORTED_GSM_INDICATOR_2","NSE_REPORTED_PROMOTER_PLEDGE_MEASURE_INDICATOR_1","NSE_REPORTED_ESM_INDICATOR_1"])
        self.assertEqual(rows[1]["findings"],[])
        for bad in (payload(True),b"<html>error</html>",payload()+payload()):
            with self.assertRaises(ValueError):s.parse(bad)
    def test_calendar_unknown_and_permission_gates(self):
        self.assertIsNone(s.prior_session({"exchange":"NSE","through":"2026-11-26","days":[]},date(2026,11,27)))
        with patch.object(s,"permitted",return_value=False):
            self.assertFalse(s.refresh(None,NOW,lambda _:self.fail("calendar called"),lambda _:self.fail("network called")))
    def test_retention_exact_current_registry_and_no_clearance(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict("os.environ",{"ATLAS_RESEARCH_SNAPSHOT_DB":tmp+"/research.sqlite"}),patch.object(s,"permitted",return_value=True):
            self.assertTrue(s.refresh(research._connect,NOW,calendar,lambda _:payload()))
            self.assertTrue(s.refresh(research._connect,NOW,calendar,lambda _:self.fail("repeat download")))
            data=snapshot()
            s.attach(data,research._connect,NOW)
            row=data["sections"][0]["result"]["steady_momentum_candidates"][0]
            self.assertEqual(row["exchange_surveillance"]["status"],"REPORTED_CAUTION_CURRENT_FILE")
            decision=governance_review.assess(row,{},NOW.date())
            self.assertFalse(decision["clearance_verified"])
            self.assertIn("NSE_REPORTED_GSM_INDICATOR_2",decision["findings"])
            other=snapshot()
            other["sections"][0]["result"]["venue_observations"].append({"id":2,"isin":"INE009A01021","symbol":"TEST","exchange":"NSE"})
            s.attach(other,research._connect,NOW)
            self.assertNotIn("exchange_surveillance",other["sections"][0]["result"]["steady_momentum_candidates"][0])
