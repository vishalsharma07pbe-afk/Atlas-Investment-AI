import {useState} from "react";
import type {EliteTarget} from "./SteadyMomentumCard";

type Stock=EliteTarget&{as_of:string;close:number;tier:string;horizon:string;score:number|null;reasons:string[];limitations:string[];qualified:false;action:string;risk?:string|null;price_plan?:{reference:number;stop_scenario:number;target_scenario:number;reward_risk:number;notice:string}|null};
type Fund={identifier:string;name:string;nav_date:string;score:number;tier:string;action:string;relative_risk?:string;reasons:string[];limitations:string[];qualified:false};
export type InvestmentAnalysis={methodology:string;status:string;research_date:string;stocks:Stock[];funds:{category:string;items:Fund[]}[];next_steps:string[];notice:string};
const money=(v:number)=>"₹"+v.toLocaleString("en-IN",{maximumFractionDigits:2});
const stockTiers:Record<string,string>={ADJUSTED_JOINT:"Joint stock screen · adjusted history",REPORTED_JOINT:"Joint stock screen · unverified adjustment",BUSINESS_SCREEN:"Business-screen candidate",TECHNICAL_LEAD:"Technical lead only"};
const fundTiers:Record<string,string>={DRIVER_SUPPORTED:"Reported growth drivers",DRIVER_REVIEW:"Underlying-business review needed",HISTORICAL_ONLY:"Historical peer evidence only"};
const categoryLabels:Record<string,string>={LARGE_CAP:"Large cap",MID_CAP:"Mid cap",SMALL_CAP:"Small cap"};
export default function InvestmentAnalystPanel({report,onOpenStock,onFunds,onPortfolio}:{report:InvestmentAnalysis;onOpenStock?:(target:EliteTarget)=>void;onFunds:()=>void;onPortfolio:()=>void}){
 const [showAll,setShowAll]=useState(false);
 if(report.methodology!=="INVESTMENT-ANALYST-1"||!Array.isArray(report.stocks)||!Array.isArray(report.funds)||!Array.isArray(report.next_steps))return null;
 const stocks=report.stocks.filter(r=>r.qualified===false);
 const groups=report.funds.filter(g=>Array.isArray(g.items));
 return <section className="visual-research-panel" aria-label="Investment analyst">
  <div className="sectionhead"><div><small className="section-kicker">INVESTMENT INTELLIGENCE</small><h3>Investment analyst</h3><small>Conditional research priorities · {report.research_date}</small></div><span className="tag">RESEARCH ONLY</span></div>
  <div className="research-action"><strong>Your next moves</strong>{report.next_steps.length?<ol>{report.next_steps.map((step,i)=><li key={i}>{step}</li>)}</ol>:<p>Awaiting current supported research.</p>}<button type="button" className="secondary" onClick={onPortfolio}>Review my holdings</button></div>
  <h3>Stock research recommendations</h3>
  {!stocks.length?<p>No supported stock candidates in the current sample. Do not force a position.</p>:<div className="elite-stock-grid">{stocks.slice(0,showAll?10:3).map(s=><article key={s.isin} className="elite-stock">
    <header><div><strong>{s.symbol}</strong><small>{s.exchange} · {s.as_of}</small></div><span>{s.action==="RESEARCH_FOR_ENTRY"?"Research for entry":"Watch for confirmation"}</span></header>
    <p>{stockTiers[s.tier]??"Research only"}{s.score!=null?" · "+s.score.toFixed(1)+"/100 research score":""}</p>
    <div className="research-kpi"><small>Observed close</small><strong>{money(s.close)}</strong>{s.risk&&<small>Historical risk: {s.risk.toLowerCase()}</small>}</div>
    <ul>{s.reasons.map((v,i)=><li key={i}>{v}</li>)}</ul>
    {s.price_plan&&<div className="research-action"><strong>Illustrative swing risk plan</strong><dl><div><dt>Reference</dt><dd>{money(s.price_plan.reference)}</dd></div><div><dt>Stop scenario</dt><dd>{money(s.price_plan.stop_scenario)}</dd></div><div><dt>Target scenario</dt><dd>{money(s.price_plan.target_scenario)}</dd></div><div><dt>Reward / risk</dt><dd>{s.price_plan.reward_risk.toFixed(2)}</dd></div></dl><small>{s.price_plan.notice}</small></div>}
    <details><summary>Evidence limitations</summary><ul>{s.limitations.map((v,i)=><li key={i}>{v}</li>)}</ul></details>
    {onOpenStock&&s.horizon==="ELITE"&&<button type="button" className="secondary" onClick={()=>onOpenStock({id:s.id,isin:s.isin,symbol:s.symbol,exchange:s.exchange})}>Open company research</button>}
  </article>)}</div>}
  {stocks.length>3&&<button type="button" className="secondary" aria-expanded={showAll} onClick={()=>setShowAll(!showAll)}>{showAll?"Show top 3":"View all "+stocks.length+" stock candidates"}</button>}
  <div className="sectionhead"><h3>Mutual fund research recommendations</h3><button type="button" className="secondary" onClick={onFunds}>Open fund research</button></div>
  <div className="autonomous-grid">{["LARGE_CAP","MID_CAP","SMALL_CAP"].map(category=>{const items=groups.find(g=>g.category===category)?.items.filter(f=>f.qualified===false)??[];return <article key={category} className="autonomous-result"><h4>{categoryLabels[category]}</h4>{!items.length?<p>Awaiting supported category research.</p>:items.slice(0,5).map((f,i)=><div key={f.identifier} className="research-action"><strong>{i+1}. {f.name}</strong><p>{fundTiers[f.tier]??"Research only"} · {f.action==="COMPARE_FOR_SIP"?"Compare for SIP":f.action==="REVIEW_BEFORE_NEW_SIP"?"Review before a new SIP":"Watch for confirmation"}</p><small>NAV observation {f.nav_date}{f.relative_risk?" · "+f.relative_risk.replace(/_/g," ").toLowerCase():""}</small><ul>{f.reasons.map((v,j)=><li key={j}>{v}</li>)}</ul><details><summary>Evidence limitations</summary><ul>{f.limitations.map((v,j)=><li key={j}>{v}</li>)}</ul></details></div>)}</article>})}</div>
  <small className="muted">{report.notice}</small>
 </section>;
}
