import unittest
from datetime import date
from app import nse_pledge_filings as p
ISIN="INE002A01018"
TODAY=date(2026,11,27)
PERIOD=date(2026,9,30)
URL="https://nsearchives.nseindia.com/corporate/ixbrl/SHP_SDD_123_17102026230154_iXBRL_WEB.html"
def html(count="20",pct="20"):
    fields={"ISIN":ISIN,"Class of Security":"Equity","Type of report":"Quarterly","Quarter Ended / Half year ended/Date of Report (For Prelisting / Allotment)":"30-Sep-2026","SEBI Regulation under which Shareholding pattern is filed":"Regulation 31 (1)(b)"}
    def row(cells):return "<tr>"+"".join("<td>"+v+"</td>" for v in cells)+"</tr>"
    header=["Category (I)","Category of shareholder (II)"]+["f"]*13+["Number of Locked in shares (XIII)","Number of Shares pledged (XIV)","Non-Disposal Undertaking (XV)","Other encumbrances, if any (XVI)","Total Number of Shares encumbered (XVII)"]
    r=["A","Promoter &amp; Promoter Group","3","100","0","0","100","50","100","0","100","50","0","0","0","0","100","50","0","0",count,pct,"10","10","0","0","30","30","100","0","0","0"]
    return ("<table>"+"".join(row([k,v]) for k,v in fields.items())+"</table><table>"+row(header)+row(r)+"</table>").encode()
class PledgeFilingTests(unittest.TestCase):
    def test_filing_aggregate_and_reconciliation(self):
        result=p.parse(html(),ISIN,PERIOD,TODAY)
        self.assertEqual(result["pledged_percent_of_promoter_shares"],20)
        self.assertEqual(result["total_encumbered_percent_of_promoter_shares"],30)
        self.assertEqual(result["promoter_shares"],100)
        for payload in (html("21","20"),html("0","0"),html().replace(b"INE002A01018",b"INE009A01021"),html().replace(b"30-Sep-2026",b"30-Jun-2026")):
            with self.assertRaises(ValueError):p.parse(payload,ISIN,PERIOD,TODAY)
    def test_latest_period_only_no_guessed_links_or_revisions(self):
        self.assertEqual(p.choose_index([{"date":"30-SEP-2026","xbrl":URL}],"TEST",TODAY),(PERIOD,URL))
        for u in ("https://example.org/"+URL.split("/")[-1],URL+"?token=x",URL.replace(".html",".xml")):
            with self.assertRaises(ValueError):p.choose_index([{"date":"30-SEP-2026","xbrl":u},{"date":"30-JUN-2026","xbrl":URL}],"TEST",TODAY)
        with self.assertRaises(ValueError):p.choose_index([{"date":"30-SEP-2026","xbrl":URL},{"date":"30-SEP-2026","xbrl":URL.replace("_123_","_124_")}],"TEST",TODAY)
