import {useEffect,useState} from "react";

type Dataset={code:string;label:string;records:number|null;latest_observed_at:string|null;age:number|null;age_unit:string;freshness_threshold:number;status:string;ingestion_mode:string;independently_verified:boolean;automatic_collection_enabled:boolean;usable_as_live_market_data:boolean};
type CalendarContext={status:string;observed_at?:string;sessions:{exchange:string;session_date:string;phase:string;open_at:string|null;close_at:string|null}[];notice?:string};
type ResearchJobs={calendar?:CalendarContext;status:string;jobs:{job:string;status:string;attempted_at:string|null;last_completed_at:string|null;next_due_at:string|null;consecutive_failures:number;interrupted_attempts:number;error_code:string|null}[];notice?:string};
type ProviderRecovery={status:string;providers:{provider:string;state:string;retry_after_seconds:number;failures:number;last_error:string|null}[]};
type PublicFeedSchedule={status:string;enabled?:boolean;jobs:{provider:string;status:string;attempts:number;interruptions:number;error_code:string|null;last_success_at:string|null;next_attempt_at:string|null}[]};
type Readiness={public_feed_schedule?:PublicFeedSchedule;provider_http_recovery?:ProviderRecovery;research_jobs?:ResearchJobs;generated_at:string;status:string;provider_mode:string;live_market_data_connected:boolean;automatic_research_enabled:boolean;actionable_recommendations_enabled:boolean;blockers:string[];datasets:Dataset[];backend_evidence?:Dataset[];research_sections?:{section:string;status:string;generated_at:string|null}[];notice:string};

