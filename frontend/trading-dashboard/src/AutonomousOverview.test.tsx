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
