// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import NotificationCenter from "./NotificationCenter";
afterEach(()=>{cleanup();localStorage.clear();vi.unstubAllGlobals();});
it("refreshes only badge metadata on focus, never full alert details until clicked",async()=>{
  let revision="ipo-a@first";
  const fetchMock=vi.fn().mockImplementation((url:string)=>Promise.resolve({ok:true,json:async()=>url.endsWith("/summary")
    ?{ids:["ipo-a"],revision_keys:[revision],total:1,live_feed_connected:false}
    :{alerts:[{id:"ipo-a",revision_key:revision,category:"IPO_UPCOMING",
       title:"Illustrative IPO",description:"Test",published_at:"2026-11-13T12:00:00Z",
       source_name:"Test source",source_url:"https://example.org/ipo",
       event_date:null,subscription_total_x:null,subscription_as_of:null}]}}));
  vi.stubGlobal("fetch",fetchMock);
  render(<NotificationCenter/>);
  await waitFor(()=>expect(screen.getByRole("button",{name:"Notifications, 1 unread"})).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  revision="ipo-a@second";
  fireEvent.focus(window);
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock.mock.calls.every(call=>(call[0] as string).endsWith("/summary"))).toBe(true);
  fireEvent.click(screen.getByRole("button",{name:"Notifications, 1 unread"}));
  await waitFor(()=>expect(screen.getByText("Illustrative IPO")).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(fetchMock.mock.calls[2][0]).not.toContain("/summary");
});
