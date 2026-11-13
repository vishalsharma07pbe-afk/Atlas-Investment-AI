"""Portfolio stress calculations use synthetic test holdings only."""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app import main
from app.portfolio_scenarios import stress_portfolio


def holding(id, symbol, qty, cost, price):
    return SimpleNamespace(
        id=id, symbol=symbol, asset_type="EQUITY",
        quantity=Decimal(qty), average_cost=Decimal(cost),
        last_price=Decimal(price) if price is not None else None,
    )


class StressTests(unittest.TestCase):
    def test_partial_coverage_does_not_invent_prices(self):
        holdings = [holding(1, "TEST", "2", "100", "120"),
                    holding(2, "UNKNOWN", "3", "50", None)]
        result = stress_portfolio(holdings)
        self.assertEqual(result["status"], "PARTIAL_PRICE_COVERAGE")
        self.assertEqual(result["total_invested_all_holdings"], "350.00")
        self.assertEqual(result["recorded_value_priced_holdings"], "240.00")
        self.assertEqual(result["unpriced_holdings"][0]["symbol"], "UNKNOWN")
        self.assertEqual(result["scenarios"][0]["stressed_value_of_priced_holdings"], "168.00")
        self.assertEqual(result["scenarios"][0]["unrealized_pnl_vs_priced_cost"], "-32.00")
        self.assertEqual(result["priced_holdings"][0]["weight_percent"], "100.00")

    def test_empty_portfolio_is_safe(self):
        result = stress_portfolio([])
        self.assertEqual(result["recorded_value_priced_holdings"], "0.00")
        self.assertIsNone(result["priced_holdings"][0]["weight_percent"] if result["priced_holdings"] else None)
        self.assertEqual(result["scenarios"][2]["change_from_recorded_value"], "0.00")

    def test_endpoint_uses_existing_portfolio_transport(self):
        with patch.object(main, "_fetch_portfolio_holdings", return_value=[holding(3, "TEST", "1", "10", "11")]):
            result = main.portfolio_stress_scenarios()
        self.assertEqual(result["status"], "COMPLETE_PRICED_SUBSET")
        self.assertEqual(result["scenarios"][2]["stressed_value_of_priced_holdings"], "11.00")


if __name__ == "__main__":
    unittest.main()
