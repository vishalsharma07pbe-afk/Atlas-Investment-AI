import React,{useState} from "react";
import type {FundHolding} from "./MutualFundHoldings";
type Review={status:string;blockers:string[];snapshot:{schemes:{scheme_code:string;scheme_name:string;nav:number;as_of:string}[];missing_scheme_codes:string[]};reconciliation:{portfolio_estimated_value:string|null;rows:{holding_id:number;scheme_code:string;status:string;estimated_value:string|null}[]}|null;notice:string};
export default function MutualFundSnapshotReview({holdings}:{holdings:FundHolding[]}){
 const funds=holdings.filter(h=>h.asset_type==="MUTUAL_FUND");
 const [text,setText]=useState(""),[source,setSource]=useState(""),[mapping,setMapping]=useState("{}");
 const [authorized,setAuthorized]=useState(false),[loading,setLoading]=useState(false);
 const [result,setResult]=useState<Review|null>(null),[error,setError]=useState("");
 async function inspect(){
  setLoading(true);setError("");setResult(null);
  try{
   const codes=JSON.parse(mapping) as Record<string,string>;
   if(!codes||Array.isArray(codes)||typeof codes!=="object")throw Error("Enter a holding ID to scheme code JSON object.");
   const positions=funds.map(h=>{
    const code=codes[String(h.id)];
    if(typeof code!=="string"||!/^[0-9]{1,12}$/.test(code))throw Error("Map every holding ID to an exact numeric scheme code.");
    return {holding_id:h.id,scheme_code:code,units:h.quantity,invested:h.invested,recorded_value:h.market_value};
   });
   if(!positions.length)throw Error("Add a mutual fund holding before reviewing.");
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/snapshot-portfolio-review",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({text,source_name:source,source_authorized:authorized,positions})
   });
   if(!response.ok)throw Error("Snapshot review rejected. Check NAV rows, source and mapping.");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Review unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund snapshot portfolio review">
  <div className="sectionhead"><div><small className="section-kicker">END-TO-END NAV QUALITY · READ ONLY</small><h2>Review NAV snapshot against portfolio</h2></div><span className="tag">NO PORTFOLIO UPDATE</span></div>
  <p className="muted tiny">One review checks the supplied NAV snapshot, freshness, scheme coverage and portfolio estimates. Scheme mapping must be explicit. Source authorization is user-attested, not independently verified.</p>
  <label htmlFor="mf-review-source">Source name</label><input id="mf-review-source" value={source} onChange={e=>setSource(e.target.value)}/>
  <label htmlFor="mf-review-map">Snapshot review holding ID to scheme code JSON</label><textarea id="mf-review-map" rows={3} style={{width:"100%"}} value={mapping} onChange={e=>setMapping(e.target.value)} placeholder='{"1":"12345"}'/>
  <label htmlFor="mf-review-text">AMFI-style NAV snapshot</label><textarea id="mf-review-text" rows={5} style={{width:"100%"}} value={text} onChange={e=>setText(e.target.value)}/>
  <label><input type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/> I confirm I am authorized to use this source</label>
  <button className="secondary" disabled={loading||!text.trim()||!source.trim()||!funds.length} onClick={inspect}>{loading?"Reviewing…":"Review portfolio snapshot"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status"><h3>{result.status.replace(/_/g," ")}</h3>
   {result.blockers.length>0&&<p>Blockers: {result.blockers.join(", ")}</p>}
   <p>Matched schemes: {result.snapshot.schemes.length} · Missing codes: {result.snapshot.missing_scheme_codes.join(", ")||"None"}</p>
   <p>Complete portfolio estimate: {result.reconciliation?.portfolio_estimated_value??"Unavailable"}</p>
   {result.reconciliation&&<div className="tablewrap"><table><thead><tr><th>Holding ID</th><th>Scheme code</th><th>Status</th><th>Estimated value</th></tr></thead><tbody>{result.reconciliation.rows.map(row=><tr key={row.holding_id}><td>{row.holding_id}</td><td>{row.scheme_code}</td><td>{row.status}</td><td>{row.estimated_value??"—"}</td></tr>)}</tbody></table></div>}
   <p className="muted tiny">{result.notice}</p></div>}
 </section>;
}
