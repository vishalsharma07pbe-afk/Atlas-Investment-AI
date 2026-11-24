/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import HorizonResearch from "./HorizonResearch";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const candidate={id:1,symbol:"TEST",exchange:"NSE",as_of:"2026-11-23",close:100,rank_score:5,review_horizon:"2–20 trading sessions",history_count:60,atr_percent:2,median_daily_traded_value:10000000,reasons:["Trend"],warnings:["Raw prices"]};
const section={section:"NSE",status:"READY",generated_at:"2026-11-24",result:{universe_size:10,eligible_count:5,horizons:{SWING:{status:"TECHNICAL_WATCH_ONLY",candidates:[candidate],matched_count:1,evaluated_count:5,blockers:["EVENT_RISK_NOT_VERIFIED"],exclusions:{}},INTRADAY:{status:"NO_QUALIFIED_EVIDENCE",candidates:[],matched_count:0,evaluated_count:0,blockers:["FRESH_INTRADAY_BARS_REQUIRED"],exclusions:{}}}}};
function stub(status="READY"){vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[{...section,status}]})})));}
describe("horizon research",()=>{
 it("loads automatic swing observations and not manual tools",async()=>{
  stub();render(<HorizonResearch horizon="SWING" onSettings={()=>{}}><p>Manual tool</p></HorizonResearch>);
  expect(await screen.findByText("TEST")).toBeTruthy();
  expect(screen.queryByText("Manual tool")).toBeNull();
 });
 it("does not relabel daily candidates as intraday setups",async()=>{
  stub();render(<HorizonResearch horizon="INTRADAY" onSettings={()=>{}}>{null}</HorizonResearch>);
  expect(await screen.findByText(/fresh intraday bars required/)).toBeTruthy();
  expect(screen.queryByText("TEST")).toBeNull();
 });
 it("suppresses candidates from failed snapshots",async()=>{
  stub("FAILED");render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
  expect(await screen.findByText("failed")).toBeTruthy();
  expect(screen.queryByText("TEST")).toBeNull();
 });
});
