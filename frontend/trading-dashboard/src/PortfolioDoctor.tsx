import {useEffect,useState} from "react";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
import AutomaticCompanyNews,{type NewsEvidence} from "./AutomaticCompanyNews";

type Thesis={status:string;company_evidence:CompanyEvidence|null;news_evidence:NewsEvidence|null;ai_status:string;ai_review:{provider:string;findings:{statement:string;evidence_ids:string[]}[];notice:string}|null};
type FundHistory={scheme_name:string;nav:number;nav_date:string;cagr_3y_percent:number;drawdown_3y_percent:number;weekly_volatility_percent?:number;sources:string[];notice:string};
type ThesisFinding={statement:string;source:string};
type ThesisSummary={status:string;risks:ThesisFinding[];observations:ThesisFinding[];review_prompts:ThesisFinding[];gaps:string[];notice:string};
type HoldingReview={thesis_summary?:ThesisSummary;thesis_evidence?:Thesis;fund_history_evidence?:FundHistory;id:number;symbol:string;asset_type:string;exchange:string|null;status:"REVIEW_REQUIRED"|"MONITOR"|"EVIDENCE_GAP";weight_percent:number|null;recorded_return_percent:number|null;evidence_date:string|null;history_count:number;change_20_observations_percent:number|null;recent_peak_change_percent:number|null;findings:string[];missing_evidence:string[]};
type Review={thesis_review_count?:number;generated_at:string;holding_count:number;attention_count:number;data_gap_count:number;holdings:HoldingReview[];notice:string};
const pct=(value:number|null)=>value==null?"—":(value>0?"+":"")+value.toFixed(2)+"%";
const statuses={REVIEW_REQUIRED:"Needs review",MONITOR:"Monitor",EVIDENCE_GAP:"Data needed"};

function ThesisDigest({summary}:{summary:ThesisSummary}){
 return <div className="thesis-digest">
  <h4>Investment research summary</h4>
  <p className="muted tiny">{summary.status==="REVIEW_EVIDENCE"?"Evidence warrants review":"Insufficient evidence for an investment verdict"}</p>
  {summary.risks.length>0&&<><strong>Recorded risks</strong><ul>{summary.risks.map((f,i)=><li key={i}>{f.statement} <small className="muted">({f.source})</small></li>)}</ul></>}
  {summary.review_prompts.length>0&&<><strong>What to investigate</strong><ul>{summary.review_prompts.map((f,i)=><li key={i}>{f.statement} <small className="muted">({f.source})</small></li>)}</ul></>}
  {summary.observations.length>0&&<><strong>Other measured observations</strong><ul>{summary.observations.map((f,i)=><li key={i}>{f.statement} <small className="muted">({f.source})</small></li>)}</ul></>}
  <details><summary>Unverified or missing evidence ({summary.gaps.length})</summary><ul>{summary.gaps.map((gap,i)=><li key={i}>{gap}</li>)}</ul></details>
  <p className="muted tiny">{summary.notice}</p>
 </div>;
}

