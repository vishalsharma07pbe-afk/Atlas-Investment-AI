import unittest
from datetime import datetime,timedelta,timezone
from pydantic import ValidationError
from app.news_events import NewsEvent,analyze_news

NOW=datetime(2026,11,13,12,tzinfo=timezone.utc)
def event(hours=1):
    return NewsEvent(headline="Synthetic example headline",
        source_name="Synthetic publisher",source_url="https://example.com/article",
        published_at=NOW-timedelta(hours=hours),geography="GLOBAL",
        event_type="MACRO",sentiment="UNKNOWN")

class NewsTests(unittest.TestCase):
    def test_fresh_and_stale(self):
        fresh=event(1)
        stale=event(100).model_copy(update={"source_url":"https://example.com/older"})
        result=analyze_news([stale,fresh],max_age_hours=72,now=NOW)
        self.assertEqual(result["fresh_count"],1)
        self.assertEqual(result["events"][0]["freshness"],"FRESH")
        self.assertFalse(result["events"][0]["independently_verified"])

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            analyze_news([event(),event()],now=NOW)

    def test_future_and_timezone_naive_rejected(self):
        with self.assertRaises(ValidationError):
            event().model_copy(update={"published_at":None})
            NewsEvent(headline="Synthetic example headline",source_name="Publisher",
                source_url="https://example.com/a",published_at=datetime.now(timezone.utc)+timedelta(days=1),
                geography="GLOBAL",event_type="MACRO")
        with self.assertRaises(ValidationError):
            NewsEvent(headline="Synthetic example headline",source_name="Publisher",
                source_url="https://example.com/a",published_at=datetime(2026,11,12),
                geography="GLOBAL",event_type="MACRO")

if __name__=="__main__":
    unittest.main()
