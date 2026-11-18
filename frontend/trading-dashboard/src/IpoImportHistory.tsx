import {useState} from "react";
type Attempt={attempted_at:string|null;mode:string;outcome:string;error_category:string|null;added:number|null;updated:number|null;skipped_older_or_equal:number|null;retained:number|null;input_sha256:string|null};
type Freshness={status:string;last_successful_apply_at:string|null;last_successful_dry_run_at:string|null;hours_since_successful_apply:number|null;stale_after_hours:number;notice:string};
type History={status:string;attempts:Attempt[];total:number;notice:string;freshness?:Freshness};
export default function IpoImportHistory(){
  const [open,setOpen]=useState(false);
  const [history,setHistory]=useState<History|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  async function toggle(){
    if(open){setOpen(false);return;}
    setOpen(true);setLoading(true);setError("");
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/notifications/providers/import-history",{cache:"no-store"});
      if(!response.ok)throw Error("Import history unavailable");
      setHistory(await response.json() as History);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <div className="atlas-source-health">
    <button className="secondary" type="button" aria-expanded={open} onClick={toggle}>{open?"Hide import history":"Check provider import history"}</button>
    {open&&<div aria-label="IPO provider import history">
      {loading&&<p role="status">Loading local import history…</p>}
      {error&&<p role="alert">{error}</p>}
      {!loading&&!error&&history&&<>
        <p className="muted tiny">{history.total} recorded attempts · {history.status.replace(/_/g," ")}</p>
        {history.freshness&&<div aria-label="Provider import freshness">
          <strong>Local import status: {history.freshness.status.replace(/_/g," ")}</strong>
          <small>Last successful apply: {history.freshness.last_successful_apply_at??"Never recorded"}</small>
          <small>Last successful dry run: {history.freshness.last_successful_dry_run_at??"Never recorded"}</small>
          <p className="muted tiny">{history.freshness.notice}</p>
        </div>}
        {history.attempts.map((a,i)=><div className="atlas-notification-item" key={i}>
          <strong>{a.outcome} · {a.mode}</strong>
          <small>{a.attempted_at??"Timestamp unavailable"}</small>
          {a.outcome==="SUCCESS"?<small>Added {a.added??0} · Updated {a.updated??0} · Retained {a.retained??0}</small>
            :<small>Failure category: {a.error_category??"Unavailable"}</small>}
        </div>)}
        <p className="muted tiny">{history.notice}</p>
      </>}
    </div>}
  </div>;
}
