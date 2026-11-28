import {describe,it,expect} from "vitest";
import {makeCapitalPlan,type OwnerReview} from "./CapitalPlanner";
import type {InvestmentAnalysis} from "./InvestmentAnalystPanel";
const now=Date.parse("2026-11-28T05:00:00Z");
const stock={id:1,isin:"INE002A01018",symbol:"RELIANCE",exchange:"NSE",as_of:"2026-11-27",close:100,tier:"ADJUSTED_JOINT",horizon:"ELITE",score:80,reasons:[],limitations:[],qualified:false as const,action:"RESEARCH_FOR_ENTRY",risk:"MEDIUM",price_plan:{reference:100,stop_scenario:96,target_scenario:108,reward_risk:2,notice:"Scenario only"}};
const fund={identifier:"123456",name:"Fund",nav_date:"2026-11-27",score:80,tier:"DRIVER_SUPPORTED",action:"COMPARE_FOR_SIP",relative_risk:"AT_OR_BELOW_PEER_MEDIAN_DOWNSIDE",reasons:[],limitations:[],qualified:false as const};
const report:InvestmentAnalysis={methodology:"INVESTMENT-ANALYST-1",status:"RESEARCH_AVAILABLE",research_date:"2026-11-28",stocks:[stock],funds:[{category:"LARGE_CAP",items:[fund]}],next_steps:[],notice:"Research"};
const empty:OwnerReview={generated_at:"2026-11-28T04:59:00Z",holding_count:0,holdings:[],investment_analysis:{scope:"OWNER_LOCAL",recent_weight_coverage:false}};
describe("local conditional capital planner",()=>{
 it("preserves capital and never fills unsupported categories",()=>{
  const p=makeCapitalPlan(report,empty,100000,"HIGH",60,now);
  expect(p.allocations.length).toBe(2);
  expect(p.planned+p.reserved).toBe(100000);
  expect(p.reserved).toBeGreaterThanOrEqual(25000);
 });
 it("excludes held and deferred identities and short horizons",()=>{
  const review:OwnerReview={...empty,holding_count:1,holdings:[{id:1,symbol:"RELIANCE",isin:stock.isin,asset_type:"EQUITY",recorded_market_value:100000,recorded_valuation_recent:true}],investment_analysis:{scope:"OWNER_LOCAL",recent_weight_coverage:true}};
  expect(makeCapitalPlan(report,review,100000,"HIGH",60,now).allocations.every(a=>a.identity!=="S:"+stock.isin)).toBe(true);
  expect(makeCapitalPlan(report,empty,100000,"HIGH",36,now).reserved).toBe(100000);
  expect(makeCapitalPlan({...report,stocks:[{...stock,ai_review:{state:"DEFER_REVIEW",providers:["OLLAMA"],reasons:[]}}]},empty,100000,"HIGH",60,now).allocations.every(a=>!a.identity.startsWith("S:"))).toBe(true);
 });
 it("reserves more when existing holdings need attention",()=>{
  const review:OwnerReview={...empty,holding_count:1,holdings:[{id:1,symbol:"OTHER",isin:"INE009A01021",asset_type:"EQUITY",recorded_market_value:100000,recorded_valuation_recent:true,investment_analysis:{action:"REVIEW_REDUCTION"}}],investment_analysis:{scope:"OWNER_LOCAL",recent_weight_coverage:true}};
  const p=makeCapitalPlan(report,review,100000,"HIGH",60,now);
  expect(p.reserved).toBeGreaterThanOrEqual(60000);
  expect(p.allocations.every(a=>!a.identity.startsWith("S:"))).toBe(true);
 });
 it("does not allocate on stale review",()=>expect(makeCapitalPlan(report,empty,100000,"HIGH",60,now+700000).planned).toBe(0));
});

it("requires a stock risk scenario and caps a high-stop-risk position",()=>{
 const risky={...stock,price_plan:{...stock.price_plan,stop_scenario:90}};
 const p=makeCapitalPlan({...report,stocks:[risky]},empty,100000,"HIGH",60,now);
 expect(p.allocations.find(a=>a.identity==="S:"+stock.isin)?.amount).toBe(5000);
 const missing={...stock,price_plan:undefined};
 expect(makeCapitalPlan({...report,stocks:[missing]},empty,100000,"HIGH",60,now).allocations.every(a=>!a.identity.startsWith("S:"))).toBe(true);
});
