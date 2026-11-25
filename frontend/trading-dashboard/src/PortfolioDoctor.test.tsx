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

it("automatically displays partial diversification coverage and missing adjusted history",async()=>{
 const holding={id:1,symbol:"TEST",asset_type:"EQUITY",exchange:"NSE",status:"MONITOR",weight_percent:100,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const diversification={status:"PARTIAL_COVERAGE",unpriced_count:0,unresolved_identity_count:0,resolved_identity_count:1,top_three_resolved_weight_percent:100,asset_exposure:[{label:"EQUITY",weight_percent:100}],direct_equity_sector_exposure:[{label:"Unknown",weight_percent:100}],fund_category_exposure:[],sector_coverage_percent:0,fund_category_coverage_percent:null,review_prompts:["Complete missing classification."],notice:"Underlying fund exposure unknown."};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-24T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding],diversification,equity_correlation:{status:"UNAVAILABLE",comparable_pairs:0,attempted_pairs:0,pairs:[],notice:"Adjusted prices required."}})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByRole("heading",{name:"Diversification & concentration"})).toBeTruthy();
 expect(screen.getByText("Complete missing classification.")).toBeTruthy();
 expect(screen.getByText("Comparable adjusted return history unavailable.")).toBeTruthy();
 expect(screen.getByText("Partial classification or pricing coverage.")).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("shows portfolio research context without promoting historical watches into recommendations",async()=>{
 const holding={id:1,symbol:"HELD",asset_type:"EQUITY",exchange:"NSE",status:"MONITOR",weight_percent:100,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const opportunity_context={status:"WATCH_CONTEXT_AVAILABLE",held_excluded_count:1,ready_sections:["NSE","LARGE_CAP"],blocked_sections:["BSE"],notice:"Research only.",equities:[{isin:"INE009A01021",symbol:"WATCH",exchange:"NSE",horizon:"LONG_TERM",as_of:"2026-11-23",sector:"energy",sector_weight_percent:55,context:"EXISTING_SECTOR_CONCENTRATION",identity_status:"NO_EXACT_HELD_IDENTITY_MATCH",adjustment_status:"RAW_UNADJUSTED",blockers:["FUNDAMENTALS_NOT_VERIFIED"]}],funds:[{scheme_code:"123456",name:"Example fund",category:"LARGE_CAP",as_of:"2026-11-23",cagr_3y_percent:12,drawdown_3y_percent:-20,context:"EXISTING_FUND_CATEGORY",identity_status:"NO_EXACT_HELD_IDENTITY_MATCH"}]};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-24T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding],opportunity_context})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByRole("heading",{name:"Research beyond your recorded holdings"})).toBeTruthy();
 expect(screen.getByText("WATCH · NSE")).toBeTruthy();
 expect(screen.getByText("Example fund")).toBeTruthy();
 expect(screen.getByText(/Not buy recommendations/)).toBeTruthy();
 expect(screen.getByText(/fundamentals not verified/)).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("shows a compact risk-first summary without loading detailed research panels",async()=>{
 const base={asset_type:"EQUITY",exchange:"NSE",weight_percent:10,recorded_return_percent:2,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,missing_evidence:[]};
 const holdings=[{...base,id:1,symbol:"MONITOR",status:"MONITOR",findings:[]},{...base,id:2,symbol:"RISK",status:"REVIEW_REQUIRED",findings:["Review recorded loss."]}];
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({holding_count:2,attention_count:1,data_gap_count:0,generated_at:"2026-11-24T10:00:00Z",holdings})})));
 render(<PortfolioDoctor compact revision={0} onSettings={()=>{}} onOpenPortfolio={()=>{}}/>);
 expect(await screen.findByText("Review recorded loss.")).toBeTruthy();
 expect(screen.getByText("RISK")).toBeTruthy();
 expect(screen.queryByText("MONITOR")).toBeNull();
 expect(screen.getByRole("button",{name:"Open full review"})).toBeTruthy();
 expect(screen.queryByText("Company thesis & local AI review")).toBeNull();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("surfaces newly reported financial deterioration ahead of unchanged holdings",async()=>{
 const base={status:"MONITOR",asset_type:"EQUITY",exchange:"NSE",weight_percent:10,recorded_return_percent:2,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:2,attention_count:0,data_gap_count:0,thesis_changed_count:1,notice:"Research only",holdings:[
 {...base,id:1,symbol:"FIRST"},
 {...base,id:2,symbol:"DETERIORATION",thesis_changes:[{metric:"NET_PROFIT",previous_period:"March 2025",current_period:"March 2026",previous_direction:"IMPROVING",current_direction:"DECLINING",observed_at:"2026-11-25T10:00:00Z"}]}
 ]})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByText("Recently observed financial direction changes")).toBeTruthy();
 expect(screen.getByText(/March 2025 \(improving\) → March 2026 \(declining\)/)).toBeTruthy();
 expect(screen.getAllByRole("article")[0].textContent).toContain("DETERIORATION");
 expect(screen.getByText("Needs review")).toBeTruthy();
});

