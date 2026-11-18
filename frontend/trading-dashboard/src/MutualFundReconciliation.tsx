import type {SharedNavHistory} from "./MutualFundHistoryImport";
import {useState} from "react";
import type {FundHolding} from "./MutualFundHoldings";
type Row={holding_id:number;scheme_code:string;status:string;estimated_value:string|null;difference_from_recorded:string|null};
type Diagnostic={code:string;severity:string;count:number;message:string};
type Result={diagnostics:Diagnostic[];rows:Row[];missing_nav_positions:number;stale_nav_positions:number;portfolio_estimated_value:string|null;verification:string;notice:string};
export default function MutualFundReconciliation({holdings,validatedHistories=[]}:{holdings:FundHolding[];validatedHistories?:SharedNavHistory[]}){
 const [mapping,setMapping]=useState("{}");const [navText,setNavText]=useState("[]");
 const [result,setResult]=useState<Result|null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 const funds=holdings.filter(h=>h.asset_type==="MUTUAL_FUND");
 async function inspect(useValidated=false){
  setLoading(true);setError("");setResult(null);
  try{
   const codes:Record<string,string>=JSON.parse(mapping);
   const positions=funds.map(h=>{
    const scheme_code=codes[String(h.id)];
    if(!scheme_code||!/^[0-9]{1,12}$/.test(scheme_code))throw Error("Map each holding ID to an exact numeric scheme code");
    return {holding_id:h.id,scheme_code,units:h.quantity,invested:h.invested,recorded_value:h.market_value};
   });
   const navs=useValidated?validatedHistories.map(history=>({scheme_code:history.schemeCode,nav:history.observations[history.observations.length-1].nav,as_of:history.observations[history.observations.length-1].as_of,source_name:history.sourceName})):JSON.parse(navText);
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/reconcile",{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({positions,navs})
   });
   if(!response.ok)throw Error("Invalid scheme mapping or NAV data");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Reconciliation unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund valuation reconciliation">
  <div className="sectionhead"><div><small className="section-kicker">PORTFOLIO NAV · READ ONLY</small><h2>Reconcile fund valuations</h2></div><span className="tag">NO PORTFOLIO CHANGES</span></div>
  <p className="muted tiny">Map each saved mutual fund holding ID to its verified-by-you scheme code. Supply authorized dated NAVs separately. No automatic symbol matching or portfolio updates.</p>
  <p className="muted tiny">Holding IDs: {funds.map(h=>h.id+" ("+h.symbol+")").join(", ")||"None"}</p>
  <label htmlFor="mf-mapping">Holding ID to scheme code JSON</label><textarea id="mf-mapping" rows={3} style={{width:"100%"}} value={mapping} onChange={e=>setMapping(e.target.value)} placeholder={'{"1":"12345","2":"67890"}'}/>
  <p className="muted tiny">Validated NAV histories available: {validatedHistories.length}. Map each holding ID explicitly; imported NAVs are never applied to holdings automatically.</p>
  <button className="secondary" disabled={loading||funds.length===0||validatedHistories.length===0} onClick={()=>inspect(true)}>Reconcile with validated imports</button>
  <label htmlFor="mf-reconcile-nav">NAV records JSON</label><textarea id="mf-reconcile-nav" rows={5} style={{width:"100%"}} value={navText} onChange={e=>setNavText(e.target.value)} placeholder={'[{"scheme_code":"12345","nav":"110","as_of":"2026-11-13","source_name":"Local export"}]'}/>
  <button className="secondary" disabled={loading||funds.length===0} onClick={()=>inspect(false)}>{loading?"Reconciling…":"Compare recorded vs supplied NAV"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   <p>{result.portfolio_estimated_value===null?"Complete portfolio estimate unavailable":"Estimated total: ₹"+result.portfolio_estimated_value}</p>
   <p className="muted tiny">Missing NAV positions: {result.missing_nav_positions} · Stale NAV positions: {result.stale_nav_positions}</p>
   <h3>Data-quality diagnostics</h3>
   <ul>{result.diagnostics.map(d=><li key={d.code}><strong>{d.severity}: {d.code.replace(/_/g," ")}</strong> ({d.count}) — {d.message}</li>)}</ul>
   <div className="tablewrap"><table><thead><tr><th>Holding ID</th><th>Scheme code</th><th>Status</th><th>Estimated value</th><th>Difference from recorded</th></tr></thead><tbody>
    {result.rows.map(row=><tr key={row.holding_id}><td>{row.holding_id}</td><td>{row.scheme_code}</td><td>{row.status}</td><td>{row.estimated_value??"—"}</td><td>{row.difference_from_recorded??"—"}</td></tr>)}
   </tbody></table></div><p className="muted tiny">{result.notice}</p>
  </div>}
 </section>;
}
