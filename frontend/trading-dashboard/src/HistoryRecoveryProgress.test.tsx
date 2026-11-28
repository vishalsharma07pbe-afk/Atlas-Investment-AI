/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen,within,fireEvent,waitFor} from "@testing-library/react";
import HistoryRecoveryProgress,{RecoveryDetails} from "./HistoryRecoveryProgress";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const venue={exchange:"NSE",target_session:"2026-11-27",calendar_status:"VERIFIED_PRIOR_REGULAR_SESSION",mapped_listings:100,mapped_companies:100,current_listings:41,deep_listings:30,adjusted_depth_listings:0,recoverable_missing:50,due_missing:20,active_claims:1,expired_claims:2,failed_last_attempts:3,never_attempted:10,suspended_listings:4,protected_adjusted_listings:5,last_attempt_at:null,last_successful_attempt_started_at:null,next_deferred_missing_attempt_at:null};
const snapshot={generated_at:"2026-11-28T08:00:00Z",configured:true,provider_blocked:true,provider_blocked_until:"2026-11-28T09:00:00Z",distinct_mapped_companies:120,depth_target:253,exchanges:[venue,{...venue,exchange:"BSE",target_session:null,calendar_status:"UNVERIFIED",current_listings:null,deep_listings:null,adjusted_depth_listings:null,recoverable_missing:null,due_missing:null}]};
it("keeps acquisition diagnostics dormant until expanded",()=>{
 const fetcher=vi.fn();vi.stubGlobal("fetch",fetcher);
 render(<HistoryRecoveryProgress/>);
 expect(screen.getByText("Automatic historical data recovery")).toBeTruthy();
 expect(fetcher).not.toHaveBeenCalled();
});
it("distinguishes known coverage from an unverified target and provider cooldown",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>snapshot})));
 render(<RecoveryDetails/>);
 expect(await screen.findByText(/Provider cooldown active/)).toBeTruthy();
 expect(screen.getByRole("meter",{name:"NSE target-session candles"}).getAttribute("aria-valuenow")).toBe("41");
 expect(within(screen.getByRole("article",{name:"BSE acquisition progress"})).getByText("Current-session coverage unknown")).toBeTruthy();
 expect(screen.queryByRole("meter",{name:"BSE target-session candles"})).toBeNull();
});
it("compares only observations with matching target and denominator",async()=>{
 const next={...snapshot,generated_at:"2026-11-28T08:02:00Z",exchanges:[{...venue,current_listings:45},snapshot.exchanges[1]]};
 const fetcher=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>snapshot}).mockResolvedValueOnce({ok:true,json:async()=>next});
 vi.stubGlobal("fetch",fetcher);render(<RecoveryDetails/>);
 await screen.findByRole("meter",{name:"NSE target-session candles"});
 await waitFor(()=>expect((screen.getByRole("button",{name:"Refresh progress"}) as HTMLButtonElement).disabled).toBe(false));
 fireEvent.click(screen.getByRole("button",{name:"Refresh progress"}));
 expect(await screen.findByText("Net change since previous observation: +4 listing(s)")).toBeTruthy();
});
it("does not present failure as zero coverage",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:false})));
 render(<RecoveryDetails/>);
 expect(await screen.findByRole("alert")).toBeTruthy();
 expect(screen.queryByRole("meter")).toBeNull();
});
