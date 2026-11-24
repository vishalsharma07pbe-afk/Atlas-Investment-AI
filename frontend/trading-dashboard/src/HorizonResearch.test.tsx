/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
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

 it("shows independent cited reviews without changing technical qualification",async()=>{
  const reviewed={...candidate,ai_review:{reviews:[{provider:"OLLAMA",findings:[{statement:"Historical volatility requires review.",evidence_ids:["OBS"]}]},{provider:"GEMINI",findings:[{statement:"Current company evidence is incomplete.",evidence_ids:["LIMITS"]}]}],reviewed_at:"2026-11-24T10:00:00Z",notice:"Unverified model commentary."}};
  const enriched={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[reviewed]}}}};
  vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,automatic_ai_status:"ENABLED",sections:[enriched]})})));
  render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
  fireEvent.click(await screen.findByText("Automatic AI evidence review (2 providers)"));
  expect(screen.getByText("OLLAMA")).toBeTruthy();
  expect(screen.getByText("GEMINI")).toBeTruthy();
  expect(screen.getByText(/event risk not verified/)).toBeTruthy();
  expect(screen.getByText("Technical watch candidates")).toBeTruthy();
 });

});

it("displays automated historical replay without removing strategy research blockers",async()=>{
 const strategy_validation={sample_count:2,notice:"No validated forward performance.",horizons:{SWING:{counts:{REPLAY_OBSERVED:1,EVIDENCE_GAP:1},observed_instruments:1,items:[{exchange:"NSE",symbol:"REPLAY",as_of:"2026-11-23",trades:3,holding_sessions:10,test_start:"2026-01-01",test_end:"2026-11-23",gross_buy_hold_percent:8,small_sample:true,cost_scenarios:[{cost_bps_per_side:30,net_return_percent:2,matched_gross_exposure_return_percent:3,max_drawdown_percent:-5,win_rate_percent:66.67,wins:2,losses:1,flat:0}]}]}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[section],strategy_validation})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 expect(await screen.findByRole("heading",{name:"Historical strategy replay"})).toBeTruthy();
 fireEvent.click(screen.getByText(/REPLAY · NSE · 3 simulated positions/));
 expect(screen.getByText("30 bps")).toBeTruthy();
 expect(screen.getByText("66.67%")).toBeTruthy();
 expect(screen.getByText(/event risk not verified/)).toBeTruthy();
});

it("shows prospective evidence gaps and candidate conflicts without implying calibrated odds",async()=>{
 const enriched={...candidate,research_reliability:{status:"REVIEW_CONFLICTING_EVIDENCE",warnings:["NET_PROFIT_DETERIORATION_REVIEW"],blockers:["STRATEGY_BACKTEST_NOT_VERIFIED"],prospective_status:"INSUFFICIENT_EVIDENCE",notice:"Watch only."}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[enriched]}}}};
 const research_reliability={horizons:{SWING:{status:"INSUFFICIENT_EVIDENCE",selected_mature_watches:2,observed_outcomes:1,distinct_observed_isins:1,coverage_percent:50,overlap_excluded:1,immature_excluded:0,incompatible_excluded:0,invalid_excluded:0,blockers:["INCOMPLETE_OUTCOME_COVERAGE"],cost_scenarios:[],notice:"No recommendation gate is lifted."}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market],research_reliability})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 expect(await screen.findByRole("heading",{name:"Prospective watch reliability"})).toBeTruthy();
 expect(screen.getByText("NOT CALIBRATED")).toBeTruthy();
 expect(screen.getByText(/50% coverage/)).toBeTruthy();
 fireEvent.click(screen.getByText("Conflicting evidence · review needed"));
 expect(screen.getByText("net profit deterioration review")).toBeTruthy();
 expect(screen.getByText(/strategy backtest not verified/)).toBeTruthy();
});
