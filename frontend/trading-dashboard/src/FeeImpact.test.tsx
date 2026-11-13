// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import FeeImpact from "./FeeImpact";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("requests fee calculation on demand and displays fee drag",async()=>{
  const mock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    without_fees:"1200",after_fees:"1100",fee_drag:"100",total_charges:"80",
    expense_ratio_charges:"60",contribution_charges:"10",flat_charges:"10",
    checkpoints:[{month:12,without_fees:"1200",after_fees:"1100",fee_drag:"100"}],
    notice:"Illustrative"})});
  vi.stubGlobal("fetch",mock);
  render(<FeeImpact/>);
  expect(mock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Calculate fee impact"}));
  await waitFor(()=>expect(screen.getByLabelText("Fee impact results")).toBeTruthy());
  expect(mock).toHaveBeenCalledTimes(1);
});
it("native form validation rejects out-of-range expense ratio",()=>{
  const mock=vi.fn();vi.stubGlobal("fetch",mock);
  render(<FeeImpact/>);
  const field=screen.getByLabelText("Annual expense ratio (%)") as HTMLInputElement;
  fireEvent.change(field,{target:{value:"7"}});
  expect(field.checkValidity()).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:"Calculate fee impact"}));
  expect(mock).not.toHaveBeenCalled();
});
