import struct
import unittest
from app.upstox_decoder import decode_quotes,DecodeError

KEY="NSE_EQ|INE002A01018"
def varint(n):
    out=bytearray()
    while n>127:out.append((n&127)|128);n>>=7
    out.append(n);return bytes(out)
def field(n,value,wire=2):
    if wire==2:return varint((n<<3)|2)+varint(len(value))+value
    if wire==0:return varint(n<<3)+varint(value)
    if wire==1:return varint((n<<3)|1)+value
def sample(key=KEY,price=150.25,trade=1000000,kind=1,mode="ltpc"):
    ltpc=field(1,struct.pack("<d",price),1)+field(2,trade,0)
    if mode=="full":feed=field(2,field(1,field(1,ltpc)))
    elif mode=="first":feed=field(3,field(1,ltpc))
    else:feed=field(1,ltpc)
    entry=field(1,key.encode())+field(2,feed)
    return field(1,kind,0)+field(2,entry)+field(3,1001000,0)

class DecoderTests(unittest.TestCase):
    def test_valid_direct_ltpc(self):
        result=decode_quotes(sample(),{KEY},now_ms=1001000)
        self.assertEqual(result["message_type"],"LIVE_FEED")
        self.assertEqual(result["quotes"][0]["last_traded_price"],150.25)
        self.assertEqual(result["rejected"],[])
    def test_full_feed(self):
        self.assertEqual(len(decode_quotes(sample(mode="full"),{KEY},now_ms=1001000)["quotes"]),1)
    def test_first_level_feed(self):
        self.assertEqual(len(decode_quotes(sample(mode="first"),{KEY},now_ms=1001000)["quotes"]),1)
    def test_market_info_is_not_quote(self):
        self.assertEqual(decode_quotes(field(1,2,0),{KEY})["quotes"],[])
    def test_initial_snapshot_not_claimed_live(self):
        self.assertEqual(decode_quotes(sample(kind=0),{KEY})["message_type"],"INITIAL_FEED")
    def test_unsubscribed_key_rejected(self):
        result=decode_quotes(sample(),{"NSE_EQ|OTHER"},now_ms=1001000)
        self.assertEqual(result["quotes"],[])
        self.assertEqual(result["rejected"],["UNSUBSCRIBED_INSTRUMENT"])
    def test_stale_trade_rejected(self):
        result=decode_quotes(sample(),{KEY},now_ms=2000000)
        self.assertEqual(result["rejected"],["INVALID_OR_STALE_TRADE"])
    def test_malformed_wire_rejected(self):
        for frame in (b"\x0a\xff",b"\x07",b"x"*(1_048_577)):
            with self.assertRaises(DecodeError):decode_quotes(frame,{KEY})

if __name__=="__main__":unittest.main()
