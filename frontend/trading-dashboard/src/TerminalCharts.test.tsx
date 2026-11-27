/** @vitest-environment jsdom */
import {cleanup,render,screen,fireEvent} from "@testing-library/react";
import {afterEach,expect,it} from "vitest";
import {ValueHistory,EvidenceBars} from "./TerminalCharts";
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