it("shows exact held fund secondary disclosures and composition without a recommendation ranking",async()=>{
 const holding={id:1,symbol:"118955",asset_type:"MUTUAL_FUND",exchange:null,status:"MONITOR",weight_percent:100,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[],fund_thesis_evidence:{
 status:"SECONDARY_REPORTED_EVIDENCE",notice:"Not independently verified.",disclosure:{scheme_name:"Held Example Fund",source:"TIGZIG_AMFI_DERIVED",plan:"REGULAR",ter_percent:1.4,riskometer:"VERY_HIGH"},portfolio:{portfolio_date:"2026-10-31",source:"TIGZIG_AMC_DERIVED",exact_listed_equity_weight_percent:90,top_10_exact_equity_weight_percent:40,top_holdings:[{isin:"INE002A01018",name:"Example Company",weight_percent:10}],underlying_research:{status:"REPORTED_HISTORICAL_DRIVERS_ONLY",annual_statement_weight_percent:60,deterioration_review_weight_percent:25,notice:"Historical only."},notice:"Reported composition."}}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding]})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByText("Held Example Fund · REGULAR")).toBeTruthy();
 expect(screen.getByText(/1.40%/)).toBeTruthy();
 expect(screen.getByText(/Underlying deterioration observations: 25.00%/)).toBeTruthy();
 expect(screen.getByText(/Example Company · 10.00%/)).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("prioritizes dated fund disclosure changes and does not treat lower fees as recovery",async()=>{
 const base={asset_type:"MUTUAL_FUND",exchange:null,status:"MONITOR",weight_percent:50,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const change={metric:"TER",previousDate:"2026-11-24",currentDate:"2026-11-25",previousValue:"0.7",currentValue:"0.9",attention:"REVIEW",observedAt:"2026-11-25T10:00:00Z"};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:2,attention_count:0,data_gap_count:0,fund_thesis_changed_count:2,fund_thesis_attention_count:1,notice:"Research only",holdings:[
 {...base,id:1,symbol:"LOWERFEE",fund_thesis_changes:[{...change,previousValue:"0.9",currentValue:"0.7",attention:"OBSERVE"}]},
 {...base,id:2,symbol:"HIGHERFEE",fund_thesis_changes:[change]}
 ]})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByText("HIGHERFEE")).toBeTruthy();
 expect(screen.getAllByRole("article")[0].textContent).toContain("HIGHERFEE");
 expect(screen.getByText(/0.7% \(2026-11-24\) → 0.9% \(2026-11-25\)/)).toBeTruthy();
 expect(screen.getByText(/Observation only. Secondary reported evidence/)).toBeTruthy();
 expect(screen.getByText("Needs review")).toBeTruthy();
});

it("prioritizes recent quarterly ownership declines without implying trades",async()=>{
 const base={asset_type:"EQUITY",exchange:"NSE",status:"MONITOR",weight_percent:50,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const change={category:"promoters",previousDate:"2026-06-30",currentDate:"2026-09-30",previousPercent:50,currentPercent:48,changePp:-2,attention:"REVIEW",observedAt:"2026-11-25T10:00:00Z"};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:2,attention_count:0,data_gap_count:0,ownership_changed_count:1,ownership_attention_count:1,notice:"Research only",holdings:[
 {...base,id:1,symbol:"UNCHANGED"},
 {...base,id:2,symbol:"OWNERSHIP",ownership_changes:[change]}
 ]})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByText("Recently observed quarterly ownership changes")).toBeTruthy();
 expect(screen.getAllByRole("article")[0].textContent).toContain("OWNERSHIP");
 expect(screen.getByText(/50.00% \(2026-06-30\) → 48.00% \(2026-09-30\)/)).toBeTruthy();
 expect(screen.getByText(/not proof of trades/)).toBeTruthy();
});

