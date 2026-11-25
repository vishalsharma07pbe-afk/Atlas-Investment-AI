import unittest
from app.peer_research import summarize,selected

TARGET="INE002A01018"
PEERS=["INE242A01010","INE009A01021","INE467B01029"]

def report(isin,revenue=100,margin=20,period="2026-03",sector="Refineries"):
    base={"period_basis":"DECLARED_ANNUAL_MONTH_END","statement_type":"consolidated",
          "latest_period_may_be_stale":False,"latest_period":period,
          "previous_period":"2025-03","unit":"crore"}
    return {"isin":isin,"sections":{"profile":{"status":"AVAILABLE","data":{"sector":sector}},
        "competitors":{"status":"AVAILABLE","data":[{"instrument_key":"NSE_EQ|"+p,"sector":sector} for p in PEERS]}},
        "financial_trends":{"items":[{**base,"metric":"REVENUE","latest_value":revenue,"change_percent":10},
            {**base,"metric":"NET_PROFIT","latest_value":revenue*margin/100}]},
        "fundamental_quality":{"derived_metrics":[{"metric":"NET_MARGIN","latest_period":period,"unit":"PERCENT","latest_value":margin}]}}

class PeerResearchTests(unittest.TestCase):
    def test_comparable_three_peer_sample_uses_median_not_market_share(self):
        target=report(TARGET)
        peers={p:report(p,r,m) for p,r,m in zip(PEERS,[80,120,150],[10,25,30])}
        result=summarize(target,peers)
        rows={r["metric"]:r for r in result["metrics"]}
        self.assertEqual(result["status"],"SAMPLED_PEER_COMPARISON")
        self.assertEqual(rows["REVENUE"]["peer_median"],120)
        self.assertEqual(rows["REVENUE"]["peers_above"],2)
        self.assertEqual(rows["REVENUE_GROWTH"]["peer_median"],10)
        self.assertEqual(rows["NET_MARGIN"]["peer_median"],25)
        self.assertIn("not a market-leadership or market-share ranking",result["notice"])

    def test_incompatible_period_or_sector_withholds_comparison(self):
        peers={p:report(p) for p in PEERS}
        peers[PEERS[0]]=report(PEERS[0],period="2025-12")
        self.assertEqual(summarize(report(TARGET),peers)["metrics"],[])
        peers[PEERS[0]]=report(PEERS[0],sector="Banks")
        self.assertEqual(summarize(report(TARGET),peers)["cached_same_sector_count"],2)

    def test_self_duplicate_wrong_sector_and_invalid_identity_excluded(self):
        target=report(TARGET)
        target["sections"]["competitors"]["data"]=[
            {"instrument_key":"NSE_EQ|"+TARGET,"sector":"Refineries"},
            {"instrument_key":"NSE_EQ|"+PEERS[0],"sector":"Refineries"},
            {"instrument_key":"BSE_EQ|"+PEERS[0],"sector":"Refineries"},
            {"instrument_key":"NSE_EQ|"+PEERS[1],"sector":"Banks"},
            {"instrument_key":"NSE_FO|"+PEERS[2],"sector":"Refineries"}]
        self.assertEqual(selected(target),[(PEERS[0],"NSE_EQ|"+PEERS[0])])

    def test_stale_source_trend_cannot_support_margin(self):
        peers={p:report(p) for p in PEERS}
        peers[PEERS[0]]["financial_trends"]["items"][1]["latest_period_may_be_stale"]=True
        rows={r["metric"] for r in summarize(report(TARGET),peers)["metrics"]}
        self.assertNotIn("NET_MARGIN",rows)
        self.assertIn("REVENUE",rows)

    def test_peer_valuation_requires_industry_identity_source_and_retrieval_window(self):
        def multiples(isin,pe=10,pb=2,ev=8):
            row=report(isin)
            row["sections"]["profile"]["data"]["industry"]="Oil refining"
            row["sections"]["ratios"]={"status":"AVAILABLE","source":{"provider":"UPSTOX",
                "endpoint":f"/v2/fundamentals/{isin}/key-ratios","retrieved_at":"2026-11-25T10:00:00+00:00"},
                "data":[{"name":name,"company_value":value,"unit":"RATIO"} for name,value in
                        (("P/E",pe),("P/B",pb),("EV/EBITDA",ev))]}
            return row
        target=multiples(TARGET,8)
        target["fundamental_quality"]["status"]="REVIEW_REQUIRED"
        target["fundamental_quality"]["warnings"]=["NET_PROFIT_DETERIORATION_REVIEW"]
        peers={p:multiples(p,pe) for p,pe in zip(PEERS,[10,20,30])}
        result=summarize(target,peers)["valuation_research"]
        by={m["metric"]:m for m in result["metrics"]}
        self.assertEqual(result["status"],"UNDATED_PEER_MULTIPLES")
        self.assertEqual(by["PE"]["peer_median"],20)
        self.assertEqual(by["PE"]["premium_discount_percent"],-60)
        self.assertEqual(by["PE"]["peer_min"],10)
        self.assertEqual(by["PE"]["peer_max"],30)
        self.assertEqual(result["review_prompt"],"DISCOUNT_WITH_REPORTED_DETERIORATION_REVIEW")
        self.assertFalse(result["valuation_eligible"])
        self.assertIsNone(result["fair_value"])
        from copy import deepcopy
        for kind in ("industry","source","stamp","duplicate","negative","unit"):
            altered=deepcopy(peers)
            peer=altered[PEERS[0]]
            ratios=peer["sections"]["ratios"]
            if kind=="industry":
                peer["sections"]["profile"]["data"]["industry"]="Other"
            elif kind=="source":
                ratios["source"]["endpoint"]="/v2/fundamentals/"+TARGET+"/key-ratios"
            elif kind=="stamp":
                ratios["source"]["retrieved_at"]="2026-11-23T10:00:00+00:00"
            elif kind=="duplicate":
                ratios["data"].append(dict(ratios["data"][0]))
            elif kind=="negative":
                ratios["data"][0]["company_value"]=-1
            else:
                ratios["data"][0]["unit"]="PERCENT"
            self.assertNotIn("PE",{m["metric"] for m in summarize(target,altered)["valuation_research"]["metrics"]},kind)
        altered=deepcopy(peers)
        altered[PEERS[0]]["sections"]["ratios"]["source"]["retrieved_at"]="2026-11-24T15:00:00+00:00"
        altered[PEERS[1]]["sections"]["ratios"]["source"]["retrieved_at"]="2026-11-26T02:00:00+00:00"
        self.assertEqual(summarize(target,altered)["valuation_research"]["metrics"],[])
