import unittest,json,os,sqlite3,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from app import official_tri as t
NOW=datetime(2026,11,27,5,tzinfo=timezone.utc)
NAME="NIFTY 100 TRI"
URL="https://www.niftyindices.com/authorized-example.csv"
def csv_bytes():
    return ("IndexName,Date,Total Returns Index,Net Total Return Index\n"+"\n".join(
      f"Nifty 100,{(NOW.date()-timedelta(days=1,weeks=156-i)).isoformat()},{100+i},{90+i}" for i in range(157))).encode()
class OfficialTRITest(unittest.TestCase):
    def test_gross_column_and_identity(self):
        result=t.parse(csv_bytes(),NAME,NOW.date())
        self.assertEqual(result[-1]["tri"],256)
        with self.assertRaises(ValueError):t.parse(csv_bytes().replace(b"Nifty 100",b"Nifty 50"),NAME,NOW.date())
        with self.assertRaises(ValueError):t.parse(csv_bytes().replace(b"Total Returns Index",b"Close"),NAME,NOW.date())
        self.assertFalse(t.valid_url("https://www.niftyindices.com.evil.test/a.csv"))
        self.assertFalse(t.valid_url("https://www.niftyindices.com/a.csv?token=secret"))
    def test_permission_cache_identity_and_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"sources.json";db=Path(d)/"cache.sqlite"
            path.write_text(json.dumps({"schema":t.VERSION,"authorization_attested":True,"sources":[{"benchmark":NAME,"url":URL}]}))
            def connect():
                c=sqlite3.connect(db);c.row_factory=sqlite3.Row;return c
            with patch.object(t,"permitted",return_value=False):
                self.assertFalse(t.refresh(NOW,path=path,loader=lambda u:self.fail("unauthorized request"),connect=connect))
            with patch.object(t,"permitted",return_value=True):
                self.assertTrue(t.refresh(NOW,path=path,loader=lambda u:csv_bytes(),connect=connect))
                result=t.read(NOW,path=path,connect=connect)
                self.assertEqual(result["status"],"CURRENT_TRI_AVAILABLE")
                self.assertEqual(result["provenance"][NAME]["source_url"],URL)
                day=max(result["indices"][NAME])
                self.assertNotIn(NAME,t.combine({"indices":{NAME:{day:1}}},result)["indices"])
                self.assertEqual(t.read(NOW+timedelta(hours=49),path=path,connect=connect)["indices"],{})
                path.write_text(json.dumps({"schema":t.VERSION,"authorization_attested":True,"sources":[]}))
                self.assertEqual(t.read(NOW,path=path,connect=connect)["indices"],{})
