// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MarketReadiness from "./MarketReadiness";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("MarketReadiness",()=>{
 it("does not call backend until requested",async()=>{
   const fetcher=vi.fn().mockResolvedValue({ok:true,json:async()=>({status:"BLOCKED",research_signals_enabled:false,blockers:["VERIFIED_LIVE_FEED_UNAVAILABLE"],latest_source_date:null,source_age_calendar_days:null,instrument_count:0,candle_count:0,notice:"No feed"})});
   vi.stubGlobal("fetch",fetcher);
   render(<MarketReadiness/>);
   expect(fetcher).not.toHaveBeenCalled();
   fireEvent.click(screen.getByRole("button",{name:"Check market readiness"}));
   await waitFor(()=>expect(screen.getByRole("status").textContent).toContain("BLOCKED"));
   expect(screen.getByRole("status").textContent).toContain("VERIFIED LIVE FEED UNAVAILABLE");
   expect(fetcher).toHaveBeenCalledTimes(1);
 });
 it("fails closed on network error",async()=>{
   vi.stubGlobal("fetch",vi.fn().mockRejectedValue(Error("offline")));
   render(<MarketReadiness/>);
   fireEvent.click(screen.getByRole("button",{name:"Check market readiness"}));
   await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("offline"));
 });
});
