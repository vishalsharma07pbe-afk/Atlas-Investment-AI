import json,os,tempfile,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from app.notifications import summary,details

class RevisionAndFreshnessTests(unittest.TestCase):
    def test_revision_keys_and_stale_subscription(self):
        published=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
        item={"id":"ipo-update-1","category":"IPO_SUBSCRIPTION",
            "title":"Illustrative IPO rate","description":"Not live market data",
            "published_at":published,"source_name":"Illustrative source",
            "source_url":"https://example.org/ipo","subscription_total_x":"2.5",
            "subscription_as_of":published}
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"alerts.json")
            with open(path,"w") as out:json.dump([item],out)
            with patch.dict(os.environ,{"ATLAS_ALERTS_FILE":path}):
                s=summary()
                d=details()
                self.assertEqual(s["ids"],["ipo-update-1"])
                self.assertEqual(s["revision_keys"],[d["alerts"][0]["revision_key"]])
                self.assertEqual(d["alerts"][0]["freshness"],"STALE")
                self.assertNotIn("alerts",s)
                self.assertNotIn("subscription_total_x",s)

if __name__=="__main__":unittest.main()
