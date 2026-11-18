// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import NotificationCenter from "./NotificationCenter";
afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals();});
it("filters loaded IPO alerts and warns about stale subscription rates",async()=>{
  const fetchMock=vi.fn().mockImplementation((url:string)=>Promise.resolve({ok:true,json:async()=>url.endsWith("/summary")
    ?{ids:["ipo-1"],revision_keys:["ipo-1@2026-11-12"],total:1}
    :{alerts:[{id:"ipo-1",revision_key:"ipo-1@2026-11-12",category:"IPO_SUBSCRIPTION",
       title:"Example IPO rate",description:"Illustrative",published_at:"2026-11-12T12:00:00Z",
       source_name:"Example source",source_url:"https://example.org/ipo",event_date:null,
       subscription_total_x:"1.2",subscription_as_of:"2026-11-12T11:00:00Z",freshness:"STALE"},
       {id:"event-1",revision_key:"event-1@2026-11-12",category:"MARKET_EVENT",
       title:"Example event",description:"Illustrative",published_at:"2026-11-12T12:00:00Z",
       source_name:"Example source",source_url:"https://example.org/event",event_date:null,
       subscription_total_x:null,subscription_as_of:null,freshness:"NOT_APPLICABLE"}]}}));
  vi.stubGlobal("fetch",fetchMock);
  render(<NotificationCenter/>);
  await waitFor(()=>expect(screen.getByRole("button",{name:"Notifications, 1 unread"})).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button",{name:"Notifications, 1 unread"}));
  await waitFor(()=>expect(screen.getByText("Example IPO rate")).toBeTruthy());
  expect(screen.getByText(/STALE SNAPSHOT/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Filter"),{target:{value:"MARKET_EVENT"}});
  expect(screen.getByText("Example event")).toBeTruthy();
  expect(screen.queryByText("Example IPO rate")).toBeNull();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
