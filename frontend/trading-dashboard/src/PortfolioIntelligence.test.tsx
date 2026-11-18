/** @vitest-environment jsdom */
import {render,screen} from "@testing-library/react";
import {describe,expect,it} from "vitest";
import PortfolioIntelligence from "./PortfolioIntelligence";

describe("PortfolioIntelligence",()=>{
 it("shows allocation, return and contextual concentration guidance",()=>{
  const holdings=[
   {id:1,symbol:"RELIANCE",asset_type:"EQUITY",quantity:10,average_cost:100,last_price:120,invested:1000,market_value:1200,unrealized_pnl:200,price_as_of:"2026-11-18T10:30:00Z"},
   {id:2,symbol:"ADANIPORTS",asset_type:"EQUITY",quantity:10,average_cost:100,last_price:80,invested:1000,market_value:800,unrealized_pnl:-200,price_as_of:"2026-11-18T10:30:00Z"},
  ];
  const analysis={holdingCount:2,invested:2000,pricedMarketValue:2000,pricedCostBasis:2000,pricedUnrealizedPnl:0,unpricedHoldings:0,valuationComplete:true,riskFlags:["RELIANCE exceeds 25% of currently valued holdings."]};
  render(<PortfolioIntelligence holdings={holdings} analysis={analysis}/>);
  expect(screen.getByText("Portfolio snapshot")).toBeTruthy();
  expect(screen.getByText("2/2")).toBeTruthy();
  expect(screen.getByText("60.0% of priced value")).toBeTruthy();
  expect(screen.getByText("Check whether this position size matches your own risk limit.")).toBeTruthy();
 });
});
