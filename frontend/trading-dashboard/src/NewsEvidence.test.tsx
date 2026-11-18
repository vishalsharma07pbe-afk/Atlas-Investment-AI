// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import NewsEvidence from "./NewsEvidence";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("NewsEvidence",()=>{
  it("never fetches articles automatically",()=>{
    const fetchMock=vi.fn();vi.stubGlobal("fetch",fetchMock);
    render(<NewsEvidence/>);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(/does not retrieve, verify or classify/)).toBeTruthy();
  });
  it("shows an unavailable state when the evidence service rejects data",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false,status:422}));
    render(<NewsEvidence/>);
    fireEvent.change(screen.getByRole("textbox",{name:"News headline"}),{target:{value:"Synthetic headline for testing"}});
    fireEvent.change(screen.getByRole("textbox",{name:"Publisher"}),{target:{value:"Test publisher"}});
    fireEvent.change(screen.getByRole("textbox",{name:"Article URL"}),{target:{value:"https://example.com/test"}});
    fireEvent.change(screen.getByLabelText("Publication date and time"),{target:{value:"2026-11-12T10:00"}});
    fireEvent.click(screen.getByRole("button",{name:"Check news evidence"}));
    await waitFor(()=>expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.queryByText("FRESH")).toBeNull();
  });
});
