/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import HistoricalInvestments from "./HistoricalInvestments";

afterEach(()=>{cleanup();vi.restoreAllMocks();});
describe("HistoricalInvestments",()=>{
 it("keeps closed investments in their own table and totals realised profit",async()=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue(new Response(JSON.stringify([{id:"1",symbol:"TCS",display_name:"Tata Consultancy Services",asset_type:"EQUITY",quantity:2,average_cost:3000,exit_price:3500,opened_on:"2024-01-01",closed_on:"2025-01-01",invested:6000,exit_value:7000,realized_pnl:1000}]),{status:200,headers:{"Content-Type":"application/json"}}));
  render(<HistoricalInvestments/>);
  expect(await screen.findByText("Tata Consultancy Services")).toBeTruthy();
  expect(screen.getAllByText("₹1,000.00").length).toBeGreaterThan(0);
  expect(screen.getByText("Past investments (closed)")).toBeTruthy();
 });
});
