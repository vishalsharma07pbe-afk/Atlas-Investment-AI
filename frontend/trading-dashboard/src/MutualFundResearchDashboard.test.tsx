// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundResearchDashboard from "./MutualFundResearchDashboard";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const response={generated_at:"2026-11-17T06:30:00Z",methodology_version:"MF-RESEARCH-1.0.0",category:"LARGE_CAP",filters:{horizon_months:60,risk_tolerance:"MODERATE"},coverage:{name_matched_schemes:120,exact_direct_growth_schemes:20,official_category_verified:0,dated_nav_history_eligible:0,portfolio_disclosures_eligible:0},top_performers:[],growth_outlook:[],suitability:{status:"POTENTIALLY_SUITABLE",flags:[]},blockers:["DATED_NAV_HISTORY_INSUFFICIENT","PORTFOLIO_DISCLOSURES_NOT_CONNECTED"],market_overview:["LARGE_CAP","MID_CAP","SMALL_CAP"].map(segment=>({segment,status:"UNAVAILABLE",benchmark:null,period:null,last_available_date:null,evidence:[],blocker:"BENCHMARK_TRI_NOT_CONNECTED"})),recommendation_status:"NO_QUALIFYING_FUNDS_INCOMPLETE_EVIDENCE",notice:"Zero picks is intentional.",snapshot_hash:"1234567890abcdef"};

describe("Mutual fund research dashboard",()=>{
  it("shows independent empty recommendation lists and short-horizon warning",async()=>{
    const fetchMock=vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:120,sample_count:20,eligible_count:0,automatic_collection_enabled:true,notice:"Historical only"}:response}));vi.stubGlobal("fetch",fetchMock);
    render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
    await screen.findByText("Top Performers");
    expect(screen.getByText("Growth Outlook")).toBeTruthy();
    expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
    fireEvent.change(screen.getByLabelText("Investment horizon"),{target:{value:"36"}});
    await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("horizon_months=36"),expect.anything()));
  });
});

it("distinguishes explicit AMFI scheme evidence from name-matched discovery without qualifying incomplete funds",async()=>{
 const official={...response,coverage:{...response.coverage,explicit_amfi_history_candidates:2}};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:120,sample_count:20,eligible_count:0,automatic_collection_enabled:true,notice:"Historical only"}:official})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 expect(await screen.findByText("Explicit AMFI Direct Growth evidence (sample)")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});

it("shows dated secondary disclosures without enabling fund recommendations",async()=>{
 const disclosed={...response,disclosure_evidence:{status:"SECONDARY_REPORTED",notice:"Not independently verified.",items:[{scheme_code:"118955",scheme_name:"Example Disclosure Fund",plan:"DIRECT",source:"TIGZIG_AMFI_DERIVED",source_url:"https://api.tigzig.com/mf/v1/download/scheme_details_latest.csv.gz",collected_at:"2026-11-25T04:00:00Z",aum_date:"2026-11-24",aum_cr_all_plans:3500,benchmark:"Nifty 100 TRI",riskometer:"VERY_HIGH",ter_date:"2026-11-24",ter_percent:0.7,base_expense_percent:0.5,document_date:"2026-10-01",fund_managers:"Example Manager",exit_load:"1% within one year",conflicts:[]}]}};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:120,sample_count:20,eligible_count:0,automatic_collection_enabled:true,notice:"Historical only"}:disclosed})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 fireEvent.click(await screen.findByText("Reported fund disclosures (1)"));
 expect(screen.getByText("Example Disclosure Fund")).toBeTruthy();
 expect(screen.getByText("Not independently verified.")).toBeTruthy();
 expect(screen.getByText("0.7% · 2026-11-24")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});

