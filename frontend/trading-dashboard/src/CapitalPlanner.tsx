import {useEffect,useState} from "react";
import type {InvestmentAnalysis} from "./InvestmentAnalystPanel";
import {visiblePolling} from "./visiblePolling";

type Holding={id:number;symbol:string;isin?:string;exact_scheme_code?:string|number;asset_type:string;recorded_market_value?:number;recorded_valuation_recent?:boolean;investment_analysis?:{action:string}};
type Comparison={asset_type:string;holding:string;alternative:string;holding_identity:string;alternative_identity:string;first_date:string;last_date:string;holding_return_percent:number;alternative_return_percent:number;basis:string};
type FundingComparison={scope:string;kind:string;status:string;purchaseNotional:number;saleNotional:number;estimates:{basisPointsPerSide:number;additionalCashIncludingTransactionCost:number;conditionalCashIfThresholdUnused?:number|null;conditionalCashIfThresholdUsed?:number|null}[];evidenceGaps:string[]};
export type OwnerReview={generated_at:string;holding_count:number;holdings:Holding[];investment_analysis?:{recent_weight_coverage:boolean;scope:string};opportunity_context?:{matched_comparisons?:Comparison[]};diversification?:{look_through?:{status:string;portfolio_date?:string;mapped_portfolio_percent?:number;exposures?:{isin:string;estimatedValue:number;indirectValue:number}[]}};portfolio_level_risk?:{look_through_status:string;attention?:{kind:string;label:string;value:number;unit:string}[]};rebalancing_funding?:{status:string;comparisons:FundingComparison[];notice:string}};
type Risk="LOW"|"MODERATE"|"HIGH";
type Allocation={identity:string;label:string;category:string;amount:number;reason:string;wholeShares?:number;stopRisk?:number};
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
 const out={allocations,comparisons,reserved:amount,planned:0,status:"AWAITING_OWNER_EVIDENCE",estimatedStockStopRisk:0,illustrativeBuyCharges:0};
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
 const policyOk=(r:{decision_quality?:{state:string;qualified:false}})=>!report.decision_quality||report.decision_quality.status!=="UNAVAILABLE"&&!report.decision_quality.forecast_allocation_hold&&r.decision_quality?.state==="PRIORITY_RESEARCH"&&r.decision_quality.qualified===false;
 const stockCounts=new Map<string,number>(),fundCounts=new Map<string,number>();
 for(const s of report.stocks)stockCounts.set(s.isin,(stockCounts.get(s.isin)??0)+1);
 for(const g of report.funds)for(const f of g.items)fundCounts.set(f.identifier,(fundCounts.get(f.identifier)??0)+1);
 const eligibleStocks=report.stocks.filter(s=>policyOk(s)&&s.qualified===false&&s.tier==="ADJUSTED_JOINT"&&s.action==="RESEARCH_FOR_ENTRY"&&
  s.ai_review?.state!=="DEFER_REVIEW"&&s.ai_review?.state!=="DISAGREEMENT"&&s.risk!=="HIGH"&&
  /^INE[A-Z0-9]{9}$/.test(s.isin)&&stockCounts.get(s.isin)===1&&!stockIds.has(s.isin)&&age(s.as_of,today)>=1&&age(s.as_of,today)<=4&&
  !!s.price_plan&&finite(s.price_plan.reference)&&finite(s.price_plan.stop_scenario)&&s.price_plan.stop_scenario>0&&s.price_plan.reference>s.price_plan.stop_scenario&&Math.abs(s.price_plan.reference-s.close)<=.0051);
 const eligibleFunds=report.funds.flatMap(g=>g.items.filter(f=>policyOk(f)&&f.qualified===false&&f.tier==="DRIVER_SUPPORTED"&&f.action==="COMPARE_FOR_SIP"&&
  f.ai_review?.state!=="DEFER_REVIEW"&&f.ai_review?.state!=="DISAGREEMENT"&&scheme(f.identifier)&&fundCounts.get(f.identifier)===1&&!fundIds.has(f.identifier)&&
  age(f.nav_date,today)>=0&&age(f.nav_date,today)<=7&&f.fund_evidence?.ter_status!=="CONFLICTING_SAME_DATE_TER").map(f=>({...f,category:g.category})));
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
 const existingReview=!!review.portfolio_level_risk?.attention?.length||review.holdings.some(h=>["REVIEW_REDUCTION","REASSESS_THESIS","REBALANCE_REVIEW","PAUSE_ADDITIONS"].includes(h.investment_analysis?.action??""));
 const reservePct=existingReview?.6:risk==="MODERATE"?.4:.25;
 const look=review.diversification?.look_through;
 const currentLook=look?.status==="DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE"&&typeof look.portfolio_date==="string"&&age(look.portfolio_date,today)>=0&&age(look.portfolio_date,today)<=60&&Array.isArray(look.exposures);
 // Existing funds with no current look-through evidence warrant restraint on
 // direct-stock additions. Partial known exposures are lower bounds only.
 const maxStock=risk==="HIGH"&&!existingReview&&(fundIds.size===0||currentLook)?.1:0, fundBudget=existingReview?.4:risk==="HIGH"?.5:.6;
 let left=Math.floor(amount*(1-reservePct));
 // Reserve 30 bps per-side illustrative purchase friction in addition to
 // the planned notional. NAV performance already reflects recurring TER.
 const chargeRate=.003;let stockRiskLeft=amount*.0075;
 const used=new Set<string>();
 function add(identity:string,label:string,category:string,desired:number,positionCap:number,reason:string,price?:number,riskPerShare?:number,knownExposure=0){
  if(used.has(identity)||left<=0)return;
  // Conservative post-contribution denominator: existing investments plus
  // only the proposed position, ignoring other planned additions and cash.
  const maxPosition=total>0?Math.max(0,Math.floor((total*positionCap-knownExposure)/(1-positionCap))):Math.floor(amount*positionCap);
  const limit=Math.min(Math.floor(desired),maxPosition,Math.floor(left/(1+chargeRate)));
  const shares=price&&riskPerShare?Math.floor(Math.min(limit/price,stockRiskLeft/riskPerShare)):undefined;
  const n=shares!=null?Math.ceil(shares*price!):limit;
  if(n<1||n>limit)return;
  const charge=Math.ceil(n*chargeRate);
  if(n+charge>left)return;
  const stopRisk=shares!=null?shares*riskPerShare!:undefined;
  if(stopRisk!=null){stockRiskLeft-=stopRisk;out.estimatedStockStopRisk+=stopRisk;}
  used.add(identity);left-=n+charge;out.illustrativeBuyCharges+=charge;allocations.push({identity,label,category,amount:n,reason,wholeShares:shares,stopRisk});
 }
 const categories=risk==="HIGH"?["LARGE_CAP","MID_CAP","SMALL_CAP"]:["LARGE_CAP","MID_CAP"];
 for(const category of categories){
  const candidates=eligibleFunds.filter(x=>x.category===category&&(risk==="HIGH"||x.relative_risk==="AT_OR_BELOW_PEER_MEDIAN_DOWNSIDE"));
  // Same category/date/benchmark only. Prefer a non-dominated candidate
  // on reported fees, historical TRI excess, drawdown and volatility.
  // Do not subtract TER again from reported NAV returns or infer expected alpha.
  const f=candidates.find(x=>!candidates.some(y=>{
    if(y===x||y.nav_date!==x.nav_date)return false;
    const a=x.fund_evidence,b=y.fund_evidence;
    const ax=a?.benchmark_context,bx=b?.benchmark_context;
    if(!a||!b||!ax||!bx||!ax.benchmark||ax.benchmark!==bx.benchmark||ax.basis!==bx.basis||a.ter_status!=="REPORTED_NOT_INDEPENDENTLY_AUTHENTICATED"||b.ter_status!==a.ter_status||a.ter_date!==b.ter_date)return false;
    const av=[a.ter_percent,ax.three_year_difference_pp,a.weekly_drawdown_percent,a.annualized_volatility_percent];
    const bv=[b.ter_percent,bx.three_year_difference_pp,b.weekly_drawdown_percent,b.annualized_volatility_percent];
    if(!av.every(finite)||!bv.every(finite))return false;
    const a1=av as number[],b1=bv as number[];
    return b1[0]<=a1[0]&&b1[1]>=a1[1]&&b1[2]>=a1[2]&&b1[3]<=a1[3]&&b1.some((v,i)=>v!==a1[i]);
  }));
  if(f)add("F:"+f.identifier,f.name,category,amount*fundBudget/categories.length,.25,"Reported growth drivers and current historical peer evidence; confirm suitability, costs and portfolio overlap.");
 }
 if(maxStock>0)for(const s of eligibleStocks){
  if(allocations.filter(a=>a.category==="EQUITY").length>=2)break;
  const matches=currentLook?(look?.exposures??[]).filter(x=>x.isin===s.isin):[];
  if(matches.length>1||matches.some(x=>!finite(x.estimatedValue)||!finite(x.indirectValue)||x.indirectValue<0||x.estimatedValue<x.indirectValue||x.estimatedValue>total))continue;
  const knownExposure=matches[0]?.estimatedValue??0;
  const plan=s.price_plan!;
  const riskPerShare=plan.reference-plan.stop_scenario;
  // At most 0.5% of fresh investable capital per stock before gaps and costs.
  const shares=Math.floor(Math.min(amount*maxStock/plan.reference,amount*.005/riskPerShare));
  add("S:"+s.isin,s.symbol,"EQUITY",Math.ceil(shares*plan.reference),.1,"Adjusted joint screen; illustrative stop risk capped at 0.5% per stock and 0.75% combined fresh capital. Recheck actual quote, gap risk, charges and any unmodeled fund exposure.",plan.reference,riskPerShare,knownExposure);
 }
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
   {plan.allocations.length>0&&<ul>{plan.allocations.map(a=><li key={a.identity}><strong>{a.label} · {money(a.amount)}</strong><p>{a.reason}</p>{a.wholeShares!=null&&<small>{a.wholeShares} illustrative whole shares · stop risk {money(a.stopRisk??0)}</small>}</li>)}</ul>}
   {!!review.portfolio_level_risk?.attention?.length&&<details><summary>Portfolio-level risk observations</summary><ul>{review.portfolio_level_risk.attention.map((v,i)=><li key={i}>{v.label}: {v.value.toFixed(1)} {v.unit}</li>)}</ul><small>Look-through status: {review.portfolio_level_risk.look_through_status}. Existing partial exposures are not complete live fund weights.</small></details>}
    {!!review.rebalancing_funding?.comparisons?.length&&<details><summary>Existing rebalancing cost and funding comparisons</summary>{review.rebalancing_funding.comparisons.slice(0,5).map((v,i)=><div key={i}><strong>{v.kind}</strong>{v.estimates.filter(e=>e.basisPointsPerSide===30).map(e=><p key={e.basisPointsPerSide}>Additional cash with illustrative charges: {money(e.additionalCashIncludingTransactionCost)}. {e.conditionalCashIfThresholdUsed!=null?`Conditional with reference tax: ${money(e.conditionalCashIfThresholdUsed)}`:"Combined tax/exit costs not established."}</p>)}{!!v.evidenceGaps.length&&<small>{v.evidenceGaps.join(" ")}</small>}</div>)}<small>{review.rebalancing_funding.notice}</small></details>}
    <p><strong>Conditional research budget {money(plan.planned)}</strong> · Keep unallocated {money(plan.reserved)}</p>{plan.planned>0&&<small>Unallocated amount includes {money(plan.illustrativeBuyCharges)} illustrative purchase-charge reserve; total modeled stock stop risk {money(plan.estimatedStockStopRisk)}. No sale or realized tax is assumed.</small>}
   <small>Policy limits are illustrative: at least 25–40% unallocated (60% when current holdings need risk review), no equity allocations under five years, no duplicate exact held identities, and capped new positions. New stocks require a supported stop scenario, with 0.5% fresh-capital risk per position and 0.75% aggregate stock risk before gaps and costs. Fund look-through and tax impact still require review. No automated execution.</small>
  </>}
 </details>;
}
