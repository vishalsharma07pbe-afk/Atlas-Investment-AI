import unittest
from app import automatic_ai_review as review, ai_public_evidence as projection

def fixture():
    item={"symbol":"TEST","exchange":"NSE","isin":"INE002A01018","as_of":"2026-11-24","close":100,
          "history_count":90,"atr_percent":2,"adjustment_status":"ADJUSTED",
          "private_balance":999999123,"deal_evidence":{"client_name":"PRIVATE CLIENT"},
          "company_evidence":{"isin":"INE002A01018","peer_research":{"valuation_research":{
              "status":"UNDATED_PEER_MULTIPLES","metrics":[{"metric":"PE","company_value":10,"peer_median":20,
                  "peer_count":3,"premium_discount_percent":-50,"observation_period":"UNVERIFIED",
                  "company_retrieved_at":"2026-11-25T09:00:00+00:00","peers":[{"name":"PRIVATE PEER"}]}]}}},
          "news_evidence":{"status":"REVIEW_AVAILABLE","retrieved_at":"2026-11-25T09:00:00+00:00","articles":[
              {"source_provider":"UPSTOX_NEWS","sentiment":"NOT_ANALYZED","published_at":"2026-11-24T08:00:00+00:00",
               "topics":["EARNINGS","INJECTED"],"headline":"SECRET RAW HEADLINE","url":"https://example.com/private"}]}}
    context={"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":"2026-11-25",
             "market_regime":{"status":"OBSERVED_BENCHMARK_REGIME","as_of":"2026-11-24","trend":"RISING",
                 "volatility_regime":"BELOW_HIGH_THRESHOLD","benchmark_change_60_percent":8,
                 "volatility_20_annualized_percent":12,"last_five_sessions":["2026-11-24","2026-11-23","2026-11-20","2026-11-19","2026-11-18"],
                 "institutional":{"status":"MATCHED_REPORTED_SESSIONS","fii":"NET_SELLING_MAJORITY","dii":"NET_BUYING_MAJORITY"}},
             "global_context":{"status":"PARTIAL","groups":[{"items":[{"key":"USD_INR","as_of":"2026-11-25",
                 "change":{"start_date":"2026-11-18","end_date":"2026-11-25","unit":"PERCENT","value":1.5},
                 "label":"SECRET LABEL"}]}]}}
    return item,context

class PublicAiEvidenceTests(unittest.TestCase):
    def test_extended_domains_and_privacy(self):
        item,ctx=fixture()
        pack=review.evidence(item,"SWING",ctx)
        supplied=review._supplied(pack)
        self.assertEqual(set(supplied),{"OBS","LIMITS","VAL","NEWS","GLOBAL","REGIME","FLOWS"})
        self.assertEqual(supplied["NEWS"]["observations"],[{"publication_date":"2026-11-24","topic":"EARNINGS"}])
        def runner(prompt,ids,providers):
            for forbidden in ("999999123","PRIVATE CLIENT","PRIVATE PEER","SECRET RAW HEADLINE","example.com","SECRET LABEL","INJECTED"):
                self.assertNotIn(forbidden,prompt)
            self.assertIn("UNDATED_PROVIDER_MULTIPLES_NOT_FAIR_VALUE",prompt)
            self.assertIn("NSE_CASH_MARKET_LEVEL_REPORTED_FLOWS_NOT_STOCK_TRANSACTIONS",prompt)
            self.assertEqual(set(ids),set(supplied))
            return {"status":"MODEL_GROUNDED","provider":providers[0],"response":{"findings":[
                {"statement":"Reported peer multiples have unverified observation periods.","evidence_ids":["VAL"]}]}}
        self.assertIsNotNone(review._review(pack,"OLLAMA",runner))
        self.assertEqual(review._committee(pack,["OLLAMA"],[{"provider":"OLLAMA","findings":[{"evidence_ids":["VAL"]}]}],{"OLLAMA"})["cited_domains"],["VAL"])
        before=review.identity(pack,["OLLAMA"])
        ctx["global_context"]["groups"][0]["items"][0]["change"]["value"]=2
        self.assertNotEqual(before,review.identity(review.evidence(item,"SWING",ctx),["OLLAMA"]))
    def test_identity_scope_invalid_units_and_stale_domains(self):
        item,ctx=fixture()
        item["company_evidence"]["isin"]="INE009A01021"
        ctx["global_context"]["groups"][0]["items"][0]["change"]["unit"]="BASIS_POINTS"
        ctx["market_regime"]["as_of"]="2026-11-23"
        pack=review.evidence(item,"SWING",ctx)
        self.assertEqual(set(review._supplied(pack)),{"OBS","LIMITS","NEWS"})
        ctx["scope"]="PRIVATE_PORTFOLIO"
        self.assertEqual(projection.summarize(item,ctx,item["as_of"]),{})
    def test_ownership_changes_reconciled(self):
        item,ctx=fixture()
        item["company_evidence"]["ownership_research"]={"status":"COMPARABLE_QUARTERS",
            "latest_period":"2026-09-30","previous_period":"2026-06-30","categories":[
                {"category":k,"latest_percent":20,"previous_percent":20,"change_pp":0} for k in projection.OWNERS]}
        pack=review.evidence(item,"SWING",ctx)
        self.assertIn("OWN",review._supplied(pack))
        item["company_evidence"]["ownership_research"]["categories"][0]["change_pp"]=5
        self.assertNotIn("OWN",review._supplied(review.evidence(item,"SWING",ctx)))
