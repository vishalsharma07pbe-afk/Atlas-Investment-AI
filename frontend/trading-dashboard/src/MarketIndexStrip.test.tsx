// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
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
  expect(screen.getByText(/Check the configured Analytics Token/)).toBeTruthy();
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
  expect(screen.getByRole("status",{name:"Market quotes live"})).toBeTruthy();
 });
});

it("keeps streamed quotes when an older HTTP response completes, then marks them last observed on disconnect",async()=>{
 class FakeSource{
  static current:FakeSource;
  onopen:(()=>void)|null=null;
  onerror:(()=>void)|null=null;
  callback:EventListener|null=null;
  constructor(){FakeSource.current=this;}
  addEventListener(_name:string,callback:EventListener){this.callback=callback;}
  removeEventListener(){this.callback=null;}
  close(){}
  emit(body:unknown){this.callback?.({data:JSON.stringify(body)} as MessageEvent<string>);}
 }
 const snapshot=(source:string,price:number,stamp:string)=>({status:"AVAILABLE",source,notice:"test",items:[
  {label:"NIFTY 50",price,change:10,change_percent:.04,as_of:stamp,freshness:"LIVE"}]});
 let finish!:(response:Response)=>void;
 vi.stubGlobal("EventSource",FakeSource);
 vi.spyOn(globalThis,"fetch").mockImplementation(()=>new Promise<Response>(resolve=>{finish=resolve;}));
 render(<MarketIndexStrip/>);
 act(()=>FakeSource.current.emit(snapshot("UPSTOX_V3_STREAM",25123.45,"2026-11-19T04:30:05Z")));
 expect(await screen.findByText("25,123.45")).toBeTruthy();
 await act(async()=>{finish({ok:true,json:async()=>snapshot("UPSTOX",25000,"2026-11-19T04:30:00Z")} as Response);});
 expect(screen.queryByText("25,000.00")).toBeNull();
 expect(screen.getByRole("status",{name:"Market quotes live"})).toBeTruthy();
 act(()=>FakeSource.current.onerror?.());
 expect(screen.getByText("LAST OBSERVED")).toBeTruthy();
 expect(screen.queryByText("LIVE")).toBeNull();
 expect(screen.getByText("25,123.45")).toBeTruthy();
 act(()=>FakeSource.current.emit(snapshot("UPSTOX_V3_STREAM",25125,"2026-11-19T04:30:06Z")));
 expect(await screen.findByText("25,125.00")).toBeTruthy();
 expect(screen.getByText("LIVE")).toBeTruthy();
});
