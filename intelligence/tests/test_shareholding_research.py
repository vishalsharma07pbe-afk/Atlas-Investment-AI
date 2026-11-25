import unittest
from datetime import date
from app import shareholding_research as research

TODAY=date(2026,11,25)


def report():
    latest=[48,20,11,10,11]
    prior=[50,19,10,10,11]
    return {"sections":{"shareholding":{"status":"AVAILABLE","data":[
        {"name":name,"history":[{"period":"Sep 2026","value":a},{"period":"Jun 2026","value":b}]}
        for name,a,b in zip(research.CATEGORIES,latest,prior)]}}}


class ShareholdingResearchTests(unittest.TestCase):
    def test_reconciled_quarters_and_percentage_point_decline(self):
        result=research.summarize(report(),TODAY)
        self.assertEqual(result["status"],"COMPARABLE_QUARTERS")
        self.assertEqual(result["latest_period"],"2026-09-30")
        self.assertEqual(result["previous_period"],"2026-06-30")
        self.assertEqual(result["categories"][0]["change_pp"],-2)
        self.assertEqual(result["categories"][1]["change_pp"],1)
        self.assertEqual([p["category"] for p in result["review_prompts"]],["promoters"])

    def test_latest_partial_does_not_fall_back(self):
        value=report()
        value["sections"]["shareholding"]["data"][0]["history"].pop(0)
        result=research.summarize(value,TODAY)
        self.assertEqual(result["status"],"PARTIAL_LATEST_QUARTER")
        self.assertEqual(result["review_prompts"],[])
        self.assertTrue(all(x["change_pp"] is None for x in result["categories"]))

    def test_conflicting_or_invalid_categories_and_unreconciled_totals(self):
        value=report()
        data=value["sections"]["shareholding"]["data"]
        data.append(data[0])
        self.assertEqual(research.summarize(value,TODAY)["status"],"CONFLICTING_REPORTED_CATEGORIES")
        value=report()
        data=value["sections"]["shareholding"]["data"]
        data[0]["history"].append(data[0]["history"][0])
        self.assertEqual(research.summarize(value,TODAY)["status"],"INVALID_OR_DUPLICATE_QUARTER")
        value=report()
        value["sections"]["shareholding"]["data"][0]["history"][0]["value"]=80
        self.assertEqual(research.summarize(value,TODAY)["status"],"UNRECONCILED_LATEST_QUARTER")

    def test_missing_adjacent_quarter_and_stale_evidence(self):
        value=report()
        for row in value["sections"]["shareholding"]["data"]:
            row["history"][1]["period"]="Mar 2026"
        self.assertEqual(research.summarize(value,TODAY)["status"],"LATEST_QUARTER_ONLY")
        self.assertEqual(research.summarize(value,date(2027,3,1))["status"],"STALE_QUARTER")
