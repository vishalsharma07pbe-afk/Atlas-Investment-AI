import unittest
from datetime import date
from decimal import Decimal
from app.mutual_fund_snapshot_pipeline import SnapshotPortfolioRequest,inspect_snapshot_portfolio
from app.mutual_fund_reconciliation import FundPosition

TODAY=date(2026,11,14)
def line(code,nav="12.5",stamp="13-Nov-2026"):
    return f"{code};ISIN1;ISIN2;Example Direct Growth;{nav};{stamp}"

def request(text,authorized=True,second=False):
    positions=[FundPosition(holding_id=1,scheme_code="12345",units=Decimal("2"),invested=Decimal("20"))]
    if second:positions.append(FundPosition(holding_id=2,scheme_code="67890",units=Decimal("1"),invested=Decimal("10")))
    return SnapshotPortfolioRequest(text=text,source_name="Authorized local snapshot",source_authorized=authorized,positions=positions)

class PipelineTests(unittest.TestCase):
    def test_valid_snapshot_produces_review_not_update(self):
        result=inspect_snapshot_portfolio(request(line("12345")),today=TODAY)
        self.assertEqual(result["status"],"READY_FOR_MANUAL_REVIEW")
        self.assertEqual(result["reconciliation"]["portfolio_estimated_value"],"25.0")
        self.assertFalse(result["stored"])
        self.assertFalse(result["portfolio_updated"])
        self.assertEqual(result["source"]["verification"],"USER_SUPPLIED_UNVERIFIED")
    def test_missing_scheme_blocks_and_preserves_diagnostics(self):
        result=inspect_snapshot_portfolio(request(line("12345"),second=True),today=TODAY)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("MISSING_EXPECTED_SCHEMES",result["blockers"])
        self.assertEqual(result["reconciliation"]["missing_nav_positions"],1)
    def test_stale_and_unauthorized_block(self):
        result=inspect_snapshot_portfolio(request(line("12345",stamp="01-Jan-2025"),authorized=False),today=TODAY)
        self.assertIn("SOURCE_AUTHORIZATION_NOT_CONFIRMED",result["blockers"])
        self.assertIn("STALE_NAV_DATES",result["blockers"])
    def test_duplicate_and_no_valid_nav_block(self):
        result=inspect_snapshot_portfolio(request(line("12345")+"\n"+line("12345")),today=TODAY)
        self.assertIn("NO_VALID_NAV_RECORDS",result["blockers"])
        self.assertIsNone(result["reconciliation"])
        self.assertFalse(result["portfolio_updated"])
    def test_unexpected_scheme_not_used(self):
        result=inspect_snapshot_portfolio(request(line("12345")+"\n"+line("67890")),today=TODAY)
        self.assertEqual(result["reconciliation"]["matched_positions"],1)
        self.assertEqual(result["status"],"READY_FOR_MANUAL_REVIEW")
if __name__=="__main__":unittest.main()
