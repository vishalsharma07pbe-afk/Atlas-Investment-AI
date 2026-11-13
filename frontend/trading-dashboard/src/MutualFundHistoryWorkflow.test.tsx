// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundHoldings from "./MutualFundHoldings";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

describe("Mutual fund validated NAV workflow",()=>{
 it("passes validated imported NAV history directly into historical risk analysis",async()=>{
  const fetchMock=vi.fn()
   .mockResolvedValueOnce({ok:true,json:async()=>({scheme_name:"Example Fund",latest_nav:{as_of:"2025-01-02",nav:11,status:"HISTORICAL"},trailing_returns_pct:{},import:{rows_accepted:2,stored:false},source:{verification:"USER_SUPPLIED_UNVERIFIED"}})})
   .mockResolvedValueOnce({ok:true,json:async()=>({observations:2,first_date:"2025-01-01",last_date:"2025-01-02",cumulative_return_pct:10,annualized_return_pct:100,maximum_drawdown_pct:0,annualized_volatility_pct:null,volatility_status:"UNAVAILABLE_IRREGULAR_OR_INSUFFICIENT",notice:"NAV-only"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<MutualFundHoldings holdings={[]}/>);
  fireEvent.change(screen.getByLabelText("Scheme code"),{target:{value:"12345"}});
  fireEvent.change(screen.getByLabelText("Scheme name"),{target:{value:"Example Fund"}});
  fireEvent.change(screen.getByLabelText("Source attribution"),{target:{value:"Local CSV"}});
  fireEvent.change(screen.getByLabelText("Historical NAV CSV"),{target:{value:"scheme_code,as_of,nav\n12345,2025-01-01,10\n12345,2025-01-02,11"}});
  fireEvent.click(screen.getByRole("button",{name:"Import and analyze history"}));
  await waitFor(()=>expect(screen.getByRole("button",{name:"Analyze validated import"})).toBeTruthy());
  fireEvent.click(screen.getByRole("button",{name:"Analyze validated import"}));
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(2));
  const [url,options]=fetchMock.mock.calls[1];
  expect(url).toContain("historical-risk");
  expect(JSON.parse(options.body)).toEqual({scheme_code:"12345",source_name:"Local CSV",observations:[{as_of:"2025-01-01",nav:"10"},{as_of:"2025-01-02",nav:"11"}]});
 });
});
