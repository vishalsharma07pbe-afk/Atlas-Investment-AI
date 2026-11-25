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
