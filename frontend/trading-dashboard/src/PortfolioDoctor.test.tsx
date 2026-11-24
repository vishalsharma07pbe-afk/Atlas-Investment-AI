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

it("renders exact-scheme history and local-only company review without a manual research call",async()=>{
 const base={status:"MONITOR",weight_percent:50,recorded_return_percent:10,evidence_date:"2026-11-23",history_count:50,change_20_observations_percent:1,recent_peak_change_percent:0,findings:[],missing_evidence:[]};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-24T10:00:00Z",holding_count:2,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[
 {...base,id:1,symbol:"TEST",asset_type:"EQUITY",exchange:"NSE",thesis_evidence:{status:"EVIDENCE_AVAILABLE",company_evidence:null,news_evidence:null,ai_status:"AVAILABLE",ai_review:{provider:"OLLAMA",findings:[{statement:"Sector comparison needs further evidence.",evidence_ids:["LIMITS"]}],notice:"Local commentary"}}},
 {...base,id:2,symbol:"123456",asset_type:"MUTUAL_FUND",exchange:null,fund_history_evidence:{scheme_name:"Example exact scheme",nav:100,nav_date:"2026-11-23",cagr_3y_percent:12,drawdown_3y_percent:-10,sources:["AMFI","MFAPI"],notice:"Historical only"}}
 ]})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByText("Local AI · OLLAMA")).toBeTruthy();
 expect(screen.getByText(/Sector comparison needs further evidence/)).toBeTruthy();
 expect(screen.getByText(/Example exact scheme/)).toBeTruthy();
 expect(screen.getByText("+12.00%")).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("prioritizes thesis review prompts and explains evidence gaps automatically",async()=>{
 const base={status:"MONITOR",asset_type:"EQUITY",exchange:"NSE",weight_percent:10,recorded_return_percent:2,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const summary={status:"REVIEW_EVIDENCE",risks:[],observations:[],review_prompts:[{statement:"P/E 25.00 vs sector 15.00.",source:"Upstox provider ratios"}],gaps:["Official filings unverified."],notice:"Partial research synthesis."};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-24T10:00:00Z",holding_count:2,attention_count:0,data_gap_count:0,thesis_review_count:1,notice:"Research only",holdings:[
 {...base,id:1,symbol:"FIRST"},
 {...base,id:2,symbol:"REVIEW",thesis_summary:summary}
 ]})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByText(/P\/E 25.00 vs sector 15.00/)).toBeTruthy();
 expect(screen.getByText("Upstox provider ratios",{exact:false})).toBeTruthy();
 expect(screen.getByText("Official filings unverified.")).toBeTruthy();
 expect(screen.getAllByRole("article")[0].textContent).toContain("REVIEW");
 expect(fetch).toHaveBeenCalledTimes(1);
});
