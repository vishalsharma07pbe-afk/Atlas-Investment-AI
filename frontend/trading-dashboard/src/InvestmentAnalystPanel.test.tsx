/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen} from "@testing-library/react";
import InvestmentAnalystPanel,{type InvestmentAnalysis} from "./InvestmentAnalystPanel";
import {HoldingDecision,OwnerInvestmentPlan} from "./InvestmentPlan";
afterEach(cleanup);
it("presents supported research, price scenario and navigation without a new scan",()=>{
 const open=vi.fn();
 const report:InvestmentAnalysis={methodology:"INVESTMENT-ANALYST-1",status:"RESEARCH_AVAILABLE",research_date:"2026-11-28",
 stocks:[{id:1,isin:"INE002A01018",symbol:"RELIANCE",exchange:"NSE",as_of:"2026-11-27",close:100,tier:"ADJUSTED_JOINT",horizon:"ELITE",score:80,reasons:["Reported earnings growth"],limitations:["Unverified valuation"],qualified:false,action:"RESEARCH_FOR_ENTRY",price_plan:{reference:100,stop_scenario:96,target_scenario:108,reward_risk:2,notice:"Scenario only"}}],
 funds:[{category:"LARGE_CAP",items:[{identifier:"123456",name:"Test Fund",nav_date:"2026-11-27",score:80,tier:"HISTORICAL_ONLY",action:"WATCH_FOR_CONFIRMATION",reasons:["Historical observation"],limitations:["Future growth not verified"],qualified:false}]}],
 next_steps:["Review current price"],notice:"Research only"};
 render(<InvestmentAnalystPanel report={report} onOpenStock={open} onFunds={()=>{}} onPortfolio={()=>{}}/>);
 expect(screen.getByText("RELIANCE")).toBeTruthy();
 expect(screen.getByText("Illustrative swing risk plan")).toBeTruthy();
 expect(screen.getByText(/Test Fund/)).toBeTruthy();
 expect(screen.getByText(/Historical peer evidence only/)).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Open company research"}));
 expect(open).toHaveBeenCalledWith({id:1,isin:"INE002A01018",symbol:"RELIANCE",exchange:"NSE"});
});
it("shows a conditional owner-local plan",()=>{
 render(<><OwnerInvestmentPlan analysis={{methodology:"OWNER-INVESTMENT-ANALYST-1",scope:"OWNER_LOCAL",status:"CONDITIONAL_PLAN",next_steps:["Review exposure"],action_counts:{},notice:"Research only"}}/><HoldingDecision analysis={{methodology:"OWNER-INVESTMENT-ANALYST-1",action:"REVIEW_REDUCTION",reasons:["Thesis change"],next_move:"Verify official evidence",qualified:false}}/></>);
 expect(screen.getByText("Review exposure")).toBeTruthy();
 expect(screen.getByText("Review potential reduction")).toBeTruthy();
 expect(screen.getByText("Verify official evidence")).toBeTruthy();
});
