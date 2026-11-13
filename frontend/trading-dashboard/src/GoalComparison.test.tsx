// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import GoalComparison from "./GoalComparison";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("compares on demand and renders independent results",async()=>{
  const mock=vi.fn().mockResolvedValue({ok:true,json:async()=>({scenarios:[
    {name:"Conservative",projected_value:"1000",contributed_principal:"900",shortfall:"200",required_monthly_contribution:"100"},
    {name:"Base",projected_value:"1200",contributed_principal:"900",shortfall:"0",required_monthly_contribution:"90"}]})});
  vi.stubGlobal("fetch",mock);
  render(<GoalComparison/>);
  expect(mock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Compare scenarios"}));
  await waitFor(()=>expect(screen.getByLabelText("Scenario comparison results")).toBeTruthy());
  expect(mock).toHaveBeenCalledTimes(1);
});
it("rejects duplicate names before fetching",()=>{
  const mock=vi.fn();vi.stubGlobal("fetch",mock);
  render(<GoalComparison/>);
  fireEvent.change(screen.getByLabelText("Scenario name 2"),{target:{value:"Conservative"}});
  fireEvent.click(screen.getByRole("button",{name:"Compare scenarios"}));
  expect(screen.getByRole("alert").textContent).toContain("unique");
  expect(mock).not.toHaveBeenCalled();
});
