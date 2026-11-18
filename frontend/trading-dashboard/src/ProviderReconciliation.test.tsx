// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import ProviderReconciliation from "./ProviderReconciliation";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("shows reconciliation blockers without automatically sending data",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"BLOCKED_FROM_AUTOMATIC_INGESTION",blockers:["INDEPENDENT_PROVENANCE_AUDIT_REQUIRED"],
    candles_reviewed:2,unmatched_session_count:0,notice:"No import."
  })});
  vi.stubGlobal("fetch",fetchMock);
  render(<ProviderReconciliation/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Reconciliation request JSON"),{target:{value:'{"sample":true}'}});
  fireEvent.click(screen.getByRole("button",{name:"Review reconciliation"}));
  await waitFor(()=>expect(screen.getByText(/Reviewed 2 candles/)).toBeTruthy());
  expect(screen.getByText(/INDEPENDENT PROVENANCE AUDIT REQUIRED/)).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
it("rejects malformed JSON without sending request",()=>{
  const fetchMock=vi.fn();
  vi.stubGlobal("fetch",fetchMock);
  render(<ProviderReconciliation/>);
  fireEvent.change(screen.getByLabelText("Reconciliation request JSON"),{target:{value:"invalid"}});
  fireEvent.click(screen.getByRole("button",{name:"Review reconciliation"}));
  expect(screen.getByRole("alert").textContent).toContain("valid reconciliation JSON");
  expect(fetchMock).not.toHaveBeenCalled();
});
