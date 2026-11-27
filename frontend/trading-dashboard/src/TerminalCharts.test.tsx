/** @vitest-environment jsdom */
import {cleanup,render,screen,fireEvent} from "@testing-library/react";
import {afterEach,expect,it} from "vitest";
import {ValueHistory,EvidenceBars,MarketTiles} from "./TerminalCharts";
afterEach(cleanup);
it("retains missing observations as gaps and renders recorded dates",()=>{
 const {container}=render(<ValueHistory points={[{date:"2026-11-01",value:100},{date:"2026-11-02",value:null},{date:"2026-11-03",value:120}]}/>);
 expect(screen.getByRole("img",{name:"Dated recorded portfolio values"})).toBeTruthy();
 expect(container.querySelectorAll("svg circle")).toHaveLength(2);
 expect(container.querySelectorAll("svg line[stroke='var(--accent)']")).toHaveLength(0);
 fireEvent.click(screen.getByRole("button",{name:"All"}));
 expect(screen.getByRole("button",{name:"All"}).getAttribute("aria-pressed")).toBe("true");
});
it("does not manufacture history or a missing return",()=>{
 render(<><ValueHistory points={[]}/><EvidenceBars title="Returns" rows={[{label:"1Y",value:null},{label:"3Y",value:-4}]}/></>);
 expect(screen.getByText("No complete valuations in this period")).toBeTruthy();
 expect(screen.getByText("—")).toBeTruthy();
 expect(screen.getByText("-4.00%")).toBeTruthy();
});

it("shows dated unique market tiles without inventing a missing movement",()=>{
 const {container}=render(<MarketTiles title="Observed sample" period="20-day momentum" items={[{key:"NSE:1",label:"ALPHA",exchange:"NSE",date:"2026-11-25",value:2},{key:"NSE:1",label:"ALPHA",exchange:"NSE",date:"2026-11-25",value:2},{key:"NSE:2",label:"BETA",exchange:"NSE",date:"2026-11-25",value:null}]}/>);
 expect(screen.getAllByText("ALPHA")).toHaveLength(1);
 expect(screen.getByText("+2.00%")).toBeTruthy();
 expect(screen.getByText("—")).toBeTruthy();
 expect(container.querySelectorAll(".tile-up")).toHaveLength(1);
});
