// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import MutualFundHoldings from "./MutualFundHoldings";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

const fund={
  id:1,symbol:"TEST-FUND",asset_type:"MUTUAL_FUND",quantity:2,average_cost:100,
  last_price:null,invested:200,market_value:null,unrealized_pnl:null,price_as_of:null
};
const stock={...fund,id:2,symbol:"TEST-STOCK",asset_type:"EQUITY",last_price:110,market_value:220,unrealized_pnl:20};

describe("MutualFundHoldings",()=>{
  it("shows only fund holdings and warns when NAV is missing",()=>{
    render(<MutualFundHoldings holdings={[fund,stock]}/>);
    fireEvent.click(screen.getByRole("button",{name:/Overview/}));
    expect(screen.getAllByText("TEST-FUND")).toHaveLength(2);
    expect(screen.queryByText("TEST-STOCK")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("1 fund position");
    expect(screen.getByText(/Benchmark returns, expense ratios/)).toBeTruthy();
  });
  it("renders empty state without inventing values",()=>{
    render(<MutualFundHoldings holdings={[]}/>);
    fireEvent.click(screen.getByRole("button",{name:/Overview/}));
    expect(screen.getAllByText(/No mutual fund holdings saved/)).toHaveLength(2);
    expect(screen.getByText("Funds owned")).toBeTruthy();
  });
});

it("opens a dedicated fund editor directly and saves existing units with exact scheme code",async()=>{
  vi.spyOn(globalThis,"fetch").mockImplementation(async()=>new Response(JSON.stringify([{scheme_code:123456,scheme_name:"Example Direct Growth",nav:120,nav_date:"2026-11-25"}]),{status:200}));
  const save=vi.fn().mockResolvedValue(undefined);
  render(<MutualFundHoldings holdings={[]} onSave={save}/>);
  fireEvent.click(screen.getByRole("button",{name:/Add mutual fund holding/}));
  expect(screen.queryByLabelText("Asset type")).toBeNull();
  fireEvent.change(screen.getByLabelText("Symbol"),{target:{value:"Example"}});
  fireEvent.click(await screen.findByText("Example Direct Growth"));
  fireEvent.change(screen.getByLabelText("Quantity"),{target:{value:"12.5"}});
  fireEvent.change(screen.getByLabelText("Average cost"),{target:{value:"100"}});
  fireEvent.click(screen.getByRole("button",{name:/Save holding/}));
  await waitFor(()=>expect(save).toHaveBeenCalledWith({symbol:"123456",assetType:"MUTUAL_FUND",quantity:12.5,averageCost:100,lastPrice:120,notes:"Example Direct Growth"}));
  expect(await screen.findByText(/Fund holding saved/)).toBeTruthy();
});
it("shows fund name and opens an existing position for total-unit editing",()=>{
  render(<MutualFundHoldings holdings={[{...fund,symbol:"123456",notes:"Example Direct Growth"}]} onSave={vi.fn()}/>);
  fireEvent.click(screen.getByRole("button",{name:/My holdings/}));
  expect(screen.getAllByText("Example Direct Growth")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button",{name:"Edit holding"}));
  expect((screen.getByLabelText("Symbol") as HTMLInputElement).value).toBe("123456");
  expect((screen.getByLabelText("Quantity") as HTMLInputElement).value).toBe("2");
});

it("reports the actual fund refresh outcome",async()=>{
 const refresh=vi.fn().mockResolvedValue({updated:0,total:1});
 render(<MutualFundHoldings holdings={[fund]} onSave={vi.fn()} onRefresh={refresh}/>);
 fireEvent.click(screen.getByRole("button",{name:"Refresh saved NAVs"}));
 expect(await screen.findByText(/Refreshed 0 of 1 saved fund valuations/)).toBeTruthy();
 expect(refresh).toHaveBeenCalledOnce();
});

it("calculates weighted purchase NAV from total cost and allotted units",async()=>{
  vi.spyOn(globalThis,"fetch").mockImplementation(async()=>new Response(JSON.stringify([{scheme_code:123456,scheme_name:"Example Growth",nav:120,nav_date:"2026-11-25"}]),{status:200}));
  const save=vi.fn().mockResolvedValue(undefined);
  render(<MutualFundHoldings holdings={[]} onSave={save}/>);
  fireEvent.click(screen.getByRole("button",{name:/Add mutual fund holding/}));
  fireEvent.change(screen.getByLabelText("Symbol"),{target:{value:"Example"}});
  fireEvent.click(await screen.findByText("Example Growth"));
  fireEvent.change(screen.getByLabelText("Quantity"),{target:{value:"12.5"}});
  fireEvent.change(screen.getByLabelText("Purchase cost entry"),{target:{value:"TOTAL"}});
  fireEvent.change(screen.getByLabelText("Total invested"),{target:{value:"1250"}});
  fireEvent.click(screen.getByRole("button",{name:/Save holding/}));
  await waitFor(()=>expect(save).toHaveBeenCalledWith(expect.objectContaining({symbol:"123456",quantity:12.5,averageCost:100})));
});
