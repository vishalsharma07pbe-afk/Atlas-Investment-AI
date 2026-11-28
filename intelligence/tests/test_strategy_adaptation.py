import json,unittest
from datetime import date,timedelta
from unittest.mock import patch
from app import strategy_adaptation as a
TODAY=date(2026,11,28)

def cohort():
    rows=[]
    for days in (220,100):
        for i in range(20):
            published=TODAY-timedelta(days=days+i%10)
            e={"methodology":"MULTI-STRATEGY-PROSPECTIVE-1","regime_policy":a.VERSION,"regime":"RISING","isin":"INE"+str(i).zfill(9),"strategies":["FIP"]}
            rows.append({"evidence":json.dumps(e),"published_at":published.isoformat()+"T00:00:00+00:00","maturity_date":(published+timedelta(days=60)).isoformat()})
    return rows

class StrategyAdaptationTest(unittest.TestCase):
    def test_two_mature_windows_and_regime_isolation(self):
        rows=cohort()
        with patch.object(a.rel,"_outcome",return_value=.10),patch.object(a.rel,"_index_change",return_value=.02):
            result=a.summarize(rows,TODAY,["FIP"],"RISING")
            self.assertEqual(a.priority(["FIP"],result),"SUPPORTED_CONTEXT")
            self.assertEqual(a.priority(["FIP"],a.summarize(rows,TODAY,["FIP"],"FALLING")),"UNVALIDATED")
            self.assertEqual(a.priority(["FIP"],a.summarize(rows[:20],TODAY,["FIP"],"RISING")),"UNVALIDATED")
            self.assertEqual(a.priority(["FIP"],a.summarize(rows,TODAY,["FIP"],"RISING",True)),"UNVALIDATED")
        with patch.object(a.rel,"_outcome",return_value=.01),patch.object(a.rel,"_index_change",return_value=.03):
            self.assertEqual(a.priority(["FIP"],a.summarize(rows,TODAY,["FIP"],"RISING")),"CAUTION")
