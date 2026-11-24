/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import DataReadiness from "./DataReadiness";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("distinguishes configured automation from live feed and renders stored AMFI evidence",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-24T10:00:00Z",provider_mode:"UPSTOX",automatic_research_enabled:true,live_market_data_connected:false,blockers:["VERIFIED_LIVE_FEED_UNAVAILABLE"],datasets:[],backend_evidence:[{code:"OFFICIAL_AMFI_NAV",label:"Official AMFI NAV",records:500,latest_observed_at:"2026-11-23",age:1,age_unit:"date",status:"RECENT_LOCAL_EVIDENCE",ingestion_mode:"STORED_PROVIDER_EVIDENCE",automatic_collection_enabled:true}],research_sections:[{section:"NSE",status:"READY",generated_at:"2026-11-24T09:00:00Z"}],notice:"Stored evidence only"})})));
 render(<DataReadiness/>);
 expect(await screen.findByText("Automatic research: configured")).toBeTruthy();
 expect(screen.getByText("Official AMFI NAV")).toBeTruthy();
 expect(screen.getByText("500")).toBeTruthy();
 expect(screen.getByText(/Live feed: not verified/)).toBeTruthy();
 expect(screen.getByText("READY")).toBeTruthy();
});
