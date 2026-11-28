import unittest
from datetime import date,timedelta
from app import long_history_validation as l

def fixture():
    names=["INE"+str(i).zfill(9) for i in range(11)]
    sessions=[];day=date(2019,1,1)
    for i in range(1700):
        while day.weekday()>=5:day+=timedelta(days=1)
        sessions.append({"date":day.isoformat(),"membership_known_on":day.isoformat(),"members":names[:],
            "observations":{k:[100*(1+.0001*(j+1))**i,10] for j,k in enumerate(names)},"benchmark_tri":100*(1.0003)**i})
        day+=timedelta(days=1)
    return {"methodology":l.VERSION,"authorization_attested":True,"historical_membership_attested":True,
        "total_return_and_terminal_events_attested":True,"benchmark":"NIFTY 500 TRI","sessions":sessions}
class LongHistoryTest(unittest.TestCase):
    def test_causal_baselines_and_costs(self):
        root=fixture();out=l.replay(root,date(2027,1,1))
        self.assertFalse(out["qualified"])
        self.assertGreater(out["monthly_rebalances"],60)
        self.assertGreater(out["momentum_top10"]["cagr_percent"],out["equal_weight_eligible"]["cagr_percent"])
        self.assertEqual(len(out["chronological_windows"]),2)
        root["sessions"][10]["membership_known_on"]="2026-01-01"
        with self.assertRaises(ValueError):l.replay(root,date(2027,1,1))
    def test_missing_held_mark_fails_instead_of_survivor_reweight(self):
        root=fixture();row=root["sessions"][600];key=row["members"][-1]
        row["members"].remove(key);del row["observations"][key]
        with self.assertRaises(ValueError):l.replay(root,date(2027,1,1))
