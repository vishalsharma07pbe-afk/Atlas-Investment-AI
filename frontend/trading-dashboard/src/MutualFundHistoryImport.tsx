import React,{useState} from "react";
type Result={scheme_name:string;latest_nav:{as_of:string;nav:number;status:string};trailing_returns_pct:Record<string,number|null>;import:{rows_accepted:number;stored:boolean};source:{verification:string}};
export type SharedNavHistory={schemeCode:string;sourceName:string;observations:{as_of:string;nav:string}[]};
export default function MutualFundHistoryImport({onValidated}:{onValidated?:(history:SharedNavHistory)=>void}){
 const [code,setCode]=useState("");const [name,setName]=useState("");const [source,setSource]=useState("");
 const [csv,setCsv]=useState("");const [result,setResult]=useState<Result|null>(null);
 const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 async function submit(){
  setLoading(true);setError("");setResult(null);
  try{
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/nav-history-import",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({scheme_code:code,scheme_name:name,source_name:source,csv_text:csv})
   });
   if(!response.ok)throw Error("Invalid historical NAV CSV, source or scheme code");
   const data:Result=await response.json();
   setResult(data);
   if(onValidated){
    const lines=csv.trim().split(/\r?\n/);
    const header=lines.shift()?.split(",").map(v=>v.trim());
    if(header?.join(",")==="scheme_code,as_of,nav"){
     const observations=lines.map(line=>line.split(",").map(v=>v.trim())).map(fields=>({as_of:fields[1],nav:fields[2]}));
     if(observations.length===data.import.rows_accepted)onValidated({schemeCode:code,sourceName:source,observations});
    }
   }
  }catch(e){setError(e instanceof Error?e.message:"Import unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund historical NAV import">
  <div className="sectionhead"><div><small className="section-kicker">HISTORICAL NAV · RESEARCH ONLY</small><h2>Import fund history and calculate returns</h2></div><span className="tag">LOCAL CSV</span></div>
  <p className="muted tiny">Provide authorized historical NAV records for one exact scheme code. No data is saved or independently verified.</p>
  <label htmlFor="history-code">Scheme code</label><input id="history-code" value={code} onChange={e=>setCode(e.target.value)} placeholder="12345"/>
  <label htmlFor="history-name">Scheme name</label><input id="history-name" value={name} onChange={e=>setName(e.target.value)} placeholder="Fund Direct Growth"/>
  <label htmlFor="history-source">Source attribution</label><input id="history-source" value={source} onChange={e=>setSource(e.target.value)} placeholder="Authorized local export"/>
  <label htmlFor="history-csv">Historical NAV CSV</label><textarea id="history-csv" rows={5} style={{width:"100%"}} value={csv} onChange={e=>setCsv(e.target.value)} placeholder={"scheme_code,as_of,nav\n12345,2025-01-01,10.0"}/>
  <button className="secondary" disabled={loading} onClick={submit}>{loading?"Analyzing…":"Import and analyze history"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status"><h3>{result.scheme_name}</h3>
   <p>Accepted {result.import.rows_accepted} NAV records · Latest ₹{result.latest_nav.nav.toFixed(4)} ({result.latest_nav.as_of}) · {result.latest_nav.status}</p>
   <div className="stats">{Object.entries(result.trailing_returns_pct).map(([period,value])=><div className="stat glass" key={period}><small>{period.toUpperCase()}</small><strong>{value===null?"Insufficient history":value.toFixed(2)+"%"}</strong></div>)}</div>
   <p className="muted tiny">User-supplied, unverified NAVs. Results are not persisted. Historical returns exclude distributions, loads and taxes.</p>
  </div>}
 </section>;
}
