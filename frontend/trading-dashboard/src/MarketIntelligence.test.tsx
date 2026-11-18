// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MarketIntelligence from "./MarketIntelligence";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("MarketIntelligence",()=>{
  it("loads only when requested and shows evidence coverage",async()=>{
    const mock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
      status:"RESEARCH_ONLY",universe_size:2,eligible_count:0,
      skipped:{STALE_OR_FUTURE:2},breadth:{advancing:0,declining:0,unchanged:0},
      top_gainers:[],top_losers:[],momentum_leaders:[],volume_leaders:[],anomaly_watch:[],
      notice:"Not a whole-market ranking."
    })});
    vi.stubGlobal("fetch",mock);
    render(<MarketIntelligence/>);
    expect(mock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Analyze daily market"}));
    await waitFor(()=>expect(screen.getByText(/Eligible: 0\/2/)).toBeTruthy());
    expect(mock).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Not a whole-market ranking/)).toBeTruthy();
  });
  it("does not invent results on provider failure",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockRejectedValue(Error("offline")));
    render(<MarketIntelligence/>);
    fireEvent.click(screen.getByRole("button",{name:"Analyze daily market"}));
    await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("offline"));
    expect(screen.queryByText("Top gainers in sample")).toBeNull();
  });
});
