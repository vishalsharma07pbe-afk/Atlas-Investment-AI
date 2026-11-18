// @vitest-environment jsdom
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import ResearchSourceAudit from "./ResearchSourceAudit";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("never fetches documents and only sends manifests on click",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"MANIFEST_REVIEW_ONLY",documents_reviewed:1,entries:[{
      source:"GROWW",document_id:"test",status:"QUARANTINE_REQUIRED",
      blockers:["DOCUMENT_CONTENT_NOT_INDEPENDENTLY_VERIFIED"]}],
    notice:"No URL fetched."
  })});
  vi.stubGlobal("fetch",fetchMock);
  render(<ResearchSourceAudit/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Research source manifests"),{target:{value:'[{"source":"GROWW"}]'}});
  fireEvent.click(screen.getByRole("button",{name:"Audit research sources"}));
  await waitFor(()=>expect(screen.getByText(/Documents reviewed: 1/)).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByText("QUARANTINE_REQUIRED")).toBeTruthy();
});
it("rejects empty manifest lists",()=>{
  const fetchMock=vi.fn();
  vi.stubGlobal("fetch",fetchMock);
  render(<ResearchSourceAudit/>);
  fireEvent.click(screen.getByRole("button",{name:"Audit research sources"}));
  expect(screen.getByRole("alert").textContent).toContain("non-empty");
  expect(fetchMock).not.toHaveBeenCalled();
});
