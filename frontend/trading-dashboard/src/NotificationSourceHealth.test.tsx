// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import NotificationSourceHealth from "./NotificationSourceHealth";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("fetches IPO source diagnostics only after explicit click",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"LOCAL_SOURCE_HEALTH",configured_sources:1,live_feed_connected:false,
    notice:"Operator-supplied only.",sources:[{source_name:"Sample publisher",
      enabled:true,permission_declared:true,alert_count:1,
      latest_publication_at:"2026-11-01T12:00:00Z",latest_subscription_as_of:"2026-11-01T11:00:00Z",
      subscription_snapshot_stale:true,status:"SUBSCRIPTION_STALE"}]
  })});
  vi.stubGlobal("fetch",fetchMock);
  render(<NotificationSourceHealth/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Check source health"}));
  await waitFor(()=>expect(screen.getByText("Sample publisher")).toBeTruthy());
  expect(screen.getByText("SUBSCRIPTION SNAPSHOT STALE")).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
