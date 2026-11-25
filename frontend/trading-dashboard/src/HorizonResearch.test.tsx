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
 const strategy_validation={sample_count:2,notice:"No validated forward performance.",horizons:{SWING:{counts:{REPLAY_OBSERVED:1,EVIDENCE_GAP:1},observed_instruments:1,items:[{exchange:"NSE",symbol:"REPLAY",as_of:"2026-11-23",trades:3,holding_sessions:10,test_start:"2026-01-01",test_end:"2026-11-23",gross_buy_hold_percent:8,small_sample:true,market_regime_research:{status:"PARTIAL",lookback_observations:60,threshold_percent:5,classified_trades:2,total_trades:3,groups:[{regime:"RISING",trades:2,small_sample:true,cost_scenarios:[{cost_bps_per_side:30,mean_trade_return_percent:1.23,win_rate_percent:50,wins:1,losses:1,flat:0}]},{regime:"UNKNOWN",trades:1,small_sample:true,cost_scenarios:[]}],notice:"Cohort means are per-position."},cost_scenarios:[{cost_bps_per_side:30,net_return_percent:2,matched_gross_exposure_return_percent:3,net_same_stock_buy_hold_percent:7.35,net_difference_vs_same_stock_pp:-5.35,gross_nifty50_price_index_percent:4.25,net_difference_vs_nifty50_pp:-2.25,max_drawdown_percent:-5,win_rate_percent:66.67,wins:2,losses:1,flat:0}]}]}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[section],strategy_validation})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 expect(await screen.findByRole("heading",{name:"Historical strategy replay"})).toBeTruthy();
 fireEvent.click(screen.getByText(/REPLAY · NSE · 3 simulated positions/));
 expect(screen.getAllByText("30 bps")).toHaveLength(2);
 expect(screen.getByText("7.35%")).toBeTruthy();
 expect(screen.getByText("-5.35 pp")).toBeTruthy();
 expect(screen.getByText("Signal-date market trend cohorts")).toBeTruthy();
 expect(screen.getByText(/2\/3 positions classified/)).toBeTruthy();
 expect(screen.getByText("1.23%")).toBeTruthy();
 expect(screen.getByText("unknown")).toBeTruthy();
 expect(screen.getByText("4.25%")).toBeTruthy();
 expect(screen.getByText("-2.25 pp")).toBeTruthy();
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

it("shows the integrated stock conclusion and exact replay without manual analysis",async()=>{
 const enriched={...candidate,research_conclusion:{status:"REVIEW_REQUIRED",summary:"Technical watch requires review.",blockers:["VALUATION_NOT_VERIFIED"],warnings:["MATCHED_REPLAY_NONPOSITIVE_AFTER_COSTS"],evidence:{technical:"WATCH_RULES_MET",valuation:"NOT_VERIFIED"},reassessment_conditions:["Reassess on new financial results."],notice:"Watch only."},
 matched_strategy_replay:{as_of:"2026-11-23",trades:3,small_sample:true,cost_scenarios:[{cost_bps_per_side:30,net_return_percent:-2,max_drawdown_percent:-5}],notice:"Not a forecast."}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[enriched]}}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 expect(await screen.findByText("Technical watch requires review.")).toBeTruthy();
 fireEvent.click(screen.getByText("Complete evidence & reassessment"));
 expect(screen.getByText("Reassess on new financial results.")).toBeTruthy();
 fireEvent.click(screen.getByText(/Same-stock historical replay/));
 expect(screen.getByText(/net simulated return -2%/)).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("shows historical price geometry with explicit costs and no trade verdict",async()=>{
 const enriched={...candidate,price_structure:{status:"HISTORICAL_STRUCTURE",scenario_status:"ILLUSTRATIVE_HISTORICAL_GEOMETRY",support:[{price:90,observed_on:"2026-11-10",confirmed_on:"2026-11-12"}],resistance:[{price:120,observed_on:"2026-11-15",confirmed_on:"2026-11-17"}],scenario:{reference_close:100,lower_reference:90,upper_reference:120,cost_bps_per_side:30,downside_percent:10.5,upside_percent:19.3,reward_to_risk:1.84},notice:"Historical geometry only."}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[enriched]}}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText("Price structure & risk scenarios"));
 expect(screen.getByText("1.84×")).toBeTruthy();
 expect(screen.getByText("Assumed cost: 30 bps each side.")).toBeTruthy();
 expect(screen.getByText("Historical geometry only.")).toBeTruthy();
});

it("keeps split normalization diagnostics separate from technical candidates",async()=>{
 const corporate_action_review={normalized_preview_count:1,withheld_count:1,notice:"Excluded from rankings and backtesting.",previews:[{symbol:"SPLITTEST",exchange:"NSE",first_date:"2026-10-20",as_of:"2026-11-13",observations:25,actions:[{ex_date:"2026-11-13",action_type:"SPLIT",post_shares_per_pre_share:"2"}],change_1d_percent:2,change_20_observation_percent:2,window_price_change_percent:2,notice:"Price only, not total return."}]};
 const market={...section,result:{...section.result,corporate_action_review}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText("NSE · corporate action diagnostics (1 previews, 1 withheld)"));
 expect(screen.getByText(/SPLITTEST · known-action price-only preview/)).toBeTruthy();
 expect(screen.getByText(/Normalized daily price change: 2%/)).toBeTruthy();
 expect(screen.getByText("Excluded from rankings and backtesting.")).toBeTruthy();
 expect(screen.getByText("TEST")).toBeTruthy();
});
