/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import FundHistoricalWatch from "./FundHistoricalWatch";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("separates historical return and downside rankings with explicit missing metrics",async()=>{
 const item={scheme_code:1,scheme_name:"Return leader",nav:100,nav_date:"2026-11-23",cagr_1y_percent:10,cagr_3y_percent:15,drawdown_3y_percent:-20,observations:750,sources:["AMFI"],weekly_volatility_percent:12,return_to_drawdown:0.75};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({category:"LARGE_CAP",items:[item],risk_adjusted_items:[{...item,scheme_code:2,scheme_name:"Downside leader"}],comparison_date:"2026-11-23",sample_count:5,universe_count:10,eligible_count:5,notice:"Historical only"})})));
 render(<FundHistoricalWatch category="LARGE_CAP"/>);
 expect(await screen.findByText("Return leader")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Return versus drawdown"}));
 expect(screen.getByText("Downside leader")).toBeTruthy();
 expect(screen.queryByText("Return leader")).toBeNull();
 expect(screen.getByText("12.00%")).toBeTruthy();
});
