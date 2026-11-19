/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import P2ResearchWorkspace from "./P2ResearchWorkspace";

afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals();});

it("presents the four P2 workflows and renders explicit planning scenarios",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({risk_profile:"BALANCED",risk_score:9,capacity_flags:[],inflation_adjusted_target:"3517751.00",scenarios:[{name:"STRESS",gross_return_assumption_percent:"4.00",projected_value:"1800000",shortfall:"1717751",required_monthly_contribution:"29000",target_met:false},{name:"BASE_ASSUMPTION",gross_return_assumption_percent:"8.00",projected_value:"2600000",shortfall:"917751",required_monthly_contribution:"22000",target_met:false},{name:"FAVOURABLE",gross_return_assumption_percent:"12.00",projected_value:"3700000",shortfall:"0",required_monthly_contribution:"14500",target_met:true}],next_steps:["Review annually."],notice:"Assumptions only."})})));
 render(<P2ResearchWorkspace/>);
 expect(screen.getByRole("tab",{name:"Ask ATLAS"})).toBeTruthy();
 expect(screen.getByRole("tab",{name:"Test a signal"})).toBeTruthy();
 expect(screen.getByRole("tab",{name:"Find matches"})).toBeTruthy();
 fireEvent.click(screen.getByRole("tab",{name:"Plan a goal"}));
 fireEvent.click(screen.getByRole("button",{name:"Build my scenarios"}));
 await waitFor(()=>expect(screen.getByText("balanced")).toBeTruthy());
 expect(screen.getByText("stress")).toBeTruthy();
 expect(screen.getByText("base assumption")).toBeTruthy();
 expect(screen.getByText("favourable")).toBeTruthy();
});

it("saves screener definitions only on the local device",()=>{
 vi.stubGlobal("prompt",vi.fn(()=>"Quality momentum"));
 render(<P2ResearchWorkspace/>);
 fireEvent.click(screen.getByRole("tab",{name:"Find matches"}));
 fireEvent.click(screen.getByRole("button",{name:"Save screen"}));
 expect(screen.getByRole("button",{name:"Quality momentum"})).toBeTruthy();
 expect(JSON.parse(localStorage.getItem("atlas:p2-saved-screeners")||"[]")).toHaveLength(1);
});

it("searches mutual funds and sends a dated, gap-aware evidence pack",async()=>{
 const fetchMock=vi.fn(async(input:RequestInfo|URL,_init?:RequestInit)=>{
  const url=String(input);
  if(url.includes("/mutual-funds/search"))return {ok:true,json:async()=>({items:[{scheme_code:"123",scheme_name:"Example Flexi Cap Fund",nav:"42.5",nav_date:"2026-11-18",source:"AMFI_MANUAL",nav_date_status:"DECLARED",as_of:"2026-11-18",freshness_status:"RECENT_NAV"}]})};
  if(url.includes("/mutual-funds/details/123"))return {ok:true,json:async()=>({identifier:"123",scheme_name:"Example Flexi Cap Fund",source:"AMFI_MANUAL",nav:{value:"42.5",declared_date:"2026-11-18",date_status:"DECLARED",catalog_observed_at:"2026-11-18T12:00:00Z",catalog_freshness:"RECENT"},performance:{observation_count:30,trailing_returns_percent:{"1m":"2.1","1y":null},status:"AVAILABLE"},portfolio:{status:"NOT_PROVIDED_BY_CONNECTED_SOURCE"},costs:{status:"NOT_PROVIDED_BY_CONNECTED_SOURCE"},rating:{status:"NO_LICENSED_RATING_SOURCE"},research_factors:[]})};
  return {ok:true,json:async()=>({status:"EVIDENCE_ONLY",provider:null,answer:"Dated NAV evidence is available.",findings:[{statement:"Latest NAV is dated.",evidence_ids:["NAV"]}],uncertainties:["Costs are missing."],sources:[{id:"NAV",source_name:"AMFI_MANUAL",observed_at:"2026-11-18T00:00:00Z",quality:"VERIFIED"}],coverage:{verified_domains:["RETURNS"],missing_expected_domains:["COSTS"]},notice:"Research only."})};
 });
 vi.stubGlobal("fetch",fetchMock);
 render(<P2ResearchWorkspace/>);
 fireEvent.click(screen.getByRole("button",{name:"Mutual fund"}));
 fireEvent.change(screen.getByLabelText("P2 instrument search"),{target:{value:"Example"}});
 await waitFor(()=>expect(screen.getByRole("button",{name:/Example Flexi Cap Fund/})).toBeTruthy());
 fireEvent.click(screen.getByRole("button",{name:/Example Flexi Cap Fund/}));
 fireEvent.click(screen.getByRole("button",{name:"Answer from evidence"}));
 await waitFor(()=>expect(screen.getByText("Dated NAV evidence is available.")).toBeTruthy());
 const request=fetchMock.mock.calls.find(([url])=>String(url).includes("/p2/research/answer"));
 expect(JSON.parse((request?.[1] as RequestInit).body as string).asset_type).toBe("MUTUAL_FUND");
});
