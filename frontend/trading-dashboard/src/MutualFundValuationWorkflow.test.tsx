// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundHoldings from "./MutualFundHoldings";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const holding={id:7,symbol:"FUND-TEST",asset_type:"MUTUAL_FUND",quantity:2,average_cost:100,last_price:null,invested:200,market_value:null,unrealized_pnl:null,price_as_of:null};

describe("Validated NAV to portfolio reconciliation",()=>{
 it("requires explicit holding mapping and reuses imported NAV without changing holdings",async()=>{
  const fetchMock=vi.fn()
   .mockResolvedValueOnce({ok:true,json:async()=>({scheme_name:"Fund A",latest_nav:{as_of:"2025-01-02",nav:11,status:"HISTORICAL"},trailing_returns_pct:{},import:{rows_accepted:2,stored:false},source:{verification:"USER_SUPPLIED_UNVERIFIED"}})})
   .mockResolvedValueOnce({ok:true,json:async()=>({rows:[{holding_id:7,scheme_code:"12345",status:"STALE_NAV",estimated_value:"22",difference_from_recorded:null}],diagnostics:[],missing_nav_positions:0,stale_nav_positions:1,portfolio_estimated_value:null,verification:"USER_SUPPLIED_UNVERIFIED",notice:"Read only"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundHoldings holdings={[holding]}/>);
  fireEvent.change(screen.getByLabelText("Scheme code"),{target:{value:"12345"}});
  fireEvent.change(screen.getByLabelText("Scheme name"),{target:{value:"Fund A"}});
  fireEvent.change(screen.getByLabelText("Source attribution"),{target:{value:"Local CSV"}});
  fireEvent.change(screen.getByLabelText("Historical NAV CSV"),{target:{value:"scheme_code,as_of,nav\n12345,2025-01-01,10\n12345,2025-01-02,11"}});
  fireEvent.click(screen.getByRole("button",{name:"Import and analyze history"}));
  await waitFor(()=>expect(screen.getByText(/Validated NAV histories available: 1/)).toBeTruthy());
  fireEvent.change(screen.getByLabelText("Holding ID to scheme code JSON"),{target:{value:'{"7":"12345"}'}});
  fireEvent.click(screen.getByRole("button",{name:"Reconcile with validated imports"}));
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2));
  const [url,options]=fetchMock.mock.calls[1];
  expect(url).toContain("/reconcile");
  expect(JSON.parse(options.body)).toEqual({positions:[{holding_id:7,scheme_code:"12345",units:2,invested:200,recorded_value:null}],
   navs:[{scheme_code:"12345",nav:"11",as_of:"2025-01-02",source_name:"Local CSV"}]});
  expect(screen.getByText("FUND-TEST")).toBeTruthy();
  expect(holding.market_value).toBeNull();
 });
 it("rejects missing holding scheme mapping before network request",async()=>{
  const fetchMock=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({scheme_name:"Fund A",latest_nav:{as_of:"2025-01-02",nav:11,status:"HISTORICAL"},trailing_returns_pct:{},import:{rows_accepted:2,stored:false},source:{verification:"USER_SUPPLIED_UNVERIFIED"}})});
  vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundHoldings holdings={[holding]}/>);
  fireEvent.change(screen.getByLabelText("Scheme code"),{target:{value:"12345"}});
  fireEvent.change(screen.getByLabelText("Scheme name"),{target:{value:"Fund A"}});
  fireEvent.change(screen.getByLabelText("Source attribution"),{target:{value:"Local CSV"}});
  fireEvent.change(screen.getByLabelText("Historical NAV CSV"),{target:{value:"scheme_code,as_of,nav\n12345,2025-01-01,10\n12345,2025-01-02,11"}});
  fireEvent.click(screen.getByRole("button",{name:"Import and analyze history"}));
  await waitFor(()=>expect(screen.getByText(/Validated NAV histories available: 1/)).toBeTruthy());
  fireEvent.click(screen.getByRole("button",{name:"Reconcile with validated imports"}));
  await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("Map each holding ID"));
  expect(fetchMock).toHaveBeenCalledTimes(1);
 });
});
