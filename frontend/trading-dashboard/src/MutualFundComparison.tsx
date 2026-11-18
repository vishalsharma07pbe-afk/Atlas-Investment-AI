import type {SharedNavHistory} from "./MutualFundHistoryImport";
import {useState} from "react";
type Fund={scheme_code:string;scheme_name:string;source:{name:string;verification:string};latest_nav:{as_of:string;nav:number;status:string};trailing_returns_pct:Record<string,number|null>};
type Result={funds:Fund[];same_latest_nav_date:boolean;comparison_status:string;notice:string};
const example=JSON.stringify({funds:[{scheme_code:"12345",scheme_name:"Fund A",source_name:"Authorized local CSV A",csv_text:"scheme_code,as_of,nav\n12345,2025-01-01,10\n12345,2025-01-31,11"},{scheme_code:"67890",scheme_name:"Fund B",source_name:"Authorized local CSV B",csv_text:"scheme_code,as_of,nav\n67890,2025-01-01,10\n67890,2025-01-31,10.5"}]},null,2);
export default function MutualFundComparison({validatedHistories=[],onRemoveValidated}:{validatedHistories?:SharedNavHistory[];onRemoveValidated?:(code:string)=>void}){
 const [input,setInput]=useState(example);const [result,setResult]=useState<Result|null>(null);
 const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 async function compare(useValidated=false){
  setLoading(true);setError("");setResult(null);
  try{
   const payload=useValidated?{funds:validatedHistories.map(history=>({scheme_code:history.schemeCode,scheme_name:history.schemeName,source_name:history.sourceName,csv_text:history.csvText}))}:JSON.parse(input);
   if(useValidated&&(validatedHistories.length<2||validatedHistories.length>5))throw Error("Import 2–5 distinct validated schemes first.");
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/compare",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
   if(!response.ok)throw Error("Invalid comparison: supply 2–5 distinct schemes with valid NAV CSV histories");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Comparison unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund NAV comparison">
  <div className="sectionhead"><div><small className="section-kicker">MULTI-FUND · RESEARCH ONLY</small><h2>Compare historical fund returns</h2></div><span className="tag">UNVERIFIED SOURCE DATA</span></div>
  <p className="muted tiny">Compare 2–5 distinct funds using authorized NAV CSV history. Example values below are illustrative, not real fund data.</p>
  <h3>Validated NAV histories in this session ({validatedHistories.length}/5)</h3>
  <p className="muted tiny">Import each scheme above. Validated histories are kept in this browser session only; a new import of the same scheme replaces its previous comparison entry.</p>
  <ul>{validatedHistories.map(history=><li key={history.schemeCode}>{history.schemeName} ({history.schemeCode}) · {history.observations.length} NAV records <button className="secondary" onClick={()=>onRemoveValidated?.(history.schemeCode)}>Remove {history.schemeCode}</button></li>)}</ul>
  <button className="secondary" disabled={loading||validatedHistories.length<2} onClick={()=>compare(true)}>Compare validated imports</button>
  <h3>Manual comparison</h3>
  <label htmlFor="mf-comparison-json">Fund histories JSON</label><textarea id="mf-comparison-json" rows={7} style={{width:"100%"}} value={input} onChange={e=>setInput(e.target.value)}/>
  <button className="secondary" disabled={loading} onClick={()=>compare(false)}>{loading?"Comparing…":"Compare fund histories"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   {!result.same_latest_nav_date&&<p className="notice">Latest NAV dates differ. Historical return figures are not directly aligned.</p>}
   <div className="tablewrap"><table><thead><tr><th>Fund</th><th>NAV date</th><th>Latest NAV</th><th>1M</th><th>3M</th><th>6M</th><th>1Y</th><th>3Y</th><th>5Y</th></tr></thead><tbody>
    {result.funds.map(f=><tr key={f.scheme_code}><td>{f.scheme_name} ({f.scheme_code})</td><td>{f.latest_nav.as_of} · {f.latest_nav.status}</td><td>₹{f.latest_nav.nav.toFixed(4)}</td>{["1m","3m","6m","1y","3y","5y"].map(period=><td key={period}>{f.trailing_returns_pct[period]===null?"—":f.trailing_returns_pct[period].toFixed(2)+"%"}</td>)}</tr>)}
   </tbody></table></div><p className="muted tiny">{result.notice}</p></div>}
 </section>;
}
