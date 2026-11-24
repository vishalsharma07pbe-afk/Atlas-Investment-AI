/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import IntradayResearch from "./IntradayResearch";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("shows closed session without invented setups",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({status:"SESSION_CLOSED_OR_UNVERIFIED",candidates:[],warnings:[],notice:"Research only"})})));
 render(<IntradayResearch/>);
 expect(await screen.findByText("Market session closed or not verified.")).toBeTruthy();
 expect(screen.getByText("No qualifying observations.")).toBeTruthy();
});
it("distinguishes a failed breakout from a qualifying volume breakout",async()=>{
 const row={id:1,symbol:"TEST",exchange:"NSE",bar_end:"2026-11-25T05:15:00Z",close:100,vwap_proxy:101,relative_volume:2,session_change_percent:1,mean_bar_range_percent:2,bar_count:6};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({status:"RESEARCH_ONLY",eligible:1,examined:1,candidates:[],warnings:[row],notice:"Not trade signals"})})));
 render(<IntradayResearch/>);
 expect(await screen.findByText("TEST · NSE")).toBeTruthy();
 expect(screen.getByText("No qualifying observations.")).toBeTruthy();
});
