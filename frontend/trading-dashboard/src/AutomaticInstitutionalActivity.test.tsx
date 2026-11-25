/** @vitest-environment jsdom */
import {afterEach,expect,it} from "vitest";
import {cleanup,render,screen,fireEvent} from "@testing-library/react";
import AutomaticInstitutionalActivity from "./AutomaticInstitutionalActivity";
afterEach(cleanup);
it("keeps aggregate provider flow units separate and shows unavailable DII evidence",()=>{
 render(<AutomaticInstitutionalActivity data={{status:"PARTIAL_PROVIDER_EVIDENCE",participants:{FII:{status:"RECENT",retrieved_at:null,endpoint:"/v2/market/fii",records:[{trade_date:"2026-11-23",observed_at:"2026-11-23T10:00:00Z",buy_amount:"120",sell_amount:"100",net_amount:"20"}]},DII:{status:"UNAVAILABLE",retrieved_at:null,endpoint:"/v2/market/dii",records:[]}},paired_five_date_window:null,notice:"Not stock-specific transactions."}}/>);
 expect(screen.getByText("Net buying: 20")).toBeTruthy();
 expect(screen.getByText(/No recent usable observation/)).toBeTruthy();
 expect(screen.getByText(/provider-reported units/)).toBeTruthy();
 expect(screen.queryByText(/five matched dates/)).toBeNull();
});

it("renders the actual disabled provider response with an empty participants object",()=>{
 render(<AutomaticInstitutionalActivity data={{status:"DISABLED_OR_NOT_AUTHORIZED",market:"NSE_CASH",unit:"PROVIDER_REPORTED",participants:{},paired_five_date_window:null,blockers:["RETAIL_FLOW_FEED_MISSING"]}}/>);
 expect(screen.getAllByText(/No recent usable observation/)).toHaveLength(2);
 expect(screen.queryByText(/Net buying:/)).toBeNull();
 expect(screen.queryByText(/five matched dates/)).toBeNull();
});
it("retains the available participant when the other is absent",()=>{
 render(<AutomaticInstitutionalActivity data={{status:"PARTIAL_PROVIDER_EVIDENCE",participants:{FII:{status:"RECENT",retrieved_at:null,endpoint:"/v2/market/fii",records:[{trade_date:"2026-11-23",observed_at:"2026-11-23T10:00:00Z",buy_amount:"120",sell_amount:"100",net_amount:"20"}]}}}}/>);
 expect(screen.getByText("Net buying: 20")).toBeTruthy();
 expect(screen.getByText(/No recent usable observation/)).toBeTruthy();
});

it("shows matched flow direction and opposition without implying consecutive sessions",()=>{
 const fii={net_amount:"-200",gross_amount:"1000",net_to_gross_percent:-20,net_buying_dates:0,net_selling_dates:5,balanced_dates:0,direction_consistency:"NET_SELLING_MAJORITY"};
 const dii={net_amount:"200",gross_amount:"1000",net_to_gross_percent:20,net_buying_dates:5,net_selling_dates:0,balanced_dates:0,direction_consistency:"NET_BUYING_MAJORITY"};
 render(<AutomaticInstitutionalActivity data={{status:"RECENT_PROVIDER_EVIDENCE",flow_context:{status:"MATCHED_PROVIDER_DATES_ONLY",windows:[{observation_count:5,dates:["2026-11-24","2026-11-23","2026-11-20","2026-11-19","2026-11-18"],participants:{FII:fii,DII:dii},both_buying_dates:0,both_selling_dates:0,fii_selling_dii_buying_dates:5,fii_buying_dii_selling_dates:0,one_or_both_balanced_dates:0,latest_date_is_today:true}],notice:"Not consecutive or verified completed trading sessions."}}}/>);
 fireEvent.click(screen.getByText(/5 matched reported dates/));
 expect(screen.getByText("-20.00%")).toBeTruthy();
 expect(screen.getByText("net selling majority")).toBeTruthy();
 expect(screen.getByText("FII selling / DII buying")).toBeTruthy();
 expect(screen.getByText(/potentially partial observation/)).toBeTruthy();
 expect(screen.getByText(/Not consecutive or verified completed trading sessions/)).toBeTruthy();
});
