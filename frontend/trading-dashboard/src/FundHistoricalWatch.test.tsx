/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import FundHistoricalWatch from "./FundHistoricalWatch";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("separates historical return and downside rankings with explicit missing metrics",async()=>{
 const item={scheme_code:1,scheme_name:"Return leader",nav:100,nav_date:"2026-11-23",cagr_1y_percent:10,cagr_3y_percent:15,drawdown_3y_percent:-20,observations:750,sources:["AMFI"],weekly_volatility_percent:12,return_to_drawdown:0.75,weekly_hurdle_sensitivity:{status:"HYPOTHETICAL_HURDLE_ONLY",weekly_intervals:156,annualized_arithmetic_return_percent:26,annualized_volatility_percent:11,scenarios:[{annual_effective_hurdle_percent:0,annualized_arithmetic_excess_percent:26,annualized_downside_percent:5,sharpe_proxy:2.3636,sortino_proxy:5.2},{annual_effective_hurdle_percent:6,annualized_arithmetic_excess_percent:20,annualized_downside_percent:6,sharpe_proxy:null,sortino_proxy:3.33}]}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({category:"LARGE_CAP",items:[item],risk_adjusted_items:[{...item,scheme_code:2,scheme_name:"Downside leader"}],comparison_date:"2026-11-23",sample_count:5,universe_count:10,eligible_count:5,notice:"Historical only"})})));
 render(<FundHistoricalWatch category="LARGE_CAP"/>);
 expect(await screen.findByText("Return leader")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Return versus drawdown"}));
 expect(screen.getByText("Downside leader")).toBeTruthy();
 expect(screen.queryByText("Return leader")).toBeNull();
 expect(screen.getByText("12.00%")).toBeTruthy();
 expect(screen.getByText("6% hypothetical annual hurdle")).toBeTruthy();
 expect(screen.getByText("2.36")).toBeTruthy();
 expect(screen.getByText(/not observed risk-free rates or benchmark TRI/)).toBeTruthy();
});