it("shows portfolio composition separately from qualifying recommendations",async()=>{
 const item={scheme_code:"118955",scheme_name:"Composition Test Fund",concentration_research:{status:"EXACT_EQUITY_SUBSET_ONLY",category:"LARGE_CAP",exact_equity_weight_percent:60,largest_equity_weight_percent:60,top_three_equity_weight_percent:60,equity_subset_hhi:10000,equity_subset_effective_holdings:1,sector_classified_weight_percent:0,unclassified_exact_equity_weight_percent:60,sector_weights:[],largest_classified_sector_weight_percent:null,reported_equity_weight_percent:60,reported_debt_weight_percent:null,reported_money_market_weight_percent:null,missing_risk_evidence:["COMPLETE_SECTOR_AND_MARKET_CAP_COVERAGE_REQUIRED"],notice:"Subset only."},portfolio_date:"2026-10-31",reported_weight_total_percent:100,asset_allocation_percent:{Equity:60,Cash:40},exact_listed_equity_weight_percent:60,top_10_exact_equity_weight_percent:60,exact_equity_count:1,cached_company_evidence_weight_percent:20,cached_company_count:1,top_holdings:[{isin:"INE002A01018",name:"Example Equity",weight_percent:60}],notice:"Secondary composition only."};
 const result={...response,portfolio_evidence:{status:"SECONDARY_COMPOSITION_ONLY",notice:"Not a forward forecast.",items:[item]}};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:120,sample_count:20,eligible_count:0,automatic_collection_enabled:true,notice:"Historical only"}:result})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 fireEvent.click(await screen.findByText("Reported fund portfolios (1)"));
 expect(screen.getByText("Composition Test Fund")).toBeTruthy();
 expect(screen.getByText("Exact equity subset HHI")).toBeTruthy();
 expect(screen.getByText("10000.00")).toBeTruthy();
 expect(screen.getByText("Unclassified exact equity weight")).toBeTruthy();
 expect(screen.getByText("Example Equity · 60.00%")).toBeTruthy();
 expect(screen.getByText("20.00% · 1 companies")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});

it("labels overlap as a lower bound rather than total portfolio overlap",async()=>{
 const result={...response,portfolio_overlap:{status:"REPORTED_LOWER_BOUND",notice:"Zero does not prove no overlap.",pairs:[{scheme_a:"118955",name_a:"Alpha Fund",scheme_b:"118956",name_b:"Beta Fund",portfolio_date:"2026-10-31",common_equity_count:10,common_weight_lower_bound_percent:35,exact_weight_a_percent:82,exact_weight_b_percent:90}]}};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:120,sample_count:20,eligible_count:0,automatic_collection_enabled:true,notice:"Historical only"}:result})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 fireEvent.click(await screen.findByText("Common equity exposure (1 comparable pairs)"));
 expect(screen.getByText(/At least 35.00% shared reported exposure/)).toBeTruthy();
 expect(screen.getByText("Zero does not prove no overlap.")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});

it("distinguishes reported underlying fundamentals from a qualified growth outlook",async()=>{
 const item={scheme_code:"118955",scheme_name:"Underlying Test Fund",portfolio_date:"2026-10-31",reported_weight_total_percent:100,asset_allocation_percent:{Equity:80,Cash:20},exact_listed_equity_weight_percent:80,top_10_exact_equity_weight_percent:45,exact_equity_count:3,cached_company_evidence_weight_percent:65,cached_company_count:2,top_holdings:[],notice:"Secondary composition.",underlying_research:{status:"REPORTED_HISTORICAL_DRIVERS_ONLY",multi_year_quality:{status:"REPORTED_MULTI_YEAR_EXPOSURE",assessed_weight_percent:65,review_weight_percent:25,cash_conversion_coverage_percent:65,exact_equity_weight_percent:80,unassessed_exact_equity_weight_percent:15,metrics:[{metric:"NET_PROFIT",periods:["2023-03","2024-03","2025-03","2026-03"],coverage:65,consistent_increases:40,repeated_declines:25,nonpositive_observations:0}],cash_conversion:[{first_period:"2023-03",last_period:"2026-03",coverage:65,below_profit:25,negative_cash_years:25}],notice:"Original reported fund weights."},annual_statement_weight_percent:65,deterioration_review_weight_percent:25,sector_weights:[{sector:"Example sector",weight_percent:65}],annual_trends:[{metric:"NET_PROFIT",previous_period:"2025-03",latest_period:"2026-03",coverage:65,increased:40,decreased:25,unchanged:0,negative_latest:25}],relative_valuation:[{metric:"PE",coverage:65,above:40,below:25,equal:0,period_status:"UNVERIFIED"}],notice:"No forecast or qualified Growth Outlook."}};
 const result={...response,portfolio_evidence:{status:"SECONDARY_COMPOSITION_ONLY",notice:"Reported data only.",items:[item]}};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:120,sample_count:20,eligible_count:0,automatic_collection_enabled:true,notice:"Historical only"}:result})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 fireEvent.click(await screen.findByText("Reported fund portfolios (1)"));
 fireEvent.click(screen.getByText("Underlying company fundamentals"));
 expect(screen.getByText("Weight with dated annual statements")).toBeTruthy();
 expect(screen.getByText(/coverage 65.00% · increased 40.00%/)).toBeTruthy();
 expect(screen.getByText("Multi-year underlying business quality")).toBeTruthy();
 expect(screen.getByText("Exact equity weight without four-year evidence")).toBeTruthy();
 fireEvent.click(screen.getByText("Four-year financial consistency by fiscal period"));
 expect(screen.getByText(/repeated declines 25.00%/)).toBeTruthy();
 expect(screen.getByText("No forecast or qualified Growth Outlook.")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});

