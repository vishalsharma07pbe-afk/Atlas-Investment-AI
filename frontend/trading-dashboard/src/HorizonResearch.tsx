import {useEffect,useState,type ReactNode} from "react";
import WatchOutcomeHistory from "./WatchOutcomeHistory";
import IntradayResearch from "./IntradayResearch";
import AdvancedSection from "./AdvancedSection";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
import AutomaticCompanyNews,{type NewsEvidence} from "./AutomaticCompanyNews";

export type Horizon="INTRADAY"|"SWING"|"SHORT_TERM"|"LONG_TERM";
type AiReview={reviews:{provider:string;findings:{statement:string;evidence_ids:string[]}[]}[];reviewed_at:string;notice:string};
type Candidate={news_evidence?:NewsEvidence;company_evidence?:CompanyEvidence;ai_review?:AiReview;id:number;symbol:string;exchange:string;as_of:string;close:number;rank_score:number;review_horizon:string;history_count:number;atr_percent:number;median_daily_traded_value:number;reasons:string[];warnings:string[]};
type HorizonResult={status:string;candidates:Candidate[];matched_count:number;evaluated_count:number;blockers:string[];exclusions:Record<string,number>};
type Section={section:string;status:string;generated_at:string|null;result:{universe_size:number;eligible_count:number;horizons?:Partial<Record<Horizon,HorizonResult>>}|null};
type ReplayCost={cost_bps_per_side:number;net_return_percent:number;matched_gross_exposure_return_percent:number;max_drawdown_percent:number;win_rate_percent:number|null;wins:number;losses:number;flat:number};
type ReplayItem={exchange:string;symbol:string;as_of:string;trades:number;holding_sessions:number;test_start:string;test_end:string;gross_buy_hold_percent:number;small_sample:boolean;cost_scenarios:ReplayCost[]};
type Validation={status?:string;sample_count?:number;horizons?:Partial<Record<Horizon,{counts:Record<string,number>;observed_instruments:number;items:ReplayItem[]}>>;notice?:string};
type Snapshot={strategy_validation?:Validation;enabled:boolean;sections:Section[];automatic_ai_status?:string;automatic_company_status?:string;automatic_news_status?:string};
const titles:Record<Horizon,string>={INTRADAY:"Intraday research",SWING:"Swing trading research",SHORT_TERM:"Short-term equity research",LONG_TERM:"Long-term investment research"};
const descriptions:Record<Horizon,string>={INTRADAY:"Completed current-session candle research. Live liquidity and event risk are not independently verified.",SWING:"Daily trend, relative volume and volatility checks for potential multi-session setups.",SHORT_TERM:"Medium-term trend and 60-session momentum. Fundamental and event research must still confirm each watch candidate.",LONG_TERM:"200-session price trend and longer-term momentum. A technical watch is not a business-quality or fair-value assessment."};
const words=(value:string)=>value.toLowerCase().replace(/_/g," ");
const money=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);

