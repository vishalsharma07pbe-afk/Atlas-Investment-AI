import unittest
from datetime import date,timedelta
from pydantic import ValidationError
from app.mutual_fund_historical_risk import HistoricalRiskRequest,historical_risk

class HistoricalRiskTests(unittest.TestCase):
    def request(self,rows):
        return HistoricalRiskRequest(scheme_code="12345",source_name="Authorized local CSV",observations=rows)
    def test_drawdown_and_returns(self):
        result=historical_risk(self.request([
            {"as_of":"2025-01-01","nav":"100"},{"as_of":"2025-01-02","nav":"120"},
            {"as_of":"2025-01-03","nav":"90"}]))
        self.assertEqual(result["maximum_drawdown_pct"],-25)
        self.assertEqual(result["cumulative_return_pct"],-10)
        self.assertIsNotNone(result["annualized_volatility_pct"])
        self.assertFalse(result["stored"])
    def test_irregular_spacing_disables_daily_volatility(self):
        result=historical_risk(self.request([
            {"as_of":"2025-01-01","nav":"100"},{"as_of":"2025-01-03","nav":"110"},
            {"as_of":"2025-01-05","nav":"105"}]))
        self.assertIsNone(result["annualized_volatility_pct"])
        self.assertEqual(result["volatility_status"],"UNAVAILABLE_IRREGULAR_OR_INSUFFICIENT")
    def test_duplicate_and_nonfinite_rejected(self):
        with self.assertRaises(ValidationError):self.request([
            {"as_of":"2025-01-01","nav":"100"},{"as_of":"2025-01-01","nav":"101"}])
        with self.assertRaises(ValidationError):self.request([
            {"as_of":"2025-01-01","nav":"100"},{"as_of":"2025-01-02","nav":"NaN"}])
    def test_two_observations_no_volatility(self):
        result=historical_risk(self.request([
            {"as_of":"2025-01-01","nav":"100"},{"as_of":"2025-01-02","nav":"110"}]))
        self.assertIsNone(result["annualized_volatility_pct"])

if __name__=="__main__":unittest.main()
