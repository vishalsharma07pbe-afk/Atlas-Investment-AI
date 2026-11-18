/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import HoldingEditor from "./HoldingEditor";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

describe("HoldingEditor",()=>{
 it("suggests stocks from one character and calculates values from a provider quote",async()=>{
  const fetcher=vi.spyOn(globalThis,"fetch").mockImplementation(async input=>{
   const url=String(input);
   if(url.includes("/instruments/search"))return new Response(JSON.stringify([
    {instrument_key:"NSE_EQ|INE002A01018",exchange_code:"NSE",isin:"INE002A01018",trading_symbol:"RELIANCE",instrument_type:"EQ"},
    {instrument_key:"NSE_EQ|INE123456789",exchange_code:"NSE",isin:"INE123456789",trading_symbol:"RBLBANK",instrument_type:"EQ"}
   ]),{status:200,headers:{"Content-Type":"application/json"}});
   return new Response(JSON.stringify({status:"FRESH",price:"2500",as_of:"2026-11-17T06:00:00Z",source:"UPSTOX",live:true,notice:"read only"}),{status:200,headers:{"Content-Type":"application/json"}});
  });
  render(<HoldingEditor busy={false} onSave={vi.fn()}/>);
  fireEvent.change(screen.getByLabelText("Symbol"),{target:{value:"r"}});
  expect(await screen.findByText("RELIANCE")).toBeTruthy();
  expect(screen.getByRole("button",{name:"Close stock suggestions"})).toBeTruthy();
  fireEvent.click(screen.getByText("RELIANCE"));
  expect(screen.queryByRole("button",{name:"Close stock suggestions"})).toBeNull();
  await waitFor(()=>expect((screen.getByLabelText("Last price") as HTMLInputElement).value).toBe("2500"));
  fireEvent.change(screen.getByLabelText("Quantity"),{target:{value:"2"}});
  fireEvent.change(screen.getByLabelText("Average cost"),{target:{value:"2000"}});
  expect(screen.getByText("₹4,000.00")).toBeTruthy();
  expect(screen.getByText("₹5,000.00")).toBeTruthy();
  expect(screen.getByText("₹1,000.00")).toBeTruthy();
  expect(fetcher.mock.calls[0][0]).toContain("q=R");
 });
});
