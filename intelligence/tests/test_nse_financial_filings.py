import unittest,json,tempfile
from datetime import date
from app import nse_financial_filings as f,governance_review

ISIN="INE002A01018"
TODAY=date(2026,11,27)
PERIOD=date(2026,9,30)
URL="https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_209923_04112026211009_iXBRL_WEB.html"
def html(declaration="Statement on impact of audit qualification"):
    meta={"ISIN":ISIN,"Type of company":"Main Board","Class of security":"Equity",
      "Date of start of financial year":"01-04-2026","Date of end of financial year":"31-03-2027","Date of board meeting when results were approved":"04-11-2026",
      "Description of presentation currency":"INR","Level of rounding used in financial results":"Lakhs","Reporting Type":"Quarterly","Reporting Quarter":"Second quarter",
      f.SCOPE:"Consolidated","Whether results are audited or unaudited for the quarter ended":"Audited",
      "Whether results are audited or unaudited for the Year to date for current period ended/year ended":"Audited",f.DECLARATION:declaration}
    def row(cells):return "<tr>"+"".join("<td>"+v+"</td>" for v in cells)+"</tr>"
    vals={"revenue":["10,000","20,000"],"other_income":["100","200"],"total_income":["10,100","20,200"],"expenses":["8,000","16,000"],"profit_before_tax":["2,100","4,200"],"total_tax":["500","1,000"],"continuing_profit":["1,600","3,200"],"net_profit":["1,600","3,200"],"owners_profit":["1,500","3,000"]}
    income=[[f.PERIOD_START,"01-07-2026","01-04-2026"],[f.PERIOD_END,"30-09-2026","30-09-2026"],[f.SCOPE,"Consolidated","Consolidated"],[f.AUDITED,"Audited","Audited"]]+[[f.METRICS[k],*v] for k,v in vals.items()]
    cash=[[f.PERIOD_START,"01-04-2026"],[f.PERIOD_END,"30-09-2026"],[f.SCOPE,"Consolidated"],[f.AUDITED,"Audited"],["Net cash flows from (used in) operating activities","(1,000)"]]
    return ("<table>"+"".join(row([k,v]) for k,v in meta.items())+"</table><table>"+"".join(row(["",*r]) for r in income)+"</table><table>"+"".join(row(r) for r in cash)+"</table><table>"+row(["Auditor's opinion","Qualified opinion"])+"</table>").encode()

class FinancialFilingTests(unittest.TestCase):
    def test_consolidated_quarter_and_ytd_and_audit(self):
        e=f.parse(html(),ISIN,PERIOD,TODAY)
        self.assertEqual(e["quarter"]["revenue"],100)
        self.assertEqual(e["year_to_date"]["revenue"],200)
        self.assertEqual(e["audit_opinion"],"QUALIFIED_OPINION")
        self.assertEqual(e["cash_flow_ytd"]["operating_cash_flow_cr"],-10)
        self.assertEqual(e["year_to_date"]["owners_profit"],30)
        row={"isin":ISIN,"exchange":"NSE","independent_financial_evidence":{**e,"status":"REPORTED_CONSOLIDATED_FILING"}}
        decision=governance_review.assess(row,{},TODAY)
        self.assertIn("ISSUER_REPORTED_AUDIT_QUALIFICATION_REVIEW",decision["findings"])
        self.assertIn("POSITIVE_PROFIT_NEGATIVE_OPERATING_CASH_FLOW_REVIEW",decision["findings"])
        self.assertFalse(decision["clearance_verified"])
    def test_invalid_identity_period_scope_reconciliation(self):
        for payload in (html().replace(ISIN.encode(),b"INE009A01021"),html().replace(b"30-09-2026",b"30-06-2026"),html().replace(b"Consolidated",b"Standalone"),html().replace(b"10,100",b"10,900")):
            with self.assertRaises(ValueError):f.parse(payload,ISIN,PERIOD,TODAY)
    def test_links_only_and_same_period_comparison(self):
        r={"isin":ISIN,"period":PERIOD.isoformat(),"url":URL}
        self.assertEqual(f.manifest(json.dumps([r]).encode(),TODAY),{ISIN:(PERIOD,URL)})
        for rows in ([r,r],[{**r,"url":"https://example.org/file.html"}],[{**r,"amount":100}]):
            with self.assertRaises(ValueError):f.manifest(json.dumps(rows).encode(),TODAY)
        e=f.parse(html(),ISIN,PERIOD,TODAY)
        company={"isin":ISIN,"quarterly_financials":{"latest_period":PERIOD.isoformat(),"items":[{"metric":"revenue","latest_value":102}]}}
        self.assertEqual(f.compare(e,company)["status"],"REVENUE_DIFFERENCE_REVIEW")
        company["quarterly_financials"]["items"][0]["latest_value"]=100.5
        self.assertEqual(f.compare(e,company)["status"],"WITHIN_ILLUSTRATIVE_TOLERANCE")
        company["quarterly_financials"]["latest_period"]="2026-06-30"
        self.assertEqual(f.compare(e,company)["status"],"NOT_COMPARABLE")

    def test_candidate_index_needs_complete_latest_unambiguous_consolidated_record(self):
        row={"symbol":"TEST","qe_Date":"30-Sep-2026","consolidated":"Consolidated","ixbrl":URL}
        def payload(rows,count=None):return {"data":rows,"page":0,"totalCount":len(rows) if count is None else count}
        self.assertEqual(f.select_index(payload([row]),"TEST",TODAY),(PERIOD,URL))
        alternate="https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_209924_04112026211009_iXBRL_WEB.html"
        for data in (payload([row],2),payload([row,{**row,"ixbrl":alternate}]),payload([{**row,"symbol":"OTHER"}]),
                     payload([{**row,"consolidated":"Standalone"}]),payload([{**row,"ixbrl":"https://evil.test/a"}])):
            with self.assertRaises(ValueError):f.select_index(data,"TEST",TODAY)
