import {useState} from "react";

type Dataset="EQUITY_QUOTES"|"EQUITY_DAILY"|"MF_NAV";
type Mode="MANUAL_IMPORT"|"AUTOMATED_FETCH"|"STREAM";
type Problem={index:number;instrument:string;reasons:string[]};
type Result={status:string;candidate_count:number;quality_passed:boolean;freshness_sla_seconds:number;problems:Problem[];entitlement_status:string;authorization_blockers:string[];authorized_to_ingest:boolean;stored_records:number;notice:string};

export default function IngestionQualityGate(){
  const [dataset,setDataset]=useState<Dataset>("EQUITY_DAILY");
  const [mode,setMode]=useState<Mode>("MANUAL_IMPORT");
  const [payload,setPayload]=useState("[]");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  async function inspect(){
    setResult(null);setError("");
    let candidates:unknown;
    try{
      candidates=JSON.parse(payload);
      if(!Array.isArray(candidates)||candidates.length<1||candidates.length>250)throw Error("Provide an array of 1–250 observations");
      if(payload.length>100_000)throw Error("Candidate batch exceeds local UI size limit");
    }catch(e){setError(e instanceof Error?e.message:"Invalid JSON");return}
    setBusy(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/ingestion/quality-preflight",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({dataset,mode,candidates})
      });
      const data=await response.json();
      if(!response.ok)throw Error("Validation rejected input (HTTP "+response.status+"): "+JSON.stringify(data.detail).slice(0,500));
      setResult(data);
    }catch(e){setError(e instanceof Error?e.message:"Preflight unavailable")}
    finally{setBusy(false)}
  }
  return <section className="panel glass quality-gate-card" aria-label="Ingestion quality preflight">
    <div className="sectionhead"><div className="section-copy"><small className="section-kicker">PRE-INGESTION VALIDATION</small><h2>Ingestion batch quality gate</h2>
      <p>Inspect candidate observations for freshness and duplicates before any provider integration. This does not authorize, store or publish market data.</p></div></div>
    <div className="control-grid control-grid-2 quality-controls"><label><span>Dataset</span><select value={dataset} onChange={e=>setDataset(e.target.value as Dataset)}>
      <option value="EQUITY_QUOTES">Equity quotes (120s SLA)</option>
      <option value="EQUITY_DAILY">Equity daily (48h SLA)</option>
      <option value="MF_NAV">Mutual fund NAV (7d SLA)</option>
    </select></label>
    <label><span>Collection mode</span><select value={mode} onChange={e=>setMode(e.target.value as Mode)}>
      <option value="MANUAL_IMPORT">Manual import</option><option value="AUTOMATED_FETCH">Automated fetch</option><option value="STREAM">Stream</option>
    </select></label></div>
    <p>Paste a JSON array of observations. Each requires <code>instrument</code>, timezone-aware <code>observed_at</code>, positive <code>value</code> and <code>source_id</code>. Do not paste credentials.</p>
    <label className="field field-full"><span>Candidate observations</span><textarea className="editor quality-editor" aria-label="Candidate observation JSON" rows={5} value={payload} onChange={e=>setPayload(e.target.value)} maxLength={100000} spellCheck={false}/></label>
    <div className="compact-form-actions"><button className="primary" type="button" onClick={()=>void inspect()} disabled={busy}>{busy?"Checking…":"Validate batch"}</button></div>
    {error&&<p role="alert">{error}</p>}
    {result&&<div role="status"><p><strong>{result.status.replace(/_/g," ")}</strong> · {result.candidate_count} observations · Quality: {result.quality_passed?"passed":"failed"} · Authorized ingestion: NO · Stored: {result.stored_records}</p>
      <p>Entitlement: {result.entitlement_status.replace(/_/g," ")}. Blockers: {result.authorization_blockers.join(", ")||"Independent authorization still required"}.</p>
      {result.problems.length>0&&<div className="tablewrap"><table><thead><tr><th>Row</th><th>Instrument</th><th>Issue</th></tr></thead><tbody>
        {result.problems.map(p=><tr key={p.index}><td>{p.index+1}</td><td>{p.instrument}</td><td>{p.reasons.join(", ")}</td></tr>)}
      </tbody></table></div>}
      <p>{result.notice}</p>
    </div>}
  </section>;
}
