// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import PortfolioConcentration from "./PortfolioConcentration";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("only requests analysis on demand and displays breaches",async()=>{
  const mock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"PARTIAL_PRICE_COVERAGE",recorded_value:"100.00",
    holdings:[{id:1,symbol:"AAA",asset_type:"EQUITY",recorded_value:"100.00",weight_percent:"100.00"}],
    exposures:[],top_three_percent:"100.00",
    breaches:[{type:"SINGLE_HOLDING",label:"AAA",actual_percent:"100.00",limit_percent:"25.00"}],
    unpriced_holdings:[{id:2,symbol:"BBB"}],notice:"Recorded prices only"})});
  vi.stubGlobal("fetch",mock);
  render(<PortfolioConcentration revision={1}/>);
  expect(mock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Check concentration"}));
  await waitFor(()=>expect(screen.getByLabelText("Concentration results")).toBeTruthy());
  expect(screen.getByText(/Missing recorded prices/)).toBeTruthy();
  expect(mock).toHaveBeenCalledTimes(1);
});
it("invalid threshold is blocked by native validation",()=>{
  const mock=vi.fn();vi.stubGlobal("fetch",mock);
  render(<PortfolioConcentration revision={1}/>);
  const input=screen.getByLabelText("Max individual holding (%)") as HTMLInputElement;
  fireEvent.change(input,{target:{value:"101"}});
  expect(input.checkValidity()).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:"Check concentration"}));
  expect(mock).not.toHaveBeenCalled();
});
