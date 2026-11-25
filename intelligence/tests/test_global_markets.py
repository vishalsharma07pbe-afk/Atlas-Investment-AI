import json
import os
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from app import global_markets as market,autonomous_research as research

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
def fred():
    return {"units":"lin","count":2,"offset":0,"observation_start":"2026-08-27","observation_end":"2026-11-24",
            "observations":[{"date":"2026-11-24","value":"6000"},{"date":"2026-11-23","value":"5000"}]}
def metal():
    return {"status":"ok","meta":{"symbol":"XAU/USD","interval":"1day","type":"Commodity"},
            "values":[{"datetime":"2026-11-24","close":"3000"},{"datetime":"2026-11-23","close":"2500"}]}

class GlobalMarketTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":tmp.name+"/research.sqlite",
            "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true","ATLAS_GLOBAL_MARKETS_SERIES":"SP500,GOLD",
            "FRED_API_KEY":"test-only","TWELVE_DATA_API_KEY":"test-only"})
        env.start()
        self.addCleanup(env.stop)
    def test_independent_caches_and_permissions(self):
        a=market.parse_fred(json.dumps(fred()).encode(),NOW.date())
        b=market.parse_metals(json.dumps(metal()).encode(),"GOLD",NOW.date())
        market.refresh(research._connect,"SP500",NOW,lambda *_:a)
        market.refresh(research._connect,"GOLD",NOW,lambda *_:b)
        report=market.read(research._connect,NOW)
        self.assertEqual(report["status"],"PARTIAL")
        items={i["series"]:i for i in report["items"]}
        self.assertEqual(items["SP500"]["changes"][0]["percent"],20)
        self.assertEqual(items["GOLD"]["value"],3000)
        self.assertEqual(items["SILVER"]["status"],"DISABLED_OR_NOT_AUTHORIZED")
        self.assertEqual(research._execute_job("GLOBAL_SILVER"),"DISABLED_OR_NOT_AUTHORIZED")
        self.assertEqual(market.read(research._connect,NOW+timedelta(hours=25))["status"],"UNAVAILABLE")
    def test_invalid_or_current_day_data(self):
        for field,value in (("date","2026-11-25"),("value","NaN"),("date","2026-11-23")):
            bad=fred()
            bad["observations"][0][field]=value
            with self.assertRaises(ValueError):
                market.parse_fred(json.dumps(bad).encode(),NOW.date())
        bad=metal()
        bad["meta"]["symbol"]="XAG/USD"
        with self.assertRaises(ValueError):
            market.parse_metals(json.dumps(bad).encode(),"GOLD",NOW.date())
    def test_fred_metadata_identity_required(self):
        with patch.object(market,"_download",return_value=b'{"seriess":[{"id":"WRONG","frequency_short":"D","units":"Index"}]}') as load:
            with self.assertRaises(ValueError):
                market.collect("SP500",NOW.date())
            self.assertEqual(load.call_count,1)
