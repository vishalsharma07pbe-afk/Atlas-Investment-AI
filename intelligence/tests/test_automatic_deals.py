import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from app import automatic_deals as deals,autonomous_research as research

HEADER="trade_date,exchange,symbol,isin,deal_type,client_name,side,quantity,price_inr,source_report\n"
ROW="2026-11-23,NSE,TEST,INE002A01018,BULK,Example Client,SELL,1000,100,Example report\n"
NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)

class AutomaticDealTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.path=Path(root.name)/"deals.csv"
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":root.name+"/research.sqlite","ATLAS_DEAL_REPORTS_ENABLED":"true","MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true"})
        env.start()
        self.addCleanup(env.stop)

    def test_exact_identity_and_separate_sides_and_types(self):
        self.path.write_text(HEADER+ROW+ROW.replace("BULK","BLOCK").replace("SELL","BUY"))
        self.assertTrue(deals.refresh(research._connect,NOW,self.path))
        a={"symbol":"TEST","exchange":"NSE","isin":"INE002A01018"}
        b={**a,"isin":"INE009A01021"}
        snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{"SWING":{"candidates":[a,b]}}}}]}
        deals.attach(snapshot,research._connect,NOW)
        self.assertNotIn("deal_evidence",b)
        self.assertEqual(a["deal_evidence"]["groups"][0]["sell_reported_value_inr"],"100000")
        self.assertEqual(a["deal_evidence"]["groups"][1]["buy_quantity"],"1000")
        self.assertEqual(snapshot["institutional_activity"]["deal_reports"]["record_count"],2)
        self.path.write_text(HEADER+ROW+ROW)
        with self.assertRaises(ValueError):
            deals.refresh(research._connect,NOW,self.path)
        self.assertEqual(deals.attach({"enabled":True,"sections":[]},research._connect,NOW)["institutional_activity"]["deal_reports"]["record_count"],2)
        self.assertEqual(deals.attach({"enabled":True,"sections":[]},research._connect,NOW+timedelta(hours=49))["institutional_activity"]["deal_reports"]["status"],"NO_CURRENT_REPORT")

    def test_invalid_rows_and_permission(self):
        for bad in (ROW.replace("2026-11-23","2026-12-01"),ROW.replace("1000","0"),ROW.replace(",100,",",NaN,"),ROW.replace("INE002A01018","UNKNOWN")):
            with self.assertRaises(ValueError):
                deals.parse((HEADER+bad).encode(),NOW.date())
        with patch.dict(os.environ,{"ATLAS_DEAL_REPORTS_ENABLED":"false"}):
            self.assertFalse(deals.refresh(research._connect,NOW,self.path))
            self.assertEqual(research._execute_job("DEAL_REPORTS"),"DISABLED_OR_NOT_AUTHORIZED")
