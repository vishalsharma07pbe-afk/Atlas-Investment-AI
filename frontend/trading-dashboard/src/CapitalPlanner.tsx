import {useEffect,useState} from "react";
import type {InvestmentAnalysis} from "./InvestmentAnalystPanel";
import {visiblePolling} from "./visiblePolling";

type Holding={id:number;symbol:string;isin?:string;exact_scheme_code?:string|number;asset_type:string;recorded_market_value?:number;recorded_valuation_recent?:boolean;investment_analysis?:{action:string}};
type Comparison={asset_type:string;holding:string;alternative:string;holding_identity:string;alternative_identity:string;first_date:string;last_date:string;holding_return_percent:number;alternative_return_percent:number;basis:string};
export type OwnerReview={generated_at:string;holding_count:number;holdings:Holding[];investment_analysis?:{recent_weight_coverage:boolean;scope:string};opportunity_context?:{matched_comparisons?:Comparison[]}};
type Risk="LOW"|"MODERATE"|"HIGH";
type Allocation={identity:string;label:string;category:string;amount:number;reason:string};
const money=(n:number)=>"₹"+n.toLocaleString("en-IN",{maximumFractionDigits:0});
const finite=(n:unknown):n is number=>typeof n==="number"&&Number.isFinite(n);
const scheme=(v:unknown)=>/^[1-9][0-9]{5,8}$/.test(String(v))?String(v):null;
function age(day:string,today:string){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!/^\d{4}-\d{2}-\d{2}$/.test(today))return Infinity;
 const a=Date.parse(day+"T00:00:00Z"),b=Date.parse(today+"T00:00:00Z");
 return Number.isFinite(a)&&new Date(a).toISOString().slice(0,10)===day?(b-a)/86400000:Infinity;
}
export function makeCapitalPlan(report:InvestmentAnalysis,review:OwnerReview|null,budget:number,risk:Risk,months:number,now=Date.now()){
 const allocations:Allocation[]=[];const comparisons:Comparison[]=[];
 const amount=Number.isSafeInteger(budget)&&budget>=0&&budget<=100000000?budget:0;
 const out={allocations,comparisons,reserved:amount,planned:0,status:"AWAITING_OWNER_EVIDENCE"};
 if(!review||!Array.isArray(review.holdings)||review.holding_count!==review.holdings.length||review.investment_analysis?.scope!=="OWNER_LOCAL")return out;
 const stamp=Date.parse(review.generated_at);
 const today=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Kolkata",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(now));
 if(!Number.isFinite(stamp)||stamp>now||now-stamp>600000||report.research_date!==today||report.status!=="RESEARCH_AVAILABLE")return out;
 const stockIds=new Set<string>(),fundIds=new Set<string>();let total=0;
 for(const h of review.holdings){
  if(h.asset_type==="EQUITY"&&typeof h.isin==="string"&&/^INE[A-Z0-9]{9}$/.test(h.isin))stockIds.add(h.isin);
  else if(h.asset_type==="MUTUAL_FUND"&&scheme(h.exact_scheme_code)&&scheme(h.exact_scheme_code)===h.symbol)fundIds.add(String(h.exact_scheme_code));
  else return out;
  if(!h.recorded_valuation_recent||!finite(h.recorded_market_value)||h.recorded_market_value<0)return out;
  total+=h.recorded_market_value;
 }
 if(!Number.isFinite(total)||review.holdings.length>0&&review.investment_analysis.recent_weight_coverage!==true)return out;
 const eligibleStocks=report.stocks.filter(s=>s.qualified===false&&s.tier==="ADJUSTED_JOINT"&&s.action==="RESEARCH_FOR_ENTRY"&&
  s.ai_review?.state!=="DEFER_REVIEW"&&s.ai_review?.state!=="DISAGREEMENT"&&s.risk!=="HIGH"&&
  /^INE[A-Z0-9]{9}$/.test(s.isin)&&!stockIds.has(s.isin)&&age(s.as_of,today)>=1&&age(s.as_of,today)<=4);
 const eligibleFunds=report.funds.flatMap(g=>g.items.filter(f=>f.qualified===false&&f.tier==="DRIVER_SUPPORTED"&&f.action==="COMPARE_FOR_SIP"&&
  f.ai_review?.state!=="DEFER_REVIEW"&&f.ai_review?.state!=="DISAGREEMENT"&&scheme(f.identifier)&&!fundIds.has(f.identifier)&&
  age(f.nav_date,today)>=0&&age(f.nav_date,today)<=7).map(f=>({...f,category:g.category})));
 // Exact identity, same-date upstream comparisons; historical advantages are
 // context, not predictions or evidence that a switch is suitable.
 for(const c of review.opportunity_context?.matched_comparisons??[]){
  if(!finite(c.holding_return_percent)||!finite(c.alternative_return_percent)||c.alternative_return_percent<=c.holding_return_percent)continue;
  if(c.asset_type==="EQUITY"&&stockIds.has(c.holding_identity)&&report.stocks.some(s=>s.isin===c.alternative_identity&&s.as_of===c.last_date&&!stockIds.has(s.isin))&&c.basis==="60_MATCHED_SESSIONS_PRICE_ONLY"||
     c.asset_type==="MUTUAL_FUND"&&fundIds.has(c.holding_identity)&&report.funds.some(g=>g.items.some(f=>f.identifier===c.alternative_identity&&f.nav_date===c.last_date&&!fundIds.has(f.identifier)))&&c.basis==="157_MATCHED_WEEKLY_NAV_CAGR_AND_DRAWDOWN"){
    comparisons.push(c);
  }
 }
 comparisons.sort((a,b)=>(b.alternative_return_percent-b.holding_return_percent)-(a.alternative_return_percent-a.holding_return_percent));
 if(!Number.isInteger(months)||months<12||months>360||risk==="LOW"||months<60){out.status="RESERVE_FOR_HORIZON_OR_RISK";return out;}
 // Illustrative policy limits on new capital, not a suitability determination.
 // No sale proceeds, emergency reserve, leverage, or assumed future gains.
 const reservePct=risk==="MODERATE"?.4:.25;
 const maxStock=risk==="HIGH"?.1:0, fundBudget=risk==="HIGH"?.5:.6;
 let left=Math.floor(amount*(1-reservePct));
 const used=new Set<string>();
 function add(identity:string,label:string,category:string,desired:number,positionCap:number,reason:string){
  if(used.has(identity)||left<=0)return;
  // Conservative post-contribution denominator: existing investments plus
  // only the proposed position, ignoring other planned additions and cash.
  const maxPosition=total>0?Math.floor(total*positionCap/(1-positionCap)):Math.floor(amount*positionCap);
  const n=Math.min(Math.floor(desired),maxPosition,left);
  if(n<1)return;
  used.add(identity);left-=n;allocations.push({identity,label,category,amount:n,reason});
 }
 const categories=risk==="HIGH"?["LARGE_CAP","MID_CAP","SMALL_CAP"]:["LARGE_CAP","MID_CAP"];
 for(const category of categories){
  const f=eligibleFunds.find(x=>x.category===category&&(risk==="HIGH"||x.relative_risk==="AT_OR_BELOW_PEER_MEDIAN_DOWNSIDE"));
  if(f)add("F:"+f.identifier,f.name,category,amount*fundBudget/categories.length,.25,"Reported growth drivers and current historical peer evidence; confirm suitability, costs and portfolio overlap.");
 }
 if(maxStock>0)for(const s of eligibleStocks.slice(0,2))add("S:"+s.isin,s.symbol,"EQUITY",amount*maxStock,.1,"Adjusted joint screen; confirm current execution, independent valuation and business evidence.");
 out.planned=allocations.reduce((n,r)=>n+r.amount,0);out.reserved=amount-out.planned;
 out.status=allocations.length?"CONDITIONAL_RESEARCH_BUDGET":"NO_SUPPORTED_ALLOCATION";
 return out;
}

