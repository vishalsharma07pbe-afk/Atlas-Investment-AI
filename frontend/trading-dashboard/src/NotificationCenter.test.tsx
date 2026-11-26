// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {act,cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import NotificationCenter from "./NotificationCenter";
afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals();});
it("loads only badge metadata on mount and details on bell click",async()=>{
  const fetchMock=vi.fn().mockImplementation((url:string)=>Promise.resolve({ok:true,json:async()=>url.endsWith("/summary")
    ?{ids:["ipo-1"],total:1,live_feed_connected:false}
    :{alerts:[{id:"ipo-1",category:"IPO_UPCOMING",title:"Test IPO",description:"Example",
       event_date:"2026-11-20",published_at:"2026-11-13T12:00:00Z",source_name:"Test source",
       source_url:"https://example.org/ipo",subscription_total_x:null,subscription_as_of:null}]} }));
  vi.stubGlobal("fetch",fetchMock);
  render(<NotificationCenter/>);
  await waitFor(()=>expect(screen.getByRole("button",{name:"Notifications, 1 unread"})).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toContain("/summary");
  fireEvent.click(screen.getByRole("button",{name:"Notifications, 1 unread"}));
  await waitFor(()=>expect(screen.getByText("Test IPO")).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock.mock.calls[1][0]).not.toContain("/summary");
  expect(screen.getByRole("button",{name:"Notifications, 0 unread"})).toBeTruthy();
});
it("shows no invented notifications for an empty feed",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockImplementation((url:string)=>Promise.resolve({ok:true,json:async()=>url.endsWith("/summary")?{ids:[],total:0}:{alerts:[]}})));
  render(<NotificationCenter/>);
  fireEvent.click(screen.getByRole("button",{name:"Notifications, 0 unread"}));
  await waitFor(()=>expect(screen.getByText(/No verified local alerts available/)).toBeTruthy());
});

it("includes authenticated personal unread count and loads private history only when opened",async()=>{
 const mock=vi.fn(async(url:string)=>({ok:true,json:async()=>url==="/api/v1/research-workspace/notifications/summary"?{unread_count:1}:url==="/api/v1/research-workspace/notifications"?[{id:"private-1",title:"Portfolio needs review",message:"Recorded risk",event_type:"PORTFOLIO_RISK",occurred_at:"2026-11-24T10:00:00Z",read_at:null}]:url.endsWith("/summary")?{ids:[],total:0}:{alerts:[]}}));
 vi.stubGlobal("fetch",mock);
 render(<NotificationCenter includePersonal/>);
 await waitFor(()=>expect(screen.getByRole("button",{name:"Notifications, 1 unread"})).toBeTruthy());
 expect(mock.mock.calls.some(([url])=>url==="/api/v1/research-workspace/notifications")).toBe(false);
 fireEvent.click(screen.getByRole("button",{name:"Notifications, 1 unread"}));
 expect(await screen.findByText("Portfolio needs review")).toBeTruthy();
});


it("focuses the notification dialog, wraps keyboard focus and restores the bell on Escape",async()=>{
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith("/summary")?{ids:[],total:0}:{alerts:[]}})));
 render(<NotificationCenter/>);
 const bell=screen.getByRole("button",{name:"Notifications, 0 unread"});
 fireEvent.click(bell);
 const dialog=await screen.findByRole("dialog",{name:"Notification center"});
 const close=dialog.querySelector<HTMLButtonElement>('button[aria-label="Close notifications"]')!;
 expect(document.activeElement).toBe(close);
 await screen.findByText(/No verified local alerts available/);
 fireEvent.keyDown(close,{key:"Tab",shiftKey:true});
 expect(dialog.contains(document.activeElement)).toBe(true);
 expect(document.activeElement).not.toBe(close);
 fireEvent.keyDown(document.activeElement!,{key:"Escape"});
 expect(screen.queryByRole("dialog",{name:"Notification center"})).toBeNull();
 expect(document.activeElement).toBe(bell);
});


