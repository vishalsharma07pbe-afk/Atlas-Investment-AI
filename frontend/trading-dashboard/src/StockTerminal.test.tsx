/** @vitest-environment jsdom */
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {afterEach,describe,expect,it,vi} from "vitest";
import StockExplorer,{dailyPriceChange} from "./StockExplorer";
vi.mock("lightweight-charts",()=>({
 ColorType:{Solid:"solid"},CandlestickSeries:"candles",HistogramSeries:"volume",LineSeries:"line",createSeriesMarkers:vi.fn(),
 createChart:()=>({addSeries:()=>({setData:vi.fn(),priceScale:()=>({applyOptions:vi.fn()})}),subscribeCrosshairMove:vi.fn(),timeScale:()=>({fitContent:vi.fn(),setVisibleRange:vi.fn()}),applyOptions:vi.fn(),remove:vi.fn()})
}));
vi.mock("./BacktestPanel",()=>({default:()=>null}));
vi.mock("./RiskQualification",()=>({default:()=>null}));
vi.mock("./ResearchAlerts",()=>({default:()=>null}));
vi.mock("./EquityResearchDashboard",()=>({default:({initialQuery}:{initialQuery:string})=><span>Company lookup: {initialQuery}</span>}));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const item={id:1,exchange:"NSE",symbol:"TEST",series:"EQ",isin:"INE000000001",security_name:"Test company",listing_status:"ACTIVE",source:"TEST",source_revision:null};
const candles=[{trade_date:"2026-11-24",open:99,high:105,low:98,close:100,volume:1000,adjustment_status:"RAW_UNADJUSTED",source_code:"TEST",received_at:"2026-11-24"},{trade_date:"2026-11-25",open:101,high:111,low:100,close:110,volume:2000,adjustment_status:"RAW_UNADJUSTED",source_code:"TEST",received_at:"2026-11-25"}];
describe("chart-first stock terminal",()=>{
 it("calculates only comparable recorded closes",()=>{
  expect(dailyPriceChange(candles)).toEqual({amount:10,percent:10});
  expect(dailyPriceChange([candles[0],{...candles[1],adjustment_status:"ADJUSTED"}])).toBeNull();
  expect(dailyPriceChange([candles[0],{...candles[1],source_code:"OTHER"}])).toBeNull();
  expect(dailyPriceChange([candles[0]])).toBeNull();
 });
 it("renders the chart ahead of advanced tools and exposes chart controls",async()=>{
  vi.stubGlobal("fetch",vi.fn(async(url:string)=>({ok:true,json:async()=>url.startsWith("/api/v1/instruments?")?[item]:url.endsWith("/summary")?{research:null,notice:"test"}:url.includes("/resolve?")?{subscription_ready:false,blocker:"NOT_CONFIGURED"}:{instrument:item,status:"AVAILABLE",as_of:"2026-11-25",candles,indicators:{},patterns:[]}})));
  render(<StockExplorer/>);
  fireEvent.change(screen.getByRole("textbox",{name:"Instrument search"}),{target:{value:"TEST"}});
  fireEvent.click(await screen.findByRole("button",{name:/NSE:TEST/}));
  const chart=await screen.findByRole("region",{name:"Stock price and volume chart"});
  expect(screen.getByText(/10.00%.*previous recorded close/)).toBeTruthy();
  expect(chart.compareDocumentPosition(screen.getByText("Research alerts"))&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Line",exact:true}));
  expect(screen.getByRole("button",{name:"Line",exact:true}).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button",{name:"1M",exact:true}));
  expect(screen.getByRole("button",{name:"1M",exact:true}).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button",{name:"Expand chart"}));
  expect(screen.getByRole("button",{name:"Reduce chart"})).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Open company research"}));
  await waitFor(()=>expect(screen.getByText("Company lookup: TEST")).toBeTruthy());
 });
});
