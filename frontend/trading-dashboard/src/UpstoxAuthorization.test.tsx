// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import UpstoxAuthorization from "./UpstoxAuthorization";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("UpstoxAuthorization",()=>{
 it("only checks on demand and never displays a token",async()=>{
   const fetcher=vi.fn().mockResolvedValue({ok:true,json:async()=>({status:"BLOCKED",authorization_request_performed:false,live_stream_connected:false,blockers:["ACCESS_TOKEN_MISSING"],notice:"Configuration only"})});
   vi.stubGlobal("fetch",fetcher);
   render(<UpstoxAuthorization/>);
   expect(fetcher).not.toHaveBeenCalled();
   fireEvent.click(screen.getByRole("button",{name:"Check Upstox configuration"}));
   await waitFor(()=>expect(screen.getByRole("status").textContent).toContain("BLOCKED"));
   expect(screen.getByRole("status").textContent).toContain("ACCESS TOKEN MISSING");
   await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(2));
   expect(fetcher).toHaveBeenCalledWith("/intelligence/api/v1/intelligence/providers/upstox/quote-status");
 });
 it("shows a safe failure state",async()=>{
   vi.stubGlobal("fetch",vi.fn().mockRejectedValue(Error("offline")));
   render(<UpstoxAuthorization/>);
   fireEvent.click(screen.getByRole("button",{name:"Check Upstox configuration"}));
   await waitFor(()=>expect(screen.getByRole("alert").textContent).toContain("offline"));
 });
});
