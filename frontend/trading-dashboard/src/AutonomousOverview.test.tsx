/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import AutonomousOverview from "./AutonomousOverview";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("automatic research overview",()=>{
 it("shows persisted observations without launching a manual scan and keeps tools hidden",async()=>{
   const fetchMock=vi.fn(async()=>({ok:true,json:async()=>({enabled:true,interval_seconds:900,sections:[{section:"NSE",status:"READY",generated_at:"2026-11-24T10:00:00Z",result:{eligible_count:1,universe_size:2,momentum_leaders:[{id:1,symbol:"TCS",exchange:"NSE",as_of:"2026-11-23",momentum_20d_percent:3}]}},{section:"LARGE_CAP",status:"READY",generated_at:null,result:{growth_outlook:[]}}]})}));
   vi.stubGlobal("fetch",fetchMock);
   render(<AutonomousOverview onPortfolio={()=>{}} onFunds={()=>{}} onSettings={()=>{}}><p>Manual research tool</p></AutonomousOverview>);
   expect(await screen.findByText("TCS")).toBeTruthy();
   expect(screen.getByText("No growth picks meet the verified evidence requirements.")).toBeTruthy();
   expect(screen.queryByText("Manual research tool")).toBeNull();
   expect(fetchMock.mock.calls.length).toBe(1);
   fireEvent.click(screen.getByRole("button",{name:"Open research tools"}));
   expect(screen.getByText("Manual research tool")).toBeTruthy();
 });
});
