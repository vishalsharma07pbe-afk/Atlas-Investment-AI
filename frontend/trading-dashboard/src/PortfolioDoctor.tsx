import {useEffect,useState} from "react";

type HoldingReview={id:number;symbol:string;asset_type:string;exchange:string|null;status:"REVIEW_REQUIRED"|"MONITOR"|"EVIDENCE_GAP";weight_percent:number|null;recorded_return_percent:number|null;evidence_date:string|null;history_count:number;change_20_observations_percent:number|null;recent_peak_change_percent:number|null;findings:string[];missing_evidence:string[]};
type Review={generated_at:string;holding_count:number;attention_count:number;data_gap_count:number;holdings:HoldingReview[];notice:string};
const pct=(value:number|null)=>value==null?"—":(value>0?"+":"")+value.toFixed(2)+"%";
const statuses={REVIEW_REQUIRED:"Needs review",MONITOR:"Monitor",EVIDENCE_GAP:"Data needed"};

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
    <div className="doctor-list">{review.holdings.slice(0,expanded?review.holdings.length:5).map(item=><article key={item.id} className="doctor-item">
      <header><div><strong>{item.symbol}</strong><small>{item.asset_type==="MUTUAL_FUND"?"Mutual fund":item.exchange||"Equity"}</small></div><span className={item.status==="REVIEW_REQUIRED"?"doctor-warning":"doctor-neutral"}>{statuses[item.status]}</span></header>
      {item.findings.length?<ul>{item.findings.map(f=><li key={f}>{f}</li>)}</ul>:<p>{item.status==="EVIDENCE_GAP"?"More reliable data is needed.":"No threshold breach in the available observations; not a complete investment assessment."}</p>}
      <details><summary>Evidence and limitations</summary><dl><div><dt>Recorded weight</dt><dd>{pct(item.weight_percent)}</dd></div><div><dt>Recorded return</dt><dd>{pct(item.recorded_return_percent)}</dd></div><div><dt>20-observation change</dt><dd>{pct(item.change_20_observations_percent)}</dd></div><div><dt>Recent peak change</dt><dd>{pct(item.recent_peak_change_percent)}</dd></div></dl><p>History: {item.history_count} observations · {item.evidence_date||"No verified observation date"}</p><ul>{item.missing_evidence.map(m=><li key={m}>{m}</li>)}</ul></details>
    </article>)}</div>
    {review.holdings.length>5&&<button type="button" className="secondary" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?"Show fewer holdings":"Show all holdings"}</button>}
    <p className="muted tiny">Reviewed {new Date(review.generated_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST. {review.notice}</p>
  </>}
 </section>;
}
