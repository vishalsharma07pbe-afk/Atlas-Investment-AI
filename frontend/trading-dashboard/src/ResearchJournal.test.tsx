// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import ResearchJournal from "./ResearchJournal";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("loads notes and filters by status",async()=>{
  const mock=vi.fn().mockResolvedValue({ok:true,json:async()=>({entries:[
    {id:"1",symbol:"TEST",thesis:"Synthetic test thesis",evidence:"Source note",risks:"Test risk",source_url:"",status:"IDEA",updated_at:"2026-01-01"},
    {id:"2",symbol:"MOCK",thesis:"Other synthetic thesis",evidence:"",risks:"",source_url:"",status:"CLOSED",updated_at:"2026-01-01"}]})});
  vi.stubGlobal("fetch",mock);
  render(<ResearchJournal/>);
  await waitFor(()=>expect(screen.getByText("Synthetic test thesis")).toBeTruthy());
  fireEvent.change(screen.getByLabelText("Filter journal status"),{target:{value:"CLOSED"}});
  expect(screen.queryByText("Synthetic test thesis")).toBeNull();
  expect(screen.getByText("Other synthetic thesis")).toBeTruthy();
});
it("saves new journal entry",async()=>{
  const mock=vi.fn().mockImplementation(async (_url:string,options?:RequestInit)=>options?.method==="POST"?
    {ok:true,json:async()=>({})}:{ok:true,json:async()=>({entries:[]})});
  vi.stubGlobal("fetch",mock);
  render(<ResearchJournal/>);
  fireEvent.change(screen.getByLabelText("Journal symbol"),{target:{value:"TEST"}});
  fireEvent.change(screen.getByLabelText("Journal thesis"),{target:{value:"A test thesis"}});
  fireEvent.click(screen.getByRole("button",{name:"Save research note"}));
  await waitFor(()=>expect(mock.mock.calls.some(c=>c[1]?.method==="POST")).toBe(true));
});
