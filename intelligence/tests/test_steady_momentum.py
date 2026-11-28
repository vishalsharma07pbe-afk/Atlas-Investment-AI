import unittest
from datetime import date,timedelta
from io import BytesIO
from app.steady_momentum import technical,fundamentals
from app.technical import Candle,compute
from app.amfi_equity_caps import parse

def bars(pump=False,count=220):
    close=100.
    result=[]
    for i in range(count):
        close*=1.0035 if i%5<3 else .998
        if pump and i==218:close*=1.2
        result.append(Candle((date(2025,1,1)+timedelta(days=i)).isoformat(),close,close*1.008,close*.992,close,1000000,"ADJUSTED"))
    return result

def indicators(c):
    result=compute(c)
    for k,v in {"sma_20":c[-1].close*.99,"sma_50":c[-1].close*.95,
                "sma_200":c[-1].close*.85,"rsi_14":60,"macd":1,"macd_signal":.8,"atr_14":2}.items():
        result[k][-1]=v
    return result

def report(base=30,pe=20,eps_base=3):
    isin="INE002A01018"
    def series(name,values):
        return {"name":name,"history":[{"period":f"Mar {year}","value":v} for year,v in zip((2024,2025,2026),values)]}
    return {"isin":isin,"sections":{"income_statement":{"status":"AVAILABLE","source":{"provider":"UPSTOX","endpoint":f"/v2/fundamentals/{isin}/income-statement"},
        "data":{"units":"INR crore","statement_type":"consolidated","time_period":"yearly","rows":[series("revenue",[200,250,300]),series("net_profit",[base,40,50])],"eps_rows":[series("eps - diluted",[eps_base,4,5])]}},
        "ratios":{"status":"AVAILABLE","data":[{"name":"P/E","company_value":pe,"sector_value":25,"unit":"RATIO","sector_unit":"RATIO"}]}}}

