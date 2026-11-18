import {useState} from "react";
type Entry={source:string;document_id:string;status:string;blockers:string[]};
type Result={status:string;documents_reviewed:number;entries:Entry[];notice:string};
export default function ResearchSourceAudit(){
  const [raw,setRaw]=useState("[]");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function audit(){
    setError("");setResult(null);
    let manifests:unknown;
    try{manifests=JSON.parse(raw);if(!Array.isArray(manifests)||!manifests.length)throw Error("invalid");}
    catch{setError("Enter a non-empty JSON array of research source manifests.");return;}
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/research/brokers/ingestion-review",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({manifests})});
      if(!response.ok)throw Error("Source manifest review rejected.");
      const value:Result=await response.json();
      if(value.status!=="MANIFEST_REVIEW_ONLY")throw Error("Unexpected response.");
      setResult(value);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">RESEARCH PROVENANCE · PERMISSIONS</small><h2>Broker research source audit</h2></div><span className="tag">NO SCRAPING</span></div>
    <p className="muted tiny">Review source permissions, document IDs, publication dates and declared hashes before any future ingestion. This never fetches documents or verifies broker research independently.</p>
    <details className="atlas-advanced"><summary>Advanced · Audit source manifest JSON</summary><div className="form-layout"><label className="field field-full" htmlFor="research-manifests"><span>Source manifests JSON</span><textarea className="editor" id="research-manifests" aria-label="Research source manifests" rows={5} value={raw} onChange={e=>setRaw(e.target.value)}/></label>
    <div className="form-actions"><button className="primary" disabled={loading} onClick={audit}>{loading?"Auditing…":"Audit research sources"}</button></div></div></details>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<div role="status"><p className="muted tiny">Documents reviewed: {result.documents_reviewed}. {result.notice}</p>
      <div className="tablewrap"><table><thead><tr><th>PROVIDER</th><th>DOCUMENT</th><th>STATUS</th><th>BLOCKERS</th></tr></thead><tbody>
        {result.entries.map((r,i)=><tr key={r.source+":"+r.document_id+":"+i}><td>{r.source}</td><td>{r.document_id}</td><td>{r.status}</td><td>{r.blockers.join(" · ").replace(/_/g," ")}</td></tr>)}
      </tbody></table></div></div>}
  </section>;
}
