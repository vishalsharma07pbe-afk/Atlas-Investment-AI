import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from app.news_events import NewsEvent, NewsRequest
from app import news_ledger

def event(url="https://example.org/article"):
    return NewsEvent(headline="Global market policy update", source_name="Example Publisher",
        source_url=url, published_at=datetime.now(timezone.utc)-timedelta(hours=1),
        geography="GLOBAL", event_type="MACRO", sentiment="UNKNOWN")

class NewsLedgerTests(unittest.TestCase):
    def test_persistence_dedup_freshness_and_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(news_ledger, "DB_PATH", Path(folder)/"news.sqlite3"):
                request=NewsRequest(events=[event()])
                self.assertEqual(news_ledger.import_news(request)["inserted"],1)
                self.assertEqual(news_ledger.import_news(request)["duplicates"],1)
                listing=news_ledger.list_news()
                self.assertEqual(listing["event_count"],1)
                self.assertEqual(listing["fresh_count"],1)
                self.assertFalse(listing["automatic_feed_connected"])
                self.assertFalse(listing["events"][0]["independently_verified"])
                self.assertEqual(news_ledger.list_news(geography="INDIA")["event_count"],0)
                with self.assertRaisesRegex(ValueError,"CONFLICTING_NEWS_EVIDENCE"):
                    news_ledger.import_news(NewsRequest(events=[event().model_copy(update={"headline":"Conflicting article headline"})]))
                self.assertEqual(news_ledger.list_news()["event_count"],1)

    def test_reject_local_and_insecure_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(news_ledger, "DB_PATH", Path(folder)/"news.sqlite3"):
                for url in ["http://example.org/article","https://localhost/private","https://user:pass@example.org/article"]:
                    with self.assertRaisesRegex(ValueError,"SOURCE_URL_MUST_BE_PUBLIC_HTTPS"):
                        news_ledger.import_news(NewsRequest(events=[event(url)]))

    def test_query_bounds(self):
        with self.assertRaisesRegex(ValueError,"INVALID_NEWS_QUERY"):
            news_ledger.list_news(limit=201)
        with self.assertRaisesRegex(ValueError,"INVALID_GEOGRAPHY"):
            news_ledger.list_news(geography="MOON")

if __name__=="__main__":
    unittest.main()
