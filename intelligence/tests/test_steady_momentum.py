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
