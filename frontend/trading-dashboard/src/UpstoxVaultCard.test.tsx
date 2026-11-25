// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {AutomaticHoldingsSync} from "./UpstoxVaultCard";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

it("requires explicit opt-in and shows credential recovery without exposing a token",async()=>{
 const base={enabled:false,status:"DISABLED",token_expires_at:null,last_attempt_at:null,last_success_at:null,next_attempt_at:null,error_code:null};
 const fetcher=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>base})
   .mockResolvedValueOnce({ok:true,json:async()=>({...base,enabled:true,status:"REAUTH_REQUIRED"})});
 vi.stubGlobal("fetch",fetcher);
 render(<AutomaticHoldingsSync/>);
 expect(await screen.findByText("Automatic sync: DISABLED")).toBeTruthy();
 expect(fetcher).toHaveBeenCalledTimes(1);
 fireEvent.click(screen.getByRole("button",{name:"Enable automatic holdings sync"}));
 await waitFor(()=>expect(screen.getByText("Automatic sync: REAUTH REQUIRED")).toBeTruthy());
 expect(fetcher).toHaveBeenLastCalledWith("/api/v1/broker/upstox/holdings-sync",{
  method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:true})});
 expect(screen.getByText(/ATLAS cannot renew access on your behalf/)).toBeTruthy();
 expect(screen.getByRole("button",{name:"Disable automatic holdings sync"})).toBeTruthy();
});

it("does not assume consent or display an enabled state when status is unavailable",async()=>{
 vi.stubGlobal("fetch",vi.fn().mockRejectedValue(Error("offline")));
 render(<AutomaticHoldingsSync/>);
 expect(await screen.findByRole("alert")).toBeTruthy();
 expect(screen.queryByRole("button",{name:"Enable automatic holdings sync"})).toBeNull();
 expect(screen.getByRole("button",{name:"Refresh sync status"})).toBeTruthy();
});
