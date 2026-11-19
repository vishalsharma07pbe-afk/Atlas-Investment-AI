// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,describe,expect,it,vi} from "vitest";
import MarketIndexStrip from "./MarketIndexStrip";

afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});

describe("MarketIndexStrip",()=>{
 it("renders verified provider values and refreshes on demand",async()=>{
  const fetchMock=vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:true,json:async()=>({
   status:"AVAILABLE",source:"UPSTOX",notice:"Read-only",items:[{
    label:"NIFTY 50",price:25050,change:50,change_percent:.2,
    as_of:"2026-11-18T04:30:00Z",freshness:"LIVE"
   }]
  })} as Response);
  render(<MarketIndexStrip/>);
  expect(await screen.findByText("NIFTY 50")).toBeTruthy();
  expect(screen.getByText("25,050.00")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Refresh market indices"}));
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2));
 });

 it("does not invent values when authorization expired",async()=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:true,json:async()=>({
   status:"UNAVAILABLE",source:"UPSTOX",reason:"PROVIDER_ACCESS_REJECTED",
   items:[],notice:"No values"
  })} as Response);
  render(<MarketIndexStrip/>);
  expect(await screen.findByText("Upstox authorization expired")).toBeTruthy();
  expect(screen.getByText(/Daily Upstox sign-in is required/)).toBeTruthy();
 });

 it("replaces the snapshot immediately when a pushed quote arrives",async()=>{
  class FakeEventSource{
   static latest:FakeEventSource;
   onopen:(()=>void)|null=null;
   onerror:(()=>void)|null=null;
   listeners=new Map<string,(event:Event)=>void>();
   constructor(public url:string){FakeEventSource.latest=this;}
   addEventListener(name:string,listener:EventListener){this.listeners.set(name,listener);}
   removeEventListener(name:string){this.listeners.delete(name);}
   close(){}
   emit(name:string,value:unknown){this.listeners.get(name)?.({data:JSON.stringify(value)} as MessageEvent<string>);}
  }
  vi.stubGlobal("EventSource",FakeEventSource);
  vi.spyOn(globalThis,"fetch").mockResolvedValue({ok:true,json:async()=>({
   status:"UNAVAILABLE",source:"UPSTOX",items:[],notice:"Waiting"
  })} as Response);
  render(<MarketIndexStrip/>);
  await waitFor(()=>expect(FakeEventSource.latest.url).toBe("/api/v1/live/market-indices"));
  FakeEventSource.latest.emit("quote",{
   status:"AVAILABLE",source:"UPSTOX_V3_STREAM",notice:"Push",items:[{
    label:"NIFTY 50",price:25123.45,change:10,change_percent:.04,
    as_of:"2026-11-19T04:30:00Z",freshness:"LIVE"
   }]
  });
  expect(await screen.findByText("25,123.45")).toBeTruthy();
  expect(screen.getByText("UPSTOX_V3_STREAM · live push")).toBeTruthy();
 });
});
