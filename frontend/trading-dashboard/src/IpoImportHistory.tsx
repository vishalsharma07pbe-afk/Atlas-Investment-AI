import React,{useState} from "react";
type Attempt={attempted_at:string|null;mode:string;outcome:string;error_category:string|null;added:number|null;updated:number|null;skipped_older_or_equal:number|null;retained:number|null;input_sha256:string|null};
type History={status:string;attempts:Attempt[];total:number;notice:string};
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
    <button type="button" aria-expanded={open} onClick={toggle}>{open?"Hide import history":"Check provider import history"}</button>
    {open&&<div aria-label="IPO provider import history">
      {loading&&<p role="status">Loading local import history…</p>}
      {error&&<p role="alert">{error}</p>}
      {!loading&&!error&&history&&<>
        <p className="muted tiny">{history.total} recorded attempts · {history.status.replace(/_/g," ")}</p>
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