it("supports debt category navigation without implying an equity ranking",async()=>{
 const fetchMock=vi.fn(async(url:string)=>{
  const category=url.includes("category=CORPORATE_BOND")?"CORPORATE_BOND":"LARGE_CAP";
  return {ok:true,json:async()=>url.includes("historical-watch")?{category,items:[],universe_count:12,sample_count:10,eligible_count:0,category_comparison_enabled:category!=="CORPORATE_BOND",notice:"Historical only"}:{...response,category,qualification_summary:{evaluated_count:0,top_eligible_count:0,growth_eligible_count:0,excluded:[]}}};
 });
 vi.stubGlobal("fetch",fetchMock);
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 fireEvent.click(screen.getByRole("tab",{name:"Corporate Bond"}));
 await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("category=CORPORATE_BOND"),expect.anything()));
 expect(await screen.findByText("Descriptive NAV observations only; category-specific risk or comparable benchmark evidence is required for ranking.")).toBeTruthy();
 expect(screen.queryByRole("button",{name:"Return versus drawdown"})).toBeNull();
 expect(await screen.findByText("Qualification evidence (0 sampled schemes)")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});

it("opens an individual scheme report and preserves missing-evidence decisions",async()=>{
 const report={identifier:"123456",name:"Example Integrated Fund",category:"LARGE_CAP",plan:"DIRECT",option:"GROWTH",nav:"100.50",nav_date:"2026-11-24",nav_age_days:1,
  historical:{weekly_hurdle_sensitivity:{status:"HYPOTHETICAL_HURDLE_ONLY",weekly_intervals:156,annualized_arithmetic_return_percent:26,annualized_volatility_percent:11,scenarios:[{annual_effective_hurdle_percent:0,annualized_arithmetic_excess_percent:26,annualized_downside_percent:5,sharpe_proxy:2.3636,sortino_proxy:5.2},{annual_effective_hurdle_percent:6,annualized_arithmetic_excess_percent:20,annualized_downside_percent:6,sharpe_proxy:null,sortino_proxy:3.33}]},sources:["AMFI","MFAPI"],returns_1y:12,returns_3y:14,sample_peer_percentile:80,worst_rolling_return:-8,max_drawdown:-17,volatility:13,rolling_peer_consistency:{status:"MATCHED_SAMPLE_ONLY",matched_windows:100,total_windows:105,minimum_peer_count:4,above_median_windows:60,below_median_windows:30,tied_windows:10,above_median_percent:60,median_difference_pp:1.5,worst_difference_pp:-10,notice:"Sample only, not benchmark TRI."}},
  secondary_disclosure_available:false,secondary_portfolio_available:false,
  research_assessment:{version:"FUND-ASSESSMENT-1",status:"REVIEW_REQUIRED",supporting_evidence:[{code:"POSITIVE_REPORTED_THREE_YEAR_CAGR",value:14,unit:"PERCENT",source:"NAV_HISTORY"}],review_findings:[{code:"NEGATIVE_WORST_ROLLING_YEAR",value:-8,unit:"PERCENT",source:"NAV_HISTORY"}],next_evidence_checks:["MATCHED_REPORTED_PORTFOLIO_REQUIRED"],notice:"Descriptive evidence only."},
  top_performer:{status:"WITHHELD",missing:["BENCHMARK_HIT_RATE"],published_rank:null},
  growth_outlook:{status:"WITHHELD",missing:["FORWARD_EARNINGS_GROWTH"],published_rank:null},
  suitability:{status:"POTENTIALLY_SUITABLE",flags:[]},conclusion:"Neither research list qualifies.",reassessment:"Re-evaluate when dated evidence is acquired."};
 const result={...response,research_reports:[report]};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:12,sample_count:10,eligible_count:1,automatic_collection_enabled:true,notice:"Historical only"}:result})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 await screen.findByText("Individual fund research reports (1)");
 fireEvent.change(screen.getByLabelText("Research report"),{target:{value:"123456"}});
 expect(screen.getByText(/100\/105 windows/)).toBeTruthy();
 expect(screen.getByText("Integrated fund assessment")).toBeTruthy();
 expect(screen.getByText("Historical return hurdle sensitivity")).toBeTruthy();
 expect(screen.getByText(/not observed risk-free rates or benchmark TRI/)).toBeTruthy();
 expect(screen.getByText(/Positive reported three year cagr/)).toBeTruthy();
 expect(screen.getByText(/Negative worst rolling year/)).toBeTruthy();
 fireEvent.click(screen.getByText("Next evidence checks (1)"));
 expect(screen.getByText("Matched reported portfolio required")).toBeTruthy();
 expect(screen.getByText("Example Integrated Fund",{selector:"h4"})).toBeTruthy();
 expect(screen.getByText("12.00% / 14.00%")).toBeTruthy();
 expect(screen.getByText("Top Performer: Withheld")).toBeTruthy();
 expect(screen.getByText("Growth Outlook: Withheld")).toBeTruthy();
 expect(screen.getByText("Missing evidence: Benchmark hit rate")).toBeTruthy();
 expect(screen.getByText("No current matched secondary disclosure in this bounded snapshot.")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});


