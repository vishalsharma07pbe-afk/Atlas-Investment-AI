// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,render,screen,waitFor} from "@testing-library/react";
import PortfolioStress from "./PortfolioStress";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

describe("PortfolioStress",()=>{
  it("renders scenarios and warns about missing prices",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:true,json:async()=>({
      status:"PARTIAL_PRICE_COVERAGE",
      price_source:"MANUALLY_RECORDED_NOT_LIVE",
      recorded_value_priced_holdings:"240.00",
      unpriced_holdings:[{id:2,symbol:"UNKNOWN"}],
      scenarios:[{name:"BEAR",assumed_uniform_price_change_percent:"-15.00",
        stressed_value_of_priced_holdings:"204.00",change_from_recorded_value:"-36.00",
        unrealized_pnl_vs_priced_cost:"4.00"}],
      notice:"Illustrative arithmetic, not a forecast."
    })}));
    render(<PortfolioStress revision={1}/>);
    expect(screen.getByText(/Loading scenario analysis/)).toBeTruthy();
    await waitFor(()=>expect(screen.getByText(/BEAR/)).toBeTruthy());
    expect(screen.getByText(/Partial coverage/)).toBeTruthy();
    expect(fetch).toHaveBeenCalledWith(
      "/intelligence/api/v1/intelligence/portfolio/stress-scenarios",
      expect.objectContaining({signal:expect.any(AbortSignal)})
    );
  });

  it("shows an error instead of inventing scenario results",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false}));
    render(<PortfolioStress revision={1}/>);
    await waitFor(()=>expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.queryByText(/BEAR/)).toBeNull();
  });
});
