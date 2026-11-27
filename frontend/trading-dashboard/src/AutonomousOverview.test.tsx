/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import AutonomousOverview from "./AutonomousOverview";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("automatic research overview",()=>{
 it("shows persisted observations without launching a manual scan and keeps tools hidden",async()=>{
   const fetchMock=vi.fn(async()=>({ok:true,json:async()=>({enabled:true,interval_seconds:900,sections:[{section:"NSE",status:"READY",generated_at:"2026-11-24T10:00:00Z",result:{eligible_count:1,universe_size:2,momentum_leaders:[{id:1,symbol:"TCS",exchange:"NSE",as_of:"2026-11-23",momentum_20d_percent:3}]}},{section:"LARGE_CAP",status:"READY",generated_at:null,result:{growth_outlook:[]}}]})}));
   vi.stubGlobal("fetch",fetchMock);
   render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}><p>Manual research tool</p></AutonomousOverview>);
   expect(await screen.findByText("TCS")).toBeTruthy();
   expect(screen.getByText("No growth picks meet the verified evidence requirements.")).toBeTruthy();
   expect(screen.queryByText("Manual research tool")).toBeNull();
   expect(fetchMock.mock.calls.length).toBe(1);
   fireEvent.click(screen.getByRole("button",{name:"Open research tools"}));
   expect(screen.getByText("Manual research tool")).toBeTruthy();
 });
});

it("links directly to current horizon watches without triggering a manual scan",async()=>{
 const navigate=vi.fn();
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[{section:"NSE",status:"READY",generated_at:null,result:{horizons:{SWING:{status:"TECHNICAL_WATCH_ONLY",candidates:[{id:1,symbol:"TEST",exchange:"NSE",as_of:"2026-11-23"}]}}}},{section:"BSE",status:"STALE",generated_at:null,result:{horizons:{SWING:{status:"TECHNICAL_WATCH_ONLY",candidates:[{id:2,symbol:"STALE",exchange:"BSE",as_of:"2026-11-23"}]}}}}]})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}} onHorizon={navigate}>{null}</AutonomousOverview>);
 expect(await screen.findByText("1 technical watches")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:/Swing/}));
 expect(navigate).toHaveBeenCalledWith("SWING");
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("keeps the overview usable when institutional access is disabled on the real API",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,interval_seconds:900,sections:[{section:"NSE",status:"READY",generated_at:null,result:{eligible_count:0,universe_size:0,momentum_leaders:[]}}],institutional_activity:{status:"DISABLED_OR_NOT_AUTHORIZED",market:"NSE_CASH",unit:"PROVIDER_REPORTED",participants:{},paired_five_date_window:null,blockers:["RETAIL_FLOW_FEED_MISSING"]}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}><p>Manual research tool</p></AutonomousOverview>);
 expect(await screen.findByText("Institutional activity & company news")).toBeTruthy();
 expect(screen.getAllByText(/No recent usable observation/)).toHaveLength(2);
 fireEvent.click(screen.getByRole("button",{name:"Open research tools"}));
 expect(screen.getByText("Manual research tool")).toBeTruthy();
});

it("shows consolidated evidence without calling technical watches qualified recommendations",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],daily_briefing:{
 status:"PARTIAL",ready_sections:1,total_sections:7,market:{eligible_histories:5,sampled_instruments:10,outlook_status:"MARKET_REGIME_NOT_VALIDATED"},
 horizons:{SWING:{displayed_watch_count:1,ai_reviewed_count:1,conflicting_evidence_count:1,qualified_count:null}},
 funds:{growth_pick_count:null,historical_watch_count:0,ready_categories:0,total_categories:5},
 institutional:{status:"UNAVAILABLE"},leading_evidence_gaps:[],notice:"Not a forecast"}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Daily research briefing"})).toBeTruthy();
 expect(screen.getByText(/Full investment qualification is not available yet/)).toBeTruthy();
 expect(screen.getByText(/1 displayed horizon watches/)).toBeTruthy();
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("shows sourced reference currency rates and derived changes without calling them live",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],global_fx:{status:"REFERENCE_RATES_AVAILABLE",items:[{pair:"USD_INR",status:"AVAILABLE",as_of:"2026-11-24",rate:90.125,basis:"DERIVED_ECB_CROSS",changes:[{observations:1,start_date:"2026-11-23",end_date:"2026-11-24",percent:1.2}]}],notice:"Not a live quote or directional forecast."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Global currency context"})).toBeTruthy();
 expect(screen.getByText(/USD\/INR/)).toBeTruthy();
 expect(screen.getByText("90.1250")).toBeTruthy();
 expect(screen.getByText("+1.20% / — / —")).toBeTruthy();
 expect(screen.getByText(/ATLAS cross-rate/)).toBeTruthy();
});

