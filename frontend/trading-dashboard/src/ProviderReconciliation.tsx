import React,{useState} from "react";
type Result={status:string;blockers:string[];candles_reviewed:number;unmatched_session_count:number;notice:string};
export default function ProviderReconciliation(){
  const [raw,setRaw]=useState("");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function review(){
    setError("");setResult(null);
    let payload:unknown;
    try{payload=JSON.parse(raw);}catch{setError("Enter valid reconciliation JSON.");return;}
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/providers/reconcile",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      if(!response.ok)throw Error("Reconciliation rejected. Check mapping, candle and session fields.");
      const value:Result=await response.json();
      if(value.status!=="BLOCKED_FROM_AUTOMATIC_INGESTION")throw Error("Unexpected reconciliation status.");
      setResult(value);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">DATA QUALITY · RECONCILIATION</small><h2>Provider-to-registry evidence review</h2></div><span className="tag">NO DATABASE WRITE</span></div>
    <p className="muted tiny">Paste a reconciliation JSON payload containing instrument mapping, local registry identifiers, provider candles, verified session dates and evidence declarations. This tool identifies blockers; it never imports candles or certifies third-party rights.</p>
    <label htmlFor="reconcile-json">Reconciliation request JSON</label>
    <textarea id="reconcile-json" aria-label="Reconciliation request JSON" rows={5} value={raw} onChange={e=>setRaw(e.target.value)} placeholder='{"mapping":{...},"candles":[...],"known_session_dates":[...]}'/>
    <button className="primary" disabled={loading} onClick={review}>{loading?"Checking…":"Review reconciliation"}</button>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<div role="status"><p className="muted tiny">Reviewed {result.candles_reviewed} candles · {result.unmatched_session_count} unmatched session dates. {result.notice}</p><p><strong>Automatic ingestion blocked:</strong> {result.blockers.join(" · ").replace(/_/g," ")}</p></div>}
  </section>;
}
