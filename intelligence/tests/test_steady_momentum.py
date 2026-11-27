import unittest
from datetime import date,timedelta
from io import BytesIO
from app.steady_momentum import technical,fundamentals
from app.technical import Candle,compute
from app.amfi_equity_caps import parse

def bars(pump=False):
    close=100.
    result=[]
    for i in range(220):
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
