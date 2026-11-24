/** @vitest-environment jsdom */
import {afterEach,expect,it} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import AutomaticInstitutionalActivity from "./AutomaticInstitutionalActivity";
afterEach(cleanup);
it("keeps aggregate provider flow units separate and shows unavailable DII evidence",()=>{
 render(<AutomaticInstitutionalActivity data={{status:"PARTIAL_PROVIDER_EVIDENCE",participants:{FII:{status:"RECENT",retrieved_at:null,endpoint:"/v2/market/fii",records:[{trade_date:"2026-11-23",observed_at:"2026-11-23T10:00:00Z",buy_amount:"120",sell_amount:"100",net_amount:"20"}]},DII:{status:"UNAVAILABLE",retrieved_at:null,endpoint:"/v2/market/dii",records:[]}},paired_five_date_window:null,notice:"Not stock-specific transactions."}}/>);
 expect(screen.getByText("Net buying: 20")).toBeTruthy();
 expect(screen.getByText(/No recent usable observation/)).toBeTruthy();
 expect(screen.getByText(/provider-reported units/)).toBeTruthy();
 expect(screen.queryByText(/five matched dates/)).toBeNull();
});
