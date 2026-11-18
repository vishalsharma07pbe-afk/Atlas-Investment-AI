import {useState} from "react";
type Research={source:string;source_name:string;rating:string;target_price:string|null;published_on:string;report_title:string;report_url:string;evidence_status:string};
type Result={status:string;fresh_provider_count:number;fresh_records:number;excluded_stale_or_superseded:number;rating_counts:Record<string,number>;targets:{median:string|null;minimum:string|null;maximum:string|null;count:number};research:Research[];notice:string;blockers:string[]};
export default function BrokerResearch(){
  const [instrument,setInstrument]=useState("");
  const [raw,setRaw]=useState("[]");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function compare(){
    setError("");setResult(null);
    let records:unknown;
    try{records=JSON.parse(raw);if(!Array.isArray(records))throw Error("not array");}
    catch{setError("Enter a JSON array of source-attributed research reports.");return;}
    if(!instrument.trim()){setError("Enter an instrument ISIN or stable identifier.");return;}
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/research/brokers/compare",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({instrument_id:instrument.trim(),records,max_age_days:180})
      });
      if(!response.ok)throw Error("Research comparison rejected; verify source codes and report fields.");
      const payload:Result=await response.json();
      if(payload.status!=="RESEARCH_COMPARISON_ONLY")throw Error("Unexpected research response.");
      setResult(payload);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <div><section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">MULTI-BROKER RESEARCH · SOURCE ATTRIBUTION</small><h2>Research consensus comparison</h2></div><span className="tag">NOT A TRADE SIGNAL</span></div>
    <p className="muted tiny">Compare dated, source-attributed research from Groww, Zerodha, Upstox, Angel One, ICICI Direct, Motilal Oswal, Nuvama and other providers. Reports must be supplied by you; ATLAS does not yet retrieve or verify broker research automatically.</p>
    <div className="form-layout">
      <label className="field field-medium" htmlFor="research-instrument"><span>Instrument ISIN / identifier</span><input id="research-instrument" aria-label="Research instrument identifier" value={instrument} onChange={e=>setInstrument(e.target.value)} placeholder="INE848E01016"/></label>
      <label className="field field-full" htmlFor="research-records"><span>Research records JSON</span><textarea className="editor" id="research-records" aria-label="Research records JSON" rows={5} value={raw} onChange={e=>setRaw(e.target.value)} placeholder='[{"source":"ICICI_DIRECT","instrument_id":"...","symbol":"...","published_on":"YYYY-MM-DD","rating":"BUY","target_price":"1200","report_url":"https://...","report_title":"...","report_id":"..."}]'/></label>
      <div className="form-actions"><button className="primary" disabled={loading} onClick={compare}>{loading?"Comparing…":"Compare broker research"}</button></div>
    </div>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<div role="status"><p className="muted tiny">Fresh providers: {result.fresh_provider_count} · Fresh reports: {result.fresh_records} · Excluded stale/superseded: {result.excluded_stale_or_superseded}</p>
      <p>Ratings: {Object.entries(result.rating_counts).map(([k,v])=>k+": "+v).join(" · ")}</p>
      <p>Submitted target range: {result.targets.minimum??"—"}–{result.targets.maximum??"—"} INR · Median: {result.targets.median??"—"} INR ({result.targets.count} targets)</p>
      <div className="tablewrap"><table><thead><tr><th>SOURCE</th><th>DATE</th><th>RATING</th><th>TARGET (INR)</th><th>REPORT</th></tr></thead><tbody>
        {result.research.map((r,i)=><tr key={r.source+":"+i}><td>{r.source_name}</td><td>{r.published_on}</td><td>{r.rating}</td><td>{r.target_price??"—"}</td><td><a href={r.report_url} target="_blank" rel="noopener noreferrer">{r.report_title}</a></td></tr>)}
        {!result.research.length&&<tr><td colSpan={5} className="empty">No fresh reports supplied.</td></tr>}
      </tbody></table></div>
      <p className="muted tiny">{result.notice}</p></div>}
  </section></div>;
}
