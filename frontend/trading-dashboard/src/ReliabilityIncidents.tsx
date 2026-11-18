import {useEffect,useState} from "react";

type Incident={dataset:string;code:string;first_seen:string;last_seen:string;occurrences:number;state:"OPEN"|"RESOLVED"};
type MonitorStatus={enabled:boolean;running:boolean;interval_seconds:number|null;blocker:string|null;completed_runs:number;last_success_at:string|null;last_error_code:string|null};
type History={incidents:Incident[];open_count:number;mode:string;live_feed_connected:boolean};
const API="/intelligence/api/v1/intelligence/reliability";

export default function ReliabilityIncidents(){
  const [history,setHistory]=useState<History|null>(null);
  const [monitor,setMonitor]=useState<MonitorStatus|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    fetch(API+"/monitor",{signal:controller.signal})
      .then(r=>{if(!r.ok)throw Error("Monitor status unavailable");return r.json()})
      .then((value:MonitorStatus)=>setMonitor(value)).catch(()=>setMonitor(null));
    fetch(API+"/incidents",{signal:controller.signal})
      .then(r=>{if(!r.ok)throw Error("History request failed ("+r.status+")");return r.json()})
      .then((value:History)=>{setHistory(value);setError("")})
      .catch(e=>{if(e.name!=="AbortError")setError(String(e.message))});
    return ()=>controller.abort();
  },[refresh]);
  async function observe(){
    setBusy(true);setError("");
    try{
      const response=await fetch(API+"/observe",{method:"POST"});
      if(!response.ok)throw Error("Readiness observation failed ("+response.status+")");
      setRefresh(n=>n+1);
    }catch(e){setError(e instanceof Error?e.message:"Observation failed")}
    finally{setBusy(false)}
  }
  return <section className="panel glass health-card" aria-label="Reliability incident history">
    <div className="sectionhead"><div className="section-copy"><small className="section-kicker">LOCAL OBSERVATION HISTORY</small><h2>Data reliability incidents</h2>
      <p>Persistent, deduplicated observations of local source readiness. No automatic provider or live market connection.</p></div>
      <button className="primary" type="button" onClick={()=>void observe()} disabled={busy}>{busy?"Observing…":"Record current readiness"}</button>
    </div>
    {error&&<p role="alert">{error}</p>}
    <p>Scheduled local monitoring: <strong>{monitor?.running?"Running":monitor?.enabled?"Starting or unavailable":"Disabled"}</strong> · Interval: {monitor?.interval_seconds??"—"} seconds · Completed: {monitor?.completed_runs??"—"} · Last success: {monitor?.last_success_at?new Date(monitor.last_success_at).toLocaleString("en-IN"):"Never"}{monitor?.last_error_code?" · Error: "+monitor.last_error_code:""}</p>
    <p>Enable locally with ATLAS_READINESS_MONITOR_ENABLED=true in Docker environment. This monitors only imported evidence, not external market feeds.</p>
    <p role="status">Open incidents: <strong>{history?.open_count??"—"}</strong> · Local observation only</p>
    <div className="tablewrap"><table><thead><tr><th>Dataset</th><th>Issue</th><th>Status</th><th>First seen</th><th>Last seen</th><th>Observations</th></tr></thead>
      <tbody>{history?.incidents.map(i=><tr key={i.dataset+":"+i.code}><td>{i.dataset}</td><td>{i.code.replace(/_/g," ")}</td><td>{i.state}</td>
        <td>{new Date(i.first_seen).toLocaleString("en-IN")}</td><td>{new Date(i.last_seen).toLocaleString("en-IN")}</td><td>{i.occurrences}</td></tr>)}
      {!history?.incidents.length&&<tr><td colSpan={6}>No observations recorded yet. Record current readiness to begin tracking.</td></tr>}</tbody></table></div>
    <p>Resolved means an issue was absent from the latest complete observation, not that a licensed feed was activated.</p>
  </section>;
}
