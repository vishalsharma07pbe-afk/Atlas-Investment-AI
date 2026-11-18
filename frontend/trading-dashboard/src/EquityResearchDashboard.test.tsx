/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import EquityResearchDashboard from "./EquityResearchDashboard";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

const json=(value:unknown)=>new Response(JSON.stringify(value),{status:200,headers:{"Content-Type":"application/json"}});

describe("EquityResearchDashboard",()=>{
 it("loads normalized evidence, citations and institutional context after selection",async()=>{
  vi.spyOn(globalThis,"fetch").mockImplementation(async input=>{
   const url=String(input);
   if(url.includes("/instruments/search"))return json([{instrument_key:"NSE_EQ|INE002A01018",exchange_code:"NSE",isin:"INE002A01018",trading_symbol:"RELIANCE",display_name:"Reliance Industries"}]);
   if(url.includes("/p1/companies/"))return json({isin:"INE002A01018",instrument_key:"NSE_EQ|INE002A01018",generated_at:"2026-11-18T10:00:00Z",coverage:{available_sections:8,total_sections:8},sections:{profile:{status:"AVAILABLE",data:{company_profile:"Diversified listed company",sector:"Refineries"}},ratios:{status:"AVAILABLE",data:[{name:"P/E",company_value:19.4,sector_value:17.6,unit:"RATIO",relative_difference_percent:10.2}]},income_statement:{status:"AVAILABLE",data:{units_in:"crore",income_statement:[{category:"revenue",history:[{value:100,period:"Mar 2026"}]}]}},balance_sheet:{status:"AVAILABLE",data:{units_in:"crore",history:[{total_asset:200,total_liability:80,period:"Mar 2026"}]}},cash_flow:{status:"AVAILABLE",data:{units_in:"crore",cash_flow:[{category:"operating",history:[{value:50,period:"Mar 2026"}]}]}},shareholding:{status:"AVAILABLE",data:[{category:"promoters",history:[{value:50,period:"Sep 2026"}]}]},corporate_actions:{status:"AVAILABLE",data:[]},competitors:{status:"AVAILABLE",data:[]}},interpretation:{},notice:"Evidence only"});
   if(url.includes("/p1/news"))return json({articles:[{instrument_key:"NSE_EQ|INE002A01018",headline:"Company update",summary:"Attributed summary",url:"https://example.test/article",published_at:"2026-11-18T09:00:00Z",sentiment:"NOT_ANALYZED"}]});
   return json({interval:"1D",participants:{fii:{status:"AVAILABLE",data:[{observed_at:"2026-11-18T00:00:00Z",buy_amount:120,sell_amount:100,net_amount:20}]},dii:{status:"AVAILABLE",data:[]}}});
  });
  render(<EquityResearchDashboard/>);
  fireEvent.change(screen.getByLabelText("Company research search"),{target:{value:"rel"}});
  fireEvent.click(await screen.findByText("RELIANCE"));
  expect(await screen.findByText("Reliance Industries")).toBeTruthy();
  expect(screen.getByText("P/E")).toBeTruthy();
  expect(screen.getByText("Company update")).toBeTruthy();
  expect(screen.getByText(/Net buying/)).toBeTruthy();
  await waitFor(()=>expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringContaining("instrument_key=NSE_EQ%7CINE002A01018")));
 });
});
