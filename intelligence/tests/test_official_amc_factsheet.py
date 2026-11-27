import unittest,tempfile,sqlite3,json
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from app import official_amc_factsheet as f
NOW=datetime(2026,11,27,5,tzinfo=timezone.utc)
URL="https://amc.ppfas.com/downloads/digital-factsheet/2026/october-2026/"
NAME="Parag Parikh Flexi Cap Fund"
def html():
    rows=[["Benchmark Name:","NIFTY 500 (TRI)"],["NAV as on October 30, 2026:"],["Direct Plan - Growth","89.2332"],
          ["Direct Plan:","0.53%*"],["Change in","Previous Month","Current Month"],["Scheme","Very High","Very High"],
          ["Benchmark","Very High","Very High"],["Change in","Previous Month","Current Month"],["Direct Plan:","0.53%*","0.53%*"]]
    return ("<h2>"+NAME+"</h2><table>"+"".join("<tr>"+"".join("<td>"+x+"</td>" for x in r)+"</tr>" for r in rows)+"</table>").encode()
class AMCSourceTests(unittest.TestCase):
    def test_exact_month_and_base_not_total(self):
        result=f.parse(html(),URL,NOW.date())[NAME]
        self.assertEqual(result["riskometer"],"VERY_HIGH")
        self.assertEqual(result["base_expense_percent"],.53)
        self.assertIsNone(result["ter_percent"])
        with self.assertRaises(ValueError):f.parse(html().replace(b"NIFTY 500 (TRI)",b"NIFTY 500"),URL,NOW.date())
        with self.assertRaises(ValueError):f.month("https://amc.ppfas.com.evil.test/downloads/digital-factsheet/2026/october-2026/",NOW.date())
    def test_cached_match_requires_exact_amfi_nav_and_revocable_permission(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"sources.json";db=Path(d)/"db.sqlite"
            path.write_text(json.dumps({"schema":f.VERSION,"authorization_attested":True,"sources":[URL]}))
            def connect():
                c=sqlite3.connect(db);c.row_factory=sqlite3.Row;return c
            with connect() as c:
                c.execute("CREATE TABLE nav_schemes(scheme_code INTEGER,isin_growth TEXT,source TEXT)")
                c.execute("CREATE TABLE nav_history(scheme_code INTEGER,nav_date TEXT,nav TEXT,source TEXT)")
                c.execute("INSERT INTO nav_schemes VALUES(123456,'INF179K01BB2','AMFI')")
                c.execute("INSERT INTO nav_history VALUES(123456,'2026-10-30','89.2332','AMFI')")
            candidate=SimpleNamespace(identifier="123456",name=NAME+" - Direct Plan - Growth",category="FLEXI_CAP",plan="DIRECT",option="GROWTH")
            rows=[{"scheme_code":123456,"isin_growth":"INF179K01BB2","amfi_plan":"DIRECT","amfi_option":"GROWTH"}]
            with patch.object(f,"permitted",return_value=True):
                self.assertTrue(f.refresh(NOW,path=path,connect=connect,loader=lambda *a:html()))
                result=f.matched([candidate],rows,NOW,path=path,connect=connect)
                self.assertEqual(result["123456"]["status"],"PUBLISHER_FACTSHEET_NAV_RECONCILED")
                self.assertFalse(result["123456"]["qualified"])
                with connect() as c:c.execute("UPDATE nav_history SET nav='90'")
                self.assertFalse(f.matched([candidate],rows,NOW,path=path,connect=connect))
            with patch.object(f,"permitted",return_value=False):
                self.assertFalse(f.matched([candidate],rows,NOW,path=path,connect=connect))
