import unittest
from datetime import date
from app.amfi_nav_import import parse_amfi
from app.mutual_fund_snapshot_pipeline import SnapshotPortfolioRequest,inspect_snapshot_portfolio
from app.mutual_fund_reconciliation import FundPosition
from decimal import Decimal

TODAY=date(2026,11,14)
VALID="12345;ISIN1;ISIN2;Example Direct Growth;12.5;13-Nov-2026"
def review(text):
    return inspect_snapshot_portfolio(SnapshotPortfolioRequest(
        text=text,source_name="User-provided NAV export",source_authorized=True,
        positions=[FundPosition(holding_id=1,scheme_code="12345",units=Decimal("2"),invested=Decimal("20"))]
    ),today=TODAY)

class SnapshotDataQualityTests(unittest.TestCase):
    def test_truncated_selected_row_is_rejected(self):
        result=review("12345;broken")
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["snapshot"]["rejected_rows"],1)
        self.assertIn("REJECTED_SNAPSHOT_ROWS",result["blockers"])
        self.assertIn("NO_VALID_NAV_RECORDS",result["blockers"])
    def test_duplicate_selected_row_after_valid_is_not_accepted(self):
        result=review(VALID+"\n12345;broken")
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["snapshot"]["schemes"],[])
        self.assertEqual(result["snapshot"]["duplicate_scheme_codes"],["12345"])
    def test_duplicate_invalid_then_valid_is_not_accepted(self):
        result=review("12345;broken\n"+VALID)
        self.assertEqual(result["snapshot"]["schemes"],[])
        self.assertIn("NO_VALID_NAV_RECORDS",result["blockers"])
    def test_huge_finite_decimal_cannot_overflow_json_float(self):
        result=review(VALID.replace("12.5","1e9999"))
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["snapshot"]["schemes"],[])
        self.assertIn("REJECTED_SNAPSHOT_ROWS",result["blockers"])
    def test_unselected_malformed_row_does_not_block_selected_scheme(self):
        result=review(VALID+"\n67890;broken")
        self.assertEqual(result["status"],"READY_FOR_MANUAL_REVIEW")
    def test_non_ascii_scheme_code_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_amfi(VALID,["１２３４５"],today=TODAY)

if __name__=="__main__":unittest.main()