function StrategyValidation({data,horizon}:{data:Validation;horizon:Horizon}){
 const result=data.horizons?.[horizon];
 return <section className="panel glass" aria-label="Automatic historical strategy validation">
  <div className="sectionhead"><div><h3>Historical strategy replay</h3><p className="muted tiny">Existing fixed rules tested on later chronological data, not a forecast.</p></div><span className="tag">RESEARCH ONLY</span></div>
  <p>{data.sample_count??0} recently attempted registry instruments · {result?.observed_instruments??0} instruments with completed simulated positions</p>
  {result&&<p className="muted tiny">{Object.entries(result.counts).map(([state,count])=>words(state)+": "+count).join(" · ")}</p>}
  {!result?.items.length?<p>No usable replay results yet. Adjusted, validated history and a sufficient holdout window are required.</p>:result.items.map(item=><details key={item.exchange+":"+item.symbol}><summary>{item.symbol} · {item.exchange} · {item.trades} simulated positions{item.small_sample?" · small sample":""}</summary>
   <p>{item.test_start} to {item.test_end} · {item.holding_sessions} session holding window · gross same-asset buy and hold {item.gross_buy_hold_percent}%.</p>
   <div className="tablewrap"><table><thead><tr><th>Cost per side</th><th>Net simulated return</th><th>Maximum drawdown</th><th>Win rate</th><th>Wins / losses / flat</th></tr></thead><tbody>{item.cost_scenarios.map(cost=><tr key={cost.cost_bps_per_side}><td>{cost.cost_bps_per_side} bps</td><td>{cost.net_return_percent}%</td><td>{cost.max_drawdown_percent}%</td><td>{cost.win_rate_percent===null?"—":cost.win_rate_percent+"%"}</td><td>{cost.wins} / {cost.losses} / {cost.flat}</td></tr>)}</tbody></table></div>
   <p className="muted tiny">Illustrative all-in costs; not actual broker fees or a market index comparison.</p>
  </details>)}
  <p className="muted tiny">{data.notice||"Historical validation unavailable or disabled."} Existing recommendation blockers remain unchanged.</p>
 </section>;
}