it("uses the exact per-report disclosure beyond the five-item display and preserves withheld decisions",async()=>{
 const common={status:"SECONDARY_REPORTED_NOT_INDEPENDENTLY_VERIFIED",source:"TIGZIG_AMFI_DERIVED",source_url:"https://api.tigzig.com/mf/v1/download/scheme_details_latest.csv.gz",collected_at:"2026-11-25T04:00:00Z",aum_date:"2026-11-24",aum_cr_all_plans:3500,benchmark:"Nifty 100 TRI",riskometer:"VERY_HIGH",ter_date:"2026-11-24",ter_percent:0.7,document_date:"2026-10-01",fund_managers:"Exact Sixth Fund Manager",exit_load:"1% within one year",conflicts:[]};
 const base={category:"LARGE_CAP",plan:"DIRECT",option:"GROWTH",nav:"100",nav_date:"2026-11-24",nav_age_days:1,historical:{sources:["AMFI","MFAPI"],returns_1y:12,returns_3y:14,sample_peer_percentile:80,worst_rolling_return:-8,max_drawdown:-17,volatility:13},secondary_disclosure_available:true,secondary_portfolio_available:false,top_performer:{status:"WITHHELD",missing:["EXPENSE_RATIO"],published_rank:null},growth_outlook:{status:"WITHHELD",missing:["OFFICIAL_RISKOMETER"],published_rank:null},suitability:{status:"POTENTIALLY_SUITABLE",flags:[]},conclusion:"Neither list qualifies.",reassessment:"Await official evidence."};
 const displayed=Array.from({length:5},(_,i)=>({...common,scheme_code:String(123450+i),scheme_name:"Displayed Fund "+i,plan:"DIRECT",base_expense_percent:0.5,fund_managers:"Other Manager "+i}));
 const reports=[{...base,identifier:"123455",name:"Sixth Fund",secondary_disclosure:common},{...base,identifier:"123450",name:"Legacy Fund"},{...base,identifier:"123451",name:"Explicitly Missing Fund",secondary_disclosure:null}];
 const result={...response,coverage:{...response.coverage,secondary_disclosure_matches:6,secondary_disclosure_displayed:5},disclosure_evidence:{status:"SECONDARY_REPORTED",notice:"Not independently verified.",items:displayed},research_reports:reports};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:12,sample_count:10,eligible_count:6,automatic_collection_enabled:true,notice:"Historical only"}:result})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 await screen.findByText("Individual fund research reports (3)");
 expect(screen.getByText(/6 exact secondary matches in the evaluated sample/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText("Research report"),{target:{value:"123455"}});
 expect(screen.getByText("Exact Sixth Fund Manager · 2026-10-01")).toBeTruthy();
 expect(screen.getByText("0.70% · 2026-11-24")).toBeTruthy();
 expect(screen.getByText("Top Performer: Withheld")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
 fireEvent.change(screen.getByLabelText("Research report"),{target:{value:"123450"}});
 expect(screen.getAllByText("Other Manager 0 · 2026-10-01",{selector:"dd"})).toHaveLength(2);
 fireEvent.change(screen.getByLabelText("Research report"),{target:{value:"123451"}});
 expect(screen.getByText("No current matched secondary disclosure in this bounded snapshot.")).toBeTruthy();
});


