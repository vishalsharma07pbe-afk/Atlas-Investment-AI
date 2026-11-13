// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import ResearchAlerts from "./ResearchAlerts";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("ResearchAlerts",()=>{
  it("does not poll and displays only API-evaluated results",async()=>{
    const mock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
      status:"EVALUATED",failures:[],triggered_count:1,
      alerts:[{metric:"CLOSE_ABOVE",threshold:100,observed:120,triggered:true,as_of:"2026-11-13"}],
      notice:"Historical research only."
    })});
    vi.stubGlobal("fetch",mock);
    render(<ResearchAlerts instrumentId={4}/>);
    expect(mock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Evaluate alert"}));
    await waitFor(()=>expect(screen.getByText("Threshold met")).toBeTruthy());
    expect(mock).toHaveBeenCalledTimes(1);
  });
  it("shows blocked evidence without invented triggers",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:true,json:async()=>({
      status:"BLOCKED",failures:["STALE_OR_FUTURE_DATA"],alerts:[],
      notice:"No alert was triggered."
    })}));
    render(<ResearchAlerts instrumentId={4}/>);
    fireEvent.click(screen.getByRole("button",{name:"Evaluate alert"}));
    await waitFor(()=>expect(screen.getByText(/STALE OR FUTURE DATA/)).toBeTruthy());
    expect(screen.queryByText("Threshold met")).toBeNull();
  });
});