export default function DataReadiness(){
  const [data,setData]=useState<Readiness|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);
    fetch("/intelligence/api/v1/intelligence/data-readiness",{signal:controller.signal})
      .then(r=>{if(!r.ok)throw Error("Readiness service returned "+r.status);return r.json()})
      .then((result:Readiness)=>{setData(result);setError("")})
      .catch(e=>{if(e.name!=="AbortError"){setError("Cannot verify source readiness: "+String(e.message));setData(null)}})
      .finally(()=>setLoading(false));
    return ()=>controller.abort();
  },[refresh]);
  return <section className="panel glass" aria-label="Source readiness">
    <div className="sectionhead"><div className="section-copy"><small className="section-kicker">SOURCE STATUS</small><h2>Data source readiness</h2>
      <p>Independent freshness, provenance and access checks. Local evidence never counts as a licensed live feed.</p></div>
      <button className="secondary" type="button" onClick={()=>setRefresh(n=>n+1)} disabled={loading}>Refresh status</button></div>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p role="status">Checking local data readiness…</p>}
    {data&&<>
      <p role="status"><strong>Automatic research: {data.automatic_research_enabled?"configured":"disabled"}</strong> · Provider: {data.provider_mode} · Live feed: {data.live_market_data_connected?"fresh subscribed tick observed":"not verified"}</p>
      <p>Last checked: {new Date(data.generated_at).toLocaleString("en-IN")}</p>
      <div className="tablewrap"><table><thead><tr><th>Dataset</th><th>Records</th><th>Latest observation</th><th>Freshness</th><th>Collection</th></tr></thead>
        <tbody>{[...(data.backend_evidence||[]),...data.datasets].map(d=><tr key={d.code}>
          <td>{d.label}</td><td>{d.records??"—"}</td><td>{d.latest_observed_at??"No records"}</td>
          <td>{d.status.replace(/_/g," ")}{d.age!==null?" ("+d.age+" "+d.age_unit+" old)":""}</td>
          <td>{d.automatic_collection_enabled?"Automatic configured":d.ingestion_mode.replace(/_/g," ").toLowerCase()}</td>
        </tr>)}</tbody></table></div>
      {data.research_sections?.length?<div><h3>Research snapshot status</h3><div className="tablewrap"><table><thead><tr><th>Section</th><th>Status</th><th>Generated</th></tr></thead><tbody>{data.research_sections.map(row=><tr key={row.section}><td>{row.section.replace(/_/g," ")}</td><td>{row.status}</td><td>{row.generated_at?new Date(row.generated_at).toLocaleString("en-IN"):"Not yet generated"}</td></tr>)}</tbody></table></div></div>:null}
      {data.research_jobs?.calendar&&data.automatic_research_enabled&&<div><h3>Exchange session context</h3>{data.research_jobs.calendar.sessions.length?<div className="tablewrap"><table><thead><tr><th>Exchange</th><th>Session date (IST)</th><th>Scheduled phase</th><th>Stored session hours (IST)</th></tr></thead><tbody>{data.research_jobs.calendar.sessions.map(row=><tr key={row.exchange}><td>{row.exchange}</td><td>{row.session_date}</td><td>{row.phase.replace(/_/g," ")}</td><td>{row.open_at&&row.close_at?`${new Date(row.open_at).toLocaleTimeString("en-IN",{timeZone:"Asia/Kolkata",hour:"2-digit",minute:"2-digit"})} – ${new Date(row.close_at).toLocaleTimeString("en-IN",{timeZone:"Asia/Kolkata",hour:"2-digit",minute:"2-digit"})}`:"—"}</td></tr>)}</tbody></table></div>:<p>Current exchange calendar context unavailable or pending.</p>}<p className="muted tiny">{data.research_jobs.calendar.notice||"Calendar status does not establish live connectivity."}</p></div>}
      {data.research_jobs&&data.automatic_research_enabled&&<details><summary>Background research job diagnostics</summary><p>{data.research_jobs.status.replace(/_/g," ")}</p>{data.research_jobs.jobs.length>0&&<div className="tablewrap"><table><thead><tr><th>Job</th><th>State</th><th>Last completed pass</th><th>Next due</th><th>Retries / interruptions</th></tr></thead><tbody>{data.research_jobs.jobs.map(job=><tr key={job.job}><td>{job.job.replace(/_/g," ").replace("SECTION:","Snapshot · ")}</td><td>{job.status.replace(/_/g," ")}{job.error_code&&<small> · {job.error_code.replace(/_/g," ")}</small>}</td><td>{job.last_completed_at?new Date(job.last_completed_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"}):"—"}</td><td>{job.next_due_at?new Date(job.next_due_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"}):"—"}</td><td>{job.consecutive_failures} / {job.interrupted_attempts}</td></tr>)}</tbody></table></div>}<p className="muted tiny">{data.research_jobs.notice}</p></details>}
      {data.public_feed_schedule&&<details><summary>Automatic catalog synchronization</summary><p>{data.public_feed_schedule.status.replace(/_/g," ")} · {data.public_feed_schedule.enabled?"Configured":"Not configured"}</p>{data.public_feed_schedule.jobs.length>0&&<div className="tablewrap"><table><thead><tr><th>Catalog</th><th>Status</th><th>Last success</th><th>Next eligible attempt</th><th>Attempts / interruptions</th></tr></thead><tbody>{data.public_feed_schedule.jobs.map(job=><tr key={job.provider}><td>{job.provider==="UPSTOX"?"Upstox instruments":"AMFI NAV"}</td><td>{job.status.replace(/_/g," ")}{job.error_code&&<small> · {job.error_code.replace(/_/g," ")}</small>}</td><td>{job.last_success_at?new Date(job.last_success_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"}):"—"}</td><td>{job.next_attempt_at?new Date(job.next_attempt_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"}):"—"}</td><td>{job.attempts} / {job.interruptions}</td></tr>)}</tbody></table></div>}<p className="muted tiny">Catalog job state is separate from source freshness and live connectivity.</p></details>}
      {data.provider_http_recovery&&<details><summary>Provider HTTP recovery</summary><p>{data.provider_http_recovery.status.replace(/_/g," ")}</p><p className="muted tiny">Shared Python HTTP recovery state; not proof of live connectivity or independent backup access.</p>{data.provider_http_recovery.providers.length>0&&<div className="tablewrap"><table><thead><tr><th>Provider</th><th>State</th><th>Retry delay</th><th>Consecutive failures</th></tr></thead><tbody>{data.provider_http_recovery.providers.map(p=><tr key={p.provider}><td>{p.provider}</td><td>{p.state.replace(/_/g," ")}{p.last_error&&<small> · {p.last_error.replace(/_/g," ")}</small>}</td><td>{p.retry_after_seconds?String(p.retry_after_seconds)+" s":"—"}</td><td>{p.failures}</td></tr>)}</tbody></table></div>}</details>}
      {data.blockers.length>0&&<p><strong>Outstanding data checks:</strong> {data.blockers.map(x=>x.replace(/_/g," ")).join(" · ")}</p>}
      <p className="muted tiny">Fully qualified investment recommendations are not enabled by this status check.</p>
      <p>{data.notice}</p>
    </>}
  </section>;
}
