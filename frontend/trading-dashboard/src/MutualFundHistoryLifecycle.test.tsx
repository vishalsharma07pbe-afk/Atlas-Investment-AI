// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundHoldings from "./MutualFundHoldings";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const success={ok:true,json:async()=>({scheme_name:"Fund A",latest_nav:{as_of:"2025-01-02",nav:11,status:"HISTORICAL"},trailing_returns_pct:{},import:{rows_accepted:2,stored:false},source:{verification:"USER_SUPPLIED_UNVERIFIED"}})};
function fill(){
 fireEvent.change(screen.getByLabelText("Scheme code"),{target:{value:"12345"}});
 fireEvent.change(screen.getByLabelText("Scheme name"),{target:{value:"Fund A"}});
 fireEvent.change(screen.getByLabelText("Source attribution"),{target:{value:"Local CSV"}});
 fireEvent.change(screen.getByLabelText("Historical NAV CSV"),{target:{value:"scheme_code,as_of,nav\n12345,2025-01-01,10\n12345,2025-01-02,11"}});
}
describe("NAV import validation lifecycle",()=>{
 it("removes a validated scheme when its source or CSV is edited",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockResolvedValue(success));
  render(<MutualFundHoldings holdings={[]}/>);
  fill();fireEvent.click(screen.getByRole("button",{name:"Import and analyze history"}));
  await waitFor(()=>expect(screen.getByText("Validated NAV histories in this session (1/5)")).toBeTruthy());
  fireEvent.change(screen.getByLabelText("Source attribution"),{target:{value:"Changed source"}});
  expect(screen.getByText("Validated NAV histories in this session (0/5)")).toBeTruthy();
  expect(screen.queryByRole("button",{name:"Analyze validated import"})).toBeNull();
 });
 it("ignores an import response that arrives after the user changes the CSV",async()=>{
  let resolve!: (value:typeof success)=>void;
  const fetchMock=vi.fn().mockImplementation(()=>new Promise<typeof success>(done=>{resolve=done;}));
  vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundHoldings holdings={[]}/>);
  fill();fireEvent.click(screen.getByRole("button",{name:"Import and analyze history"}));
  fireEvent.change(screen.getByLabelText("Historical NAV CSV"),{target:{value:"scheme_code,as_of,nav\n12345,2025-01-01,12"}});
  resolve(success);
  await waitFor(()=>expect(screen.getByText("Validated NAV histories in this session (0/5)")).toBeTruthy());
  expect(screen.queryByRole("button",{name:"Analyze validated import"})).toBeNull();
  expect(screen.queryByText(/Accepted 2 NAV records/)).toBeNull();
 });
});
