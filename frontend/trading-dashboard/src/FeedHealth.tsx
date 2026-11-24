import {useEffect,useState} from "react";

type Health={
 generated_at:string;provider:string;state:string;reason:string;retry_after_seconds?:number;
 transport_connected:boolean;worker_running:boolean;frames_processed:number;
 rejected_entries:number;cached_instruments:number;live_prices_verified:boolean;
 entitlement_verified:boolean;configuration_ready:boolean;fresh_provider_frames:boolean;blocker_codes:string[];note:string;
};
export default function FeedHealth(){
 const [health,setHealth]=useState<Health|null>(null);
 const [error,setError]=useState("");
 const [refresh,setRefresh]=useState(0);
 useEffect(()=>{
   const controller=new AbortController();
   fetch("/intelligence/api/v1/intelligence/providers/upstox/feed-health",{signal:controller.signal})
    .then(r=>{if(!r.ok)throw Error("Feed diagnostics unavailable");return r.json()})
    .then((data:Health)=>{setHealth(data);setError("")})
    .catch(e=>{if(e.name!=="AbortError"){setHealth(null);setError("Unable to read feed health")}});
   return ()=>controller.abort();
 },[refresh]);
 return <section className="panel glass health-card" aria-label="Provider feed health">
  <div className="sectionhead"><div className="section-copy"><small className="section-kicker">READ-ONLY DIAGNOSTICS</small><h2>Provider feed health</h2>
   <p>Read-only Upstox transport diagnostics. Connection alone never verifies live prices or data rights.</p></div>
   <button className="secondary" type="button" onClick={()=>setRefresh(n=>n+1)}>Refresh diagnostics</button></div>
  {error&&<p role="alert">{error}</p>}
  {health&&<>
   <div className="health-status" role="status"><strong>{health.state.replace(/_/g," ")}</strong><span>{health.reason.replace(/_/g," ")}</span><small>Observed {new Date(health.generated_at).toLocaleString("en-IN")}</small></div>
   {health.reason==="FEED_CREDENTIAL_REJECTED"&&<p role="alert">Upstox rejected the configured credential. Renew it using your authorized Upstox sign-in, update local configuration and restart the affected services. Never paste a token into a support message.</p>}
   {!!health.retry_after_seconds&&<p>Automatic reconnect cooldown: about {Math.ceil(health.retry_after_seconds/60)} minute(s) remaining at the last check.</p>}
   <div className="stats health-metrics">
    <div className="stat glass"><small>TRANSPORT</small><strong>{health.transport_connected?"Connected":"Disconnected"}</strong></div>
    <div className="stat glass"><small>FRAMES</small><strong>{health.frames_processed}</strong></div>
    <div className="stat glass"><small>REJECTED</small><strong>{health.rejected_entries}</strong></div>
    <div className="stat glass"><small>CACHED KEYS</small><strong>{health.cached_instruments}</strong></div>
   </div>
   <p>Provider configuration: {health.configuration_ready?"Ready":"Incomplete"} · Fresh validated frames: {health.fresh_provider_frames?"Yes":"No"}</p>
   {health.blocker_codes.length>0&&<p>Blockers: {health.blocker_codes.join(", ")}</p>}
   <p>{health.note}</p>
  </>}
 </section>;
}
