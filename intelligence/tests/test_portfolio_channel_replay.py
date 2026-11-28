import unittest
from datetime import date,timedelta
from unittest.mock import patch
from app import portfolio_channel_replay as p
from app.technical import Candle

A="INE002A01018";B="INE467B01029"
def history():
    start=date(2025,1,1)
    return [Candle((start+timedelta(days=i)).isoformat(),100+i*.04,101+i*.04,99+i*.04,100+i*.04,2_000_000,"ADJUSTED") for i in range(320)]

class SharedCashReplayTest(unittest.TestCase):
    def test_shared_capital_pyramiding_and_gap_exit(self):
        a=history();b=history()
        for i in range(253,280):
            o=110+2*(i-253)
            for c in (a,b):c[i]=Candle(c[i].date,o,o+1,o-1,o,2_000_000,"ADJUSTED")
        for i in range(280,320):
            for c in (a,b):c[i]=Candle(c[i].date,90,91,89,90,2_000_000,"ADJUSTED")
        from app import multi_strategy as m
        # Test portfolio execution independently from the price signal selector.
        def select(window,calendar):
            return {"match":window[-1].date==a[252].date}
        with patch.object(m,"price_features",side_effect=select),patch.object(m,"price_lanes",side_effect=lambda f:["TURTLE_LONG_BREAKOUT"] if f["match"] else []):
            result=p.simulate({A:a,B:b})
        self.assertEqual(result["completed_positions"],2)
        self.assertGreater(result["pyramid_adds"],0)
        self.assertLessEqual(result["maximum_open_units"],8)
        self.assertFalse(result["qualified"])
        self.assertIsNone(p.simulate({A:a,B:b[:-1]}))
        self.assertIsNone(p.unpack(p.pack(a)[:-100]))

    def test_cache_keeps_exact_identity_and_date_cohorts(self):
        a=history();today=date.fromisoformat(a[-1].date)+timedelta(days=1)
        raw=p.pack(a)
        self.assertIsNone(p.from_cache([{"isin":A,"_portfolio_channel_history":raw},{"isin":A,"_portfolio_channel_history":raw}],today))
        self.assertIsNone(p.from_cache([{"isin":A,"_portfolio_channel_history":raw},{"isin":B,"_portfolio_channel_history":raw[:-1]}],today))
