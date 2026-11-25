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

it("shows automatic capture provenance without presenting recorded prices as market closes",async()=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue(new Response(JSON.stringify({
    transaction_count:0,snapshot_count:2,xirr_percent:null,maximum_drawdown_percent:null,
    xirr_status:"UNAVAILABLE",drawdown_status:"UNAVAILABLE",methodology:"Recorded valuations.",
    automatic_snapshot_count:1,latest_capture_source:"AUTO_RECORDED",
    latest_oldest_price_at:"2026-11-24T10:00:00Z",latest_newest_price_at:"2026-11-25T10:00:00Z",
    valuation_through:"2026-11-25"
  }),{status:200}));
  render(<PortfolioPerformanceHistory/>);
  expect(await screen.findByText(/Automatic evening valuation records: 1/)).toBeTruthy();
  expect(screen.getByText(/Latest capture: Automatic/)).toBeTruthy();
  expect(screen.getByText(/not certified market closes/)).toBeTruthy();
});

it("shows linked cash-flow-adjusted estimates separately from XIRR and raw drawdown",async()=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue(new Response(JSON.stringify({
    transaction_count:1,snapshot_count:3,xirr_percent:null,maximum_drawdown_percent:null,
    xirr_status:"UNAVAILABLE",drawdown_status:"UNAVAILABLE_EXTERNAL_FLOWS_REQUIRE_FLOW_ADJUSTED_HISTORY",
    flow_adjusted_status:"AVAILABLE_ESTIMATE",flow_adjusted_return_percent:8.5,flow_adjusted_drawdown_percent:-3.25,
    flow_adjusted_interval_count:2,flow_adjusted_cash_flow_count:1,flow_adjusted_max_interval_days:2,
    flow_adjusted_from:"2026-11-20",flow_adjusted_through:"2026-11-23",
    flow_adjusted_methodology:"Linked Modified Dietz estimate.",methodology:"Recorded valuations."
  }),{status:200}));
  render(<PortfolioPerformanceHistory/>);
  expect(await screen.findByText("8.50%")).toBeTruthy();
  expect(screen.getByText("-3.25%")).toBeTruthy();
  expect(screen.getByText("Non-annualized estimate, not exact TWR")).toBeTruthy();
  expect(screen.getByText(/longest gap 2 days/)).toBeTruthy();
});

it("withholds adjusted performance for sparse valuations",async()=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue(new Response(JSON.stringify({
    transaction_count:0,snapshot_count:2,xirr_percent:null,maximum_drawdown_percent:null,
    xirr_status:"UNAVAILABLE",drawdown_status:"UNAVAILABLE",
    flow_adjusted_status:"UNAVAILABLE_VALUATION_GAPS",flow_adjusted_return_percent:null,
    flow_adjusted_drawdown_percent:null,methodology:"Recorded valuations."
  }),{status:200}));
  render(<PortfolioPerformanceHistory/>);
  expect(await screen.findByText("Valuation intervals exceed seven calendar days.")).toBeTruthy();
});

it("distinguishes exact-date price reference from portfolio estimates and unavailable windows",async()=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue(new Response(JSON.stringify({
    transaction_count:0,snapshot_count:31,xirr_percent:null,maximum_drawdown_percent:null,
    xirr_status:"UNAVAILABLE",drawdown_status:"UNAVAILABLE",
    benchmark_reference:"NIFTY 50 price index (not TRI)",
    rolling_performance:[
      {days:30,status:"AVAILABLE_ESTIMATE",returnPercent:10,drawdownPercent:-2,benchmarkStatus:"AVAILABLE_PRICE_REFERENCE",benchmarkReturnPercent:5,relativePercentagePoints:5},
      {days:90,status:"UNAVAILABLE_EXACT_START_DATE",returnPercent:null,drawdownPercent:null,benchmarkStatus:"UNAVAILABLE_PORTFOLIO_WINDOW"}
    ],
    weekly_risk_estimate:{status:"UNAVAILABLE_EXACT_WEEKLY_HISTORY",weeklyObservations:0},
    methodology:"Recorded valuations."
  }),{status:200}));
  render(<PortfolioPerformanceHistory/>);
  expect(await screen.findByText("10.00%")).toBeTruthy();
  expect(screen.getByText("Index price return: 5.00%")).toBeTruthy();
  expect(screen.getByText("Relative difference: 5.00 pp")).toBeTruthy();
  expect(screen.getByText("Exact starting valuation missing.")).toBeTruthy();
  expect(screen.getByText(/Insufficient contiguous weekly evidence/)).toBeTruthy();
});

it("shows relative risk estimates as a review flag, not a trading signal",async()=>{
  vi.spyOn(globalThis,"fetch").mockResolvedValue(new Response(JSON.stringify({
    transaction_count:0,snapshot_count:14,xirr_percent:null,maximum_drawdown_percent:null,
    xirr_status:"UNAVAILABLE",drawdown_status:"UNAVAILABLE",methodology:"Recorded valuations.",
    benchmark_risk_estimate:{status:"AVAILABLE_PRICE_REFERENCE_ESTIMATE",matchedWeeks:13,
      from:"2026-08-21",through:"2026-11-20",portfolioReturnPercent:1,benchmarkReturnPercent:8,
      relativePercentagePoints:-7,beta:0.75,annualizedTrackingErrorPercent:4,informationRatio:-1.2,
      attentionStatus:"REVIEW_RELATIVE_LAG"}
  }),{status:200}));
  render(<PortfolioPerformanceHistory/>);
  expect(await screen.findByText(/recorded portfolio lagged/)).toBeTruthy();
  expect(screen.getByText("-7.00 pp")).toBeTruthy();
  expect(screen.getByText("0.75")).toBeTruthy();
  expect(screen.getByText(/not a buy or sell signal/)).toBeTruthy();
});
