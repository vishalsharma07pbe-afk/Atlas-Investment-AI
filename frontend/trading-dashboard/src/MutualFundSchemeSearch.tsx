import {useState} from "react";
type Scheme={scheme_code:string;scheme_name:string;nav:number;as_of:string;status:string};
type Result={schemes:Scheme[];matches_total:number;truncated:boolean;source:{verification:string};notice:string};
export default function MutualFundSchemeSearch(){
 const [snapshot,setSnapshot]=useState(""),[query,setQuery]=useState("");
 const [result,setResult]=useState<Result|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
 async function search(){
  setLoading(true);setError("");setResult(null);
  try{
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/scheme-search",{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text:snapshot,query,limit:25})
   });
   if(!response.ok)throw Error("Provide an AMFI-style snapshot and at least two search characters.");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Scheme search unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund scheme discovery">
  <div className="sectionhead"><div><small className="section-kicker">SCHEME DISCOVERY · RESEARCH ONLY</small><h2>Find exact mutual fund scheme codes</h2></div><span className="tag">USER-SUPPLIED SNAPSHOT</span></div>
  <p className="muted tiny">Paste an authorized AMFI-style semicolon-separated NAV snapshot, then search by scheme name or code. No automatic download, verification, storage or holding mapping.</p>
  <label htmlFor="mf-search-snapshot">NAV snapshot text</label><textarea id="mf-search-snapshot" rows={4} style={{width:"100%"}} value={snapshot} onChange={e=>{setSnapshot(e.target.value);setResult(null);}}/>
  <label htmlFor="mf-search-query">Scheme name or code</label><input id="mf-search-query" value={query} onChange={e=>{setQuery(e.target.value);setResult(null);}} placeholder="Direct Growth"/>
  <button className="secondary" disabled={loading||query.trim().length<2||!snapshot.trim()} onClick={search}>{loading?"Searching…":"Search snapshot"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status"><p>{result.matches_total} matching scheme(s){result.truncated?" · showing first 25":""}</p>
   <div className="tablewrap"><table><thead><tr><th>Exact code</th><th>Scheme name</th><th>Latest NAV</th><th>As of</th><th>Status</th></tr></thead><tbody>
    {result.schemes.map(s=><tr key={s.scheme_code}><td>{s.scheme_code}</td><td>{s.scheme_name}</td><td>₹{s.nav.toFixed(4)}</td><td>{s.as_of}</td><td>{s.status}</td></tr>)}
   </tbody></table></div><p className="muted tiny">{result.notice}</p></div>}
 </section>;
}
