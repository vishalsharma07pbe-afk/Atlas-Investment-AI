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

    def test_authorization_gate(self):
        with patch.dict("os.environ",{"MARKET_DATA_USAGE_RIGHTS_CONFIRMED":"false"}),patch.object(portfolios.httpx,"Client") as client:
            self.assertEqual(autonomous_research._execute_job("FUND_PORTFOLIOS"),"DISABLED_OR_NOT_AUTHORIZED")
            with self.assertRaises(ValueError):
                portfolios.refresh()
            client.assert_not_called()
