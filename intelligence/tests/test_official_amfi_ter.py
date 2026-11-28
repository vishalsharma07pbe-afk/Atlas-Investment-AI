import unittest,json,tempfile,sqlite3
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from app import official_amfi_ter as t
NOW=datetime(2026,11,28,5,tzinfo=timezone.utc)
KEY=(9,"HDFC/O/E/TEST")
MAPPING={KEY:{"scheme_code":123456,"isin_growth":"INF179K01BB2","plan":"DIRECT","option":"GROWTH"}}
def response():
    return {"meta":{"page":1,"pageCount":1,"total":1},"data":[{"NSDLSchemeCode":KEY[1],"MF_ID":9,"Month":"11-2026","SchemeType_Desc":"Open Ended",
        "TER_Date":"2026-11-27T00:00:00.000Z","D_BER":"0.3000","D_BrokerageCost":"0.0500","D_TransactionCost":"0.0500","D_StatutoryLevies":"0.1000","D_TER":"0.5000"}]}
class OfficialTerTest(unittest.TestCase):
    def test_exact_response_contract(self):
        row=t.parse(json.dumps(response()).encode(),9,"11-2026",NOW.date(),MAPPING)["123456"]
        self.assertEqual(row["ter_percent"],.5)
        self.assertEqual(row["isin_growth"],MAPPING[KEY]["isin_growth"])
        bad=response();bad["data"][0]["D_TER"]="0.30"
        with self.assertRaises(ValueError):t.parse(json.dumps(bad).encode(),9,"11-2026",NOW.date(),MAPPING)
        bad=response();bad["meta"]["total"]=2
        with self.assertRaises(ValueError):t.parse(json.dumps(bad).encode(),9,"11-2026",NOW.date(),MAPPING)
        self.assertEqual(t.parse(json.dumps(response()).encode(),9,"11-2026",NOW.date(),{}),{})
    def test_scheduler_one_request_and_original_date(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"map.json"
            path.write_text(json.dumps({"schema":t.VERSION,"authorization_attested":True,"schemes":[{"amc_id":9,"nsdl_scheme_code":KEY[1],"verified_date":"2026-11-27",**MAPPING[KEY]}]}))
            def connect():
                db=sqlite3.connect(Path(d)/"test.sqlite");db.row_factory=sqlite3.Row;return db
            calls=[]
            def loader(a,m):calls.append((a,m));return json.dumps(response()).encode()
            with patch.object(t,"permitted",return_value=True),patch.object(t.nav_catalog,"_connect",side_effect=connect):
                self.assertEqual(t.refresh(NOW,loader,path),1)
                self.assertEqual(t.refresh(NOW+timedelta(minutes=1),loader,path),0)
                self.assertEqual(calls,[(9,"11-2026")])
                self.assertEqual(t.read(NOW.date(),path)["items"]["123456"]["ter_date"],"2026-11-27")
                self.assertEqual(t.read(NOW.date()+timedelta(days=8),path)["items"],{})
            with patch.object(t,"permitted",return_value=False):
                self.assertEqual(t.refresh(NOW,loader,path),0)