it("distinguishes dated oil prices and treasury yield changes",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],global_macro:{status:"PARTIAL",sources:[{source:"US Treasury",status:"AVAILABLE",items:[{series:"US10Y",label:"US 10-year par yield",unit:"PERCENT",status:"AVAILABLE",as_of:"2026-11-24",value:4.2,changes:[{observations:1,start_date:"2026-11-23",end_date:"2026-11-24",value:5,unit:"BASIS_POINTS"}]}]},{source:"US EIA",status:"DISABLED_OR_NOT_AUTHORIZED",items:[]}],notice:"Dated observations, not live."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Global oil and interest-rate context"})).toBeTruthy();
 expect(screen.getByText("4.20%")).toBeTruthy();
 expect(screen.getByText("+5.00 bp / — / —")).toBeTruthy();
 expect(screen.getByText("US EIA")).toBeTruthy();
});

it("shows independent international observations and unavailable instruments",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],global_markets:{status:"PARTIAL",items:[{series:"SP500",label:"S&P 500",source:"S&P DJI via FRED",unit:"INDEX_POINTS",status:"AVAILABLE",as_of:"2026-11-23",value:6000,changes:[{observations:1,start_date:"2026-11-20",end_date:"2026-11-23",percent:1.5}]},{series:"GOLD",label:"Gold spot / USD",source:"Twelve Data",unit:"USD_PROVIDER_QUOTE",status:"DISABLED_OR_NOT_AUTHORIZED",changes:[]}],notice:"Prior-date observations only."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"International indices and metals"})).toBeTruthy();
 expect(screen.getByText("6,000 points")).toBeTruthy();
 expect(screen.getByText("+1.50% / — / —")).toBeTruthy();
 expect(screen.getByText("disabled or not authorized")).toBeTruthy();
});

it("shows integrated global evidence coverage without a composite market prediction",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],global_context:{status:"PARTIAL",available_count:1,total_count:17,groups:[{group:"CURRENCIES",available_count:1,total_count:6,items:[{key:"USD_INR",label:"USD/INR",source:"ECB derived cross-rate",as_of:"2026-11-24",change:{start_date:"2026-11-17",end_date:"2026-11-24",value:1.2,unit:"PERCENT"}}]}],notice:"Not synchronized or a forecast."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Integrated global research"})).toBeTruthy();
 expect(screen.getByText("1/17 dated indicators")).toBeTruthy();
 expect(screen.getByText("+1.20% over 5 observed dates")).toBeTruthy();
 expect(screen.getByText("Not synchronized or a forecast.")).toBeTruthy();
});

it("shows official economic announcements with source and publication date",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],global_releases:{status:"PARTIAL",sources:[{source:"FED",label:"Federal Reserve monetary policy",status:"CURRENT_FEED"}],events:[{id:"one",headline:"Example monetary policy statement",source_name:"Federal Reserve",source_url:"https://www.federalreserve.gov/newsevents/pressreleases/example.htm",published_at:"2026-11-24T12:00:00Z",topics:["MONETARY_POLICY"],geography:"US"}],notice:"Published feed headline, not a forecast."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Official global economic announcements"})).toBeTruthy();
 expect(screen.getByRole("link",{name:"Example monetary policy statement"}).getAttribute("href")).toContain("federalreserve.gov");
 expect(screen.getByText("monetary policy")).toBeTruthy();
 expect(screen.getByText("Published feed headline, not a forecast.")).toBeTruthy();
});

it("keeps scheduled macro events separate from published announcements",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],economic_calendar:{status:"CURRENT_SCHEDULE",source_url:"https://www.bls.gov/help/hlpiCAL.htm",events:[{id:"one",headline:"Consumer Price Index",topic:"INFLATION",scheduled_at:"2026-11-26T13:30:00+00:00",status:"SCHEDULED",review_window:true},{id:"two",headline:"Employment Situation",topic:"EMPLOYMENT",scheduled_at:"2026-11-25T13:30:00+00:00",status:"SCHEDULE_TIME_PASSED_RELEASE_UNVERIFIED",review_window:false}],notice:"Scheduled time does not establish publication."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Upcoming economic release calendar"})).toBeTruthy();
 expect(screen.getByText("Consumer Price Index")).toBeTruthy();
 expect(screen.getByText(/Upcoming within 24 hours/)).toBeTruthy();
 expect(screen.getByText(/schedule time passed release unverified/)).toBeTruthy();
 expect(screen.getByText("Scheduled time does not establish publication.")).toBeTruthy();
});

