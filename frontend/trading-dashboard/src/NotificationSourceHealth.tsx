import {useState} from "react";
import IpoImportHistory from "./IpoImportHistory";
type Source={source_name:string;enabled:boolean;permission_declared:boolean;alert_count:number;latest_publication_at:string|null;latest_subscription_as_of:string|null;subscription_snapshot_stale:boolean|null;status:string};
type Health={status:string;configured_sources:number;sources:Source[];live_feed_connected:boolean;notice:string};
export default function NotificationSourceHealth(){
  const [open,setOpen]=useState(false);
  const [health,setHealth]=useState<Health|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function toggle(){
    if(open){setOpen(false);return;}
    setOpen(true);setError("");setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/notifications/sources/health",{cache:"no-store"});
      if(!response.ok)throw Error("Source diagnostics unavailable");
      setHealth(await response.json() as Health);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <div className="atlas-source-health">
    <button className="secondary" type="button" aria-expanded={open} onClick={toggle}>{open?"Hide source health":"Check source health"}</button>
    {open&&<div aria-label="Notification source health">
      {loading&&<p role="status">Checking local source health…</p>}
      {error&&<p role="alert">{error}</p>}
      {!loading&&!error&&health&&<>
        <p className="muted tiny">{health.configured_sources} configured sources · Live feeds: {health.live_feed_connected?"connected":"not connected"}</p>
        {health.sources.map(s=><div className="atlas-notification-item" key={s.source_name}>
          <strong>{s.source_name}</strong>
          <small>Status: {s.status.replace(/_/g," ")} · {s.alert_count} imported alerts</small>
          {s.latest_publication_at&&<small>Last publication: {s.latest_publication_at}</small>}
          {s.latest_subscription_as_of&&<small>Subscription as of: {s.latest_subscription_as_of}</small>}
          {s.subscription_snapshot_stale&&<strong className="atlas-stale-label">SUBSCRIPTION SNAPSHOT STALE</strong>}
        </div>)}
        <p className="muted tiny">{health.notice}</p>
      </>}
    </div>}
    <IpoImportHistory/>
  </div>;
}
