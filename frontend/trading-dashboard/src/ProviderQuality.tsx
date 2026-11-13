import React,{useState} from "react";
type Row={instrument_key:string;status:string;candle_count:number;latest_trade_date:string|null;age_calendar_days:number|null;quality_flags:string[]};
type Result={status:string;requested:number;succeeded:number;failed:number;results:Row[];notice:string};
export default function ProviderQuality(){
  const [keys,setKeys]=useState("");
  const [from,setFrom]=useState("2026-11-01");
  const [to,setTo]=useState("2026-11-13");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function review(){
    const instrument_keys=keys.split(/[\n,]+/).map(x=>x.trim()).filter(Boolean);
    if(instrument_keys.length<1||instrument_keys.length>5||new Set(instrument_keys).size!==instrument_keys.length){
      setError("Enter one to five distinct NSE_EQ or BSE_EQ instrument keys.");return;
    }
    setLoading(true);setError("");setResult(null);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/providers/upstox/batch-review",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({instrument_keys,from_date:from,to_date:to,max_age_days:7})
      });
      if(!response.ok)throw Error("Provider review unavailable or not authorized.");
      const payload:Result=await response.json();
      if(payload.status!=="REVIEW_ONLY")throw Error("Unexpected provider response.");
      setResult(payload);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">OPT-IN · UPSTOX · DATA QUALITY</small><h2>Provider batch review</h2></div><span className="tag">NO INGESTION</span></div>
    <p className="muted tiny">Review up to five permitted NSE/BSE equity instrument keys. Requests are sequential and rate-paced. Results do not enter your portfolio, research signals or database. Requires configured provider credentials and data-use entitlements.</p>
    <div className="form-layout">
      <label className="field field-full" htmlFor="provider-keys"><span>Instrument keys <small>One permitted key per line · maximum five</small></span><textarea className="editor editor-compact" id="provider-keys" aria-label="Provider instrument keys" rows={3} value={keys} onChange={e=>setKeys(e.target.value)} placeholder="NSE_EQ|INE848E01016"/></label>
      <div className="control-grid control-grid-2">
        <label className="field"><span>From</span><input aria-label="Provider from date" type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label>
        <label className="field"><span>To</span><input aria-label="Provider to date" type="date" value={to} onChange={e=>setTo(e.target.value)}/></label>
      </div>
      <div className="form-actions"><button className="primary" disabled={loading} onClick={review}>{loading?"Reviewing…":"Review provider data"}</button></div>
    </div>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<div role="status"><p className="muted tiny">Reviewed {result.requested} · Preview received {result.succeeded} · Failed {result.failed}. {result.notice}</p>
      <div className="tablewrap"><table><thead><tr><th>INSTRUMENT</th><th>STATUS</th><th>CANDLES</th><th>LATEST</th><th>AGE (DAYS)</th><th>QUALITY FLAGS</th></tr></thead><tbody>
      {result.results.map(r=><tr key={r.instrument_key}><td>{r.instrument_key}</td><td>{r.status}</td><td>{r.candle_count}</td><td>{r.latest_trade_date??"—"}</td><td>{r.age_calendar_days??"—"}</td><td>{r.quality_flags.join(" · ").replace(/_/g," ")}</td></tr>)}
      </tbody></table></div></div>}
  </section>;
}