it("shows matched release evidence without claiming numeric results",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],economic_calendar:{status:"CURRENT_SCHEDULE",source_url:"https://www.bls.gov/help/hlpiCAL.htm",events:[{id:"one",headline:"Consumer Price Index",topic:"INFLATION",scheduled_at:"2026-11-25T13:30:00+00:00",status:"SCHEDULE_TIME_PASSED_RELEASE_UNVERIFIED",review_window:false,release_match:{status:"MATCHED_OFFICIAL_RELEASE_HEADLINE",headline:"Published CPI announcement",source_url:"https://www.bls.gov/news.release/archives/cpi_11252026.htm",published_at:"2026-11-25T13:30:00+00:00",notice:"Review the actual release; numerical surprise unverified."}}],notice:"Scheduled time does not establish publication."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("link",{name:"Published CPI announcement"})).toBeTruthy();
 expect(screen.getByText("matched official release headline")).toBeTruthy();
 expect(screen.getByText("Review the actual release; numerical surprise unverified.")).toBeTruthy();
});

it("shows observed benchmark regime with bounded sample breadth",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],market_regime:{status:"OBSERVED_BENCHMARK_REGIME",trend:"RISING",as_of:"2026-11-24",benchmark_change_60_percent:8,volatility_20_annualized_percent:12,volatility_regime:"BELOW_HIGH_THRESHOLD",breadth:{status:"MATCHED_SAMPLE_ONLY",advancing:20,declining:30,unchanged:0,matched_count:50,selected_count:60},agreement:"OPPOSING_DAILY_BREADTH_REVIEW",notice:"Not a forecast or validated strategy."}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Observed market regime"})).toBeTruthy();
 expect(screen.getByText(/Nifty 50 · rising/)).toBeTruthy();
 expect(screen.getByText(/20 advancing · 30 declining/)).toBeTruthy();
 expect(screen.getByText(/opposing daily breadth review/)).toBeTruthy();
});


it("links canonical briefing watches and company evidence review to existing workspaces",async()=>{
 const horizon=vi.fn(),portfolio=vi.fn();
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[],daily_briefing:{
 status:"PARTIAL",ready_sections:1,total_sections:12,market:{eligible_histories:5,sampled_instruments:10,outlook_status:"MARKET_REGIME_NOT_VALIDATED"},
 horizons:{SWING:{displayed_watch_count:1,ai_reviewed_count:1,conflicting_evidence_count:1,qualified_count:null}},
 funds:{growth_pick_count:null,historical_watch_count:0,ready_categories:0,total_categories:10},institutional:{status:"UNAVAILABLE"},leading_evidence_gaps:[],news_headline_count:2,notice:"Not a forecast",
 decision_context:{horizons:{SWING:{selected_watches:[{isin:"INE009A01021",id:1,exchange:"NSE",symbol:"TEST",as_of:"2026-11-23",unresolved_requirement_count:2}],qualified_count:0}},review_company_count:1,review_companies:[{isin:"INE009A01021",symbol:"TEST",horizons:["SWING"],findings:["REPLAY_REVIEW"],observations:[{exchange:"NSE",as_of:"2026-11-23"}]}],regime:{status:"OBSERVED_BENCHMARK_REGIME",trend:"RISING",as_of:"2026-11-23"},global_coverage:{available_count:3,total_count:8},notice:"Review only."}}})})));
 render(<AutonomousOverview onPortfolio={portfolio} onFunds={()=>{}} onSettings={()=>{}} onHorizon={horizon}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Today's evidence review"})).toBeTruthy();
 expect(screen.getByText(/0 qualified in the reviewed sample/)).toBeTruthy();
 expect(screen.getByText(/3\/8 dated global indicators/)).toBeTruthy();
 fireEvent.click(screen.getByText(/TEST · 1 findings/));
 expect(screen.getByText("replay review")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Review swing research"}));
 expect(horizon).toHaveBeenCalledWith("SWING");
 fireEvent.click(screen.getByRole("button",{name:"Open private portfolio review"}));
 expect(portfolio).toHaveBeenCalledTimes(1);
 expect(fetch).toHaveBeenCalledTimes(1);
});


