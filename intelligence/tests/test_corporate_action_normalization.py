import json
import unittest
from datetime import date,timedelta
from dataclasses import replace
from app.technical import Candle
from app.corporate_action_normalization import preview,reconstruct
from app.screener import screen

ISIN="INE002A01018"

def action(day,kind="SPLIT",ratio="2"):
    return {"ex_date":day,"action_type":kind,"ratio":ratio,"cash_amount":None,
            "isin":ISIN,"ratio_basis":"POST_SHARES_PER_PRE_SHARE","source_revision":"test-1"}

def instrument(actions):
    return {"id":1,"exchange":"NSE","symbol":"TEST","isin":ISIN,
            "latest_action_date":max(a["ex_date"] for a in actions),
            "corporate_action_context":json.dumps(actions)}

def series():
    first=date(2026,10,20)
    return [Candle((first+timedelta(days=i)).isoformat(),p,p,p,p,1000)
            for i in range(25) for p in (100 if i<24 else 51,)]

class CorporateActionNormalizationTests(unittest.TestCase):
    def test_split_return_uses_share_multiplier_and_keeps_original_history(self):
        rows=series()
        result=preview(rows,instrument([action(rows[-1].date)]))
        self.assertEqual(result["status"],"KNOWN_ACTIONS_NORMALIZED_PRICE_ONLY")
        self.assertEqual(result["change_1d_percent"],2)
        self.assertEqual(result["window_price_change_percent"],2)
        self.assertEqual(rows[-2].close,100)
        self.assertEqual(rows[-2].adjustment_status,"RAW_UNADJUSTED")

    def test_bonus_and_split_compound(self):
        rows=series()
        rows=[replace(c,open=300,high=300,low=300,close=300) if i<10
              else replace(c,open=200,high=200,low=200,close=200) if i<24
              else replace(c,open=100,high=100,low=100,close=100) for i,c in enumerate(rows)]
        result=preview(rows,instrument([action(rows[10].date,"BONUS","1.5"),action(rows[-1].date)]))
        self.assertEqual(result["window_price_change_percent"],0)
        self.assertEqual(result["change_1d_percent"],0)

    def test_ambiguous_unsupported_and_mismatched_actions_are_withheld(self):
        rows=series()
        good=action(rows[-1].date)
        for events in ([{**good,"ratio_basis":None}],[{**good,"isin":"INE000A01001"}],
                       [good,{**good,"source_revision":"other"}],[{**good,"action_type":"DIVIDEND"}],
                       [{**good,"ratio":"NaN"}],[{**good,"action_type":"BONUS","ratio":"0.5"}]):
            with self.subTest(events=events):
                self.assertEqual(preview(rows,instrument(events))["status"],"NORMALIZATION_WITHHELD")

    def test_preview_does_not_admit_raw_history_to_rankings(self):
        rows=series()
        result=screen([instrument([action(rows[-1].date)])],lambda _:{"candles":[
            {"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,"close":c.close,
             "volume":c.volume,"adjustment_status":c.adjustment_status} for c in rows]},
            as_of=date(2026,11,14),batch_loaded=True,include_horizons=True)
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["RAW_CORPORATE_ACTION"],1)
        self.assertEqual(result["corporate_action_review"]["normalized_preview_count"],1)
        self.assertEqual(result["corporate_action_review"]["previews"][0]["change_1d_percent"],2)
        self.assertEqual(result["top_gainers"],[])

    def test_fresh_provider_crossing_blocks_raw_history_even_without_local_action(self):
        from datetime import datetime,timezone
        from app.corporate_action_normalization import normalize_reported_actions
        rows=series()
        instant=datetime(2026,11,14,10,tzinfo=timezone.utc)
        raw={"isin":ISIN,"sections":{"corporate_actions":{"status":"AVAILABLE",
              "source":{"provider":"UPSTOX","endpoint":"/v2/fundamentals/"+ISIN+"/corporate-actions","retrieved_at":instant.isoformat()},
              "data":normalize_reported_actions([{"name":"Split","expiry_date":rows[-1].date,"ratio":"1:2"}])}}}
        identity={"id":1,"exchange":"NSE","symbol":"TEST","isin":ISIN,"latest_action_date":None,"corporate_action_context":"[]"}
        def load(_):
            return {"candles":[{"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,"close":c.close,
                "volume":c.volume,"adjustment_status":c.adjustment_status} for c in rows]}
        result=screen([identity],load,as_of=instant.date(),batch_loaded=True,include_horizons=True,action_reports={ISIN:raw},instant=instant)
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["RAW_CORPORATE_ACTION"],1)
        self.assertEqual(result["corporate_action_review"]["provider_crossing_count"],1)
        self.assertEqual(result["corporate_action_review"]["normalized_preview_count"],0)
        self.assertEqual(result["top_gainers"],[])
        result=screen([identity],load,as_of=instant.date(),batch_loaded=True,action_reports={ISIN:raw},instant=instant+timedelta(hours=25))
        self.assertEqual(result["corporate_action_review"]["provider_crossing_count"],0)

    def test_reconstruction_preserves_ohlc_share_units_and_raw_rows(self):
        rows=[Candle("2026-11-19",100,110,90,104,101),Candle("2026-11-20",70,75,65,70,90)]
        data=instrument([action(rows[-1].date,"BONUS","1.5")])
        result=reconstruct(rows,data,expected_dates=tuple(c.date for c in rows))
        self.assertEqual(result["status"],"KNOWN_ACTIONS_RECONSTRUCTED_OHLCV")
        self.assertFalse(result["adjustment_eligible"])
        self.assertFalse(result["qualification_eligible"])
        self.assertEqual(result["calendar_status"],"STORED_SESSION_DATES_MATCHED")
        old,new=result["rows"]
        from fractions import Fraction
        self.assertEqual(Fraction(old["volume_share_equivalent_exact"]),Fraction(303,2))
        self.assertEqual(old["share_multiplier_exact"],"3/2")
        self.assertAlmostEqual(float(old["high"]),110/1.5)
        self.assertAlmostEqual(float(old["low"]),90/1.5)
        self.assertEqual(new["close"],"70")
        self.assertEqual(new["volume_share_equivalent"],"90")
        self.assertEqual(rows[0].volume,101)
        self.assertEqual(rows[0].adjustment_status,"RAW_UNADJUSTED")
        self.assertEqual(result["derived_fingerprint"],reconstruct(rows,data)["derived_fingerprint"])
        revised=reconstruct([replace(rows[0],revision=2),rows[1]],data)
        self.assertNotEqual(result["raw_fingerprint"],revised["raw_fingerprint"])
        self.assertNotEqual(result["derived_fingerprint"],revised["derived_fingerprint"])
        revised_action=instrument([{**action(rows[-1].date,"BONUS","1.5"),"source_revision":"test-2"}])
        self.assertNotEqual(result["action_fingerprint"],reconstruct(rows,revised_action)["action_fingerprint"])

    def test_reverse_split_fractional_volume_and_calendar_mismatch(self):
        rows=[Candle("2026-11-19",50,51,49,50,101),Candle("2026-11-20",100,102,98,100,60)]
        data=instrument([action(rows[-1].date,"SPLIT","0.5")])
        result=reconstruct(rows,data)
        self.assertEqual(result["rows"][0]["close"],"100")
        self.assertEqual(result["rows"][0]["volume_share_equivalent_exact"],"101/2")
        self.assertEqual(result["calendar_status"],"SESSION_CONTINUITY_UNVERIFIED")
        self.assertEqual(reconstruct(rows,data,expected_dates=("2026-11-18","2026-11-20"))["reason"],"STORED_SESSION_MISMATCH")
        self.assertEqual(reconstruct([replace(rows[0],high=1),rows[1]],data)["reason"],"INVALID_RAW_OHLCV")

    def test_adjusted_label_does_not_clear_unreconciled_recorded_action(self):
        rows=[replace(c,adjustment_status="ADJUSTED") for c in series()]
        data=instrument([action(rows[-1].date)])
        result=screen([data],lambda _ : {"candles":[
            {"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,"close":c.close,
             "volume":c.volume,"adjustment_status":c.adjustment_status} for c in rows]},
            as_of=date(2026,11,14),batch_loaded=True,include_horizons=True)
        self.assertEqual(result["eligible_count"],0)
        self.assertEqual(result["skipped"]["ADJUSTED_ACTION_RECONCILIATION"],1)
        self.assertEqual(result["top_gainers"],[])
