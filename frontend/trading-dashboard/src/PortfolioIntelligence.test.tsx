/** @vitest-environment jsdom */
import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,describe,expect,it} from "vitest";
import PortfolioIntelligence from "./PortfolioIntelligence";

afterEach(cleanup);

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
 it("withholds return without a positive cost basis and warns about stale valuations",()=>{
  const holdings=[{id:1,symbol:"STALE",asset_type:"EQUITY",quantity:1,average_cost:0,last_price:120,invested:0,market_value:120,unrealized_pnl:120,price_as_of:"2026-11-01T10:30:00Z",valuation_status:"STALE"}];
  const analysis={holdingCount:1,invested:0,pricedMarketValue:120,pricedCostBasis:0,pricedUnrealizedPnl:120,unpricedHoldings:0,valuationComplete:true,recordedReturnPercent:null,recentRecordedHoldings:0,stalePriceHoldings:1,undatedPriceHoldings:0,futureDatedPriceHoldings:0,valuationFreshnessStatus:"INCOMPLETE_OR_AGED",valuationFreshnessNotice:"Recent recorded values are not independently verified live quotes.",riskFlags:[]};
  render(<PortfolioIntelligence holdings={holdings} analysis={analysis}/>);
  expect(screen.getByText("VALUATION GAPS")).toBeTruthy();
  expect(screen.getByText("Unavailable")).toBeTruthy();
  expect(screen.getByText("Valuation age: 0/1 recent recorded")).toBeTruthy();
  expect(screen.getByText(/Return unavailable/)).toBeTruthy();
 });
});
