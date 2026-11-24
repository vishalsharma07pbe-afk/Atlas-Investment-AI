// @vitest-environment jsdom
import {fireEvent,render,screen,waitFor} from "@testing-library/react";
import {beforeEach,expect,it,vi} from "vitest";
import PortfolioPerformanceHistory from "./PortfolioPerformanceHistory";

beforeEach(()=>vi.restoreAllMocks());

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
