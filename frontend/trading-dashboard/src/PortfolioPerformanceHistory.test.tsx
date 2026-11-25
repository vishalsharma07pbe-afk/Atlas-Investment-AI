// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,beforeEach,expect,it,vi} from "vitest";
import PortfolioPerformanceHistory from "./PortfolioPerformanceHistory";

beforeEach(()=>vi.restoreAllMocks());
afterEach(cleanup);

it("shows measured performance and records an external cash flow",async()=>{
  const fetchMock=vi.spyOn(globalThis,"fetch").mockImplementation(async(input,init)=>{
    const url=String(input);
    if(url.endsWith("/performance"))return new Response(JSON.stringify({transaction_count:2,snapshot_count:3,xirr_percent:10,maximum_drawdown_percent:-4.25,xirr_status:"AVAILABLE",drawdown_status:"AVAILABLE",methodology:"Measured from dated records."}),{status:200,headers:{"Content-Type":"application/json"}});
    if(init?.method==="POST")return new Response(JSON.stringify({saved:true}),{status:200,headers:{"Content-Type":"application/json"}});
    return new Response(null,{status:404});
  });
  render(<PortfolioPerformanceHistory/>);
  expect(await screen.findByText("10.00%")).toBeTruthy();
  expect(screen.getByText("-4.25%")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Amount (₹)"),{target:{value:"5000"}});
  fireEvent.click(screen.getByRole("button",{name:"Save cash flow"}));
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith("/api/v1/portfolio/history/transactions",expect.objectContaining({method:"POST"})));
});

it("explains performance exclusions, refuses aged snapshots and clears stale results",async()=>{
  let offline=false;
  vi.spyOn(globalThis,"fetch").mockImplementation(async(input)=>{
    if(String(input).endsWith("/snapshots/current"))return new Response(JSON.stringify({recorded:false}),{status:200});
    if(offline)return new Response(null,{status:503});
    return new Response(JSON.stringify({transaction_count:3,snapshot_count:2,external_cash_flow_count:2,external_flows_after_valuation:1,incomplete_snapshot_count:0,future_snapshot_count:0,valuation_through:"2026-11-20",xirr_percent:12,maximum_drawdown_percent:null,xirr_status:"AVAILABLE",drawdown_status:"UNAVAILABLE_EXTERNAL_FLOWS_REQUIRE_FLOW_ADJUSTED_HISTORY",methodology:"Recorded valuation."}),{status:200});
  });
  const view=render(<PortfolioPerformanceHistory revision={0}/>);
  expect(await screen.findByText("12.00%")).toBeTruthy();
  expect(screen.getByText("External flows require flow-adjusted history.")).toBeTruthy();
  expect(screen.getByText(/1 later external flows excluded/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Record today's value"}));
  expect(await screen.findByText(/Valuation not recorded/)).toBeTruthy();
  offline=true;
  view.rerender(<PortfolioPerformanceHistory revision={1}/>);
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.queryByText("12.00%")).toBeNull();
});
