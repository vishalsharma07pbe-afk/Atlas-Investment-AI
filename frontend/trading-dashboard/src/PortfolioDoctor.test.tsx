/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import PortfolioDoctor from "./PortfolioDoctor";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("portfolio doctor",()=>{
 it("automatically displays holding risks without requesting evidence input",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-24T10:00:00Z",holding_count:1,attention_count:1,data_gap_count:1,notice:"Research only",holdings:[{id:1,symbol:"TEST",asset_type:"EQUITY",exchange:"NSE",status:"REVIEW_REQUIRED",weight_percent:100,recorded_return_percent:-20,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:["Review concentration."],missing_evidence:["No history"]}]})})));
  render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
  expect(await screen.findByText("Review concentration.")).toBeTruthy();
  expect(screen.getByText("TEST")).toBeTruthy();
  expect(screen.getByText("Needs review")).toBeTruthy();
  expect(fetch).toHaveBeenCalledWith("/api/v1/portfolio/review",expect.objectContaining({cache:"no-store"}));
 });
 it("shows an explicit failure instead of claiming portfolio health",async()=>{
  vi.stubGlobal("fetch",vi.fn(async()=>({ok:false})));
  render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
  expect(await screen.findByRole("alert")).toBeTruthy();
 });
});
