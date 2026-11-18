import {useState} from "react";
import type {FundHolding} from "./MutualFundHoldings";
type Snapshot={year:number;contributed:string;projected_value:string};
type Allocation={holding_id:number;label:string;recorded_value:string;weight_pct:string|null};
type Result={projection:{contributed:string;projected_value:string;projected_gain:string;annual_snapshots:Snapshot[]};portfolio:{total_positions:number;priced_positions:number;unpriced_positions:number;recorded_total:string|null;priced_subset_total:string;largest_holding_weight_pct:string|null;allocations:Allocation[];complete:boolean};notice:string};
export default function MutualFundPlanning({holdings}:{holdings:FundHolding[]}){
 const [monthly,setMonthly]=useState("10000"),[annual,setAnnual]=useState("10"),[years,setYears]=useState("10"),[stepUp,setStepUp]=useState("0"),[initial,setInitial]=useState("0");
 const [result,setResult]=useState<Result|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
 const funds=holdings.filter(h=>h.asset_type==="MUTUAL_FUND");
 async function calculate(){
  setError("");setResult(null);setLoading(true);
  try{
   const fields=[monthly,annual,years,stepUp,initial];
   if(fields.some(x=>!x.trim()||!Number.isFinite(Number(x))))throw Error("Enter finite numeric inputs.");
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/plan",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({sip:{monthly_contribution:monthly,annual_return_pct:annual,years:Number(years),annual_step_up_pct:stepUp,initial_amount:initial},
     positions:funds.map(h=>({holding_id:h.id,label:h.symbol,invested:h.invested,recorded_value:h.market_value}))})
   });
   if(!response.ok)throw Error("Invalid SIP inputs or portfolio data. Check values and try again.");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Planning unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund SIP and portfolio planning">
  <div className="sectionhead"><div><small className="section-kicker">FUND PLANNING · RESEARCH ONLY</small><h2>SIP planner &amp; portfolio allocation</h2></div><span className="tag">ILLUSTRATIVE</span></div>
  <p className="muted tiny">Project regular monthly investing using an assumed annual return. Portfolio allocation uses saved, manually recorded values, not live NAVs.</p>
  <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(160px,1fr))",gap:12}}>
   {([["Monthly SIP (₹)",monthly,setMonthly],["Assumed annual return (%)",annual,setAnnual],["Years",years,setYears],["Annual SIP step-up (%)",stepUp,setStepUp],["Initial investment (₹)",initial,setInitial]] as const).map(([label,value,set])=><label key={label}>{label}<input type="number" value={value} onChange={e=>set(e.target.value)} style={{width:"100%"}}/></label>)}
  </div>
  <button className="secondary" disabled={loading} onClick={calculate}>{loading?"Calculating…":"Calculate SIP & allocation"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   <div className="stats">
    <div className="stat glass"><small>CONTRIBUTED</small><strong>₹{result.projection.contributed}</strong></div>
    <div className="stat glass"><small>PROJECTED VALUE</small><strong>₹{result.projection.projected_value}</strong></div>
    <div className="stat glass"><small>PROJECTED GAIN</small><strong>₹{result.projection.projected_gain}</strong></div>
   </div>
   <h3>Year-by-year SIP projection</h3>
   <div className="tablewrap"><table><thead><tr><th>Year</th><th>Contributed (₹)</th><th>Projected value (₹)</th></tr></thead><tbody>
    {result.projection.annual_snapshots.map(s=><tr key={s.year}><td>{s.year}</td><td>{s.contributed}</td><td>{s.projected_value}</td></tr>)}
   </tbody></table></div>
   <h3>Saved fund allocation</h3>
   {result.portfolio.unpriced_positions>0&&<p className="notice">Incomplete portfolio: {result.portfolio.unpriced_positions} unpriced fund(s). Weights are for priced holdings only.</p>}
   <p>Priced subset total: ₹{result.portfolio.priced_subset_total} · Largest holding weight: {result.portfolio.largest_holding_weight_pct??"—"}%</p>
   <div className="tablewrap"><table><thead><tr><th>Fund</th><th>Recorded value (₹)</th><th>Weight (%)</th></tr></thead><tbody>
    {result.portfolio.allocations.map(a=><tr key={a.holding_id}><td>{a.label}</td><td>{a.recorded_value}</td><td>{a.weight_pct??"—"}</td></tr>)}
    {!result.portfolio.allocations.length&&<tr><td colSpan={3}>No priced fund holdings to analyze.</td></tr>}
   </tbody></table></div>
   <p className="muted tiny">{result.notice}</p>
  </div>}
 </section>;
}
