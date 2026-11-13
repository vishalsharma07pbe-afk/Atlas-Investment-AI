// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import MutualFundHoldings from "./MutualFundHoldings";

afterEach(cleanup);

const fund={
  id:1,symbol:"TEST-FUND",asset_type:"MUTUAL_FUND",quantity:2,average_cost:100,
  last_price:null,invested:200,market_value:null,unrealized_pnl:null,price_as_of:null
};
const stock={...fund,id:2,symbol:"TEST-STOCK",asset_type:"EQUITY",last_price:110,market_value:220,unrealized_pnl:20};

describe("MutualFundHoldings",()=>{
  it("shows only fund holdings and warns when NAV is missing",()=>{
    render(<MutualFundHoldings holdings={[fund,stock]}/>);
    expect(screen.getByText("TEST-FUND")).toBeTruthy();
    expect(screen.queryByText("TEST-STOCK")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("1 fund position");
    expect(screen.getByText(/Benchmark returns, expense ratios/)).toBeTruthy();
  });
  it("renders empty state without inventing values",()=>{
    render(<MutualFundHoldings holdings={[]}/>);
    expect(screen.getByText(/No mutual fund holdings saved/)).toBeTruthy();
    expect(screen.getByText("FUND POSITIONS")).toBeTruthy();
  });
});
