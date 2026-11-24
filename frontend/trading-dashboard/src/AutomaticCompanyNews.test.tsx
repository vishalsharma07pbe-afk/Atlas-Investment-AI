/** @vitest-environment jsdom */
import {afterEach,expect,it} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import AutomaticCompanyNews from "./AutomaticCompanyNews";
afterEach(cleanup);
it("shows source-linked topic observations without inferred sentiment",()=>{
 render(<AutomaticCompanyNews evidence={{status:"REVIEW_AVAILABLE",retrieved_at:"2026-11-24T10:00:00Z",articles:[{id:"a",headline:"Company announces quarterly results",url:"https://example.org/report",published_at:"2026-11-24T09:00:00Z",topics:["EARNINGS"],sentiment:"NOT_ANALYZED",source_provider:"UPSTOX_NEWS"}],notice:"Claims unverified."}}/>);
 expect(screen.getByText("Company announces quarterly results").closest("a")?.getAttribute("href")).toBe("https://example.org/report");
 expect(screen.getByText(/Sentiment not analyzed/)).toBeTruthy();
 expect(screen.getByText("Claims unverified.")).toBeTruthy();
});
