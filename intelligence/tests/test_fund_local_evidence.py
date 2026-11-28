import unittest,json
from datetime import date,timedelta
from hashlib import sha256
from app import fund_local_evidence as f
TODAY=date(2026,11,27)
def fixture():
    days=[TODAY-timedelta(days=1,weeks=156-i) for i in range(157)]
    data={"schema":f.VERSION,"authorization_attested":True,"indices":[{"benchmark":"NIFTY 100 TRI","source_url":f.TRI_SOURCE,"series_type":"GROSS_TOTAL_RETURN_INDEX","observations":[{"date":d.isoformat(),"tri":100+i} for i,d in enumerate(days)]}],"schemes":[{"scheme_code":123456,"isin_growth":"INF179K01BB2","plan":"DIRECT","option":"GROWTH","benchmark":"NIFTY 100 TRI","source_url":f.AMFI_DISCLOSURE,"ter_source_url":f.AMFI_SOURCE,"disclosure_date":"2026-11-20","ter_date":"2026-11-19","ter_percent":.5,"riskometer":"VERY_HIGH","riskometer_date":"2026-10-31"}]}
    row={"nav_date":days[-1].isoformat(),"weekly_anchor_series":[{"date":d.isoformat(),"nav":100+2*i} for i,d in enumerate(days)],"matched_weekly_comparison":{"methodology":"MF-WEEKLY-MATCH-1","first_date":days[0].isoformat(),"last_date":days[-1].isoformat(),"date_digest":sha256("".join(d.isoformat()+"\n" for d in days).encode()).hexdigest()}}
    return data,row,days
class LocalEvidenceTests(unittest.TestCase):
    def test_exact_total_return_comparison(self):
        data,row,days=fixture()
        loaded=f.parse(json.dumps(data).encode(),TODAY)
        values=loaded["indices"]["NIFTY 100 TRI"]
        report=f.compare(row,values)
        self.assertEqual(report["matched_anchors"],157)
        self.assertEqual(report["rolling_windows"],105)
        self.assertGreater(report["windows"][1]["difference_pp"],0)
        del values[days[8]]
        self.assertIsNone(f.compare(row,values))
    def test_no_price_index_and_duplicate_rows(self):
        data,_,_=fixture();data["indices"][0]["series_type"]="PRICE_INDEX"
        with self.assertRaises(ValueError):f.parse(json.dumps(data).encode(),TODAY)
        data,_,_=fixture();data["schemes"].append(data["schemes"][0])
        with self.assertRaises(ValueError):f.parse(json.dumps(data).encode(),TODAY)
    def test_changed_anchor_digest_rejected(self):
        data,row,_=fixture();loaded=f.parse(json.dumps(data).encode(),TODAY)
        row["matched_weekly_comparison"]["date_digest"]="b"*64
        self.assertIsNone(f.compare(row,loaded["indices"]["NIFTY 100 TRI"]))

    def test_cost_only_import_and_same_date_conflict(self):
        from types import SimpleNamespace
        data,row,_=fixture()
        raw=(",".join(f.TER_FIELDS)+"\n123456,INF179K01BB2,DIRECT,GROWTH,2026-11-26,0.3,0.05,0.05,0.1,0.5\n").encode()
        ter=f.parse_ter(raw,TODAY)
        candidate=SimpleNamespace(identifier="123456",plan="DIRECT",option="GROWTH")
        row.update(scheme_code=123456,isin_growth="INF179K01BB2")
        report=f.reports([candidate],[row],{"status":"MISSING_OR_INVALID_LOCAL_EXPORTS"},TODAY,ter=ter)["123456"]
        self.assertEqual(report["disclosure"]["ter_percent"],.5)
        self.assertIsNone(report["disclosure"]["benchmark"])
        self.assertIsNone(report["benchmark_comparison"])
        self.assertEqual(report["ter_components_evidence"]["status"],"OPERATOR_NORMALIZED_TER_COMPONENTS")
        self.assertEqual(f.reports([candidate],[row,row],{},TODAY,ter=ter),{})
        self.assertEqual(f.reports([candidate],[row],{},TODAY+timedelta(days=8),ter=ter),{})
        with self.assertRaises(ValueError):f.parse_ter(raw.replace(b",0.1,0.5",b",0.1,0.3"),TODAY)
        data["schemes"][0].update(ter_date="2026-11-26",disclosure_date="2026-11-26",ter_percent=.8)
        loaded={**f.parse(json.dumps(data).encode(),TODAY),"status":"LOCAL_EXPORTS_LOADED"}
        conflict=f.reports([candidate],[row],loaded,TODAY,ter=ter)["123456"]
        self.assertIsNone(conflict["disclosure"]["ter_percent"])
        self.assertEqual(conflict["ter_components_evidence"]["status"],"CONFLICTING_SAME_DATE_TER")
