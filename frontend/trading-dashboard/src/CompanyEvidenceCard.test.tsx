/** @vitest-environment jsdom */
import {afterEach,expect,it} from "vitest";
import {cleanup,render,screen} from "@testing-library/react";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
afterEach(cleanup);
it("shows dated provider ratios and explicitly missing financial sections",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:{status:"AVAILABLE",data:[{name:"P/E",company_value:20,sector_value:10,unit:"RATIO"}],source:null},income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("P/E")).toBeTruthy();
 expect(screen.getByText("20")).toBeTruthy();
 expect(screen.getByText("10")).toBeTruthy();
 expect(screen.getByText(/No fair-value estimate/)).toBeTruthy();
});

it("shows comparable fundamentals and valuation without claiming fair value",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},fundamental_quality:{
 status:"REVIEW_REQUIRED",strengths:[],warnings:["NET_MARGIN_DETERIORATION_REVIEW"],
 derived_metrics:[{metric:"NET_MARGIN",previous_year:2024,latest_year:2025,previous_value:20,latest_value:15,change:-5,unit:"PERCENT"}],
 sector_comparisons:[{metric:"PE",company:20,sector:10,unit:"RATIO",difference:10,premium_discount_percent:100,position:"ABOVE_SECTOR"}],
 valuation:{status:"SECTOR_COMPARISON_ONLY",fair_value:null,scenario_status:"DATED_VALUATION_INPUTS_REQUIRED"},gaps:["RATIO_OBSERVATION_PERIOD_UNVERIFIED"],notice:"Comparisons only."}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("Reported deterioration requires review")).toBeTruthy();
 expect(screen.getByText("100% premium")).toBeTruthy();
 expect(screen.getByText("FY2025: 15%")).toBeTruthy();
 expect(screen.getByText(/Fair value and valuation scenarios withheld/)).toBeTruthy();
});

it("renders bounded peer comparisons without implying sector leadership",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},peer_research:{
 status:"SAMPLED_PEER_COMPARISON",selected_peer_count:3,cached_same_sector_count:3,minimum_peers_per_metric:3,sample_limit:3,
 metrics:[{metric:"REVENUE",period:"2026-03",unit:"INR_CRORE",company_value:100,peer_median:120,peer_count:3,peers_above:2,peers_below:1,peers:[]}],
 notice:"Sample only; not market share."}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("2 above · 1 below · 3 peers")).toBeTruthy();
 expect(screen.getByText("120 Cr")).toBeTruthy();
 expect(screen.getByText("Sample only; not market share.")).toBeTruthy();
});

it("shows reported quarterly ownership changes without treating them as trades",()=>{
 const missing={status:"UNAVAILABLE",data:null,source:null};
 const evidence:CompanyEvidence={isin:"INE002A01018",retrieved_at:"2026-11-24T10:00:00Z",available_sections:1,total_sections:8,notice:"Provider reported.",sections:{profile:missing,ratios:missing,income_statement:missing,cash_flow:missing,balance_sheet:missing,shareholding:missing,corporate_actions:missing,competitors:missing},
 ownership_research:{status:"COMPARABLE_QUARTERS",latest_period:"2026-09-30",previous_period:"2026-06-30",
 categories:[{category:"promoters",latest_percent:48,previous_percent:50,change_pp:-2}],
 review_prompts:[{category:"promoters",change_pp:-2,reason:"REPORTED_OWNERSHIP_DECLINE_AT_LEAST_ONE_PP"}],
 notice:"Quarterly ownership changes are not proof of buying or selling.",blockers:["PROMOTER_PLEDGE_DATA_UNVERIFIED"]}};
 render(<CompanyEvidenceCard evidence={evidence}/>);
 expect(screen.getByText("48%")).toBeTruthy();
 expect(screen.getByText("-2 pp")).toBeTruthy();
 expect(screen.getByText(/Review reported declines/)).toBeTruthy();
 expect(screen.getByText(/not proof of buying or selling/)).toBeTruthy();
});
