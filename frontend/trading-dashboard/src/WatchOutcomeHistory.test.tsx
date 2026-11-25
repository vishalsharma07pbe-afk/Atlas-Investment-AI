/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import WatchOutcomeHistory from "./WatchOutcomeHistory";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("distinguishes unavailable evidence from observed price changes",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({horizon:"SWING",counts:{OBSERVED:1,EVIDENCE_GAP:1},items:[
 {symbol:"FIRST",exchange:"NSE",observed_date:"2026-10-01",published_at:"2026-10-02T10:00:00Z",maturity_date:"2026-10-16",status:"OBSERVED",outcome:{entry_date:"2026-10-05",exit_date:"2026-10-16",observed_price_return_pct:4.25,source_code:"TEST_PROVIDER"}},
 {symbol:"SECOND",exchange:"NSE",observed_date:"2026-10-01",published_at:"2026-10-02T10:00:00Z",maturity_date:"2026-10-16",status:"EVIDENCE_GAP",outcome:null}
 ],notice:"Public technical watch history, not trades or validated strategy performance."})})));
 render(<WatchOutcomeHistory horizon="SWING"/>);
 expect(await screen.findByText(/4\.25%/)).toBeTruthy();
 expect(screen.getByText(/Legacy evidence — excluded from current reliability metrics/)).toBeTruthy();
 expect(screen.getByText("EVIDENCE GAP")).toBeTruthy();
 expect(screen.getByText("—")).toBeTruthy();
 expect(screen.getByText(/not trades or validated strategy performance/)).toBeTruthy();
});
