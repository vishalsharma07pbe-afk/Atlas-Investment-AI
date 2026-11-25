import unittest
from datetime import datetime,timezone
from app import global_context as context

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
def fixture():
    return {"enabled":True,"global_fx":{"items":[{"pair":"USD_INR","status":"AVAILABLE","rate":90,"as_of":"2026-11-24",
        "changes":[{"observations":5,"start_date":"2026-11-17","end_date":"2026-11-24","percent":2}]}]},
        "global_macro":{"sources":[{"source":"US Treasury","items":[{"series":"US10Y","status":"AVAILABLE","value":4.2,"as_of":"2026-11-24",
        "changes":[{"observations":5,"start_date":"2026-11-17","end_date":"2026-11-24","value":5,"unit":"BASIS_POINTS"}]}]}]}}

def company(sector):
    return {"isin":"INE002A01018","sections":{"profile":{"status":"AVAILABLE","data":{"sector":sector},"source":{"provider":"UPSTOX","retrieved_at":NOW.isoformat()}}}}

class GlobalContextTests(unittest.TestCase):
    def test_partial_coverage_units_and_no_duplicate_acceptance(self):
        snap=fixture()
        result=context.summarize(snap,NOW.date())
        self.assertEqual(result["total_count"],17)
        self.assertEqual(result["available_count"],2)
        self.assertEqual(result["groups"][2]["items"][0]["change"]["unit"],"BASIS_POINTS")
        snap["global_fx"]["items"]*=2
        self.assertEqual(context.summarize(snap,NOW.date())["available_count"],1)
        snap["enabled"]=False
        self.assertEqual(context.summarize(snap,NOW.date())["available_count"],0)

    def test_exact_sector_and_identity_required(self):
        snap=fixture()
        item={"exchange":"NSE","isin":"INE002A01018","company_evidence":company("Information Technology")}
        wrong={**item,"isin":"INE009A01021"}
        unmapped={**item,"company_evidence":company("Information Technology unrelated")}
        snap["sections"]=[{"section":"NSE","status":"READY","result":{"horizons":{"SWING":{"candidates":[item,wrong,unmapped]}}}}]
        context.attach(snap,NOW)
        report=item["global_exposure"]
        self.assertEqual(report["status"],"SECTOR_QUESTIONS_ONLY")
        self.assertEqual(report["questions"][0]["factor"],"USD_INR")
        self.assertEqual(report["missing_factors"],["NASDAQCOM"])
        self.assertEqual(wrong["global_exposure"]["status"],"COMPANY_SECTOR_UNAVAILABLE")
        self.assertEqual(unmapped["global_exposure"]["status"],"SECTOR_UNMAPPED")

    def test_invalid_change_not_converted_into_neutral(self):
        snap=fixture()
        snap["global_fx"]["items"][0]["changes"][0]["end_date"]="2026-11-23"
        self.assertIsNone(context.summarize(snap,NOW.date())["groups"][0]["items"][0]["change"])
