// @vitest-environment jsdom
import React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import BrokerResearch from "./BrokerResearch";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it("compares user-submitted reports only after explicit action",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({
    status:"RESEARCH_COMPARISON_ONLY",fresh_provider_count:0,fresh_records:0,
    excluded_stale_or_superseded:0,rating_counts:{BUY:0,HOLD:0},targets:{median:null,minimum:null,maximum:null,count:0},
    research:[],notice:"No automatic broker feed.",blockers:[]
  })});
  vi.stubGlobal("fetch",fetchMock);
  render(<BrokerResearch/>);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Research instrument identifier"),{target:{value:"INE848E01016"}});
  fireEvent.click(screen.getByRole("button",{name:"Compare broker research"}));
  await waitFor(()=>expect(screen.getByText(/Fresh providers: 0/)).toBeTruthy());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/No automatic broker feed/)).toBeTruthy();
});
it("does not send malformed reports",()=>{
  const fetchMock=vi.fn();
  vi.stubGlobal("fetch",fetchMock);
  render(<BrokerResearch/>);
  fireEvent.change(screen.getByLabelText("Research instrument identifier"),{target:{value:"INE848E01016"}});
  fireEvent.change(screen.getByLabelText("Research records JSON"),{target:{value:"broken"}});
  fireEvent.click(screen.getByRole("button",{name:"Compare broker research"}));
  expect(screen.getByRole("alert").textContent).toContain("JSON array");
  expect(fetchMock).not.toHaveBeenCalled();
});
