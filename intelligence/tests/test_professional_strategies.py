import unittest
from datetime import date,datetime,timedelta,timezone
from app import professional_strategies as p
from app.technical import Candle

class ProfessionalStrategiesTest(unittest.TestCase):
    def test_channels_exclude_signal_bar(self):
        start=date(2025,1,1)
        c=[Candle((start+timedelta(days=i)).isoformat(),100,101,99,100,1_000_000,"ADJUSTED") for i in range(252)]
        c.append(Candle((start+timedelta(days=252)).isoformat(),101,112,101,110,2_000_000,"ADJUSTED"))
        f=p.price_patterns(c)
        self.assertTrue(f["breakout20"])
        self.assertTrue(f["breakout55"])
        self.assertIn("DONCHIAN_BREAKOUT",p.price_matches({"professional_patterns":f},True))
        self.assertEqual(p.price_matches({"professional_patterns":f},False),[])
    def test_full_f_score_requires_all_matched_components(self):
        t=date(2026,11,28)
        a,b,c="2024-03","2025-03","2026-03"
        x={"profit":{b:10,c:20},"cash":{b:12,c:25},"assets":{a:100,b:120,c:130},"revenue":{b:100,c:150},
           "gross_profit":{b:30,c:60},"long_debt":{b:30,c:20},"current_assets":{b:40,c:60},
           "current_liabilities":{b:30,c:30},"issuance":{b:0,c:0}}
        self.assertEqual(p.piotroski(x,t)["score"],9)
        del x["issuance"]
        self.assertIsNone(p.piotroski(x,t))
    def test_pead_requires_prior_consensus(self):
        now=datetime(2026,11,28,tzinfo=timezone.utc)
        e={"consensus_eps":10,"actual_eps":12,"consensus_as_of":"2026-11-20T00:00:00+00:00","released_at":"2026-11-24T00:00:00+00:00",
           "consensus_verified":True,"release_verified":True,"same_share_basis":True,"analyst_count":3}
        self.assertEqual(p.pead(e,now),20)
        e["consensus_as_of"]="2026-11-25T00:00:00+00:00"
        self.assertIsNone(p.pead(e,now))

    def test_matched_beta_is_date_and_venue_specific(self):
        today=date(2026,11,28)
        y=[.01 if i%2 else -.01 for i in range(60)]
        x=[v*.5 for v in y]
        f={"professional_patterns":{"beta_dates_digest":"test","beta_returns":x}}
        regime={"as_of":"2026-11-27","calendar_checked_on":"2026-11-28","beta_window":{"dates_digest":"test","returns":y}}
        row={"exchange":"NSE","as_of":"2026-11-27"}
        self.assertEqual(p.matched_beta(f,regime,row,today),.5)
        self.assertIsNone(p.matched_beta(f,regime,{**row,"exchange":"BSE"},today))
        self.assertIsNone(p.matched_beta(f,regime,row,today+timedelta(days=1)))

    def test_authorized_event_normalization_excludes_conflicts(self):
        from app import earnings_expectations as e
        now=datetime(2026,11,28,tzinfo=timezone.utc)
        row={"isin":"INE467B01029","quarter_end":"2026-09-30","consensus_eps":10,"actual_eps":12,
             "consensus_as_of":"2026-11-20T00:00:00+00:00","released_at":"2026-11-24T00:00:00+00:00",
             "consensus_verified":True,"release_verified":True,"same_share_basis":True,"analyst_count":3,
             "operator_reviewed":True,"consensus_source":"https://consensus.example/report.pdf",
             "release_source":"https://issuer.example/report.pdf","consensus_document_sha256":"a"*64,
             "release_document_sha256":"b"*64}
        def normalize(items):return e.normalize({"methodology":"AUTHORIZED-EARNINGS-EVENTS-1","events":items},now)
        result=normalize([row])
        self.assertIn(row["isin"],result)
        self.assertNotIn("consensus_source",result[row["isin"]])
        self.assertEqual(normalize([{**row,"operator_reviewed":False}]),{})
        self.assertEqual(normalize([row,{**row,"actual_eps":13}]),{})
        self.assertEqual(normalize([{**row,"consensus_eps":"10"}]),{})

    def test_strategy_risk_geometry_requires_adjustment_and_calendar(self):
        start=date(2025,1,1)
        c=[Candle((start+timedelta(days=i)).isoformat(),100,101,99,100,1_000_000,"ADJUSTED") for i in range(252)]
        c.append(Candle((start+timedelta(days=252)).isoformat(),101,112,101,110,2_000_000,"ADJUSTED"))
        f={"professional_patterns":p.price_patterns(c),"close":110,"calendar_matched":True,"adjustment_status":"ADJUSTED"}
        plan=p.strategy_risk_plan(f,["TURTLE_LONG_BREAKOUT"])
        self.assertEqual(plan["entry_trigger"],101)
        self.assertEqual(plan["channel_exit"],99)
        self.assertEqual(plan["exit_rule"],"20_SESSION_LOW_OR_2N_STOP")
        self.assertAlmostEqual(plan["n_or_atr"],2.5)
        self.assertEqual(plan["stop_scenario"],105)
        self.assertEqual(plan["target_scenario"],120)
        self.assertFalse(plan["qualified"])
        self.assertIsNone(p.strategy_risk_plan({**f,"calendar_matched":False},["TURTLE_LONG_BREAKOUT"]))
        self.assertIsNone(p.strategy_risk_plan({**f,"adjustment_status":"RAW_UNADJUSTED"},["TURTLE_LONG_BREAKOUT"]))
        self.assertIsNone(p.strategy_risk_plan({**f,"close":120},["TURTLE_LONG_BREAKOUT"]))

    def test_turtle_unit_is_cash_and_risk_capped(self):
        self.assertEqual(p.turtle_unit_size(100000,5,100,100000)["shares"],100)
        self.assertEqual(p.turtle_unit_size(100000,5,100,2500)["shares"],25)
        self.assertEqual(p.turtle_unit_size(100000,5,100,0)["shares"],0)
        self.assertIsNone(p.turtle_unit_size(100000,0,100,2500))
        self.assertIsNone(p.turtle_unit_size(100000,5,100,2500,2))
