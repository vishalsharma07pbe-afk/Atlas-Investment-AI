// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import IpoImportHistory from "./IpoImportHistory";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("does not fetch import history until explicitly opened",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"LOCAL_AUDIT_HISTORY",total:1,notice:"Local operator records only",
    attempts:[{attempted_at:"2026-11-13T12:00:00Z",mode:"DRY_RUN",outcome:"SUCCESS",
      error_category:null,added:2,updated:0,retained:2}]})});
  vi.stubGlobal("fetch",fetchMock);
  render(<IpoImportHistory/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button",{name:"Check provider import history"}));
  await waitFor(()=>expect(screen.getByText("SUCCESS · DRY_RUN")).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/Added 2/)).toBeTruthy();
});
