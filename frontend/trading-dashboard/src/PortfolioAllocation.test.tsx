// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import PortfolioAllocation from "./PortfolioAllocation";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("only requests a plan when submitted and shows partial coverage",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"PARTIAL_PRICE_COVERAGE",recorded_value:"100.00",contribution:"10000.00",
    unallocated_contribution:"0.00",unpriced_holdings:[{symbol:"UNKNOWN"}],
    allocations:[{asset_type:"EQUITY",current_weight_percent:"100.00",target_weight_percent:"70.00",
      hypothetical_contribution:"7000.00",remaining_target_gap:"0.00"}],
    notice:"Hypothetical only"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<PortfolioAllocation revision={0}/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Calculate hypothetical allocation"}));
  await waitFor(()=>expect(screen.getByLabelText("Allocation results")).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Partial coverage/)).toBeTruthy();
});
it("blocks targets that do not total 100",()=>{
  const fetchMock=vi.fn();vi.stubGlobal("fetch",fetchMock);
  render(<PortfolioAllocation revision={0}/>);
  fireEvent.change(screen.getByLabelText("Target percent 1"),{target:{value:"60"}});
  fireEvent.click(screen.getByRole("button",{name:"Calculate hypothetical allocation"}));
  expect(screen.getByRole("alert").textContent).toContain("100%");
  expect(fetchMock).not.toHaveBeenCalled();
});
