/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,render,screen,within} from "@testing-library/react";
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
 const first=screen.getByText("NSE:FIRST").closest("tr")!;
 const second=screen.getByText("NSE:SECOND").closest("tr")!;
 expect(within(first).getAllByRole("cell")[5].textContent).toBe("—");
 expect(within(second).getAllByRole("cell")[4].textContent).toBe("—");
 expect(within(second).getAllByRole("cell")[5].textContent).toBe("—");
 expect(screen.getByText(/not trades or validated strategy performance/)).toBeTruthy();
});

it("shows corporate action withholding separately from legacy observations",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({horizon:"SWING",counts:{RECORDED_ACTION_RECONCILIATION_REQUIRED:1},items:[
 {symbol:"SPLITTEST",exchange:"NSE",observed_date:"2026-10-01",published_at:"2026-10-02T10:00:00Z",maturity_date:"2026-10-16",status:"RECORDED_ACTION_RECONCILIATION_REQUIRED",outcome:null}
 ],notice:"Recorded actions require reconciliation."})})));
 render(<WatchOutcomeHistory horizon="SWING"/>);
 expect(await screen.findByText("RECORDED ACTION RECONCILIATION REQUIRED")).toBeTruthy();
 const withheld=screen.getByText("NSE:SPLITTEST").closest("tr")!;
 expect(within(withheld).getAllByRole("cell")[4].textContent).toBe("—");
 expect(within(withheld).getAllByRole("cell")[5].textContent).toBe("—");
});

it("renders observed closing downside separately from final return",async()=>{
 vi.stubGlobal("fetch",vi.fn(async()=>({ok:true,json:async()=>({horizon:"SWING",counts:{OBSERVED:1},items:[
 {symbol:"PATH",exchange:"NSE",observed_date:"2026-10-01",published_at:"2026-10-02T10:00:00Z",maturity_date:"2026-10-16",status:"OBSERVED",outcome:{entry_date:"2026-10-05",exit_date:"2026-10-16",observed_price_return_pct:10,source_code:"TEST_PROVIDER",evidence_version:"WATCH-SESSION-EVIDENCE-2",calendar_status:"STORED_SESSIONS_MATCHED",corporate_action_status:"NO_RECORDED_CROSSING_ACTION",observations:10,risk_path:{version:"WATCH-CLOSE-PATH-1",worst_close_from_entry_percent:-10,best_close_from_entry_percent:20,peak_to_trough_close_drawdown_percent:-25}}}
 ],notice:"Gross close marks."})})));
 render(<WatchOutcomeHistory horizon="SWING"/>);
 expect(await screen.findByText(/-10\.00% from entry/)).toBeTruthy();
 expect(screen.getByText(/-25\.00% peak-to-trough/)).toBeTruthy();
 expect(screen.getByText(/10\.00% · 2026-10-05/)).toBeTruthy();
});