it("shows local dated research alerts without inventing an external source link",async()=>{
 const alert={id:"research-test",revision_key:"research-test",category:"RISK_WARNING",title:"TEST · breakout review",description:"Observed re-entry, not a trade signal.",event_date:"2026-11-25",published_at:"2026-11-26T03:00:00Z",publication_basis:"RESEARCH_SNAPSHOT",source_name:"ATLAS local research",source_url:null,subscription_total_x:null,subscription_as_of:null};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith("/summary")?{ids:[alert.id],revision_keys:[alert.id],total:1}:{alerts:[alert]}})));
 render(<NotificationCenter/>);
 await waitFor(()=>expect(screen.getByRole("button",{name:"Notifications, 1 unread"})).toBeTruthy());
 fireEvent.click(screen.getByRole("button",{name:"Notifications, 1 unread"}));
 expect(await screen.findByText(alert.title)).toBeTruthy();
 expect(screen.getByText(/Research snapshot.*ATLAS local research/)).toBeTruthy();
 expect(screen.getByText(/Local saved research/)).toBeTruthy();
 expect(screen.queryByRole("link",{name:"Source"})).toBeNull();
});


it("distinguishes retained historical research from current observations",async()=>{
 const alert={id:"research-old",revision_key:"research-old",category:"RISK_WARNING",title:"Earlier market review",description:"Recorded risk observation.",event_date:"2026-11-25",published_at:"2026-11-26T03:00:00Z",publication_basis:"RESEARCH_SNAPSHOT",research_state:"HISTORICAL_OBSERVATION",source_name:"ATLAS local research",source_url:null,subscription_total_x:null,subscription_as_of:null};
 vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith("/summary")?{ids:[alert.id],total:1}:{alerts:[alert]}})));
 render(<NotificationCenter/>);
 await waitFor(()=>expect(screen.getByRole("button",{name:"Notifications, 1 unread"})).toBeTruthy());
 fireEvent.click(screen.getByRole("button",{name:"Notifications, 1 unread"}));
 expect(await screen.findByText("Earlier market review")).toBeTruthy();
 expect(screen.getByText("Historical observation — not a current signal")).toBeTruthy();
});

it("refreshes open details on visibility and cancels an outstanding response on close",async()=>{
 let resolve:(value:unknown)=>void=()=>{};
 let signal:AbortSignal|undefined;
 let detailCalls=0;
 const alert={id:"a-test",category:"MARKET_EVENT",title:"First alert",description:"Test",published_at:"2026-11-25T10:00:00Z",source_name:"Test",source_url:null,event_date:null,subscription_total_x:null,subscription_as_of:null};
 const mock=vi.fn((url:string,init?:RequestInit)=>{
  if(url.endsWith("/summary"))return Promise.resolve({ok:true,json:async()=>({ids:["a-test"],total:1})});
  detailCalls++;
  if(detailCalls===1)return Promise.resolve({ok:true,json:async()=>({alerts:[alert]})});
  signal=init?.signal??undefined;
  return new Promise(done=>{resolve=done;});
 });
 vi.stubGlobal("fetch",mock);
 render(<NotificationCenter/>);
 await waitFor(()=>expect(screen.getByRole("button",{name:"Notifications, 1 unread"})).toBeTruthy());
 fireEvent.click(screen.getByRole("button",{name:"Notifications, 1 unread"}));
 expect(await screen.findByText("First alert")).toBeTruthy();
 fireEvent(document,new Event("visibilitychange"));
 await waitFor(()=>expect(detailCalls).toBe(2));
 fireEvent.keyDown(document.activeElement!,{key:"Escape"});
 expect(signal?.aborted).toBe(true);
 await act(async()=>{resolve({ok:true,json:async()=>({alerts:[{...alert,id:"late",title:"Late alert"}]})});});
 expect(screen.queryByText("Late alert")).toBeNull();
 expect(localStorage.getItem("atlas:read-alert-ids")).not.toContain("late");
});
