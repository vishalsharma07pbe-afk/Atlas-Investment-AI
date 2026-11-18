import {useState} from "react";
type Scheme={scheme_code:string;scheme_name:string;nav:number;as_of:string;status:string};
type ImportResult={schemes:Scheme[];missing_scheme_codes:string[];rejected_rows:number;source:{name:string;verification:string};notice:string};
export default function AmfiNavImport(){
 const [codes,setCodes]=useState("");
 const [raw,setRaw]=useState("");
 const [result,setResult]=useState<ImportResult|null>(null);
 const [error,setError]=useState("");
 const [loading,setLoading]=useState(false);
 async function inspect(){
  setError("");setResult(null);setLoading(true);
  try{
   const scheme_codes=codes.split(",").map(x=>x.trim()).filter(Boolean);
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/amfi-nav-import",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scheme_codes,text:raw})});
   if(!response.ok)throw Error("Invalid NAV snapshot or scheme codes");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"NAV import unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="AMFI NAV snapshot inspection">
  <div className="sectionhead"><div><small className="section-kicker">SOURCE-ATTRIBUTED · NAV SNAPSHOT</small><h2>Import NAV snapshot</h2></div><span className="tag">NO AUTOMATIC FETCH</span></div>
  <p className="muted tiny">Paste an authorized AMFI-style semicolon-separated NAV export. Select exact numeric scheme codes. Imported data is inspected only, not saved or independently verified.</p>
  <label htmlFor="amfi-codes">Scheme codes (comma-separated)</label><input id="amfi-codes" value={codes} onChange={e=>setCodes(e.target.value)} placeholder="12345,67890"/>
  <label htmlFor="amfi-text">NAV text</label><textarea id="amfi-text" rows={4} style={{width:"100%"}} value={raw} onChange={e=>setRaw(e.target.value)} placeholder="Scheme Code;...;Scheme Name;Net Asset Value;Date"/>
  <button className="secondary" disabled={loading} onClick={inspect}>{loading?"Inspecting…":"Inspect NAV snapshot"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status"><p className="muted tiny">{result.source.verification.replace(/_/g," ")} · Rejected rows: {result.rejected_rows}</p>
    <div className="tablewrap"><table><thead><tr><th>Scheme code</th><th>Scheme</th><th>NAV</th><th>Date</th><th>Status</th></tr></thead><tbody>
    {result.schemes.map(x=><tr key={x.scheme_code}><td>{x.scheme_code}</td><td>{x.scheme_name}</td><td>₹{x.nav.toFixed(4)}</td><td>{x.as_of}</td><td>{x.status}</td></tr>)}
    </tbody></table></div>
    {result.missing_scheme_codes.length>0&&<p>Missing or rejected codes: {result.missing_scheme_codes.join(", ")}</p>}
    <p className="muted tiny">{result.notice}</p></div>}
 </section>;
}
