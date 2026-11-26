/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {act,cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import PersonalNotificationInbox from "./PersonalNotificationInbox";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("reads owner history and marks read only after a successful server response",async()=>{
 const fetchMock=vi.fn(async(_url:string,init?:RequestInit)=>({ok:true,json:async()=>init?.method==="PATCH"?{read:true}:[{id:"risk-1",title:"Portfolio review needs attention",message:"Recorded risk",event_type:"PORTFOLIO_RISK",occurred_at:"2026-11-24T10:00:00Z",read_at:null}]}));
 vi.stubGlobal("fetch",fetchMock);const onRead=vi.fn();
 render(<PersonalNotificationInbox onRead={onRead}/>);
 expect(await screen.findByText("Portfolio review needs attention")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Mark read"}));
 await waitFor(()=>expect(onRead).toHaveBeenCalledOnce());
 expect(fetchMock).toHaveBeenCalledWith("/api/v1/research-workspace/notifications/risk-1/read",{method:"PATCH"});
 expect(screen.getByText("Read")).toBeTruthy();
});

it("keeps a successful read acknowledgement when an older inbox poll returns",async()=>{
 const row={id:"risk-2",title:"Risk review",message:"Observed",event_type:"PORTFOLIO_RISK",occurred_at:"2026-11-24T10:00:00Z",read_at:null};
 let reads=0;
 let resolve:(value:unknown)=>void=()=>{};
 const mock=vi.fn((_url:string,init?:RequestInit)=>{
  if(init?.method==="PATCH")return Promise.resolve({ok:true});
  if(++reads===1)return Promise.resolve({ok:true,json:async()=>[row]});
  return new Promise(done=>{resolve=done;});
 });
 vi.stubGlobal("fetch",mock);
 const onRead=vi.fn();render(<PersonalNotificationInbox onRead={onRead}/>);
 expect(await screen.findByText("Risk review")).toBeTruthy();
 fireEvent(document,new Event("visibilitychange"));
 await waitFor(()=>expect(reads).toBe(2));
 fireEvent.click(screen.getByRole("button",{name:"Mark read"}));
 await waitFor(()=>expect(onRead).toHaveBeenCalledOnce());
 await act(async()=>{resolve({ok:true,json:async()=>[row]});});
 expect(screen.getByText("Read")).toBeTruthy();
 expect(screen.queryByRole("button",{name:"Mark read"})).toBeNull();
});
