import React,{useState} from "react";
type Result={target_amount:string;required_monthly_sip:string;additional_monthly_sip:string;current_monthly_sip:string;current_projected_value:string;current_shortfall:string;required_plan:{annual_snapshots:{year:number;contributed:string;projected_value:string}[]};notice:string};
export default function MutualFundGoals(){
 const [target,setTarget]=useState("1500000"),[years,setYears]=useState("5"),[annual,setAnnual]=useState("10");
 const [stepUp,setStepUp]=useState("0"),[initial,setInitial]=useState("0"),[current,setCurrent]=useState("10000");
 const [result,setResult]=useState<Result|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
 async function calculate(){
  setResult(null);setError("");setLoading(true);
  try{
   if([target,years,annual,stepUp,initial,current].some(x=>!x.trim()||!Number.isFinite(Number(x))))throw Error("Enter finite numeric values.");
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/goal-plan",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({target_amount:target,years:Number(years),annual_return_pct:annual,
     annual_step_up_pct:stepUp,initial_amount:initial,current_monthly_sip:current})
   });
   if(!response.ok)throw Error("Goal parameters are outside supported limits.");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Goal planning unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund goal planner">
  <div className="sectionhead"><div><small className="section-kicker">GOAL PLANNING · RESEARCH ONLY</small><h2>Monthly SIP required for your goal</h2></div><span className="tag">ILLUSTRATIVE</span></div>
  <p className="muted tiny">Estimate the SIP needed for a target and compare it with your planned contribution. Returns are assumptions, not forecasts.</p>
  <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(160px,1fr))",gap:12}}>
   {([["Target amount (₹)",target,setTarget],["Years",years,setYears],["Assumed annual return (%)",annual,setAnnual],["Annual SIP step-up (%)",stepUp,setStepUp],["Initial amount (₹)",initial,setInitial],["Current monthly SIP (₹)",current,setCurrent]] as const).map(([label,value,set])=><label key={label}>{label}<input type="number" value={value} onChange={e=>set(e.target.value)} style={{width:"100%"}}/></label>)}
  </div>
  <button className="secondary" disabled={loading} onClick={calculate}>{loading?"Calculating…":"Calculate goal plan"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   <div className="stats">
    <div className="stat glass"><small>REQUIRED MONTHLY SIP</small><strong>₹{result.required_monthly_sip}</strong></div>
    <div className="stat glass"><small>ADDITIONAL MONTHLY SIP</small><strong>₹{result.additional_monthly_sip}</strong></div>
    <div className="stat glass"><small>PROJECTED SHORTFALL</small><strong>₹{result.current_shortfall}</strong></div>
   </div>
   <p>Target: ₹{result.target_amount} · Current-plan projected value: ₹{result.current_projected_value}</p>
   <h3>Required SIP projection by year</h3>
   <div className="tablewrap"><table><thead><tr><th>Year</th><th>Contributed (₹)</th><th>Projected value (₹)</th></tr></thead><tbody>
    {result.required_plan.annual_snapshots.map(row=><tr key={row.year}><td>{row.year}</td><td>{row.contributed}</td><td>{row.projected_value}</td></tr>)}
   </tbody></table></div>
   <p className="muted tiny">{result.notice}</p>
  </div>}
 </section>;
}