class SteadyMomentumTests(unittest.TestCase):
    def test_single_day_pump_rejected(self):
        c=bars(True)
        self.assertIsNone(technical(c,indicators(c)))

    def test_insufficient_history_rejected(self):
        c=bars()[:200]
        self.assertIsNone(technical(c,compute(c)))

    def test_gradual_bullish_screen(self):
        c=bars()
        row=technical(c,indicators(c))
        self.assertIsNotNone(row)
        self.assertEqual(row["technical_rating"],"ATLAS_STRONG_BULLISH")

    def test_multiscale_observations_require_exact_window_depth(self):
        from app.steady_momentum import window_observations
        c=bars(count=253)
        observed=window_observations(c)
        self.assertEqual(set(observed),{"20","60","120","252"})
        self.assertAlmostEqual(observed["252"]["return_percent"],100*(c[-1].close/c[0].close-1),places=3)
        self.assertGreater(observed["252"]["maximum_close_drawdown_percent"],0)
        self.assertNotIn("252",window_observations(c[1:]))
        self.assertNotIn("252",window_observations([c[0],*c[10:]]))

    def test_cap_tabs_rank_beyond_overall_top_ten(self):
        from app.steady_momentum import ranked_shortlists
        rows=[{"isin":f"INE000A{i:05d}","exchange":"NSE","cap_category":"LARGE_CAP" if i<12 else "SMALL_CAP",
               "positive_day_percent":80-i,"largest_gain_share_percent":5,
               "median_daily_turnover_cr":10,"earnings_growth_percent":20} for i in range(13)]
        overall,categories,total=ranked_shortlists(rows+[{**rows[0],"exchange":"BSE"}])
        self.assertEqual(total,13)
        self.assertEqual(len(overall),10)
        self.assertEqual(categories["SMALL_CAP"],[rows[-1]])
        self.assertEqual(len(categories["LARGE_CAP"]),10)
        self.assertEqual(categories["MID_CAP"],[])

    def test_meaningful_earnings_and_valuation(self):
        item,reason=fundamentals(report(),date(2026,11,27))
        self.assertIsNone(reason)
        self.assertEqual(item["earnings_growth_percent"],25)
        for data,expected in ((report(base=1),"EARNINGS_BASE_OR_CONSISTENCY"),(report(eps_base=.01),"EPS_BASE_OR_GROWTH"),(report(pe=60),"VALUATION_SCREEN")):
            self.assertEqual(fundamentals(data,date(2026,11,27))[1],expected)

    def test_official_workbook_schema_and_identity(self):
        from openpyxl import Workbook
        workbook=Workbook()
        sheet=workbook.active
        sheet.append(["Average Market Capitalization"])
        sheet.append(["Sr. No.","Company name","ISIN","BSE Symbol","BSE cap","NSE Symbol","NSE cap","MSEI Symbol","MSEI cap","Average of All Exchanges (Rs. Cr.)","Categorization as per SEBI"])
        for i in range(1,251):
            sheet.append([i,"Fixture",f"INE000A{i:05d}","TEST",1000,"TEST",1000,None,None,1000,"Large Cap" if i<=100 else "Mid Cap"])
        output=BytesIO()
        workbook.save(output)
        self.assertEqual(len(parse(output.getvalue())),250)

    def test_coverage_is_not_the_count_of_technical_matches(self):
        from datetime import datetime,timezone
        from unittest.mock import patch
        from app.steady_momentum import summarize
        now=datetime(2026,11,27,7,tzinfo=timezone.utc)
        snapshot={"enabled":True,"sections":[
            {"section":"NSE","status":"READY","result":{"universe_size":200,"eligible_count":120,
             "discovery_coverage":{"calendar_checked_on":"2026-11-27","calendar_status":"PUBLISHED_SESSION"}}},
            {"section":"BSE","status":"READY","result":{"universe_size":200,"eligible_count":60,
             "discovery_coverage":{"calendar_checked_on":"2026-11-26","calendar_status":"PUBLISHED_SESSION"}}}]}
        with patch("app.automatic_company_evidence.permitted",return_value=False):
            result=summarize(snapshot,None,now)
        self.assertEqual(result["sampled_count"],400)
        self.assertEqual(result["eligible_history_count"],120)
        self.assertEqual(result["technical_count"],0)
        self.assertEqual(result["matched_count"],0)

    def test_amfi_period_rollover_does_not_relabel_old_classification(self):
        from app.amfi_equity_caps import periods,url_for
        self.assertEqual(periods(date(2026,11,27)),[date(2026,6,30)])
        self.assertEqual(periods(date(2027,1,3)),[date(2026,12,31),date(2026,6,30)])
        self.assertTrue(url_for(date(2026,12,31)).endswith("31Dec2026.xlsx"))

    def test_joint_strict_screen_ranks_after_fundamental_filters_and_deduplicates(self):
        from datetime import datetime,timezone
        from app import fip_research
        from app.steady_momentum import strict_suggestions
        now=datetime(2026,11,28,5,tzinfo=timezone.utc)
        rows=[]
        for i in range(13):
            rows.append({"id":i+1,"isin":f"INE000A{i:05d}","exchange":"NSE","symbol":f"T{i}",
              "adjustment_status":"ADJUSTED","as_of":"2026-11-27","median_daily_turnover_cr":10,
              "strict_fip_evidence":{"methodology":fip_research.VERSION,"status":"FIP_PRICE_MATCH","score":100-i,
                 "calendar_status":"STORED_SESSIONS_MATCHED","adjustment_status":"ADJUSTED","as_of":"2026-11-27"}})
        rows[0]["governance_review"]={"findings":["REVIEW"]}
        rows[1]["adjustment_status"]="RAW_UNADJUSTED"
        rows[2]["strict_fip_evidence"]={**rows[2]["strict_fip_evidence"],"as_of":"2026-11-26"}
        obs={rows[3]["isin"]:[{"exchange":"BSE","id":50,"security_state":"PCA"}]}
        matches,count=strict_suggestions(rows+[{**rows[4],"exchange":"BSE","id":51}],obs,now)
        self.assertEqual(count,9)
        self.assertEqual([r["isin"] for r in matches],[r["isin"] for r in rows[4:]])
        self.assertEqual(matches[0]["exchange"],"BSE")
        self.assertEqual(len({r["isin"] for r in matches}),len(matches))

    def test_full_stored_evidence_path_produces_joint_suggestion_and_company_report(self):
        from datetime import datetime,timezone
        from dataclasses import replace
        from contextlib import closing
        from unittest.mock import patch
        import json,sqlite3,tempfile
        from app import fip_research,steady_momentum,company_venues,company_reports,automatic_company_evidence
        now=datetime(2026,11,28,5,tzinfo=timezone.utc);today=now.date()
        day=date(2026,11,27);dates=[]
        while len(dates)<253:
            if day.weekday()<5:dates.append(day.isoformat())
            day-=timedelta(days=1)
        dates=tuple(reversed(dates))
        candles=[replace(c,date=d) for c,d in zip(bars(count=253),dates)]
        raw=[{"trade_date":c.date,"open":c.open,"high":c.high,"low":c.low,"close":c.close,
              "volume":c.volume,"adjustment_status":"ADJUSTED","quality_status":"PROVIDER_VALIDATED",
              "source_code":"TEST","revision":1} for c in candles]
        price=fip_research.observe(raw,dates,today)
        self.assertEqual(price["status"],"FIP_PRICE_MATCH")
        identity={"id":1,"isin":"INE002A01018","symbol":"TEST","exchange":"NSE","security_state":"NORMAL","as_of":dates[-1]}
        technical_match=technical(candles,indicators(candles))
        self.assertIsNotNone(technical_match)
        candidate={**technical_match,**identity}
        evidence=report()
        evidence["retrieved_at"]=now.isoformat()
        cap={"isin":identity["isin"],"average_cap_cr":2000,"cap_category":"SMALL_CAP","cap_as_of":"2026-06-30"}
        snapshot={"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":today.isoformat(),"sections":[{
          "section":"NSE","status":"READY","result":{"universe_size":1,"eligible_count":1,
            "discovery_coverage":{"calendar_checked_on":today.isoformat(),"calendar_status":"PUBLISHED_SESSION","expected_session":dates[-1]},
            "steady_momentum_candidates":[candidate],"company_research_universe":[{**identity,"fip_research":price}],
            "venue_observations":[company_venues.observation(identity,candles)]}}]}
        with tempfile.TemporaryDirectory() as folder:
            def connect():
                db=sqlite3.connect(folder+"/evidence.sqlite")
                db.row_factory=sqlite3.Row
                return db
            with closing(connect()) as db,db:
                automatic_company_evidence._table(db)
                db.execute("INSERT INTO automatic_company_evidence VALUES(?,?,?,?,?)",
                    (identity["isin"],now.isoformat(),now.isoformat(),"PARTIAL",json.dumps(evidence)))
            with patch.object(automatic_company_evidence,"permitted",return_value=True),patch("app.amfi_equity_caps.read",return_value={identity["isin"]:cap}):
                snapshot["steady_momentum"]=steady_momentum.summarize(snapshot,connect,now)
                result=snapshot["steady_momentum"]
                self.assertEqual(result["strict_suggestions"]["status"],"JOINT_SCREEN_MATCHES")
                self.assertEqual(result["strict_suggestions"]["matched_count"],1)
                self.assertEqual(result["strict_suggestions"]["items"][0]["isin"],identity["isin"])
                self.assertFalse(result["strict_suggestions"]["qualification_eligible"])
                self.assertEqual(result["qualified_count"],0)
                company_reports.attach(snapshot,now)
                self.assertIn(identity["isin"],snapshot["company_reports"]["items"])
                self.assertFalse(snapshot["company_reports"]["items"][identity["isin"]]["qualified"])
                with closing(connect()) as db,db:
                    db.execute("DELETE FROM automatic_company_evidence")
                self.assertEqual(steady_momentum.summarize(snapshot,connect,now)["strict_suggestions"]["items"],[])
