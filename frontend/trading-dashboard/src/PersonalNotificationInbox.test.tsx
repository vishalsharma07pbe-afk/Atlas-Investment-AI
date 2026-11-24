/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
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