export default function CapitalPlanner({report}:{report:InvestmentAnalysis}){
 const [open,setOpen]=useState(false),[review,setReview]=useState<OwnerReview|null>(null),[error,setError]=useState(false);
 const [budget,setBudget]=useState(""),[risk,setRisk]=useState<Risk>("MODERATE"),[months,setMonths]=useState("60");
 useEffect(()=>{if(!open){setReview(null);return;}return visiblePolling(async signal=>{
  try{const r=await fetch("/api/v1/portfolio/review",{cache:"no-store",signal});if(!r.ok)throw Error();
   const body:OwnerReview=await r.json();if(!Array.isArray(body.holdings))throw Error();
   if(!signal.aborted){setReview(body);setError(false);}
  }catch{if(!signal.aborted){setReview(null);setError(true);}}
 },60000);},[open]);
 const plan=makeCapitalPlan(report,review,Number(budget),risk,Number(months));
 return <details className="research-action" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
  <summary>Plan my next investment · compare holdings and opportunities</summary>
  <p>Owner-local conditional research budget. Enter only surplus investable cash after essential expenses and emergency savings. No data is sent to an external AI.</p>
  <div className="autonomous-grid">
   <label>New capital (₹)<input type="number" min="0" max="100000000" step="1" value={budget} onChange={e=>setBudget(e.target.value)}/></label>
   <label>Risk tolerance<select value={risk} onChange={e=>setRisk(e.target.value as Risk)}><option value="LOW">Low</option><option value="MODERATE">Moderate</option><option value="HIGH">High</option></select></label>
   <label>Investment horizon (months)<input type="number" min="12" max="360" value={months} onChange={e=>setMonths(e.target.value)}/></label>
  </div>
  {error?<p role="alert">Owner portfolio evidence unavailable.</p>:!review?<p>Loading your portfolio evidence…</p>:<>
   <p>{plan.status==="AWAITING_OWNER_EVIDENCE"?"Fresh resolved portfolio values are needed.":plan.status==="RESERVE_FOR_HORIZON_OR_RISK"?"Keep this capital outside the equity research allocation under the selected horizon/risk limits.":plan.status==="NO_SUPPORTED_ALLOCATION"?"No supported allocation under the current evidence and policy.":"Conditional research allocations, not buy orders."}</p>
   {!!plan.comparisons.length&&<><h4>Matched historical alternatives to current holdings</h4><ul>{plan.comparisons.slice(0,5).map(c=><li key={c.holding_identity+":"+c.alternative_identity}>{c.holding} → {c.alternative}: {c.holding_return_percent.toFixed(1)}% vs {c.alternative_return_percent.toFixed(1)}% · {c.first_date} to {c.last_date}. Historical comparison only.</li>)}</ul></>}
   {plan.allocations.length>0&&<ul>{plan.allocations.map(a=><li key={a.identity}><strong>{a.label} · {money(a.amount)}</strong><p>{a.reason}</p></li>)}</ul>}
   <p><strong>Conditional research budget {money(plan.planned)}</strong> · Keep unallocated {money(plan.reserved)}</p>
   <small>Policy limits are illustrative: at least 25–40% unallocated for eligible risk profiles, no equity allocations under five years, no duplicate exact held identities, and capped new positions. Fund look-through and tax impact still require review. No automated execution.</small>
  </>}
 </details>;
}
