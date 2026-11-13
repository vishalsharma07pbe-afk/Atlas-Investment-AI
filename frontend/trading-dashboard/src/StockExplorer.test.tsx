// @vitest-environment jsdom
import React from "react";
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import StockExplorer from "./StockExplorer";
import {App} from "./main";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

describe("StockExplorer",()=>{
  it("renders the truthful empty registry state",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:true,json:async()=>[]}));
    render(<StockExplorer/>);
    fireEvent.click(screen.getByRole("button",{name:"Search"}));
    await waitFor(()=>expect(fetch).toHaveBeenCalledWith("/api/v1/instruments?q=&limit=50"));
    expect(screen.getByText(/production registry is empty/i)).toBeTruthy();
    expect(screen.getByText(/No demonstration prices are shown/i)).toBeTruthy();
  });
});

describe("Liquid Glass appearance",()=>{
  it("maps panel opacity checkpoints to background alpha and keeps blur independent",()=>{
    localStorage.clear();
    vi.stubGlobal("fetch",vi.fn().mockRejectedValue(new Error("offline test")));
    const {container}=render(<App/>);
    fireEvent.click(screen.getByRole("button",{name:"Open appearance settings"}));
    const opacity=screen.getByLabelText("Panel opacity");
    const blur=screen.getByLabelText("Backdrop blur");
    const dashboard=container.querySelector(".dashboard") as HTMLElement;
    for(const value of [0,25,50,75,100]){
      fireEvent.change(opacity,{target:{value:String(value)}});
      expect(dashboard.style.getPropertyValue("--panel-alpha")).toBe((value/100).toFixed(2));
    }
    fireEvent.change(blur,{target:{value:"37"}});
    expect(dashboard.style.getPropertyValue("--panel-blur")).toBe("37px");
    fireEvent.change(opacity,{target:{value:"0"}});
    expect(dashboard.style.getPropertyValue("--panel-blur")).toBe("0px");
    expect(dashboard.dataset.panelClear).toBe("true");
  });

  it("supports Auto, Dark and Light theme modes",()=>{
    localStorage.clear();
    vi.stubGlobal("fetch",vi.fn().mockRejectedValue(new Error("offline test")));
    const {container}=render(<App/>);
    fireEvent.click(screen.getByRole("button",{name:"Open appearance settings"}));
    const dashboard=container.querySelector(".dashboard") as HTMLElement;
    fireEvent.click(screen.getByRole("button",{name:/dark/i}));
    expect(dashboard.dataset.theme).toBe("dark");
    fireEvent.click(screen.getByRole("button",{name:/light/i}));
    expect(dashboard.dataset.theme).toBe("light");
    fireEvent.click(screen.getByRole("button",{name:/auto/i}));
    expect(dashboard.dataset.theme).toBe("system");
  });
});
