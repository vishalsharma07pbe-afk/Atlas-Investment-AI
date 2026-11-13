// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundHoldings from "./MutualFundHoldings";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

describe("Validated multi-fund comparison workflow",()=>{
 it("imports two funds and compares server-validated CSVs without manual JSON",async()=>{
  const importResponse=(name:string)=>({ok:true,json:async()=>({scheme_name:name,latest_nav:{as_of:"2025-01-02",nav:11,status:"HISTORICAL"},trailing_returns_pct:{},import:{rows_accepted:2,stored:false},source:{verification:"USER_SUPPLIED_UNVERIFIED"}})});
  const fetchMock=vi.fn()
   .mockResolvedValueOnce(importResponse("Fund A"))
   .mockResolvedValueOnce(importResponse("Fund B"))
   .mockResolvedValueOnce({ok:true,json:async()=>({funds:[],same_latest_nav_date:true,comparison_status:"SAME_AS_OF_DATE",notice:"User-supplied"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundHoldings holdings={[]}/>);
  for(const [code,name] of [["12345","Fund A"],["67890","Fund B"]]){
   fireEvent.change(screen.getByLabelText("Scheme code"),{target:{value:code}});
   fireEvent.change(screen.getByLabelText("Scheme name"),{target:{value:name}});
   fireEvent.change(screen.getByLabelText("Source attribution"),{target:{value:"Authorized CSV"}});
   fireEvent.change(screen.getByLabelText("Historical NAV CSV"),{target:{value:`scheme_code,as_of,nav\n${code},2025-01-01,10\n${code},2025-01-02,11`}});
   fireEvent.click(screen.getByRole("button",{name:"Import and analyze history"}));
   await waitFor(()=>expect(screen.getByText(new RegExp(`Validated NAV histories in this session \\\(${code==="12345"?"1":"2"}/5\\\)`))).toBeTruthy());
  }
  fireEvent.click(screen.getByRole("button",{name:"Compare validated imports"}));
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(3));
  const [url,options]=fetchMock.mock.calls[2];
  expect(url).toContain("/compare");
  const payload=JSON.parse(options.body);
  expect(payload.funds.map((f:{scheme_code:string})=>f.scheme_code)).toEqual(["12345","67890"]);
  expect(payload.funds[0].csv_text).toContain("12345,2025-01-01,10");
  expect(payload.funds[1].csv_text).toContain("67890,2025-01-02,11");
 });
});
