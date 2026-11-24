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
