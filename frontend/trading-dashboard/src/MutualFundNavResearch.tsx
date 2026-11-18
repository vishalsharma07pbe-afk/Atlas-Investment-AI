import {useState} from "react";

type Result={scheme_name:string;source:{name:string;verification:string};latest_nav:{as_of:string;nav:number;status:string;age_days:number};trailing_returns_pct:Record<string,number|null>;caveats:string[];ratings:null};
const sample='{"scheme_code":"12345","scheme_name":"Your fund name","source_name":"Your NAV export","navs":[]}';
export default function MutualFundNavResearch(){
 const [input,setInput]=useState(sample);
 const [result,setResult]=useState<Result|null>(null);
 const [error,setError]=useState("");
 const [loading,setLoading]=useState(false);
 async function analyze(){
  setLoading(true);setError("");setResult(null);
  try{
   const payload=JSON.parse(input);
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/nav-analysis",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
   if(!response.ok)throw Error(response.status===422?"Invalid NAV history. Provide dated positive NAVs in ascending order.":"NAV analysis unavailable");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Invalid NAV data");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund NAV research">
  <div className="sectionhead"><div><small className="section-kicker">SOURCE-ATTRIBUTED · DAILY NAV</small><h2>NAV performance research</h2></div><span className="tag">USER-SUPPLIED</span></div>
  <p className="muted tiny">Paste dated NAV JSON from a source you are authorized to use. ATLAS does not fetch, verify or store the NAVs, and never fabricates ratings.</p>
  <label htmlFor="mf-nav-json">NAV history JSON</label>
  <textarea id="mf-nav-json" rows={5} value={input} onChange={e=>setInput(e.target.value)} style={{width:"100%"}}/>
  <button className="secondary" onClick={analyze} disabled={loading}>{loading?"Analyzing…":"Analyze NAV history"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status"><h3>{result.scheme_name}</h3>
   <p>Latest NAV: ₹{result.latest_nav.nav.toFixed(4)} · {result.latest_nav.as_of} · {result.latest_nav.status} ({result.latest_nav.age_days} days old)</p>
   <p className="muted tiny">Source: {result.source.name} · {result.source.verification.replace(/_/g," ")}</p>
   <div className="stats">{Object.entries(result.trailing_returns_pct).map(([period,value])=><div className="stat glass" key={period}><small>{period.toUpperCase()}</small><strong>{value===null?"Insufficient history":value.toFixed(2)+"%"}</strong></div>)}</div>
   <p className="muted tiny">Ratings unavailable. Returns exclude distributions, taxes and loads; source is not independently verified.</p>
  </div>}
 </section>;
}
