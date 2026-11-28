// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import NavCatalog from "./NavCatalog";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

const fund={scheme_code:"INF846K016M6",scheme_name:"Axis Long Duration Fund Direct Growth",nav:"12.3456",nav_date:"2026-11-17",nav_date_status:"PROVIDER_NOT_SUPPLIED",as_of:"2026-11-17T06:30:00+00:00",freshness_status:"CATALOG_RECENT_NAV_DATE_UNVERIFIED",stale:false,source:"UPSTOX_MF_INSTRUMENTS"};

describe("Automatic mutual-fund catalog",()=>{
  it("opens transparent fund details and blocks unsupported recommendations",async()=>{
    vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>{
      const url=String(input);
      if(url.includes("/status"))return {ok:true,json:async()=>({scheme_count:1,latest_nav_date:null,automatic_collection_enabled:true})};
      if(url.includes("/details/"))return {ok:true,json:async()=>({
        identifier:fund.scheme_code,scheme_name:fund.scheme_name,source:fund.source,scheme_type:"DEBT",plan:"DIRECT",dividend_type:null,
        nav:{value:fund.nav,declared_date:null,date_status:"PROVIDER_NOT_SUPPLIED",catalog_observed_at:fund.as_of,catalog_freshness:"RECENT"},
        trading_terms:{purchase_allowed:true,redemption_allowed:true,minimum_purchase_amount:500,additional_purchase_amount:500,settlement_type:"T1"},
        performance:{observation_count:1,trailing_returns_percent:{"1m":null,"3m":null,"6m":null,"1y":null,"3y":null,"5y":null},status:"COLLECTING_DATED_HISTORY"},
        portfolio:{top_holdings:null,market_cap_allocation:null,sector_allocation:null,status:"NOT_PROVIDED_BY_CONNECTED_SOURCE"},costs:{expense_ratio:null,exit_load:null,status:"NOT_PROVIDED_BY_CONNECTED_SOURCE"},rating:{value:null,agency:null,status:"NO_LICENSED_RATING_SOURCE"},
        research_factors:[{factor:"Returns",status:"WAITING_FOR_HISTORY",value:null}],recommendation:{status:"BLOCKED_INSUFFICIENT_VERIFIED_FACTORS",label:"No recommendation available",reason:"Verified factors are incomplete."},notice:"Research only"
      })};
      return {ok:true,json:async()=>({items:[fund]})};
    }));
    render(<NavCatalog/>);
    const link=await screen.findByRole("button",{name:/Axis Long Duration Fund/});
    expect(screen.getByText(/Catalog checked recently/)).toBeTruthy();
    fireEvent.click(link);
    await waitFor(()=>expect(screen.getByRole("heading",{name:fund.scheme_name})).toBeTruthy());
    expect(screen.getByText("No recommendation available")).toBeTruthy();
    expect(screen.getByText("Portfolio and market-cap mix")).toBeTruthy();
    expect(screen.getByText("No licensed rating or cost feed")).toBeTruthy();
  });
});

it("offers a holding shortcut only for exact numeric AMFI records",async()=>{
  const record=vi.fn();
  vi.stubGlobal("fetch",vi.fn(async(input:RequestInfo|URL)=>String(input).includes("/status")?{ok:true,json:async()=>({scheme_count:2,automatic_collection_enabled:false})}:{ok:true,json:async()=>({items:[fund,{...fund,scheme_code:"123456",scheme_name:"Exact AMFI Fund",source:"AMFI_MANUAL_DOWNLOAD",nav_date_status:"DECLARED"}]})}));
  render(<NavCatalog onRecordHolding={record}/>);
  const button=await screen.findByRole("button",{name:"Record holding"});
  fireEvent.click(button);
  expect(record).toHaveBeenCalledWith("123456");
  expect(screen.getAllByRole("button",{name:"Record holding"})).toHaveLength(1);
});
