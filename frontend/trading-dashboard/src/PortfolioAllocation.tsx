import React,{useState} from "react";
type Allocation={asset_type:string;recorded_value:string;current_weight_percent:string;target_weight_percent:string;target_value_after_contribution:string;hypothetical_contribution:string;remaining_target_gap:string};
type Plan={status:string;recorded_value:string;contribution:string;unallocated_contribution:string;unpriced_holdings:{symbol:string}[];allocations:Allocation[];notice:string};
const money=(v:string)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(Number(v));
export default function PortfolioAllocation({revision}:{revision:number}){
  const [contribution,setContribution]=useState("10000");
  const [targets,setTargets]=useState([{asset_type:"EQUITY",weight_percent:"70"},{asset_type:"MUTUAL_FUND",weight_percent:"30"}]);
  const [result,setResult]=useState<Plan|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [lastRevision,setLastRevision]=useState(revision);
  if(lastRevision!==revision){setLastRevision(revision);setResult(null);}
  async function calculate(event:React.FormEvent){
    event.preventDefault();setError("");setResult(null);
    const weights=targets.map(t=>Number(t.weight_percent));
    if(!targets.length||weights.some(n=>!Number.isFinite(n)||n<0||n>100)||Math.abs(weights.reduce((a,b)=>a+b,0)-100)>1e-9){
      setError("Target weights must total exactly 100%.");return;
    }
    if(!Number.isFinite(Number(contribution))||Number(contribution)<0||Number(contribution)>100000000){setError("Enter a valid nonnegative contribution.");return;}
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/portfolio/allocation-plan",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({contribution,targets})});
      if(!response.ok)throw Error("Allocation calculation unavailable. Check target asset types and weights.");
      setResult(await response.json() as Plan);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass" aria-label="Portfolio allocation planner">
    <div className="sectionhead"><div><small className="section-kicker">PORTFOLIO PLANNING</small><h2>Allocation & contribution planner</h2></div><span className="tag">HYPOTHETICAL</span></div>
    <p className="muted tiny">Uses manually recorded prices. Set asset-type targets and explore a cash-only contribution; no orders or sales.</p>
    <form onSubmit={calculate}>
      <label>Additional contribution (INR) <input aria-label="Additional contribution" type="number" min="0" max="100000000" step="0.01" value={contribution} onChange={e=>setContribution(e.target.value)}/></label>
      {targets.map((target,i)=><div key={i}>
        <label>Asset type <input aria-label={`Asset type ${i+1}`} value={target.asset_type} onChange={e=>setTargets(old=>old.map((t,j)=>i===j?{...t,asset_type:e.target.value.toUpperCase()}:t))}/></label>
        <label>Target % <input aria-label={`Target percent ${i+1}`} type="number" min="0" max="100" step="0.01" value={target.weight_percent} onChange={e=>setTargets(old=>old.map((t,j)=>i===j?{...t,weight_percent:e.target.value}:t))}/></label>
        <button type="button" className="secondary" onClick={()=>setTargets(old=>old.filter((_,j)=>j!==i))}>Remove</button>
      </div>)}
      <button type="button" className="secondary" disabled={targets.length>=20} onClick={()=>setTargets(old=>[...old,{asset_type:"",weight_percent:"0"}])}>Add asset type</button>
      <button type="submit" className="primary" disabled={loading}>{loading?"Calculating…":"Calculate hypothetical allocation"}</button>
    </form>
    {error&&<p role="alert">{error}</p>}
    {result&&<div aria-label="Allocation results">
      <p>Recorded value: <strong>{money(result.recorded_value)}</strong> · Contribution: {money(result.contribution)}</p>
      {result.unpriced_holdings.length>0&&<p role="status">Partial coverage: {result.unpriced_holdings.length} unpriced holding(s) excluded.</p>}
      <div className="tablewrap"><table><thead><tr><th>ASSET TYPE</th><th>CURRENT</th><th>TARGET</th><th>HYPOTHETICAL ADDITION</th><th>REMAINING GAP</th></tr></thead><tbody>
        {result.allocations.map(a=><tr key={a.asset_type}><td>{a.asset_type}</td><td>{a.current_weight_percent}%</td><td>{a.target_weight_percent}%</td><td>{money(a.hypothetical_contribution)}</td><td>{money(a.remaining_target_gap)}</td></tr>)}
      </tbody></table></div>
      <p>Unallocated contribution: {money(result.unallocated_contribution)}</p>
      <p className="muted tiny">{result.notice}</p>
    </div>}
  </section>;
}
