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
 const strategy_validation={sample_count:2,notice:"No validated forward performance.",horizons:{SWING:{counts:{REPLAY_OBSERVED:1,EVIDENCE_GAP:1},observed_instruments:1,items:[{exchange:"NSE",symbol:"REPLAY",as_of:"2026-11-23",trades:3,holding_sessions:10,test_start:"2026-01-01",test_end:"2026-11-23",gross_buy_hold_percent:8,small_sample:true,chronological_validation:{status:"INSUFFICIENT_OBSERVED_FOLDS",eligible_folds:2,observed_folds:1,no_signal_folds:1,folds:[{fold:1,status:"REPLAY_OBSERVED",exposure_start:"2026-01-02",test_end:"2026-06-01",trades:2,small_sample:true,cost_scenarios:[{cost_bps_per_side:15,net_return_percent:2.71,net_same_stock_buy_hold_percent:4.71,max_drawdown_percent:-3.71}]},{fold:2,status:"NO_SIGNALS",exposure_start:"2026-06-02",test_end:"2026-11-23",trades:0,small_sample:true,cost_scenarios:[]}],cost_summaries:[],notice:"Fixed rules; no fitting."},market_regime_research:{status:"PARTIAL",lookback_observations:60,threshold_percent:5,classified_trades:2,total_trades:3,groups:[{regime:"RISING",trades:2,small_sample:true,cost_scenarios:[{cost_bps_per_side:30,mean_trade_return_percent:1.23,win_rate_percent:50,wins:1,losses:1,flat:0}]},{regime:"UNKNOWN",trades:1,small_sample:true,cost_scenarios:[]}],notice:"Cohort means are per-position."},cost_scenarios:[{cost_bps_per_side:30,net_return_percent:2,matched_gross_exposure_return_percent:3,net_same_stock_buy_hold_percent:7.35,net_difference_vs_same_stock_pp:-5.35,gross_nifty50_price_index_percent:4.25,net_difference_vs_nifty50_pp:-2.25,max_drawdown_percent:-5,win_rate_percent:66.67,wins:2,losses:1,flat:0}]}]}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[section],strategy_validation})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 expect(await screen.findByRole("heading",{name:"Historical strategy replay"})).toBeTruthy();
 fireEvent.click(screen.getByText(/REPLAY · NSE · 3 simulated positions/));
 expect(screen.getAllByText("30 bps")).toHaveLength(2);
 expect(screen.getByText("7.35%")).toBeTruthy();
 expect(screen.getByText("-5.35 pp")).toBeTruthy();
 expect(screen.getByText("Repeated chronological test windows")).toBeTruthy();
 expect(screen.getByText(/1\/2 windows with simulated positions/)).toBeTruthy();
 expect(screen.getByText("2.71%")).toBeTruthy();
 expect(screen.getByText(/No signals — no return estimate/)).toBeTruthy();
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
 const enriched={...candidate,research_conclusion:{status:"REVIEW_REQUIRED",supporting_evidence:["REVENUE_THREE_ANNUAL_INCREASES"],next_evidence_checks:["DATED_VALUATION_AND_INDEPENDENT_FILING_EVIDENCE_REQUIRED"],qualification_status:"WATCH_ONLY_UNQUALIFIED",summary:"Technical watch requires review.",blockers:["VALUATION_NOT_VERIFIED"],warnings:["MATCHED_REPLAY_NONPOSITIVE_AFTER_COSTS"],evidence:{technical:"WATCH_RULES_MET",valuation:"NOT_VERIFIED"},reassessment_conditions:["Reassess on new financial results."],notice:"Watch only."},
 matched_strategy_replay:{as_of:"2026-11-23",trades:3,small_sample:true,cost_scenarios:[{cost_bps_per_side:30,net_return_percent:-2,max_drawdown_percent:-5}],notice:"Not a forecast."}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[enriched]}}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 expect(await screen.findByText("Technical watch requires review.")).toBeTruthy();
 expect(screen.getByText("Supporting reported evidence")).toBeTruthy();
 expect(screen.getByText("revenue three annual increases")).toBeTruthy();
 fireEvent.click(screen.getByText("Complete evidence & reassessment"));
 expect(screen.getByText("Reassess on new financial results.")).toBeTruthy();
 expect(screen.getByText("dated valuation and independent filing evidence required")).toBeTruthy();
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

