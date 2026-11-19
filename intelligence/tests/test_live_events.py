import asyncio
import unittest
from unittest.mock import patch

from app.live_events import changed_events,index_snapshot


class LiveEventTests(unittest.IsolatedAsyncioTestCase):
    def test_index_snapshot_only_exposes_fresh_validated_ticks(self):
        fresh={"status":"LIVE","reason":None,"quote":{
            "last_traded_price":25000.0,"change":100.0,"change_percent":0.4,
            "traded_at":"2026-11-19T04:00:00+00:00","age_ms":1000}}
        with patch("app.live_events.quote_worker.cache.snapshot",side_effect=lambda key:fresh if "Nifty 50" in key else {"status":"UNAVAILABLE","quote":None}):
            result=index_snapshot()
        self.assertEqual(result["status"],"AVAILABLE")
        self.assertEqual(len(result["items"]),1)
        self.assertEqual(result["items"][0]["price"],25000.0)

    async def test_stream_emits_initial_and_changed_payload_only(self):
        values=iter([
            {"status":"UNAVAILABLE","items":[],"reason":"WAITING"},
            {"status":"UNAVAILABLE","items":[],"reason":"WAITING"},
            {"status":"AVAILABLE","items":[{"instrument_key":"K","as_of":"T","price":1}]},
        ])
        stream=changed_events(lambda:next(values),interval=.001,heartbeat_seconds=60)
        first=await anext(stream)
        second=await asyncio.wait_for(anext(stream),.1)
        await stream.aclose()
        self.assertIn("event: quote",first)
        self.assertIn('"reason":"WAITING"',first)
        self.assertIn('"status":"AVAILABLE"',second)


if __name__=="__main__":unittest.main()
