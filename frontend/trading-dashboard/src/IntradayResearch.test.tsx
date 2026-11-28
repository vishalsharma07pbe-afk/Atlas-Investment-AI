/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import IntradayResearch from "./IntradayResearch";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("shows closed session without invented setups",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({status:"SESSION_CLOSED_OR_UNVERIFIED",candidates:[],warnings:[],notice:"Research only"})})));
 render(<IntradayResearch/>);
 expect(await screen.findByText("Market session closed or not verified.")).toBeTruthy();
 expect(screen.getByText("No qualifying observations.")).toBeTruthy();
});
it("distinguishes a failed breakout from a qualifying volume breakout",async()=>{
 const row={id:1,symbol:"TEST",exchange:"NSE",bar_end:"2026-11-25T05:15:00Z",close:100,vwap_proxy:101,relative_volume:2,session_change_percent:1,mean_bar_range_percent:2,bar_count:6};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({status:"RESEARCH_ONLY",eligible:1,examined:1,candidates:[],warnings:[row],notice:"Not trade signals"})})));
 render(<IntradayResearch/>);
 expect(await screen.findByText("TEST · NSE")).toBeTruthy();
 expect(screen.getByText("No qualifying observations.")).toBeTruthy();
});

it("keeps intraday qualification separate from current technical patterns",async()=>{
 const qualification={status:"NO_QUALIFIED_IN_REVIEWED_SAMPLE",reviewed_count:1,review_required_count:1,qualified_count:0,unidentified_listing_count:1,cross_venue_company_count:1,conflicting_company_count:1,leading_blockers:[],notice:"Exact identities only."};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({status:"RESEARCH_ONLY",eligible:3,examined:3,candidates:[],warnings:[],qualification,notice:"Research only."})})));
 render(<IntradayResearch/>);
 expect(await screen.findByText(/0 qualified in reviewed sample/)).toBeTruthy();
 expect(screen.getByText(/1 conflicting companies/)).toBeTruthy();
});

it("shows the chosen research venue without claiming execution clearance",async()=>{
 const row={id:1,symbol:"TEST",exchange:"BSE",bar_end:"2026-11-25T05:15:00Z",close:100,vwap_proxy:99,relative_volume:2,session_change_percent:1,mean_bar_range_percent:2,bar_count:6,
 company_venue_context:{status:"PAIRED_QUOTE_LIQUIDITY_PREFERENCE",preferred_exchange:"BSE",representative_exchange:"BSE",observed_venues:["BSE","NSE"],venue_observations:[],notice:"No verified execution."}};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({status:"RESEARCH_ONLY",eligible:2,examined:2,candidates:[row],warnings:[],notice:"Research only."})})));
 render(<IntradayResearch/>);
 expect(await screen.findByText("Exchange comparison · BSE + NSE")).toBeTruthy();
 expect(screen.getByText(/Research venue: BSE/)).toBeTruthy();
});
