// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import GoalPlanner from "./GoalPlanner";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("calculates only on demand and renders projection",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"TARGET_SHORTFALL",target_amount:"1000000.00",projected_value:"500000.00",
    contributed_principal:"360000.00",hypothetical_growth:"140000.00",
    shortfall:"500000.00",required_monthly_contribution:"25000.00",
    checkpoints:[{month:12,projected_value:"120000.00",total_contributions:"120000.00"}],
    notice:"Illustrative only"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<GoalPlanner/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Calculate goal"}));
  await waitFor(()=>expect(screen.getByLabelText("Goal projection results")).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByText("Target shortfall under assumptions")).toBeTruthy();
});
it("blocks invalid month horizon before request",()=>{
  const fetchMock=vi.fn();vi.stubGlobal("fetch",fetchMock);
  render(<GoalPlanner/>);
  fireEvent.change(screen.getByLabelText("Time horizon in months"),{target:{value:"0"}});
  const horizon=screen.getByLabelText("Time horizon in months") as HTMLInputElement;
  expect(horizon.checkValidity()).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:"Calculate goal"}));
  expect(fetchMock).not.toHaveBeenCalled();
});
