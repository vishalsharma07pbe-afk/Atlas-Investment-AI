import tempfile,sqlite3,unittest
from datetime import datetime,timezone
from app import ranking_challenger as r
NOW=datetime(2026,11,28,6,tzinfo=timezone.utc)
def item(i,rank):
    return {"id":i,"isin":"INE"+str(i).zfill(9),"symbol":"TEST"+str(i),"exchange":"NSE","as_of":"2026-11-27","close":100,
        "adjustment_verified_for_screen":True,"publication_regime":"RISING","rank":rank}
class RankingChallengerTest(unittest.TestCase):
    def test_distinct_pair_and_weekly_budget(self):
        a,b=item(1,(1,0)),item(2,(0,1))
        experiment=r.selection([a,b],lambda x:x["rank"])
        self.assertEqual(experiment["fixed"]["id"],1)
        self.assertEqual(experiment["adaptive"]["id"],2)
        with tempfile.TemporaryDirectory() as tmp:
            def connect():
                db=sqlite3.connect(tmp+"/watch.db");db.row_factory=sqlite3.Row;return db
            snapshot={"enabled":True,"scope":"PUBLIC_MARKET_RESEARCH_ONLY","research_date":"2026-11-28","multi_strategy":{"ranking_experiment":experiment}}
            self.assertEqual(r.publish(snapshot,connect,NOW),2)
            self.assertEqual(r.publish(snapshot,connect,NOW),0)
            self.assertEqual(r.summary(connect,NOW)["published_pairs"],1)
            self.assertEqual(r.summary(connect,NOW)["observed_pairs"],0)
        b["exchange"]="BSE"
        self.assertEqual(r.selection([a,b],lambda x:x["rank"])["status"],"NONCOMPARABLE_SELECTIONS")
        self.assertEqual(r.selection([a],lambda x:x["rank"])["status"],"SAME_SELECTION")