it("surfaces portfolio-level benchmark lag without requiring a flagged individual holding",async()=>{
 const holding={id:1,symbol:"EXAMPLE",asset_type:"EQUITY",exchange:"NSE",status:"MONITOR",weight_percent:100,recorded_return_percent:2,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding],
 portfolio_level_risk:{benchmark_status:"COMPARABLE_PRICE_REFERENCE",concentration_status:"INSUFFICIENT_EVIDENCE",sector_status:"INSUFFICIENT_EVIDENCE",attention:[{kind:"BENCHMARK_RELATIVE_LAG",label:"13-week lag versus NIFTY 50 price index",value:-6,threshold:-5,unit:"PP",evidenceThrough:"2026-11-25"}],notice:"Price reference, not TRI."}})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByText("Portfolio-level risk monitoring")).toBeTruthy();
 expect(screen.getByText("-6.00 pp")).toBeTruthy();
 expect(screen.getByText("Price reference, not TRI.")).toBeTruthy();
});

it("displays automatic allocation alternatives without manual targets or extra requests",async()=>{
 const holding={id:1,symbol:"TEST",asset_type:"EQUITY",exchange:"NSE",status:"MONITOR",weight_percent:100,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const allocation_research={status:"HYPOTHETICAL_SCENARIOS_AVAILABLE",recorded_value:1000,current_largest_percent:100,current_top_three_percent:100,single_identity_review_threshold_percent:25,top_three_review_threshold_percent:60,scenarios:[{hypotheticalNewIdentities:5,additionalCapital:3000,equalNewInvestmentAmount:600,projectedLargestPercent:25,projectedTopThreePercent:55,hypotheticalRedistributedCapital:750,redistributedPercent:75}],notice:"Before fees, taxes and execution constraints."};
 const diversification={status:"CLASSIFIED_PRICED_HOLDINGS",unpriced_count:0,unresolved_identity_count:0,resolved_identity_count:1,top_three_resolved_weight_percent:100,asset_exposure:[],direct_equity_sector_exposure:[],fund_category_exposure:[],sector_coverage_percent:100,fund_category_coverage_percent:null,review_prompts:[],notice:"Recorded prices.",allocation_research};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding],diversification})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByRole("heading",{name:"Automatic allocation research"})).toBeTruthy();
 expect(screen.getByText("₹3,000")).toBeTruthy();
 expect(screen.getByText("₹750 (75.00%)")).toBeTruthy();
 expect(screen.getByText("25.00% / 55.00%")).toBeTruthy();
 expect(screen.getByText("Before fees, taxes and execution constraints.")).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("displays independent automatic exposure stress results and withheld scenarios",async()=>{
 const holding={id:1,symbol:"TEST",asset_type:"EQUITY",exchange:"NSE",status:"MONITOR",weight_percent:100,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const exposure_stress={status:"PARTIAL_SCENARIO_COVERAGE",recorded_value:1000,scenarios:[{kind:"DIRECT_EQUITY_SELL_OFF",title:"Direct equity sell-off",shocks:[{exposure:"DIRECT_EQUITY",label:"Direct equity",assumedChangePercent:-20,recordedExposure:1000,valueChange:-200}],changeAmount:-200,changePercent:-20,stressedValue:800}],withheld:["SECTOR_SHOCK_REQUIRES_COMPLETE_DIRECT_EQUITY_CLASSIFICATION"],notice:"Not a forecast."};
 const diversification={status:"PARTIAL_COVERAGE",unpriced_count:0,unresolved_identity_count:0,resolved_identity_count:1,top_three_resolved_weight_percent:100,asset_exposure:[],direct_equity_sector_exposure:[],fund_category_exposure:[],sector_coverage_percent:0,fund_category_coverage_percent:null,review_prompts:[],notice:"Recorded prices.",exposure_stress};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding],diversification})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByRole("heading",{name:"Automatic portfolio stress research"})).toBeTruthy();
 expect(screen.getByText("Direct equity sell-off")).toBeTruthy();
 expect(screen.getByText("₹800")).toBeTruthy();
 expect(screen.getByText("Largest sector scenario requires complete direct-equity sector classification.")).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("shows mapped combined equity exposure and same-date overlap without extra API calls",async()=>{
 const holding={id:1,symbol:"123456",asset_type:"MUTUAL_FUND",exchange:null,status:"MONITOR",weight_percent:100,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const look_through={status:"DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE",portfolio_date:"2026-10-31",risk_observation_count:3,sector_status:"PARTIAL_CLASSIFIED_EXPOSURE",sector_classified_portfolio_percent:59,sector_unclassified_mapped_value:280,sector_count:1,sector_review_count:1,sector_exposures:[{sector:"energy",directValue:200,indirectValue:390,estimatedValue:590,portfolioPercent:59,reviewConcentration:true}],sector_notice:"Whole recorded portfolio denominator.",matched_fund_value_percent:100,mapped_portfolio_percent:87,unmodeled_value:130,matched_scheme_count:2,mapped_equity_count:2,overlap_pair_count:1,exposures:[{isin:"INE002A01018",directValue:200,indirectValue:390,estimatedValue:590,portfolioPercent:59,contributingSchemes:2}],overlap_pairs:[{schemeA:"123456",schemeB:"123457",sameUnderlyingFund:false,commonEquities:2,sharedWeightPercent:50,coverageA:80,coverageB:90}],notice:"Dated secondary disclosures."};
 const diversification={status:"PARTIAL_COVERAGE",unpriced_count:0,unresolved_identity_count:0,resolved_identity_count:1,top_three_resolved_weight_percent:100,asset_exposure:[],direct_equity_sector_exposure:[],fund_category_exposure:[],sector_coverage_percent:0,fund_category_coverage_percent:100,review_prompts:[],notice:"Recorded prices.",look_through};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding],diversification})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByRole("heading",{name:"Combined equity exposure and fund overlap"})).toBeTruthy();
 expect(screen.getAllByText("₹590")).toHaveLength(2);
 expect(screen.getAllByText("59.00%")).toHaveLength(2);
 expect(screen.getByText("50.00%")).toBeTruthy();
 expect(screen.getByText("Dated secondary disclosures.")).toBeTruthy();
 expect(screen.getByText("3 hidden concentration or high overlap review observations.")).toBeTruthy();
 expect(screen.getByText("energy · Review")).toBeTruthy();
 expect(screen.getByText("1 sectors exceed the illustrative 40% portfolio review threshold.")).toBeTruthy();
 expect(screen.getByText("Whole recorded portfolio denominator.")).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("shows historical fixed-weight alternatives and observed variability automatically",async()=>{
 const holding={id:1,symbol:"TEST",asset_type:"EQUITY",exchange:"NSE",status:"MONITOR",weight_percent:100,recorded_return_percent:1,evidence_date:null,history_count:0,change_20_observations_percent:null,recent_peak_change_percent:null,findings:[],missing_evidence:[]};
 const historical_allocation={status:"HISTORICAL_COMPARISON_AVAILABLE",observations:40,first_date:"2026-10-15",last_date:"2026-11-24",lowest_observed_variability:"EQUAL_WEIGHTS",alternatives:[{kind:"EQUAL_WEIGHTS",sampleMeanPercent:0.12,sampleVolatilityPercent:0.82,largestWeightPercent:50,oneWayTurnoverPercent:30,weights:[{isin:"INE002A01018",symbol:"TEST",weightPercent:50}]}],notice:"In-sample only."};
 const diversification={status:"CLASSIFIED_PRICED_HOLDINGS",unpriced_count:0,unresolved_identity_count:0,resolved_identity_count:1,top_three_resolved_weight_percent:100,asset_exposure:[],direct_equity_sector_exposure:[],fund_category_exposure:[],sector_coverage_percent:100,fund_category_coverage_percent:null,review_prompts:[],notice:"Recorded prices."};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T10:00:00Z",holding_count:1,attention_count:0,data_gap_count:0,notice:"Research only",holdings:[holding],diversification,equity_correlation:{status:"AVAILABLE",historical_allocation,notice:"Adjusted history."}})})));
 render(<PortfolioDoctor revision={0} onSettings={()=>{}}/>);
 expect(await screen.findByRole("heading",{name:"Historical allocation alternatives"})).toBeTruthy();
 expect(screen.getByText("0.82%")).toBeTruthy();
 expect(screen.getByText("30.00%")).toBeTruthy();
 expect(screen.getByText("In-sample only.")).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});
