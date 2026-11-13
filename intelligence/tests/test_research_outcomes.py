import unittest
from datetime import date,timedelta
from pydantic import ValidationError
from app.research_outcomes import OutcomeRequest,evaluate

TODAY=date.today()
def report(days):
    return {"source":"GROWW","instrument_id":"INE848E01016","symbol":"EXAMPLE",
        "published_on":(TODAY-timedelta(days=days)).isoformat(),"rating":"BUY",
        "report_url":"https://example.org/research","report_title":"Historical example",
        "report_id":"r1"}
def price(days,close,adjustment="ADJUSTED",revision="rev1"):
    return {"trade_date":(TODAY-timedelta(days=days)).isoformat(),"close":close,
        "adjustment_status":adjustment,"source_revision":revision}

class ResearchOutcomeTests(unittest.TestCase):
    def test_mature_outcome_uses_post_publication_entry(self):
        request=OutcomeRequest(instrument_id="INE848E01016",horizon_days=30,
            reports=[report(50)],prices=[price(50,10),price(49,100),price(20,110)])
        result=evaluate(request)
        row=result["outcomes"][0]
        self.assertEqual(row["entry_date"],(TODAY-timedelta(days=49)).isoformat())
        self.assertEqual(row["observed_price_return_pct_unverified"],"10.0")
        self.assertFalse(row["accuracy_verified"])
        self.assertIsNone(result["verified_analyst_accuracy_score"])

    def test_immature_report_never_gets_outcome(self):
        request=OutcomeRequest(instrument_id="INE848E01016",horizon_days=30,
            reports=[report(10)],prices=[price(9,100),price(1,150)])
        row=evaluate(request)["outcomes"][0]
        self.assertIn("HORIZON_NOT_MATURE",row["blockers"])
        self.assertIsNone(row["observed_price_return_pct_unverified"])

    def test_adjustment_mismatch_blocks_return(self):
        request=OutcomeRequest(instrument_id="INE848E01016",horizon_days=30,
            reports=[report(50)],prices=[price(49,100),price(20,110,"RAW_UNADJUSTED")])
        row=evaluate(request)["outcomes"][0]
        self.assertIn("MIXED_PRICE_ADJUSTMENTS",row["blockers"])
        self.assertIsNone(row["observed_price_return_pct_unverified"])

    def test_duplicate_prices_and_future_reports_rejected(self):
        with self.assertRaises(ValidationError):
            OutcomeRequest(instrument_id="INE848E01016",reports=[report(50)],
                prices=[price(49,100),price(49,110)])
        with self.assertRaises(ValidationError):
            OutcomeRequest(instrument_id="INE848E01016",reports=[report(-1)],prices=[])

if __name__=="__main__":unittest.main()
