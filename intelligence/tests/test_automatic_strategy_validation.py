import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from app.automatic_strategy_validation import refresh,read
from app.horizon_research import VERSION
from unittest.mock import patch

class AutomaticValidationTests(unittest.TestCase):
    def test_rotates_registry_not_current_picks_and_avoids_repeat_within_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            def connect():
                db=sqlite3.connect(directory+"/validation.sqlite")
                db.row_factory=sqlite3.Row
                return db
            now=datetime(2026,11,24,10,tzinfo=timezone.utc)
            snapshot={"enabled":True,"sections":[{"section":"NSE","status":"READY","result":{"horizons":{}}}]}
            calls=[]
            registry=[{"id":i,"symbol":f"TEST{i}","active":True,"listing_status":"ACTIVE","series":"EQ","exchange":"NSE","instrument_type":"EQUITY"} for i in (1,2)]
            def loader(path):
                calls.append(path)
                if path.startswith("/api/v1/instruments?"):
                    return registry
                i=int(path.split("/")[5])
                return {"instrument":{"id":i,"symbol":f"TEST{i}","exchange":"NSE"},"candles":[]}
            with patch("app.automatic_strategy_validation.replay",return_value={"status":"INSUFFICIENT_HISTORY","horizons":{}}):
                for _ in range(3):
                    refresh(snapshot,connect,loader,now)
            self.assertEqual(sum("candles?" in x for x in calls),2)
            result=read(connect,now)
            self.assertEqual(result["sample_count"],2)
            self.assertEqual(result["horizons"]["SWING"]["counts"],{"INSUFFICIENT_HISTORY":2})
            self.assertEqual(read(connect,now+timedelta(hours=49))["sample_count"],0)
            self.assertEqual(result["methodology"],VERSION)
