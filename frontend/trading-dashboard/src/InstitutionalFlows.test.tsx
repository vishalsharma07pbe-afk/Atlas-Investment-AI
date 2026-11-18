// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import InstitutionalFlows from "./InstitutionalFlows";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("InstitutionalFlows",()=>{
  it("requires user-provided records and does not fetch automatically",async()=>{
    const fetchMock=vi.fn();
    vi.stubGlobal("fetch",fetchMock);
    render(<InstitutionalFlows/>);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Analyze flow evidence"}));
    expect(screen.getByRole("alert").textContent).toContain("Provide a header");
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("submits CSV evidence and labels it unverified",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:true,json:async()=>({
      records:[{trade_date:"2026-11-12",market:"NSE",participant:"FII",
        net_crore_inr:"-20",direction:"NET_SELL",source_name:"Research note",verification:"USER_REPORTED"}],
      independent_verification:false,notice:"User-supplied only; not verified."
    })}));
    render(<InstitutionalFlows/>);
    fireEvent.change(screen.getByRole("textbox",{name:"Institutional flow CSV"}),{
      target:{value:"trade_date,market,participant,buy_crore_inr,sell_crore_inr,source_name\n2026-11-12,NSE,FII,100,120,Research note"}
    });
    fireEvent.click(screen.getByRole("button",{name:"Analyze flow evidence"}));
    await waitFor(()=>expect(screen.getByText("NET_SELL")).toBeTruthy());
    expect(screen.getByText(/User-supplied only/)).toBeTruthy();
  });
});
