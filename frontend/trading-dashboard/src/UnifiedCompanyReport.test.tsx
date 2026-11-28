/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import UnifiedCompanyReport from "./UnifiedCompanyReport";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const isin="INE002A01018";
it("shows one company report with explicitly scoped daily observations",async()=>{
 const item={isin,status:"RESEARCH_ONLY",observations:[{id:1,exchange:"NSE",symbol:"TEST",horizon:"SWING",as_of:"2026-11-26",close:100,qualification_status:"WITHHELD_EVIDENCE_GAPS"},{id:2,exchange:"BSE",symbol:"TEST",horizon:"LONG_TERM",as_of:"2026-11-26",close:101,qualification_status:"WITHHELD_EVIDENCE_GAPS"}],observed_venues:["BSE","NSE"],review_findings:[],company_evidence:null,ai_review:null,notice:"Research only"};
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,company_reports:{items:{[isin]:item}}})})));
 render(<UnifiedCompanyReport isin={isin}/>);
 expect(await screen.findByText(isin+" · BSE + NSE")).toBeTruthy();
 expect(screen.getByText("₹100.00")).toBeTruthy();
 expect(screen.getByText("₹101.00")).toBeTruthy();
});
it("rejects a report with a different exact identity",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({enabled:true,company_reports:{items:{[isin]:{isin:"INE009A01021",observations:[]}}}})})));
 render(<UnifiedCompanyReport isin={isin}/>);
 expect(await screen.findByText("No current unified company research in the saved shortlist.")).toBeTruthy();
});
