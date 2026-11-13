// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundSchemeSearch from "./MutualFundSchemeSearch";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("Scheme discovery",()=>{
 it("searches supplied snapshot and displays exact code without modifying holdings",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({schemes:[{scheme_code:"12345",scheme_name:"Alpha Direct Growth",nav:12.5,as_of:"2026-11-13",status:"RECENT"}],matches_total:1,truncated:false,source:{verification:"USER_SUPPLIED_UNVERIFIED"},notice:"User-supplied"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundSchemeSearch/>);
  fireEvent.change(screen.getByLabelText("NAV snapshot text"),{target:{value:"12345;A;B;Alpha Direct Growth;12.5;13-Nov-2026"}});
  fireEvent.change(screen.getByLabelText("Scheme name or code"),{target:{value:"Direct Growth"}});
  fireEvent.click(screen.getByRole("button",{name:"Search snapshot"}));
  await waitFor(()=>expect(screen.getByText("Alpha Direct Growth")).toBeTruthy());
  expect(screen.getByText("12345")).toBeTruthy();
  expect(JSON.parse(fetchMock.mock.calls[0][1].body).query).toBe("Direct Growth");
 });
});
