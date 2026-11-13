// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import ResearchOutcomes from "./ResearchOutcomes";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("runs only on explicit request and labels unverified outcomes",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"HISTORICAL_OUTCOME_REVIEW_ONLY",reports_reviewed:1,horizon_days:90,
    outcomes:[{source_name:"Groww",report_id:"r1",rating:"BUY",published_on:"2026-01-01",
      horizon_end:"2026-04-01",observed_price_return_pct_unverified:"10",
      blockers:["PRICE_PROVENANCE_AND_ADJUSTMENTS_UNVERIFIED"]}],
    notice:"No verified analyst accuracy."
  })});
  vi.stubGlobal("fetch",fetchMock);
  render(<ResearchOutcomes/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Outcome instrument identifier"),{target:{value:"INE848E01016"}});
  fireEvent.click(screen.getByRole("button",{name:"Review historical outcomes"}));
  await waitFor(()=>expect(screen.getByText(/Reports reviewed: 1/)).toBeTruthy());
  expect(screen.getByText("10%")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
it("does not submit malformed price arrays",()=>{
  const fetchMock=vi.fn();
  vi.stubGlobal("fetch",fetchMock);
  render(<ResearchOutcomes/>);
  fireEvent.change(screen.getByLabelText("Outcome instrument identifier"),{target:{value:"INE848E01016"}});
  fireEvent.change(screen.getByLabelText("Outcome prices JSON"),{target:{value:"invalid"}});
  fireEvent.click(screen.getByRole("button",{name:"Review historical outcomes"}));
  expect(screen.getByRole("alert").textContent).toContain("JSON arrays");
  expect(fetchMock).not.toHaveBeenCalled();
});