it("shows a full-sample composition without claiming detailed company enrichment or qualification",async()=>{
 const report={identifier:"123456",name:"Composition-only Fund",category:"LARGE_CAP",plan:"DIRECT",option:"GROWTH",nav:"100",nav_date:"2026-11-24",nav_age_days:1,historical:{sources:["AMFI"],returns_1y:12,returns_3y:14,sample_peer_percentile:80,worst_rolling_return:-8,max_drawdown:-17,volatility:13},secondary_disclosure_available:false,secondary_portfolio_available:false,secondary_portfolio_summary:{status:"SECONDARY_COMPOSITION_ONLY",portfolio_date:"2026-10-31",collected_at:"2026-11-25T04:00:00Z",reported_weight_total_percent:100,asset_allocation_percent:{Equity:60,Cash:40},exact_listed_equity_weight_percent:60,top_10_exact_equity_weight_percent:60,exact_equity_count:1,top_holdings:[{isin:"INE002A01018",name:"Exact Holding",weight_percent:60}],notice:"Secondary reported composition; not independently verified."},top_performer:{status:"WITHHELD",missing:["EXPENSE_RATIO"],published_rank:null},growth_outlook:{status:"WITHHELD",missing:["RECENT_PORTFOLIO_DISCLOSURE"],published_rank:null},suitability:{status:"POTENTIALLY_SUITABLE",flags:[]},conclusion:"Neither list qualifies.",reassessment:"Await official evidence."};
 const result={...response,coverage:{...response.coverage,secondary_portfolio_composition_matches:1,secondary_portfolio_matches:0},portfolio_evidence:{status:"NOT_AVAILABLE_OR_NOT_AUTHORIZED",items:[],notice:"Enrichment bounded."},research_reports:[report]};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:12,sample_count:10,eligible_count:1,automatic_collection_enabled:true,notice:"Historical only"}:result})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 await screen.findByText("Individual fund research reports (1)");
 expect(screen.getByText(/1 exact secondary composition matches/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText("Research report"),{target:{value:"123456"}});
 expect(screen.getByText("Exact Holding · 60.00%")).toBeTruthy();
 expect(screen.getByText("Detailed underlying company enrichment not included in this bounded snapshot.")).toBeTruthy();
 expect(screen.getByText("Growth Outlook: Withheld")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});