export default function HorizonResearch({horizon,children,onSettings}:{horizon:Horizon;children:ReactNode;onSettings:()=>void}){
 const [data,setData]=useState<Snapshot|null>(null);
 const [error,setError]=useState(false);
 useEffect(()=>{
   let active=true,pending=false;const controller=new AbortController();
   async function load(){
     if(pending)return;pending=true;
     try{
       const response=await fetch("/intelligence/api/v1/intelligence/research/overview",{cache:"no-store",signal:controller.signal});
       if(!response.ok)throw Error();
       const result:Snapshot=await response.json();
       if(!Array.isArray(result.sections))throw Error();
       if(active){setData(result);setError(false);}
     }catch{if(active)setError(true);}finally{pending=false;}
   }
   if(horizon==="INTRADAY")return;
   void load();const timer=window.setInterval(load,30000);
   return()=>{active=false;controller.abort();window.clearInterval(timer);};
 },[horizon]);
 const sections=data?.sections.filter(s=>s.section==="NSE"||s.section==="BSE")||[];
 const ready=sections.filter(s=>s.status==="READY"&&data?.enabled&&!error&&s.result?.horizons?.[horizon]);
 const ranked=ready.flatMap(s=>s.result!.horizons![horizon]!.candidates).sort((a,b)=>b.rank_score-a.rank_score||a.exchange.localeCompare(b.exchange)||a.symbol.localeCompare(b.symbol)).slice(0,5);
 const blockers=[...new Set(ready.flatMap(s=>s.result!.horizons![horizon]!.blockers))];
 return <section className="horizon-workspace" aria-label={titles[horizon]}>
  <section className="panel glass horizon-hero">
   <div className="sectionhead"><div><small className="section-kicker">AUTOMATIC RESEARCH</small><h2>{titles[horizon]}</h2><p>{descriptions[horizon]}</p></div><span className="tag">{horizon!=="INTRADAY"&&error?"UNAVAILABLE":horizon!=="INTRADAY"&&data?.enabled===false?"AUTOMATION OFF":"RESEARCH ONLY"}</span></div>
   {horizon!=="INTRADAY"&&<>
   {!data&&!error&&<p role="status">Loading saved research…</p>}
   {error&&<p role="alert" className="notice warning-notice">Research service is unavailable. No previous candidates are shown as current.</p>}
   {data?.enabled===false&&<p className="notice warning-notice">Automatic research is disabled.</p>}
   <div className="horizon-coverage">{sections.map(s=><div key={s.section}><strong>{s.section}</strong><span>{ready.includes(s)?(s.result?.eligible_count||0)+" / "+(s.result?.universe_size||0)+" daily histories eligible":s.status==="READY"?"Waiting for horizon refresh":words(s.status)}</span></div>)}</div>
   <p className="muted tiny">Bounded registry sample; not a whole-market ranking. Missing source evidence is never replaced with estimates.</p>
   </>}
  </section>
  {horizon==="INTRADAY"?<IntradayResearch/>:<section className="panel glass horizon-results">
   <div className="sectionhead"><div><h3>Technical watch candidates</h3><p className="muted tiny">Up to five observations across the available NSE/BSE samples.</p></div></div>
   {ranked.length?<div className="horizon-cards">{ranked.map((candidate,index)=><article className="horizon-card" key={candidate.exchange+":"+candidate.id}>
    <header><div><small>#{index+1} · {candidate.exchange}</small><h3>{candidate.symbol}</h3></div><strong>{money(candidate.close)}</strong></header>
    <p className="muted tiny">Daily close · {candidate.as_of}</p><p>{candidate.review_horizon}</p>
    <dl><div><dt>ATR / price</dt><dd>{candidate.atr_percent.toFixed(2)}%</dd></div><div><dt>History</dt><dd>{candidate.history_count} sessions</dd></div></dl>
    <details><summary>Why this appears &amp; risks</summary><ul>{candidate.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul><p>{candidate.warnings.join(" ")}</p><p className="muted tiny">Median historical daily traded value: {money(candidate.median_daily_traded_value)}</p></details>
    <CompanyEvidenceCard evidence={candidate.company_evidence} status={data?.automatic_company_status}/>
    <AutomaticCompanyNews evidence={candidate.news_evidence} status={data?.automatic_news_status}/>
    {candidate.ai_review?.reviews.length?<details><summary>Automatic AI evidence review ({candidate.ai_review.reviews.length} provider{candidate.ai_review.reviews.length===1?"":"s"})</summary>{candidate.ai_review.reviews.map(review=><div key={review.provider}><strong>{review.provider}</strong><ul>{review.findings.map((finding,i)=><li key={i}>{finding.statement} <small>[{finding.evidence_ids.join(", ")}]</small></li>)}</ul></div>)}<p className="muted tiny">OBS = dated technical observations above; LIMITS = missing research evidence. {candidate.ai_review.notice}</p></details>:<p className="muted tiny">{data?.automatic_ai_status==="ENABLED"?"AI review pending or unavailable.":data?.automatic_ai_status==="NO_CONFIGURED_PROVIDER"?"No permitted AI provider configured.":"Automatic AI review unavailable or disabled."}</p>}
   </article>)}</div>:<div className="research-empty"><strong>{ready.length?"No technical candidates meet the current rules":"Waiting for current research"}</strong><p>The background engine will reassess available evidence automatically. No manual scan is required.</p></div>}
   {blockers.length>0&&<p className="notice warning-notice">Still required before a complete investment verdict: {blockers.map(words).join(" · ")}.</p>}
   <button type="button" className="secondary" onClick={onSettings}>Check data connections</button>
  </section>
  }
  {horizon!=="INTRADAY"&&data?.enabled&&!error&&data.strategy_validation&&<StrategyValidation data={data.strategy_validation} horizon={horizon}/>}
  {horizon!=="INTRADAY"&&<AdvancedSection title="Research history and outcomes" description="Automatically tracked dated technical watches"><WatchOutcomeHistory horizon={horizon}/></AdvancedSection>}
  <details className="advanced-tools glass" key={horizon}><summary><span><strong>Advanced research tools</strong><small>Optional detailed analysis and evidence review</small></span><b>Open tools</b></summary>{/* Closed tools stay available without loading their workflows. */}<DeferredTools>{children}</DeferredTools></details>
 </section>;
}
function DeferredTools({children}:{children:ReactNode}){
 // Existing tools are preserved. Explicitly mount only after user request.
 const [open,setOpen]=useState(false);
 return <div className="advanced-tools-content">{open?children:<button type="button" className="secondary" onClick={()=>setOpen(true)}>Load detailed tools</button>}</div>;
}
