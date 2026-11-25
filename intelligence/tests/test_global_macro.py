import os
import tempfile
import unittest
import json
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from app import global_macro as macro, autonomous_research as research

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
def oil():
    return {"response":{"total":"4","frequency":"daily","data":[
        {"series":key,"period":day,"units":"$/BBL","value":value}
        for key in ("RBRTE","RWTC") for day,value in (("2026-11-24","80"),("2026-11-23","100"))]}}

def yields():
    return b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
    <entry><content><m:properties><d:NEW_DATE>2026-11-24T00:00:00</d:NEW_DATE><d:BC_2YEAR>4.05</d:BC_2YEAR><d:BC_10YEAR>4.2</d:BC_10YEAR><d:BC_30YEAR>4.8</d:BC_30YEAR></m:properties></content></entry>
    <entry><content><m:properties><d:NEW_DATE>2026-11-23T00:00:00</d:NEW_DATE><d:BC_2YEAR>4.00</d:BC_2YEAR><d:BC_10YEAR>4.15</d:BC_10YEAR><d:BC_30YEAR>4.7</d:BC_30YEAR></m:properties></content></entry></feed>'''

class GlobalMacroTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":root.name+"/research.sqlite",
            "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true","ATLAS_GLOBAL_OIL_ENABLED":"true","EIA_API_KEY":"test-only",
            "ATLAS_GLOBAL_YIELDS_ENABLED":"true"})
        env.start()
        self.addCleanup(env.stop)
    def test_changes_keep_units_separate_and_source_failure_isolated(self):
        a=macro.parse_oil(json.dumps(oil()).encode(),NOW.date())
        b=macro.parse_yields(yields(),2026,NOW.date())
        self.assertEqual(macro.summarize("OIL",a,NOW.date())[0]["changes"][0]["value"],-20)
        self.assertEqual(macro.summarize("YIELDS",b,NOW.date())[1]["changes"][0]["value"],5)
        macro.refresh(research._connect,"YIELDS",NOW,lambda *_:b)
        self.assertEqual(macro.read(research._connect,NOW)["status"],"PARTIAL")
        macro.refresh(research._connect,"OIL",NOW,lambda *_:a)
        self.assertEqual(macro.read(research._connect,NOW)["status"],"AVAILABLE")
        self.assertEqual(macro.read(research._connect,NOW+timedelta(hours=25))["status"],"UNAVAILABLE")
    def test_invalid_and_nonpositive_data(self):
        for field,value in (("units","EUR"),("series","UNKNOWN"),("period","2026-12-01"),("value","NaN")):
            bad=oil()
            bad["response"]["data"][0][field]=value
            with self.assertRaises(ValueError):
                macro.parse_oil(json.dumps(bad).encode(),NOW.date())
        bad=oil()
        bad["response"]["data"][0]["value"]="-10"
        rows=macro.parse_oil(json.dumps(bad).encode(),NOW.date())
        self.assertEqual(macro.summarize("OIL",rows,NOW.date())[0]["changes"],[])
        with self.assertRaises(ValueError):
            macro.parse_yields(b'<!DOCTYPE foo>'+yields(),2026,NOW.date())
        with self.assertRaises(ValueError):
            macro.parse_yields(yields(),2025,NOW.date())
    def test_permissions_no_external_fetch(self):
        with patch.dict(os.environ,{"EIA_API_KEY":"","ATLAS_GLOBAL_YIELDS_ENABLED":"false"}):
            for job in macro.JOBS:
                self.assertEqual(research._execute_job(job),"DISABLED_OR_NOT_AUTHORIZED")
