// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import DailyScreener from "./DailyScreener";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("DailyScreener",()=>{
  it("only fetches on demand and identifies sample limitations",async()=>{
    const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
      universe_size:0,eligible_count:0,skipped:{NO_HISTORY:0,STALE:0},
      top_gainers:[],top_losers:[],momentum_leaders:[],
      notice:"Not a full-market ranking."
    })});
    vi.stubGlobal("fetch",fetchMock);
    render(<DailyScreener/>);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Run daily screener"}));
    await waitFor(()=>expect(screen.getByText(/Eligible: 0 of 0/)).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toContain("max_age_days=7");
    expect(screen.getByText(/Not a full-market ranking/)).toBeTruthy();
  });
  it("does not display fabricated rows on API error",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false}));
    render(<DailyScreener/>);
    fireEvent.click(screen.getByRole("button",{name:"Run daily screener"}));
    await waitFor(()=>expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.queryByText(/Top daily gainers in sample/)).toBeNull();
  });
});
