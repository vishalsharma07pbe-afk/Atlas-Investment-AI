// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundSnapshotReview from "./MutualFundSnapshotReview";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const holding={id:7,symbol:"FUND-A",asset_type:"MUTUAL_FUND",quantity:2,average_cost:10,last_price:null,invested:20,market_value:null,unrealized_pnl:null,price_as_of:null};
describe("Integrated snapshot portfolio review",()=>{
 it("sends explicit scheme mapping and displays read-only blockers",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({status:"BLOCKED",blockers:["STALE_NAV_DATES"],snapshot:{schemes:[{scheme_code:"12345",scheme_name:"Fund A",nav:12.5,as_of:"2025-01-01"}],missing_scheme_codes:[]},reconciliation:{portfolio_estimated_value:null,rows:[{holding_id:7,scheme_code:"12345",status:"STALE_NAV",estimated_value:"25.0"}]},notice:"Research only"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundSnapshotReview holdings={[holding]}/>);
  fireEvent.change(screen.getByLabelText("Source name"),{target:{value:"Local NAV export"}});
  fireEvent.change(screen.getByLabelText("Holding ID to scheme code JSON"),{target:{value:'{"7":"12345"}'}});
  fireEvent.change(screen.getByLabelText("AMFI-style NAV snapshot"),{target:{value:"12345;A;B;Fund A;12.5;01-Jan-2025"}});
  fireEvent.click(screen.getByRole("button",{name:"Review portfolio snapshot"}));
  await waitFor(()=>expect(screen.getByText(/STALE_NAV_DATES/)).toBeTruthy());
  const payload=JSON.parse(fetchMock.mock.calls[0][1].body);
  expect(payload.positions).toEqual([{holding_id:7,scheme_code:"12345",units:2,invested:20,recorded_value:null}]);
  expect(payload.source_authorized).toBe(false);
  expect(holding.last_price).toBeNull();
 });
 it("blocks unmapped holding before API request",async()=>{
  const fetchMock=vi.fn();vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundSnapshotReview holdings={[holding]}/>);
  fireEvent.change(screen.getByLabelText("Source name"),{target:{value:"Local export"}});
  fireEvent.change(screen.getByLabelText("AMFI-style NAV snapshot"),{target:{value:"snapshot"}});
  fireEvent.click(screen.getByRole("button",{name:"Review portfolio snapshot"}));
  await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("Map every holding ID"));
  expect(fetchMock).not.toHaveBeenCalled();
 });
});
