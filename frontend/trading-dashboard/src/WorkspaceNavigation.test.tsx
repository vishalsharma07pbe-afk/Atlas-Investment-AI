/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import WorkspaceNavigation,{validPage} from "./WorkspaceNavigation";
import AdvancedSection from "./AdvancedSection";
import PortfolioSummary from "./PortfolioSummary";

afterEach(cleanup);
describe("results-first workspace",()=>{
 it("preserves existing route ids and supports portfolio and market pages",()=>{
  expect(validPage("6")).toBe(6);expect(validPage("8")).toBe(8);
  expect(validPage("9")).toBe(9);expect(validPage("10")).toBe(10);
  expect(validPage("99")).toBe(0);
  const navigate=vi.fn();
  render(<WorkspaceNavigation page={9} onNavigate={navigate}/>);
  expect(screen.getByRole("button",{name:"My Portfolio",current:"page"})).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Market Intelligence"}));
  expect(navigate).toHaveBeenCalledWith(10);
 });
 it("opens mobile navigation and closes it after selection",()=>{
  render(<WorkspaceNavigation page={0} onNavigate={()=>{}}/>);
  const menu=screen.getByRole("button",{name:"Overview",expanded:false});
  fireEvent.click(menu);
  expect(menu.getAttribute("aria-expanded")).toBe("true");
  fireEvent.click(screen.getByRole("button",{name:"Settings"}));
  expect(menu.getAttribute("aria-expanded")).toBe("false");
 });
 it("does not mount advanced tools until opened",()=>{
  render(<AdvancedSection title="Advanced diagnostics" description="Optional"><p>Expensive tool</p></AdvancedSection>);
  expect(screen.queryByText("Expensive tool")).toBeNull();
  const details=screen.getByText("Advanced diagnostics").closest("details")!;
  details.open=true;fireEvent(details,new Event("toggle"));
  expect(screen.getByText("Expensive tool")).toBeTruthy();
 });
 it("labels recorded rather than live portfolio values",()=>{
  const open=vi.fn();
  render(<PortfolioSummary analysis={{holdingCount:2,invested:100,pricedMarketValue:0,pricedUnrealizedPnl:0,unpricedHoldings:2,valuationComplete:false}} onOpen={open}/>);
  expect(screen.getAllByText("—")).toHaveLength(3); // value, P&L and previous-close change all unavailable
  expect(screen.getByText("2 unpriced")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Open portfolio"}));expect(open).toHaveBeenCalledOnce();
 });
});

it("shows fresh coverage separately from recorded portfolio values",()=>{
 const stamp=new Date().toISOString();
 render(<PortfolioSummary analysis={{holdingCount:2,invested:100,pricedMarketValue:120,pricedUnrealizedPnl:20,unpricedHoldings:0,valuationComplete:true}} holdings={[{asset_type:"EQUITY",price_as_of:stamp,one_day_change:5},{asset_type:"EQUITY",price_as_of:"2025-01-01",one_day_change:null}]} feedConnected onOpen={()=>{}}/>);
 expect(screen.getByText("1/2 stocks priced in the last 20s")).toBeTruthy();
 expect(screen.getByText(/1\/2 with previous close/)).toBeTruthy();
 expect(screen.getByText("Recorded value")).toBeTruthy();
});
