// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import ProviderQuality from "./ProviderQuality";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("never calls provider until user requests review",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"REVIEW_ONLY",requested:1,succeeded:1,failed:0,
    results:[{instrument_key:"NSE_EQ|INE848E01016",status:"REVIEW_REQUIRED",candle_count:1,
      latest_trade_date:"2026-11-12",age_calendar_days:1,quality_flags:["ADJUSTMENT_UNVERIFIED"]}],
    notice:"Not persisted."
  })});
  vi.stubGlobal("fetch",fetchMock);
  render(<ProviderQuality/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Provider instrument keys"),{target:{value:"NSE_EQ|INE848E01016"}});
  fireEvent.click(screen.getByRole("button",{name:"Review provider data"}));
  await waitFor(()=>expect(screen.getByText(/Reviewed 1/)).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/ADJUSTMENT UNVERIFIED/)).toBeTruthy();
});
it("blocks duplicate keys in the browser",()=>{
  const fetchMock=vi.fn();
  vi.stubGlobal("fetch",fetchMock);
  render(<ProviderQuality/>);
  fireEvent.change(screen.getByLabelText("Provider instrument keys"),{target:{value:"NSE_EQ|INE848E01016\nNSE_EQ|INE848E01016"}});
  fireEvent.click(screen.getByRole("button",{name:"Review provider data"}));
  expect(screen.getByRole("alert").textContent).toContain("distinct");
  expect(fetchMock).not.toHaveBeenCalled();
});
