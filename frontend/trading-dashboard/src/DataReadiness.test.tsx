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

it("renders background job failures without conflating scheduler completion with source readiness",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-24T10:00:00Z",provider_mode:"UPSTOX",automatic_research_enabled:true,live_market_data_connected:false,blockers:[],datasets:[],research_jobs:{status:"PERSISTED_LOCAL_JOB_LEDGER",jobs:[{job:"COMPANY_NEWS",status:"FAILED",attempted_at:"2026-11-24T09:00:00Z",last_completed_at:null,next_due_at:"2026-11-24T10:01:00Z",consecutive_failures:2,interrupted_attempts:1,error_code:"RESEARCH_JOB_FAILED"}],notice:"Pass completion is not provider verification."}})})));
 render(<DataReadiness/>);
 expect(await screen.findByText("Background research job diagnostics")).toBeTruthy();
 expect(screen.getByText("COMPANY NEWS")).toBeTruthy();
 expect(screen.getByText("2 / 1")).toBeTruthy();
 expect(screen.getByText("Pass completion is not provider verification.")).toBeTruthy();
});

it("shows independently stored calendar states without asserting live connectivity",async()=>{
 const calendar={status:"STORED_SESSION_CONTEXT",sessions:[{exchange:"NSE",session_date:"2026-11-25",phase:"PRE_MARKET",open_at:"2026-11-25T03:45:00Z",close_at:"2026-11-25T10:00:00Z"},{exchange:"BSE",session_date:"2026-11-25",phase:"CALENDAR_UNVERIFIED",open_at:null,close_at:null}],notice:"Stored schedule only."};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T02:30:00Z",provider_mode:"UPSTOX",automatic_research_enabled:true,live_market_data_connected:false,blockers:[],datasets:[],research_jobs:{status:"PERSISTED_LOCAL_JOB_LEDGER",jobs:[],calendar}})})));
 render(<DataReadiness/>);
 expect(await screen.findByText("Exchange session context")).toBeTruthy();
 expect(screen.getByText("PRE MARKET")).toBeTruthy();
 expect(screen.getByText("CALENDAR UNVERIFIED")).toBeTruthy();
 expect(screen.getByText(/Live feed: not verified/)).toBeTruthy();
});

it("shows persistent provider cooldown separately from streaming verification",async()=>{
 const provider_http_recovery={status:"PERSISTED_QUOTE_RECOVERY",providers:[{provider:"UPSTOX",state:"OPEN",retry_after_seconds:120,failures:2,last_error:"PROVIDER_RATE_LIMITED"},{provider:"POLYGON",state:"NOT_OBSERVED",retry_after_seconds:0,failures:0,last_error:null}]};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T02:30:00Z",provider_mode:"UPSTOX",automatic_research_enabled:true,live_market_data_connected:false,blockers:[],datasets:[],provider_http_recovery})})));
 render(<DataReadiness/>);
 expect(await screen.findByText("Provider HTTP recovery")).toBeTruthy();
 expect(screen.getByText("120 s")).toBeTruthy();
 expect(screen.getByText("NOT OBSERVED")).toBeTruthy();
 expect(screen.getByText(/Live feed: not verified/)).toBeTruthy();
});

it("shows separate automatic catalog recovery states",async()=>{
 const public_feed_schedule={status:"PERSISTED_PUBLIC_FEED_SCHEDULE",enabled:true,jobs:[
 {provider:"UPSTOX",status:"RETRY",attempts:2,interruptions:1,error_code:"PROVIDER_RATE_LIMITED",last_success_at:null,next_attempt_at:"2026-11-25T03:00:00Z"},
 {provider:"AMFI",status:"SUCCESS",attempts:1,interruptions:0,error_code:null,last_success_at:"2026-11-25T02:30:00Z",next_attempt_at:null}]};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({generated_at:"2026-11-25T02:30:00Z",provider_mode:"UPSTOX",automatic_research_enabled:true,live_market_data_connected:false,blockers:[],datasets:[],public_feed_schedule})})));
 render(<DataReadiness/>);
 expect(await screen.findByText("Automatic catalog synchronization")).toBeTruthy();
 expect(screen.getByText("Upstox instruments")).toBeTruthy();
 expect(screen.getByText("AMFI NAV")).toBeTruthy();
 expect(screen.getByText("2 / 1")).toBeTruthy();
 expect(screen.getByText(/Live feed: not verified/)).toBeTruthy();
});
