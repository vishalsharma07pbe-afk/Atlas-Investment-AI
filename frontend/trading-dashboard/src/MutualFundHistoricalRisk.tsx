import type {SharedNavHistory} from "./MutualFundHistoryImport";
import React,{useState} from "react";
type Risk={observations:number;first_date:string;last_date:string;cumulative_return_pct:number;annualized_return_pct:number;maximum_drawdown_pct:number;annualized_volatility_pct:number|null;volatility_status:string;notice:string};
export default function MutualFundHistoricalRisk({validatedHistory}:{validatedHistory?:SharedNavHistory|null}){
 const [code,setCode]=useState(""),[source,setSource]=useState(""),[csv,setCsv]=useState("as_of,nav\n");
 const [result,setResult]=useState<Risk|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
 async function analyze(shared?:SharedNavHistory){
  setResult(null);setError("");setLoading(true);
  try{
   const selectedCode=shared?.schemeCode??code;
   const selectedSource=shared?.sourceName??source;
   if(!/^[0-9]{1,12}$/.test(selectedCode))throw Error("Enter an exact numeric scheme code.");
   let observations:{as_of:string;nav:string}[];
   if(shared){
    observations=shared.observations;
   }else{
    const lines=csv.trim().split(/\r?\n/);
    if(lines.shift()?.trim()!=="as_of,nav")throw Error("CSV header must be as_of,nav.");
    observations=lines.map(line=>{
     const fields=line.split(",").map(x=>x.trim());
     if(fields.length!==2||!/^\d{4}-\d{2}-\d{2}$/.test(fields[0])||!fields[1])throw Error("Each row needs an ISO date and NAV.");
     return {as_of:fields[0],nav:fields[1]};
    });
   }
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/historical-risk",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({scheme_code:selectedCode,source_name:selectedSource,observations})
   });
   if(!response.ok)throw Error("Invalid NAV history. Check chronological dates and positive finite values.");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Risk analysis unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund historical NAV risk">
  <div className="sectionhead"><div><small className="section-kicker">HISTORICAL NAV · READ ONLY</small><h2>Drawdown &amp; return risk</h2></div><span className="tag">USER-SUPPLIED DATA</span></div>
  <p className="muted tiny">Analyze dated NAV observations. Maximum drawdown is based on observed peaks; volatility is only shown when all dates are consecutive calendar days.</p>
  <label htmlFor="risk-code">Exact scheme code</label><input id="risk-code" value={code} onChange={e=>setCode(e.target.value)} placeholder="12345"/>
  <label htmlFor="risk-source">NAV source</label><input id="risk-source" value={source} onChange={e=>setSource(e.target.value)} placeholder="Authorized local CSV"/>
  <label htmlFor="risk-csv">NAV history CSV (as_of,nav)</label><textarea id="risk-csv" rows={6} style={{width:"100%"}} value={csv} onChange={e=>setCsv(e.target.value)}/>
  {validatedHistory&&<p className="muted tiny">Validated import ready: scheme {validatedHistory.schemeCode} · {validatedHistory.observations.length} NAV records. Run risk analysis without re-entering the CSV.</p>}
  {validatedHistory&&<button className="secondary" disabled={loading} onClick={()=>analyze(validatedHistory)}>Analyze validated import</button>}
  <button className="secondary" disabled={loading} onClick={()=>analyze()}>{loading?"Analyzing…":"Analyze historical risk"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   <p>{result.observations} observations · {result.first_date} to {result.last_date}</p>
   <div className="stats">
    <div className="stat glass"><small>CUMULATIVE RETURN</small><strong>{result.cumulative_return_pct.toFixed(2)}%</strong></div>
    <div className="stat glass"><small>ANNUALIZED RETURN</small><strong>{result.annualized_return_pct.toFixed(2)}%</strong></div>
    <div className="stat glass"><small>MAX OBSERVED DRAWDOWN</small><strong>{result.maximum_drawdown_pct.toFixed(2)}%</strong></div>
    <div className="stat glass"><small>ANNUALIZED VOLATILITY</small><strong>{result.annualized_volatility_pct===null?"Unavailable":result.annualized_volatility_pct.toFixed(2)+"%"}</strong></div>
   </div>
   <p className="muted tiny">Volatility status: {result.volatility_status}</p><p className="muted tiny">{result.notice}</p>
  </div>}
 </section>;
}