export default function PortfolioDoctor({revision,onSettings}:{revision:number;onSettings:()=>void}){
 const [review,setReview]=useState<Review|null>(null);
 const [error,setError]=useState(false);
 const [expanded,setExpanded]=useState(false);
 useEffect(()=>{
  let active=true,pending=false;const controller=new AbortController();
  async function load(){
   if(pending)return;pending=true;
   try{
    const response=await fetch("/api/v1/portfolio/review",{cache:"no-store",signal:controller.signal});
    if(!response.ok)throw Error();
    const body:Review=await response.json();
    if(!Array.isArray(body.holdings))throw Error();
    if(active){setReview(body);setError(false);}
   }catch{if(active){setReview(null);setError(true);}}finally{pending=false;}
  }
  void load();const timer=window.setInterval(load,60000);
  return()=>{active=false;controller.abort();window.clearInterval(timer);};
 },[revision]);
 return <section className="panel glass portfolio-doctor" aria-label="Automatic portfolio review">
  <div className="sectionhead"><div><small className="section-kicker">AUTOMATIC PORTFOLIO REVIEW</small><h2>What needs your attention?</h2><p className="muted">ATLAS reviews your saved holdings and available historical evidence without a manual scan.</p></div><span className="tag">LOCAL RESEARCH</span></div>
  {error?<div role="alert" className="notice warning-notice">Portfolio review unavailable. <button type="button" className="secondary" onClick={onSettings}>Check data connections</button></div>:!review?<p role="status">Loading portfolio review…</p>:!review.holding_count?<p>No holdings yet. Add or synchronize your investments to begin automatic review.</p>:<>
    <div className="doctor-stats"><div><span>Holdings reviewed</span><strong>{review.holding_count}</strong></div><div><span>Need attention</span><strong>{review.attention_count}</strong></div><div><span>Core data gaps</span><strong>{review.data_gap_count}</strong></div></div>
    {review.thesis_review_count!=null&&<p className="muted">Holdings with research review prompts: <strong>{review.thesis_review_count}</strong> (includes recorded risk flags).</p>}
    <div className="doctor-list">{[...review.holdings].sort((a,b)=>Number(b.thesis_summary?.status==="REVIEW_EVIDENCE")-Number(a.thesis_summary?.status==="REVIEW_EVIDENCE")).slice(0,expanded?review.holdings.length:5).map(item=><article key={item.id} className="doctor-item">
      <header><div><strong>{item.symbol}</strong><small>{item.asset_type==="MUTUAL_FUND"?"Mutual fund":item.exchange||"Equity"}</small></div><span className={item.status==="REVIEW_REQUIRED"?"doctor-warning":"doctor-neutral"}>{statuses[item.status]}</span></header>
      {item.thesis_summary?<ThesisDigest summary={item.thesis_summary}/>:item.findings.length?<ul>{item.findings.map(f=><li key={f}>{f}</li>)}</ul>:<p>{item.status==="EVIDENCE_GAP"?"More reliable data is needed.":"No threshold breach in the available observations; not a complete investment assessment."}</p>}
      <details><summary>Evidence and limitations</summary><dl><div><dt>Recorded weight</dt><dd>{pct(item.weight_percent)}</dd></div><div><dt>Recorded return</dt><dd>{pct(item.recorded_return_percent)}</dd></div><div><dt>20-observation change</dt><dd>{pct(item.change_20_observations_percent)}</dd></div><div><dt>Recent peak change</dt><dd>{pct(item.recent_peak_change_percent)}</dd></div></dl><p>History: {item.history_count} observations · {item.evidence_date||"No verified observation date"}</p><ul>{item.missing_evidence.map(m=><li key={m}>{m}</li>)}</ul></details>
      {item.asset_type==="EQUITY"&&<details><summary>Company thesis &amp; local AI review</summary>
       <CompanyEvidenceCard evidence={item.thesis_evidence?.company_evidence??undefined} status={item.thesis_evidence?"ENABLED":undefined}/>
       <AutomaticCompanyNews evidence={item.thesis_evidence?.news_evidence??undefined} status={item.thesis_evidence?"ENABLED":undefined}/>
       {item.thesis_evidence?.ai_review?<><h4>Local AI · {item.thesis_evidence.ai_review.provider}</h4><ul>{item.thesis_evidence.ai_review.findings.map((f,i)=><li key={i}>{f.statement} <small>[{f.evidence_ids.join(", ")}]</small></li>)}</ul><p className="muted tiny">{item.thesis_evidence.ai_review.notice}</p></>:<p className="muted tiny">Local AI evidence pending or local model not configured. No external fallback.</p>}
      </details>}
      {item.asset_type==="MUTUAL_FUND"&&<details><summary>Exact scheme historical evidence</summary>{item.fund_history_evidence?<><p>{item.fund_history_evidence.scheme_name} · NAV ₹{item.fund_history_evidence.nav.toFixed(2)} · {item.fund_history_evidence.nav_date}</p><dl><div><dt>3-year CAGR</dt><dd>{pct(item.fund_history_evidence.cagr_3y_percent)}</dd></div><div><dt>Observed drawdown</dt><dd>{pct(item.fund_history_evidence.drawdown_3y_percent)}</dd></div><div><dt>Weekly volatility proxy</dt><dd>{pct(item.fund_history_evidence.weekly_volatility_percent??null)}</dd></div></dl><p className="muted tiny">Sources: {item.fund_history_evidence.sources.join(" · ")}. {item.fund_history_evidence.notice}</p></>:<p>Exact-scheme history insufficient or unavailable.</p>}</details>}
    </article>)}</div>
    {review.holdings.length>5&&<button type="button" className="secondary" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?"Show fewer holdings":"Show all holdings"}</button>}
    <p className="muted tiny">Reviewed {new Date(review.generated_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST. {review.notice}</p>
  </>}
 </section>;
}