it("shows historical liquidity diagnostics separately from executable recommendations",async()=>{
 const enriched={...candidate,matched_strategy_replay:{as_of:"2026-11-23",trades:3,small_sample:true,cost_scenarios:[],notice:"Watch only.",
 execution_research:{status:"HISTORICAL_PROXY_ONLY",positions:3,lookback_observations:20,participation_limit_percent:.5,zero_volume_endpoint_positions:1,
 notional_scenarios:[{entry_notional_inr:100000,within_proxy_limit:1,exceeds_proxy_limit:1,unknown:1}],
 base_friction_bps_per_side:30,friction_scenarios:[{extra_bps_per_side:75,total_bps_per_side:105,net_return_percent:-6.12,max_drawdown_percent:-9.23}],notice:"Not verified execution."}}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[enriched]}}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText(/Same-stock historical replay/));
 fireEvent.click(screen.getByText("Historical liquidity and execution stress"));
 expect(screen.getByText(/1 with zero-volume entry or exit/)).toBeTruthy();
 expect(screen.getByText("105 bps")).toBeTruthy();
 expect(screen.getByText("-6.12%")).toBeTruthy();
 expect(screen.getByText("Not verified execution.")).toBeTruthy();
});

it("shows full history provenance without claiming point-in-time certification",async()=>{
 const enriched={...candidate,matched_strategy_replay:{as_of:"2026-11-23",trades:3,small_sample:true,cost_scenarios:[],notice:"Watch only.",
 history_provenance:{status:"OVERLAP_UNCHANGED",history_observations:500,first_date:"2025-06-01",last_date:"2026-11-23",overlap_observations:499,changed_observations:0,changed_dates:[],corporate_action_status:"NO_RECORDED_CROSSING_ACTION",notice:"Not point-in-time certified."}}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[enriched]}}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText(/Same-stock historical replay/));
 fireEvent.click(screen.getByText("Historical evidence provenance"));
 expect(screen.getByText(/500 observations/)).toBeTruthy();
 expect(screen.getByText(/499 overlapping observations/)).toBeTruthy();
 expect(screen.getByText(/no recorded crossing action/)).toBeTruthy();
 expect(screen.getByText("Not point-in-time certified.")).toBeTruthy();
});

it("explains withheld calendar evidence without simulated returns",async()=>{
 const strategy_validation={sample_count:1,horizons:{SWING:{counts:{HISTORICAL_SESSION_MISMATCH:1},observed_instruments:0,items:[],
 calendar_withheld:[{exchange:"NSE",symbol:"GAP",status:"HISTORICAL_SESSION_MISMATCH",calendar_days:300,regular_sessions:200,missing_sessions:1,unexpected_observations:0,unknown_days:0,special_days:0,missing_dates:["2026-10-01"],unexpected_dates:[],unknown_dates:[],special_dates:[],notice:"Stored calendar only."}]}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[section],strategy_validation})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText(/GAP · NSE · historical calendar evidence withheld/));
 expect(screen.getByText(/1 missing sessions/)).toBeTruthy();
 expect(screen.getByText(/Missing dates.*2026-10-01/)).toBeTruthy();
 expect(screen.getByText(/No usable replay results yet/)).toBeTruthy();
});

