/** @vitest-environment jsdom */
import {cleanup,render,screen} from "@testing-library/react";
import {afterEach,describe,expect,it} from "vitest";
import PortfolioVisuals,{recordedAllocation} from "./PortfolioVisuals";
afterEach(cleanup);
describe("recorded portfolio charts",()=>{
 it("uses priced holdings only and retains the coverage warning",()=>{
  const holdings=[{asset_type:"EQUITY",market_value:750,invested:600},{asset_type:"MUTUAL_FUND",market_value:250,invested:300},{asset_type:"EQUITY",market_value:null,invested:100}];
  expect(recordedAllocation(holdings)).toMatchObject({total:1000,cost:900,excluded:1,pricedCount:2});
  render(<PortfolioVisuals holdings={holdings}/>);
  expect(screen.getByRole("img",{name:"Asset allocation by recorded value"})).toBeTruthy();
  expect(screen.getByText("75.0%")).toBeTruthy();
  expect(screen.getByText("25.0%")).toBeTruthy();
  expect(screen.getByText(/1 position\(s\) without a usable recorded valuation excluded/)).toBeTruthy();
 });
 it("does not draw an allocation when no valuations exist",()=>{
  render(<PortfolioVisuals holdings={[{asset_type:"EQUITY",market_value:null,invested:100}]}/>);
  expect(screen.getByText("No recorded valuations")).toBeTruthy();
  expect(screen.queryByRole("img")).toBeNull();
 });
 it("does not compute a percentage from a zero recorded value",()=>{
  render(<PortfolioVisuals holdings={[{asset_type:"EQUITY",market_value:0,invested:100}]}/>);
  expect(screen.getByText("Recorded value is zero")).toBeTruthy();
  expect(screen.queryByRole("img")).toBeNull();
 });
});
