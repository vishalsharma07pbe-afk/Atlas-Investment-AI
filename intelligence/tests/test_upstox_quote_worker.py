import asyncio
import struct
import unittest
from app.upstox_quote_worker import QuoteCache,QuoteWorker

KEY="NSE_EQ|INE002A01018"
def varint(n):
    out=bytearray()
    while n>127:out.append((n&127)|128);n>>=7
    out.append(n);return bytes(out)
def f(n,v,wire=2):
    if wire==2:return varint(n*8+2)+varint(len(v))+v
    if wire==0:return varint(n*8)+varint(v)
    return varint(n*8+1)+v
def frame(price=100.0,timestamp=1000000,previous_close=98.0):
    ltpc=f(1,struct.pack("<d",price),1)+f(2,timestamp,0)+f(4,struct.pack("<d",previous_close),1)
    return f(1,1,0)+f(2,f(1,KEY.encode())+f(2,f(1,ltpc)))

class QuoteCacheTests(unittest.TestCase):
    def test_freshness_and_disconnect(self):
        cache=QuoteCache()
        cache.ingest(frame(),{KEY},now_ms=1001000)
        self.assertEqual(cache.snapshot(KEY,now_ms=1001000)["status"],"UNAVAILABLE")
        cache.connected=True
        live=cache.snapshot(KEY,now_ms=1001000)
        self.assertEqual(live["status"],"LIVE")
        self.assertEqual(live["quote"]["previous_close"],98.0)
        self.assertAlmostEqual(live["quote"]["change_percent"],2.0408163265)
        self.assertEqual(cache.snapshot(KEY,now_ms=2000000)["status"],"STALE")
        cache.connected=False
        self.assertEqual(cache.snapshot(KEY,now_ms=1001000)["status"],"UNAVAILABLE")
    def test_rejects_unknown_key_and_malformed_frames(self):
        cache=QuoteCache()
        result=cache.ingest(frame(),{"NSE_EQ|UNKNOWN"},now_ms=1001000)
        self.assertEqual(result["quotes"],[])
        self.assertEqual(cache.diagnostics()["rejected_entries"],1)

class QuoteWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_gates_and_clears_state(self):
        worker=QuoteWorker()
        blocked=await worker.run("",[KEY],provider="UPSTOX",rights=True,entitlement=True)
        self.assertEqual(blocked["status"],"BLOCKED")
        async def mock_stream(token,keys,on_frame,*,stop):
            await on_frame(frame())
            return {"status":"STOPPED"}
        result=await worker.run("token",[KEY],provider="UPSTOX",rights=True,entitlement=True,stream=mock_stream)
        self.assertEqual(result["status"],"STOPPED")
        self.assertFalse(worker.running)
        self.assertFalse(worker.cache.connected)
        self.assertEqual(worker.cache.snapshot(KEY)["status"],"UNAVAILABLE")

if __name__=="__main__":unittest.main()
