import {useEffect,useState} from "react";
import {CoverageMeter,fmt} from "./ResearchVisuals";

type Venue={
 exchange:"NSE"|"BSE";target_session:string|null;calendar_status:string;
 mapped_listings:number;mapped_companies:number;current_listings:number|null;deep_listings:number|null;
 adjusted_depth_listings:number|null;recoverable_missing:number|null;due_missing:number|null;
 active_claims:number;expired_claims:number;failed_last_attempts:number;never_attempted:number;
 suspended_listings:number;protected_adjusted_listings:number;last_attempt_at:string|null;
 last_successful_attempt_started_at:string|null;next_deferred_missing_attempt_at:string|null;
};
type Progress={
 generated_at:string;configured:boolean;provider_blocked:boolean;provider_blocked_until:string|null;
 distinct_mapped_companies:number;depth_target:number;exchanges:Venue[];
};
type Observation={current:Progress;previous:Progress|null};
const date=(s:string|null)=>s&&Number.isFinite(Date.parse(s))?new Date(s).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"}):"—";
const amount=(n:number|null)=>fmt(n,0);

export function RecoveryDetails(){
 const [observation,setObservation]=useState<Observation|null>(null);
 const [error,setError]=useState(false);
 const [loading,setLoading]=useState(false);
 const [revision,setRevision]=useState(0);
 useEffect(()=>{
  let pending=false;
  const controller=new AbortController();
  const poll=async()=>{
   if(document.visibilityState!=="visible"||pending||controller.signal.aborted)return;
   pending=true;setLoading(true);
   try{
    const response=await fetch("/api/v1/data-health/history-recovery",{signal:controller.signal,cache:"no-store"});
    if(!response.ok)throw Error("Recovery unavailable");
    const next:Progress=await response.json();
    if(!Array.isArray(next.exchanges)||next.exchanges.length!==2||!Number.isFinite(Date.parse(next.generated_at)))throw Error("Invalid observation");
    if(!controller.signal.aborted){
     setObservation(old=>({current:next,previous:old?.current??null}));setError(false);
    }
   }catch{
    if(!controller.signal.aborted){setError(true);setObservation(null);}
   }finally{pending=false;if(!controller.signal.aborted)setLoading(false);}
  };
  void poll();
  const timer=window.setInterval(poll,120000);
  document.addEventListener("visibilitychange",poll);
  return()=>{controller.abort();window.clearInterval(timer);document.removeEventListener("visibilitychange",poll);};
 },[revision]);
 const data=observation?.current;
 return <div className="overview-evidence-body">
  <div className="sectionhead"><div><h3>Historical acquisition progress</h3><small>Stored listing evidence · no provider requests</small></div>
   <button className="secondary" type="button" disabled={loading} onClick={()=>setRevision(n=>n+1)}>Refresh progress</button></div>
  {error&&<p role="alert">Acquisition progress is unavailable. No coverage estimate is shown.</p>}
  {!data&&!error&&<p role="status">Checking acquisition ledger…</p>}
  {data&&<>
   <p role="status">{data.configured?"Automatic history collection configured":"Automatic history collection not configured"} · {data.provider_blocked?"Provider cooldown active":"No operator cooldown observed"}</p>
   {data.provider_blocked&&<p>Provider cooldown until {date(data.provider_blocked_until)} IST. Due counts do not override this block.</p>}
   <p><strong>{amount(data.distinct_mapped_companies)}</strong> distinct mapped ISINs across NSE and BSE · Observed {date(data.generated_at)} IST</p>
   <div className="research-visual-grid">
   {data.exchanges.map(v=>{
    const prior=observation?.previous?.exchanges.find(p=>p.exchange===v.exchange);
    const delta=prior&&prior.target_session===v.target_session&&v.target_session&&prior.mapped_listings===v.mapped_listings&&prior.current_listings!==null&&v.current_listings!==null?v.current_listings-prior.current_listings:null;
    return <article className="autonomous-result" key={v.exchange} aria-label={v.exchange+" acquisition progress"}>
     <header><strong>{v.exchange}</strong><small>{v.target_session?"Target "+v.target_session:"Target session unverified"}</small></header>
     <p>{amount(v.mapped_listings)} mapped listings · {amount(v.mapped_companies)} distinct ISINs</p>
     {v.current_listings!==null&&v.mapped_listings>0?<CoverageMeter label={v.exchange+" target-session candles"} value={v.current_listings} total={v.mapped_listings}/>:<p>{v.target_session?"No mapped listings":"Current-session coverage unknown"}</p>}
     {delta!==null&&<p>Net change since previous observation: {delta>0?"+":""}{delta} listing(s)</p>}
     <dl className="research-status-line"><div><dt>Latest-session backlog eligible for recovery</dt><dd>{amount(v.recoverable_missing)}</dd></div><div><dt>Due missing listings (ledger)</dt><dd>{amount(v.due_missing)}</dd></div></dl>
     <p>{amount(v.deep_listings)} with at least {data.depth_target} validated dates · {amount(v.adjusted_depth_listings)} with at least {data.depth_target} adjusted dates</p>
     <details><summary>Attempt ledger &amp; exclusions</summary>
      <p>{amount(v.active_claims)} unexpired claims · {amount(v.expired_claims)} expired claims · {amount(v.failed_last_attempts)} failed last attempts · {amount(v.never_attempted)} never attempted</p>
      <p>{amount(v.suspended_listings)} reported suspended · {amount(v.protected_adjusted_listings)} adjusted-series protected (may overlap)</p>
      <p>Last attempt: {date(v.last_attempt_at)} · Latest retained successful attempt started: {date(v.last_successful_attempt_started_at)} · Next deferred missing attempt: {date(v.next_deferred_missing_attempt_at)} (IST)</p>
     </details>
    </article>;
   })}
   </div>
   <p className="muted tiny">Listing counts are venue-specific; ISINs can overlap. Due counts are for missing target candles, not all depth or gap repairs. Depth counts do not prove continuity or research eligibility. Research snapshot eligibility and qualification are reported separately. Updates every two minutes while expanded and visible; no ETA is inferred.</p>
  </>}
 </div>;
}
export default function HistoryRecoveryProgress(){
 const [open,setOpen]=useState(false);
 return <details className="overview-evidence-group" onToggle={e=>setOpen(e.currentTarget.open)}>
  <summary>Automatic historical data recovery</summary>
  {open&&<RecoveryDetails/>}
 </details>;
}
