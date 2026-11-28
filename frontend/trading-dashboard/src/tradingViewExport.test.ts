import {describe,it,expect} from "vitest";
import {buildTradingViewExport,indiaDate} from "./tradingViewExport";
const item={id:1,isin:"INE002A01018",symbol:"RELIANCE",exchange:"NSE",as_of:"2026-11-27",status:"SCREEN_MATCH_ONLY",
 adjustment_status:"ADJUSTED",strict_fip_evidence:{status:"FIP_PRICE_MATCH",adjustment_status:"ADJUSTED",calendar_status:"STORED_SESSIONS_MATCHED",as_of:"2026-11-27"},
 governance_review:{findings:[]},company_venue_context:{review_findings:[]}};
const report={status:"JOINT_SCREEN_MATCHES",matched_count:1,qualification_eligible:false as const,items:[item]};
describe("TradingView import export",()=>{
 it("exports distinct strict research only in documented format",()=>{
  expect(buildTradingViewExport({...report,matched_count:2,items:[item,{...item,id:2,isin:"INE009A01021",symbol:"INFY"}]},"2026-11-28"))
   .toEqual({filename:"TV-Suggestion-2026-11-28.txt",text:"NSE:RELIANCE,NSE:INFY",count:2,session:"2026-11-27"});
  expect(indiaDate(new Date("2026-11-27T20:00:00Z"))).toBe("2026-11-28");
 });
 it("rejects preliminary, stale, duplicate, malformed or flagged candidates",()=>{
  expect(buildTradingViewExport({...report,status:"REPORTED_JOINT_MATCHES"},"2026-11-28")).toBeNull();
  expect(buildTradingViewExport(report,"2026-12-03")).toBeNull();
  expect(buildTradingViewExport({...report,matched_count:2,items:[item,{...item,exchange:"BSE"}]},"2026-11-28")).toBeNull();
  expect(buildTradingViewExport({...report,items:[{...item,symbol:"TEST,###"}]},"2026-11-28")).toBeNull();
  expect(buildTradingViewExport({...report,items:[{...item,governance_review:{findings:["REVIEW"]}}]},"2026-11-28")).toBeNull();
  expect(buildTradingViewExport({...report,items:[{...item,adjustment_status:"RAW_UNADJUSTED"}]},"2026-11-28")).toBeNull();
 });
});
