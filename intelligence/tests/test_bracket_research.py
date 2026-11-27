import unittest
from app import bracket_research as b
from datetime import date,timedelta
from app.replay_evidence import full_manifest
def bar(d,o,h,l,c):
    return {"trade_date":d,"open":o,"high":h,"low":l,"close":c,"volume":1000,"source_code":"UPSTOX","revision":1,"quality_status":"PROVIDER_VALIDATED","adjustment_status":"ADJUSTED"}
P={"lower_reference":90,"upper_reference":140,"stress_gap_percent":2}
class BracketTests(unittest.TestCase):
    def test_gap_stop_and_same_bar_ambiguity(self):
        first=bar("2026-11-23",100,110,95,105)
        result=b.simulate(P,[first,bar("2026-11-24",80,95,75,90)],30)
        self.assertEqual(result["status"],"LOWER_GAP")
        self.assertEqual(result["exit_reference"],80)
        self.assertLess(result["net_change_percent"],-20)
        both=b.simulate(P,[bar("2026-11-23",100,145,85,110)],30)
        self.assertEqual(both["status"],"AMBIGUOUS_BOTH_BOUNDARIES")
        self.assertNotIn("net_change_percent",both)
        self.assertLess(both["lower_case_net_percent"],both["upper_case_net_percent"])
    def test_no_chasing_and_cost_stress(self):
        self.assertEqual(b.simulate(P,[bar("2026-11-23",141,145,95,100)],30)["status"],"NO_ENTRY_OUTSIDE_BRACKET")
        self.assertEqual(b.simulate(P,[bar("2026-11-23",130,135,95,100)],30)["status"],"NO_ENTRY_STRESS_RATIO")
        self.assertEqual(b.simulate(P,[bar("2026-11-23",100,145,95,140)],30)["status"],"UPPER_TOUCHED")
        self.assertEqual(b.simulate(P,[bar("2026-11-23",100,110,95,105)],30)["status"],"EXPIRED_CLOSE")
        self.assertLess(b.ceiling(90,140,2,60),b.ceiling(90,140,2,15))
    def test_frozen_bridge_requires_original_fingerprint_and_actions(self):
        first=date(2026,9,1);days=[first+timedelta(days=i) for i in range(62)]
        rows=[bar(d.isoformat(),100,110,95,105) for d in days]
        today=days[-1]+timedelta(days=1)
        m=full_manifest(rows[:60],today)
        p={**P,"first_date":days[0].isoformat(),"as_of":days[59].isoformat(),"history_count":60,"history_fingerprint":m["digest"],"source_code":"UPSTOX"}
        calendar={"exchange":"NSE","through":days[-1].isoformat(),"days":[{"trade_date":d.isoformat(),"state":"REGULAR"} for d in days]}
        identity={"exchange":"NSE","isin":"INE002A01018","corporate_action_context":"[]","latest_action_date":None,"action_context_through":days[-1].isoformat()}
        result=b.evaluate_frozen(p,identity,rows,days[-2:],calendar,today,None,None)
        self.assertEqual(result["status"],"OBSERVED_BRACKET_CASES")
        changed=[dict(r) for r in rows];changed[0]["revision"]=2
        self.assertIsNone(b.evaluate_frozen(p,identity,changed,days[-2:],calendar,today,None,None))
        self.assertIsNone(b.evaluate_frozen(p,identity,rows[:60]+rows[61:],days[-2:],calendar,today,None,None))
        bad={**identity,"latest_action_date":days[60].isoformat(),"corporate_action_context":'[{"ex_date":"'+days[60].isoformat()+'","action_type":"SPLIT"}]'}
        self.assertIsNone(b.evaluate_frozen(p,bad,rows,days[-2:],calendar,today,None,None))
