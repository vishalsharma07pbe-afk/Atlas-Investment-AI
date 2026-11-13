import React,{useState} from "react";
type Fund={scheme_code:string;scheme_name:string;source:{name:string;verification:string};latest_nav:{as_of:string;nav:number;status:string};trailing_returns_pct:Record<string,number|null>};
type Result={funds:Fund[];same_latest_nav_date:boolean;comparison_status:string;notice:string};
const example=JSON.stringify({funds:[{scheme_code:"12345",scheme_name:"Fund A",source_name:"Authorized local CSV A",csv_text:"scheme_code,as_of,nav\n12345,2025-01-01,10\n12345,2025-01-31,11"},{scheme_code:"67890",scheme_name:"Fund B",source_name:"Authorized local CSV B",csv_text:"scheme_code,as_of,nav\n67890,2025-01-01,10\n67890,2025-01-31,10.5"}]},null,2);
export default function MutualFundComparison(){
 const [input,setInput]=useState(example);const [result,setResult]=useState<Result|null>(null);
 const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 async function compare(){
  setLoading(true);setError("");setResult(null);
  try{
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/compare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(JSON.parse(input))});
   if(!response.ok)throw Error("Invalid comparison: supply 2–5 distinct schemes with valid NAV CSV histories");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Comparison unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund NAV comparison">
  <div className="sectionhead"><div><small className="section-kicker">MULTI-FUND · RESEARCH ONLY</small><h2>Compare historical fund returns</h2></div><span className="tag">UNVERIFIED SOURCE DATA</span></div>
  <p className="muted tiny">Compare 2–5 distinct funds using authorized NAV CSV history. Example values below are illustrative, not real fund data.</p>
  <label htmlFor="mf-comparison-json">Fund histories JSON</label><textarea id="mf-comparison-json" rows={7} style={{width:"100%"}} value={input} onChange={e=>setInput(e.target.value)}/>
  <button className="secondary" disabled={loading} onClick={compare}>{loading?"Comparing…":"Compare fund histories"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   {!result.same_latest_nav_date&&<p className="notice">Latest NAV dates differ. Historical return figures are not directly aligned.</p>}
   <div className="tablewrap"><table><thead><tr><th>Fund</th><th>NAV date</th><th>Latest NAV</th><th>1M</th><th>3M</th><th>6M</th><th>1Y</th><th>3Y</th><th>5Y</th></tr></thead><tbody>
    {result.funds.map(f=><tr key={f.scheme_code}><td>{f.scheme_name} ({f.scheme_code})</td><td>{f.latest_nav.as_of} · {f.latest_nav.status}</td><td>₹{f.latest_nav.nav.toFixed(4)}</td>{["1m","3m","6m","1y","3y","5y"].map(period=><td key={period}>{f.trailing_returns_pct[period]===null?"—":f.trailing_returns_pct[period].toFixed(2)+"%"}</td>)}</tr>)}
   </tbody></table></div><p className="muted tiny">{result.notice}</p></div>}
 </section>;
}
