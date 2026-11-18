// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import RiskQualification from "./RiskQualification";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("RiskQualification",()=>{
  it("runs only when requested and shows blocked evidence",async()=>{
    const mock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
      status:"BLOCKED",failures:["STALE_OR_FUTURE_DATA"],observations:{},
      notice:"Failed evidence gates."
    })});
    vi.stubGlobal("fetch",mock);
    render(<RiskQualification instrumentId={17}/>);
    expect(mock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Run risk checks"}));
    await waitFor(()=>expect(screen.getByText(/STALE OR FUTURE DATA/)).toBeTruthy());
    expect(mock.mock.calls[0][0]).toContain("/risk-qualification/17");
  });
  it("does not invent risk results when API fails",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false}));
    render(<RiskQualification instrumentId={17}/>);
    fireEvent.click(screen.getByRole("button",{name:"Run risk checks"}));
    await waitFor(()=>expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.queryByText(/OBSERVATIONS READY/)).toBeNull();
  });
});
