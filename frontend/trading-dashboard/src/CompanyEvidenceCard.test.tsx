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