it("explains contradictory listing evidence without implying historical universe coverage",async()=>{
 const strategy_validation={sample_count:1,horizons:{SWING:{counts:{LISTING_CONTEXT_CONTRADICTION:1},observed_instruments:0,items:[],
 listing_withheld:[{exchange:"NSE",symbol:"LISTING",status:"LISTING_CONTEXT_CONTRADICTION",listed_on:"2026-10-01",delisted_on:null,registry_source:null,registry_revision:null,universe_basis:"CURRENT_ACTIVE_REGISTRY_SAMPLE",historical_universe_verified:false,notice:"Survivorship bias remains."}]}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[section],strategy_validation})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText(/LISTING · NSE · listing evidence withheld/));
 expect(screen.getByText(/Recorded listing: 2026-10-01/)).toBeTruthy();
 expect(screen.getByText(/Historical universe not verified/)).toBeTruthy();
 expect(screen.getByText("Survivorship bias remains.")).toBeTruthy();
});

it("shows reported deal sides without promoting a watch",async()=>{
 const item={...candidate,deal_evidence:{status:"LOCAL_REPORTED_ONLY",latest_date:"2026-11-23",groups:[{deal_type:"BULK",record_count:1,buy_quantity:"0",sell_quantity:"1000",buy_reported_value_inr:"0",sell_reported_value_inr:"100000"}],recent_records:[{trade_date:"2026-11-23",deal_type:"BULK",client_name:"Example Client",side:"SELL",quantity:"1000",price_inr:"100",source_report:"Example report"}],notice:"Not verified institutional activity."}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[item]}}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText("Reported bulk / block deal observations"));
 expect(screen.getByText("Example Client")).toBeTruthy();
 expect(screen.getByText(/sell quantity 1000/)).toBeTruthy();
 expect(screen.getByText(/event risk not verified/)).toBeTruthy();
});

it("shows unusual price volume research separately from technical picks",async()=>{
 const pressure={status:"OBSERVED_PRICE_VOLUME_ONLY",as_of:"2026-11-23",relative_volume:3,change_percent:-4,findings:["HIGH_VOLUME_DECLINE_REVIEW"],adjustment_status:"RAW_UNADJUSTED",notice:"No institutional attribution."};
 const market={...section,result:{...section.result,price_volume_review:{evaluated_count:4,flagged_count:1,downside_items:[{id:2,symbol:"DOWNTEST",exchange:"NSE",as_of:"2026-11-23",price_volume_pressure:pressure}],upside_items:[],notice:"Bounded diagnostic sample."}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText("NSE · unusual price and volume (1 of 4 assessed)"));
 expect(screen.getByText("DOWNTEST")).toBeTruthy();
 expect(screen.getByText("high volume decline review")).toBeTruthy();
 expect(screen.getByText(/3× preceding median volume/)).toBeTruthy();
 expect(screen.getByText("Technical watch candidates")).toBeTruthy();
});

it("shows sector research questions separately from qualification",async()=>{
 const item={...candidate,global_exposure:{status:"SECTOR_QUESTIONS_ONLY",sector:"Information Technology",questions:[{factor:"USD_INR",indicator:"USD/INR",as_of:"2026-11-23",change:{start_date:"2026-11-16",end_date:"2026-11-23",value:2,unit:"PERCENT"},question:"Check actual export revenue and currency hedges."}],missing_factors:["NASDAQCOM"],notice:"No company sensitivity established."}};
 const market={...section,result:{...section.result,horizons:{...section.result.horizons,SWING:{...section.result.horizons.SWING,candidates:[item]}}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[market]})})));
 render(<HorizonResearch horizon="SWING" onSettings={()=>{}}>{null}</HorizonResearch>);
 fireEvent.click(await screen.findByText("Global sector exposure research"));
 expect(screen.getByText("Check actual export revenue and currency hedges.")).toBeTruthy();
 expect(screen.getByText(/Missing relevant evidence: nasdaqcom/)).toBeTruthy();
 expect(screen.getByText(/event risk not verified/)).toBeTruthy();
});
