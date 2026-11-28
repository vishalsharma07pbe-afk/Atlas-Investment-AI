import csv
import io
import tempfile
import unittest
from datetime import date,datetime,timezone
from unittest.mock import patch
from app import fund_portfolios as portfolios,nav_catalog,autonomous_research

TODAY=date(2026,11,25)
INSTANT=datetime(2026,11,25,4,tzinfo=timezone.utc)

def row(**changes):
    value=dict(fund_code="EXAMPLE",fund_name="Example Fund",month_end="2026-10-31",
               isin="INE002A01018",isin_as_filed="INE002A01018",security_name="Example Equity",
               pct_of_fund="60",asset_group="Equity",asset_subgroup="Listed shares",
               mapping_category="",amfi_ssd_fund_id="fund:123",isin_type="ISIN")
    value.update(changes)
    return value

def payload(*rows):
    output=io.StringIO(newline="")
    writer=csv.DictWriter(output,fieldnames=sorted(portfolios.REQUIRED))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()

CASH=row(isin="SYN-CASH",isin_as_filed="",isin_type="Group code",security_name="Cash",
         asset_group="Cash",asset_subgroup="TREPS",pct_of_fund="40")

class FundPortfoliosTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path=patch.object(nav_catalog,"DB_PATH",nav_catalog.Path(folder.name)/"nav.sqlite")
        path.start()
        self.addCleanup(path.stop)
        env=patch.dict("os.environ",{"ATLAS_MF_DISCLOSURE_AUTO_REFRESH_ENABLED":"true",
                                    "MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"true"})
        env.start()
        self.addCleanup(env.stop)

    def test_exact_weights_and_no_normalization(self):
        item=portfolios.parse(payload(row(),CASH),TODAY)["fund:123"]
        self.assertEqual(item["exact_listed_equity_weight_percent"],60)
        self.assertEqual(item["asset_allocation_percent"],{"Cash":40,"Equity":60})
        self.assertEqual(item["top_10_exact_equity_weight_percent"],60)
        mapped=portfolios.parse(payload(row(mapping_category="CORPORATE_ACTION"),CASH),TODAY)["fund:123"]
        self.assertEqual(mapped["exact_listed_equity_weight_percent"],0)
        for bad in (payload(row()),payload(row(),row(),CASH),payload(row(month_end="2026-12-31"),CASH)):
            with self.assertRaises(ValueError):
                portfolios.parse(bad,TODAY)

    def test_persisted_match_and_failed_refresh_preserves_good_data(self):
        portfolios.store(payload(row(),CASH),TODAY,INSTANT.isoformat())
        with self.assertRaises(ValueError):
            portfolios.store(payload(row()),TODAY,INSTANT.isoformat())
        identity={"fund_id":"fund:123","scheme_code":"123456","scheme_name":"Example"}
        with patch.object(portfolios,"company_coverage",return_value={"cached_company_evidence_weight_percent":60,"cached_company_count":1}):
            item=portfolios.matched([identity],INSTANT)[0]
            self.assertEqual(item["top_holdings"][0]["isin"],"INE002A01018")
            self.assertEqual(item["cached_company_count"],1)
            self.assertEqual(portfolios.matched([{**identity,"fund_id":"fund:456"}],INSTANT),[])
            # A portfolio beyond the first five disclosure candidates must
            # not be skipped solely because earlier candidates lack holdings.
            later=[{**identity,"fund_id":"missing:"+str(i)} for i in range(6)]+[identity]
            self.assertEqual(portfolios.matched(later,INSTANT)[0]["fund_id"],identity["fund_id"])

    def test_composition_full_sample_without_expensive_enrichment(self):
        rows=[]
        ids=[]
        for i in range(7):
            fund="fund:"+str(i)
            changes={"fund_code":str(i),"amfi_ssd_fund_id":fund}
            rows.extend([row(**changes),{**CASH,**changes}])
            ids.append({"fund_id":fund,"scheme_code":str(123450+i),"scheme_name":str(i)})
        portfolios.store(payload(*rows),TODAY,INSTANT.isoformat())
        with patch("app.fund_underlying_research.load") as load,patch.object(portfolios,"company_coverage") as coverage:
            matches=portfolios.composition_matches(ids,INSTANT)
            self.assertEqual(len(matches),7)
            self.assertEqual(matches[-1]["scheme_code"],"123456")
            self.assertEqual(matches[-1]["asset_allocation_percent"],{"Cash":40,"Equity":60})
            self.assertEqual(matches[-1]["top_holdings"][0]["weight_percent"],60)
            self.assertNotIn("exact_equity_weights",matches[-1])
            self.assertNotIn("underlying_research",matches[-1])
            self.assertEqual(len(portfolios.composition_matches(ids+[ids[0]],INSTANT)),6)
            self.assertEqual(portfolios.composition_matches(ids,datetime(2026,11,29,tzinfo=timezone.utc)),[])
            with patch.dict("os.environ",{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}):
                self.assertEqual(portfolios.composition_matches(ids,INSTANT),[])
            load.assert_not_called()
            coverage.assert_not_called()

    def test_overlap_uses_full_same_date_weights_and_distinct_funds(self):
        a=row(pct_of_fund="80")
        b=row(fund_code="SECOND",amfi_ssd_fund_id="fund:456",pct_of_fund="60")
        other=row(fund_code="SECOND",amfi_ssd_fund_id="fund:456",isin="INE009A01021",
                  isin_as_filed="INE009A01021",pct_of_fund="30")
        cash_a={**CASH,"pct_of_fund":"20"}
        cash_b={**CASH,"fund_code":"SECOND","amfi_ssd_fund_id":"fund:456","pct_of_fund":"10"}
        portfolios.store(payload(a,cash_a,b,other,cash_b),TODAY,INSTANT.isoformat())
        identities=[{"fund_id":"fund:123","scheme_code":"123456","scheme_name":"A"},
                    {"fund_id":"fund:456","scheme_code":"123457","scheme_name":"B"},
                    {"fund_id":"fund:123","scheme_code":"123458","scheme_name":"A other plan"}]
        report=portfolios.overlap(identities,INSTANT)
        self.assertEqual(report["status"],"REPORTED_LOWER_BOUND")
        self.assertEqual(len(report["pairs"]),1)
        pair=report["pairs"][0]
        self.assertEqual(pair["common_weight_lower_bound_percent"],60)
        self.assertEqual(pair["exact_weight_a_percent"],80)
        self.assertEqual(pair["exact_weight_b_percent"],90)
        self.assertEqual(pair["common_equity_count"],1)
        portfolios.store(payload(a,cash_a,{**b,"month_end":"2026-09-30"},
                                 {**other,"month_end":"2026-09-30"},
                                 {**cash_b,"month_end":"2026-09-30"}),TODAY,INSTANT.isoformat())
        self.assertEqual(portfolios.overlap(identities,INSTANT)["pairs"],[])
        portfolios.store(payload(a,cash_a,{**b,"pct_of_fund":"40"},
                                 {**other,"pct_of_fund":"30"},
                                 {**cash_b,"pct_of_fund":"30"}),TODAY,INSTANT.isoformat())
        self.assertEqual(portfolios.overlap(identities,INSTANT)["pairs"],[])

    def test_internal_exact_weights_are_complete_and_opt_in(self):
        equities=[row(isin=f"INE{i:09d}",isin_as_filed=f"INE{i:09d}",
                      security_name=f"Equity {i}",pct_of_fund="8") for i in range(12)]
        portfolios.store(payload(*equities,{**CASH,"pct_of_fund":"4"}),TODAY,INSTANT.isoformat())
        identity={"fund_id":"fund:123","scheme_code":"123456","scheme_name":"Example"}
        with patch.object(portfolios,"company_coverage",return_value={}):
            public=portfolios.matched([identity],INSTANT)[0]
            internal=portfolios.matched([identity],INSTANT,include_exact_weights=True)[0]
        self.assertNotIn("exact_equity_weights",public)
        self.assertEqual(len(internal["top_holdings"]),10)
        self.assertEqual(len(internal["exact_equity_weights"]),12)
        self.assertEqual(sum(internal["exact_equity_weights"].values()),96)

    def test_authorization_gate(self):
        with patch.dict("os.environ",{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}),patch.object(portfolios.httpx,"Client") as client:
            self.assertEqual(autonomous_research._execute_job("FUND_PORTFOLIOS"),"DISABLED_OR_NOT_AUTHORIZED")
            with self.assertRaises(ValueError):
                portfolios.refresh()
            client.assert_not_called()

    def test_concentration_is_subset_only_with_category_specific_gaps(self):
        holdings=[{"isin":"INE002A01018","weight_percent":40},
                  {"isin":"INE009A01021","weight_percent":30},
                  {"isin":"INE242A01010","weight_percent":10}]
        sectors={"INE002A01018":{"sector":"Banking"},"INE009A01021":{"sector":" banking "}}
        result=portfolios.concentration(holdings,sectors,"Large Cap Fund",{"Equity":90,"Cash":10})
        self.assertEqual(result["category"],"LARGE_CAP")
        self.assertEqual(result["exact_equity_weight_percent"],80)
        self.assertEqual(result["largest_equity_weight_percent"],40)
        self.assertEqual(result["top_three_equity_weight_percent"],80)
        self.assertEqual(result["equity_subset_hhi"],4062.5)
        self.assertAlmostEqual(result["equity_subset_effective_holdings"],2.4615,places=4)
        self.assertEqual(result["sector_classified_weight_percent"],70)
        self.assertEqual(result["unclassified_exact_equity_weight_percent"],10)
        self.assertEqual(result["largest_classified_sector_weight_percent"],70)
        self.assertIsNone(result["risk_rating"])
        debt=portfolios.concentration([],{},"Corporate Bond Fund",{"Debt":90})
        self.assertEqual(debt["reported_debt_weight_percent"],90)
        self.assertIn("MATURITY_AND_MODIFIED_DURATION_REQUIRED",debt["missing_risk_evidence"])
        self.assertIsNone(debt["equity_subset_hhi"])
        hybrid=portfolios.concentration(holdings,sectors,"Aggressive Hybrid Fund",{"Equity":80,"Debt":20})
        self.assertIn("DEBT_CREDIT_AND_DURATION_REQUIRED",hybrid["missing_risk_evidence"])
        self.assertIsNone(portfolios.concentration(holdings+[holdings[0]],sectors,"Large Cap Fund",{})["equity_subset_hhi"])
        self.assertIsNone(portfolios.concentration(holdings,{},"Large Cap Fund",{})["largest_classified_sector_weight_percent"])

    def test_company_priority_uses_shared_public_fund_weights(self):
        a="INE002A01018";b="INE009A01021"
        rows=[]
        for i in range(2):
            fields={"fund_code":str(i),"amfi_ssd_fund_id":"fund:"+str(i)}
            rows.extend([row(**fields,isin=a,isin_as_filed=a,pct_of_fund="30"),
                         row(**fields,isin=b,isin_as_filed=b,pct_of_fund="50" if i==0 else "1"),
                         {**CASH,**fields,"pct_of_fund":"20" if i==0 else "69"}])
        portfolios.store(payload(*rows),TODAY,INSTANT.isoformat())
        self.assertEqual(portfolios.research_identities(INSTANT),[a,b])

    def test_ingestion_audit_distinguishes_missing_and_rejected_without_replacing_good_snapshot(self):
        bad={"fund_code":"BAD","amfi_ssd_fund_id":"fund:bad"}
        stale={"fund_code":"STALE","amfi_ssd_fund_id":"fund:stale","month_end":"2026-08-31"}
        portfolios.store(payload(row(),CASH,row(**bad),row(**stale),{**CASH,**stale}),TODAY,INSTANT.isoformat())
        ids=[{"fund_id":i} for i in ("fund:123","fund:bad","fund:stale","fund:absent",None)]
        audit=portfolios.ingestion_coverage(ids,INSTANT)
        self.assertEqual(audit["source_counts"],{"ACCEPTED":1,"WEIGHTS_NOT_RECONCILED":1,"STALE_PORTFOLIO_DATE":1})
        self.assertEqual(audit["sample_counts"],{"ACCEPTED":1,"WEIGHTS_NOT_RECONCILED":1,"STALE_PORTFOLIO_DATE":1,"NOT_IN_SOURCE_FILE":1,"MISSING_FUND_ID":1})
        with self.assertRaises(ValueError):
            portfolios.store(payload(row()),TODAY,INSTANT.isoformat())
        self.assertEqual(portfolios.ingestion_coverage(ids,INSTANT),audit)
        self.assertEqual(portfolios.ingestion_coverage(ids,datetime(2026,11,29,tzinfo=timezone.utc))["status"],"STALE_OR_INCONSISTENT_AUDIT")
        with patch.dict("os.environ",{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}):
            self.assertEqual(portfolios.ingestion_coverage(ids,INSTANT)["status"],"DISABLED_OR_NOT_AUTHORIZED")

    def test_invalid_cached_composition_does_not_discard_valid_fund(self):
        from contextlib import closing
        other={"fund_code":"SECOND","amfi_ssd_fund_id":"fund:456"}
        portfolios.store(payload(row(),CASH,row(**other),{**CASH,**other}),TODAY,INSTANT.isoformat())
        with closing(nav_catalog._connect()) as db,db:
            db.execute("UPDATE fund_portfolio_snapshot SET payload='invalid json' WHERE fund_id='fund:123'")
        identities=[{"fund_id":"fund:123","scheme_code":"123456","scheme_name":"A"},
                    {"fund_id":"fund:456","scheme_code":"123457","scheme_name":"B"}]
        self.assertEqual([r["scheme_code"] for r in portfolios.composition_matches(identities,INSTANT)],["123457"])
        self.assertEqual([r["scheme_code"] for r in portfolios.matched(identities,INSTANT)],["123457"])

    def test_priority_includes_funds_beyond_old_alphabetical_limit(self):
        from contextlib import closing
        rows=[]
        for n in range(101):
            fields={"fund_code":str(n),"amfi_ssd_fund_id":f"fund:{n:03}"}
            key="INE009A01021" if n==100 else "INE002A01018"
            rows.extend([row(**fields,isin=key,isin_as_filed=key),{**CASH,**fields}])
        portfolios.store(payload(*rows),TODAY,INSTANT.isoformat())
        with closing(nav_catalog._connect()) as db,db:
            db.execute("UPDATE fund_portfolio_snapshot SET payload='invalid' WHERE fund_id='fund:001'")
        self.assertEqual(portfolios.research_identities(INSTANT),["INE002A01018","INE009A01021"])

    def test_current_category_portfolio_targets_get_priority_without_dropping_broad_funds(self):
        a="INE002A01018";b="INE009A01021"
        rows=[]
        for i in range(4):
            fields={"fund_code":str(i),"amfi_ssd_fund_id":"fund:"+str(i)}
            key=b if i==3 else a
            rows.extend([row(**fields,isin=key,isin_as_filed=key),{**CASH,**fields}])
        portfolios.store(payload(*rows),TODAY,INSTANT.isoformat())
        self.assertEqual(portfolios.research_identities(INSTANT),[a,b])
        self.assertEqual(portfolios.research_identities(INSTANT,preferred_funds={"fund:3":"2026-10-31"}),[b,a])
        self.assertEqual(portfolios.research_identities(INSTANT,preferred_funds={"fund:3":"2026-09-30"}),[a,b])
