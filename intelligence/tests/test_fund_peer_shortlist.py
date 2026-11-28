import unittest
from datetime import date
from app import fund_peer_shortlist as p
from app.mutual_fund_recommendations import FundEvidence
TODAY=date(2026,11,27)
FIT={"status":"POTENTIALLY_SUITABLE"}
def fixture():
    funds=[];rows=[]
    for i in range(6):
        code=str(123450+i)
        funds.append(FundEvidence(identifier=code,name="Fund "+str(i),category="LARGE_CAP",category_verified=True,plan="DIRECT",option="GROWTH",nav=100,nav_date="2026-11-26",worst_rolling_return=i,volatility=20-i))
        rows.append({"scheme_code":int(code),"isin_growth":"INF"+str(i).zfill(9),"matched_weekly_comparison":{"methodology":"MF-WEEKLY-MATCH-1","anchor_count":157,"date_digest":"a"*64,"first_date":"2023-11-30","last_date":"2026-11-26","cagr_percent":10+i,"drawdown_percent":-20+i}})
    return funds,rows
def rolling(r):return {"above_median_percent":60}
class FundPeerTests(unittest.TestCase):
    def test_same_dates_and_risk_direction(self):
        f,r=fixture();s=p.build(f,r,"LARGE_CAP",FIT,TODAY,rolling)
        self.assertEqual(s["matched_count"],6)
        self.assertEqual(s["items"][0]["identifier"],"123455")
        self.assertEqual(s["items"][0]["score"],100)
        self.assertFalse(s["items"][0]["qualified"])
        self.assertEqual(len(s["items"]),3)
        r[-1]["matched_weekly_comparison"]["date_digest"]="b"*64
        self.assertEqual(p.build(f,r,"LARGE_CAP",FIT,TODAY,rolling)["matched_count"],5)
        r[-2]["isin_growth"]=r[-3]["isin_growth"]
        self.assertEqual(p.build(f,r,"LARGE_CAP",FIT,TODAY,rolling)["items"],[])
    def test_not_for_specialized_or_unsuitable(self):
        f,r=fixture()
        for cat,fit in (("INDEX",FIT),("LARGE_CAP",{"status":"POOR_FIT"})):
            self.assertEqual(p.build(f,r,cat,fit,TODAY,rolling)["items"],[])
    def test_holdings_quality_requires_original_weight_and_same_period(self):
        f,_=fixture()
        metric={"metric":"NET_PROFIT","periods":["2023-03-31","2024-03-31","2025-03-31","2026-03-31"],"coverage_weight_percent":75,"positive_growth_weight_percent":60,"negative_growth_weight_percent":10,"flat_growth_weight_percent":5,"covered_subset_weighted_cagr_percent":12}
        row={"scheme_code":f[0].identifier,"status":"SECONDARY_COMPOSITION_ONLY","portfolio_date":"2026-10-31","exact_listed_equity_weight_percent":95,"underlying_research":{"multi_year_quality":{"status":"REPORTED_MULTI_YEAR_EXPOSURE","assessed_weight_percent":80,"review_weight_percent":10,"historical_growth":[metric]}}}
        s=p.quality_watch(f,[row],"LARGE_CAP",FIT,TODAY)
        self.assertEqual(s["items"][0]["unassessed_fund_weight_percent"],20)
        self.assertFalse(s["items"][0]["qualified"])
        metric["positive_growth_weight_percent"]=61
        self.assertEqual(p.quality_watch(f,[row],"LARGE_CAP",FIT,TODAY)["items"],[])

    def test_public_category_research_does_not_imply_personal_suitability(self):
        from dataclasses import replace
        funds,rows=fixture()
        funds=[replace(f,category="SMALL_CAP") for f in funds]
        poor={"status":"POOR_FIT"}
        self.assertEqual(p.build(funds,rows,"SMALL_CAP",poor,TODAY,rolling)["items"],[])
        result=p.build(funds,rows,"SMALL_CAP",poor,TODAY,rolling,category_only=True)
        self.assertTrue(result["items"])
        self.assertEqual(result["scope"],"CATEGORY_RESEARCH_ONLY")
        self.assertEqual(result["selected_suitability"],"POOR_FIT")
        self.assertTrue(all(x["qualified"] is False for x in result["items"]))
