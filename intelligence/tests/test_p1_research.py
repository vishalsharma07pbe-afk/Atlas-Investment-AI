import unittest
from unittest.mock import patch

from app import p1_research as p1


class P1ResearchTests(unittest.TestCase):
    def test_company_research_normalizes_ratios_and_keeps_partial_failures(self):
        def fake_get(path, params=None):
            if path.endswith("key-ratios"):
                return [{"name": "P/E", "company_value": "20", "sector_value": "10"}]
            if path.endswith("competitors"):
                raise p1.ProviderFailure("PROVIDER_HTTP_FAILURE")
            return [] if path.endswith(("share-holdings", "corporate-actions")) else {}
        with patch.object(p1, "_get", side_effect=fake_get):
            result = p1.company_research("INE002A01018", "NSE_EQ|INE002A01018")
        ratio = result["sections"]["ratios"]["data"][0]
        self.assertEqual(ratio["relative_difference_percent"], 100.0)
        self.assertEqual(result["sections"]["competitors"]["status"], "UNAVAILABLE")
        self.assertIsNone(result["recommendation"])

    def test_ratio_unit_mismatch_cannot_produce_relative_difference(self):
        ratio=p1._normalize_ratios([{"name":"ROE","company_value":"12%","sector_value":"0.1"}])[0]
        self.assertEqual(ratio["unit"],"PERCENT")
        self.assertEqual(ratio["sector_unit"],"RATIO")
        self.assertIsNone(ratio["relative_difference_percent"])

    def test_competitors_request_uses_documented_isin_without_exchange_mapping(self):
        with patch.object(p1,"_get",return_value=[]) as get:
            p1.company_research("INE002A01018")
            self.assertIn("/v2/fundamentals/INE002A01018/competitors",[call.args[0] for call in get.call_args_list])

    def test_competitor_route_uses_exact_supplied_venue_key_without_retry(self):
        for key in ("NSE_EQ|INE002A01018","BSE_EQ|INE002A01018","NSE_EQ|INE009A01021"):
            with patch.object(p1,"_get",return_value=[]) as get:
                p1.company_research("INE002A01018",key)
            calls=[call.args[0] for call in get.call_args_list if call.args[0].endswith("/competitors")]
            expected=key.replace("|","%7C") if key.endswith("INE002A01018") else "INE002A01018"
            self.assertEqual(calls,["/v2/fundamentals/"+expected+"/competitors"])

    def test_company_research_rejects_bad_identifiers(self):
        with self.assertRaisesRegex(ValueError, "INVALID_ISIN"):
            p1.company_research("bad")
        with self.assertRaisesRegex(ValueError, "INVALID_INSTRUMENT_KEY"):
            p1.company_research("INE002A01018", "bad key")

    def test_news_deduplicates_and_does_not_invent_sentiment(self):
        stamp = 1793471400000
        row = {"heading": "Result", "summary": "Summary", "article_link": "https://example.test/a",
               "thumbnail": None, "published_time": stamp}
        with patch.object(p1, "_get", return_value={"NSE_EQ|INE002A01018": [row, row]}):
            result = p1.company_news(["NSE_EQ|INE002A01018"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["sentiment"], "NOT_ANALYZED")

    def test_institutional_activity_computes_net_amount(self):
        with patch.object(p1, "_get", return_value={"NSE_EQ|CASH": [{
            "time_stamp": 1793471400000, "buy_amount": 150.5, "sell_amount": 100.25
        }]}):
            result = p1.institutional_activity("1d")
        self.assertEqual(result["participants"]["fii"]["data"][0]["net_amount"], 50.25)
        self.assertEqual(result["participants"]["dii"]["status"], "AVAILABLE")

    def test_institutional_activity_rejects_unknown_interval(self):
        with self.assertRaisesRegex(ValueError, "INVALID_INTERVAL"):
            p1.institutional_activity("weekly")


if __name__ == "__main__":
    unittest.main()
