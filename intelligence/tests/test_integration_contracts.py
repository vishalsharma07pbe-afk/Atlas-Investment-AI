"""Integration contract tests for API endpoints, with deterministic local fixtures.

No network access, exchange data, broker credentials or database required.
"""
import unittest
from datetime import date,timedelta
from unittest.mock import patch
from fastapi import HTTPException
from app import main
from app.research_alerts import AlertRequest,AlertRule

def fixture(count=90):
    start=date.today()-timedelta(days=count-1)
    return {"instrument":{"id":7,"symbol":"TEST"},"candles":[{
        "trade_date":(start+timedelta(days=i)).isoformat(),
        "open":100+i*.2,"high":102+i*.2,"low":99+i*.2,
        "close":101+i*.2,"volume":1000,"adjustment_status":"RAW_UNADJUSTED",
        "revision":1
    } for i in range(count)]}

class IntegrationContracts(unittest.TestCase):
    @patch.object(main,"backend_json")
    def test_research_pipeline_on_valid_data(self,backend):
        backend.return_value=fixture()
        qualification=main.risk_qualification(7,max_age_days=7)
        self.assertEqual(qualification["status"],"OBSERVATIONS_READY")
        alerts=main.evaluate_research_alerts(AlertRequest(instrument_id=7,
            rules=[AlertRule(metric="CLOSE_ABOVE",threshold=1)]))
        self.assertEqual(alerts["status"],"EVALUATED")
        self.assertEqual(alerts["triggered_count"],1)
        backtest=main.daily_backtest(7,fast=10,slow=30,fee_bps=10,slippage_bps=5)
        self.assertEqual(backtest["status"],"HISTORICAL_SIMULATION_ONLY")
        self.assertEqual(backtest["candle_count"],90)
        self.assertEqual(backend.call_count,3)

    @patch.object(main,"backend_json")
    def test_invalid_adjustments_fail_closed(self,backend):
        raw=fixture()
        raw["candles"][-1]["adjustment_status"]="ADJUSTED"
        backend.return_value=raw
        qualification=main.risk_qualification(7,max_age_days=7)
        self.assertEqual(qualification["status"],"BLOCKED")
        alerts=main.evaluate_research_alerts(AlertRequest(instrument_id=7,
            rules=[AlertRule(metric="CLOSE_ABOVE",threshold=1)]))
        self.assertEqual(alerts["status"],"BLOCKED")
        self.assertEqual(alerts["alerts"],[])
        with self.assertRaises(HTTPException) as context:
            main.daily_backtest(7,fast=10,slow=30,fee_bps=10,slippage_bps=5)
        self.assertEqual(context.exception.status_code,422)

    @patch.object(main,"backend_json")
    def test_backend_unavailable_is_not_silently_substituted(self,backend):
        backend.side_effect=HTTPException(status_code=503,detail="Market-data backend unavailable")
        with self.assertRaises(HTTPException) as context:
            main.risk_qualification(7,max_age_days=7)
        self.assertEqual(context.exception.status_code,503)

    @patch.object(main,"backend_json")
    def test_insufficient_data_blocks_alerts_and_backtest(self,backend):
        backend.return_value=fixture(8)
        result=main.evaluate_research_alerts(AlertRequest(instrument_id=7,
            rules=[AlertRule(metric="CLOSE_ABOVE",threshold=1)]))
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["alerts"],[])
        simulation=main.daily_backtest(7,fast=10,slow=30,fee_bps=10,slippage_bps=5)
        self.assertEqual(simulation["status"],"INSUFFICIENT_HISTORY")

class LifespanContracts(unittest.IsolatedAsyncioTestCase):
    async def test_all_existing_services_are_started_and_stopped(self):
        from unittest.mock import AsyncMock
        from contextlib import ExitStack
        events=[]
        def callback(name):
            async def invoke(): events.append(name)
            return AsyncMock(side_effect=invoke)
        with ExitStack() as patches:
            patches.enter_context(patch.object(main,"start_opt_in_upstox_feed",callback("start_feed")))
            patches.enter_context(patch.object(main,"stop_opt_in_upstox_feed",callback("stop_feed")))
            for label,service in (("monitor",main.readiness_monitor),("nav",main.nav_refresh_scheduler),("research",main.research_scheduler)):
                patches.enter_context(patch.object(service,"start",callback("start_"+label)))
                patches.enter_context(patch.object(service,"stop",callback("stop_"+label)))
            async with main.lifespan(main.app):
                self.assertEqual(events,["start_feed","start_monitor","start_nav","start_research"])
            self.assertEqual(events,["start_feed","start_monitor","start_nav","start_research","stop_research","stop_nav","stop_monitor","stop_feed"])

    async def test_partial_startup_is_cleaned_up(self):
        from unittest.mock import AsyncMock
        with patch.object(main,"start_opt_in_upstox_feed",AsyncMock()),patch.object(main,"stop_opt_in_upstox_feed",AsyncMock()) as feed_stop,patch.object(main.readiness_monitor,"start",AsyncMock(side_effect=RuntimeError("fixture"))),patch.object(main.readiness_monitor,"stop",AsyncMock()) as monitor_stop:
            with self.assertRaises(RuntimeError):
                async with main.lifespan(main.app):
                    self.fail("Failed startup must not yield")
            monitor_stop.assert_awaited_once()
            feed_stop.assert_awaited_once()


if __name__=="__main__":
    unittest.main()
