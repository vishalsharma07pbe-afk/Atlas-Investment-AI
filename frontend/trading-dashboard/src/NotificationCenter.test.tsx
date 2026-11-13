// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
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