it("keeps the briefing first and evidence in expandable sections without duplicate navigation or requests",async()=>{
 const navigate=vi.fn();
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[{section:"NSE",status:"READY",generated_at:null,result:{momentum_leaders:[{id:1,symbol:"MOMENTUM",exchange:"NSE",as_of:"2026-11-23",momentum_20d_percent:3}]}}],global_fx:{status:"REFERENCE_RATES_AVAILABLE",items:[],notice:"Reference only."},daily_briefing:{
 status:"PARTIAL",ready_sections:1,total_sections:12,market:{eligible_histories:1,sampled_instruments:2,outlook_status:"MARKET_REGIME_NOT_VALIDATED"},horizons:{},funds:{growth_pick_count:null,historical_watch_count:0,ready_categories:0,total_categories:10},institutional:{status:"UNAVAILABLE"},leading_evidence_gaps:[],notice:"Not a forecast",
 decision_context:{horizons:{SWING:{selected_watches:[{isin:"INE009A01021",id:1,exchange:"NSE",symbol:"TEST",as_of:"2026-11-23",unresolved_requirement_count:2}],qualified_count:0}},review_company_count:0,review_companies:[],regime:{status:"UNAVAILABLE"},global_coverage:null,notice:"Review only."}}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}} onHorizon={navigate}>{null}</AutonomousOverview>);
 expect(await screen.findByRole("region",{name:"Daily research briefing"})).toBeTruthy();
 const observations=screen.getByText("Market and fund observation details").closest("details")!;
 const global=screen.getByText("Detailed market regime and global evidence").closest("details")!;
 const selected=screen.getByText("View 1 selected observations").closest("details")!;
 expect(observations.open).toBe(false);
 expect(global.open).toBe(false);
 expect(selected.open).toBe(false);
 expect(screen.queryByLabelText("Automatic equity research shortcuts")).toBeNull();
 fireEvent.click(screen.getByText("Detailed market regime and global evidence"));
 expect(global.open).toBe(true);
 expect(screen.getByRole("region",{name:"Global currency context"})).toBeTruthy();
 fireEvent.click(screen.getByText("View 1 selected observations"));
 expect(selected.open).toBe(true);
 expect(screen.getByText(/TEST · NSE/)).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Open TEST NSE research report"}));
 expect(navigate).toHaveBeenCalledWith("SWING",{exchange:"NSE",id:1,isin:"INE009A01021",as_of:"2026-11-23"});
 fireEvent.click(screen.getByRole("button",{name:"Review swing research"}));
 expect(navigate).toHaveBeenCalledWith("SWING");
 expect(fetch).toHaveBeenCalledTimes(1);
});

it("consolidates empty research and hides unavailable global panels without inventing results",async()=>{
 const fund=(section:string)=>({section,status:"READY",generated_at:null,result:{growth_outlook:[],historical_coverage:{items:[{scheme_code:section.length,scheme_name:section+" fund",cagr_3y_percent:9,nav_date:"2026-11-26"}]}}});
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,sections:[{section:"NSE",status:"READY",generated_at:null,result:{eligible_count:0,universe_size:126,skipped:{NO_HISTORY:126}}},fund("LARGE_CAP"),fund("MID_CAP"),fund("SMALL_CAP")],daily_briefing:{status:"PARTIAL",ready_sections:4,total_sections:4,market:{eligible_histories:0,sampled_instruments:126,outlook_status:"UNAVAILABLE"},horizons:{},funds:{growth_pick_count:0,historical_watch_count:3,ready_categories:3,total_categories:3},institutional:{status:"UNAVAILABLE"},leading_evidence_gaps:[],notice:"Research only"},global_context:{status:"UNAVAILABLE",available_count:0,total_count:17,groups:[],notice:"No data"},global_markets:{status:"UNAVAILABLE",items:[],notice:"No data"}})})));
 render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}>{null}</AutonomousOverview>);
 expect(await screen.findByText("Equity research is not ready")).toBeTruthy();
 expect(screen.queryByLabelText("Research coverage summary")).toBeNull();
 expect(screen.queryByRole("region",{name:"International indices and metals"})).toBeNull();
 expect(screen.getByText("View full fund list (3 categories with observations)")).toBeTruthy();
 expect(screen.queryByText("MID_CAP fund")).toBeNull();
 const diagnostics=screen.getByText("Research coverage & missing data").closest("details")!;
 diagnostics.open=true;fireEvent(diagnostics,new Event("toggle"));
 expect(await screen.findByText("Insufficient daily history")).toBeTruthy();
});
