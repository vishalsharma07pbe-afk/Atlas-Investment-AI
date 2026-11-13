import asyncio
import json
import unittest
from app.upstox_transport import receive_session,reconnecting_stream,TransportPolicy,TransportUnavailable

class FakeWebSocket:
    def __init__(self,frames):self.frames=frames;self.sent=[]
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def send(self,message):self.sent.append(json.loads(message))
    def __aiter__(self):return self._iterate()
    async def _iterate(self):
        for frame in self.frames:yield frame

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscribe_and_binary_only(self):
        ws=FakeWebSocket([b"protobuf-data","ignore-text"])
        urls=[]
        def connect(url,**kwargs):
            urls.append(url)
            return ws
        frames=[]
        async def callback(frame):frames.append(frame)
        result=await receive_session("secret",["NSE_EQ|INE002A01018"],callback,
                                     connect=connect,authorize=lambda token:"wss://feed.upstox.com/test")
        self.assertEqual(result,1)
        self.assertEqual(frames,[b"protobuf-data"])
        self.assertEqual(ws.sent[0]["data"]["instrumentKeys"],["NSE_EQ|INE002A01018"])
        self.assertEqual(ws.sent[0]["method"],"sub")
        self.assertEqual(len(urls),1)

    async def test_oversize_frame_fails_closed(self):
        ws=FakeWebSocket([b"0123456789"])
        async def callback(frame):self.fail("Oversized frame forwarded")
        with self.assertRaises(TransportUnavailable):
            await receive_session("secret",["NSE_EQ|INE002A01018"],callback,
                                  policy=TransportPolicy(max_frame_bytes=4),
                                  connect=lambda *a,**k:ws,authorize=lambda token:"wss://feed.upstox.com/test")

    async def test_bounded_reconnect(self):
        attempts=[]
        async def failed_session(*args,**kwargs):
            attempts.append(1)
            raise OSError("token and URL must not leak")
        async def no_sleep(delay):pass
        result=await reconnecting_stream("secret",["NSE_EQ|INE002A01018"],
            lambda x:None,stop=asyncio.Event(),policy=TransportPolicy(max_retries=2),
            session=failed_session,sleep=no_sleep)
        self.assertEqual(len(attempts),3)
        self.assertEqual(result["status"],"DISCONNECTED")
        self.assertNotIn("secret",str(result))

    async def test_stop(self):
        stop=asyncio.Event()
        async def session(*args,**kwargs):stop.set();return 0
        result=await reconnecting_stream("secret",["NSE_EQ|INE002A01018"],
            lambda x:None,stop=stop,session=session)
        self.assertEqual(result["status"],"STOPPED")
        self.assertEqual(result["sessions"],1)

if __name__=="__main__":unittest.main()
