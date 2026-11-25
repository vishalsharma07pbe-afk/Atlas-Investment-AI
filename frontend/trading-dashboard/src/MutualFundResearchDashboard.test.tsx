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
 const item={scheme_code:"118955",scheme_name:"Composition Test Fund",portfolio_date:"2026-10-31",reported_weight_total_percent:100,asset_allocation_percent:{Equity:60,Cash:40},exact_listed_equity_weight_percent:60,top_10_exact_equity_weight_percent:60,exact_equity_count:1,cached_company_evidence_weight_percent:20,cached_company_count:1,top_holdings:[{isin:"INE002A01018",name:"Example Equity",weight_percent:60}],notice:"Secondary composition only."};
 const result={...response,portfolio_evidence:{status:"SECONDARY_COMPOSITION_ONLY",notice:"Not a forward forecast.",items:[item]}};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.includes("historical-watch")?{category:"LARGE_CAP",items:[],universe_count:120,sample_count:20,eligible_count:0,automatic_collection_enabled:true,notice:"Historical only"}:result})));
 render(<MutualFundResearchDashboard onExplore={()=>{}}/>);
 fireEvent.click(await screen.findByText("Reported fund portfolios (1)"));
 expect(screen.getByText("Composition Test Fund")).toBeTruthy();
 expect(screen.getByText("Example Equity · 60.00%")).toBeTruthy();
 expect(screen.getByText("20.00% · 1 companies")).toBeTruthy();
 expect(screen.getAllByText("No fund currently qualifies")).toHaveLength(2);
});
