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
