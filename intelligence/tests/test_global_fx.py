import os
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from app import global_fx as fx, autonomous_research as research

NOW=datetime(2026,11,25,12,tzinfo=timezone.utc)
HEADER="FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"

def fixture():
    rows=[]
    for day,usd,inr in (("2026-11-24","1.2","108"),("2026-11-23","1.1","99"),("2026-11-20","1","90")):
        rows.extend((f"D,USD,EUR,SP00,A,{day},{usd}",f"D,INR,EUR,SP00,A,{day},{inr}"))
    return HEADER+"\n".join(rows)+"\n"

class GlobalFxTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        env=patch.dict(os.environ,{"ATLAS_RESEARCH_SNAPSHOT_DB":root.name+"/research.sqlite",
            "ATLAS_GLOBAL_FX_ENABLED":"true","MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true"})
        env.start()
        self.addCleanup(env.stop)
    def test_rates_and_cross_use_same_dates_no_fallback(self):
        rows=fx.parse(fixture().encode(),NOW.date())
        items={r["pair"]:r for r in fx.summarize(rows,NOW.date())}
        self.assertEqual(items["USD_INR"]["rate"],90)
        self.assertEqual(items["USD_INR"]["changes"][0]["percent"],0)
        self.assertEqual(items["EUR_INR"]["rate"],108)
        self.assertEqual(items["GBP_INR"]["status"],"UNAVAILABLE")
        rows["USD"]["2026-11-25"]="1.2"
        self.assertEqual({r["pair"]:r for r in fx.summarize(rows,NOW.date())}["USD_INR"]["status"],"UNAVAILABLE")
    def test_invalid_rows_and_atomic_refresh(self):
        fx.refresh(research._connect,NOW,lambda _:fixture().encode())
        self.assertEqual(fx.read(research._connect,NOW)["status"],"PARTIAL_REFERENCE_RATES")
        for bad in (fixture()+"D,USD,EUR,SP00,A,2026-11-24,1.5\n",
                    fixture().replace("D,USD,EUR","M,USD,EUR"),fixture().replace(",108",",NaN")):
            with self.assertRaises(ValueError):
                fx.refresh(research._connect,NOW,lambda _:bad.encode())
        self.assertEqual(fx.read(research._connect,NOW)["status"],"PARTIAL_REFERENCE_RATES")
        self.assertEqual(fx.read(research._connect,NOW+timedelta(hours=25))["status"],"STALE_CAPTURE")
    def test_permission_gate(self):
        with patch.dict(os.environ,{"ATLAS_GLOBAL_FX_ENABLED":"false"}):
            fx.refresh(research._connect,NOW,lambda _:self.fail("network called"))
            self.assertEqual(research._execute_job("GLOBAL_FX"),"DISABLED_OR_NOT_AUTHORIZED")
