import React,{useState} from "react";
type Checkpoint={month:number;projected_value:string;total_contributions:string};
type Projection={status:string;target_amount:string;projected_value:string;contributed_principal:string;hypothetical_growth:string;shortfall:string;required_monthly_contribution:string;checkpoints:Checkpoint[];notice:string};
const inr=(v:string)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(Number(v));
export default function GoalPlanner(){
  const [target,setTarget]=useState("1000000");
  const [initial,setInitial]=useState("0");
  const [monthly,setMonthly]=useState("10000");
  const [months,setMonths]=useState("36");
  const [rate,setRate]=useState("8");
  const [result,setResult]=useState<Projection|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function calculate(e:React.FormEvent){
    e.preventDefault();setResult(null);setError("");
    const fields=[Number(target),Number(initial),Number(monthly),Number(months),Number(rate)];
    if(fields.some(n=>!Number.isFinite(n))||fields[0]<=0||fields[0]>1e9||fields[1]<0||fields[1]>1e9||
       fields[2]<0||fields[2]>1e7||!Number.isInteger(fields[3])||fields[3]<1||fields[3]>600||fields[4]<-30||fields[4]>30){
      setError("Enter valid values: 1–600 months, assumed return -30% to 30%, and nonnegative amounts.");return;
    }
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/planning/goal-projection",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({target_amount:target,initial_amount:initial,monthly_contribution:monthly,months:Number(months),annual_return_percent:rate})});
      if(!response.ok)throw Error("Goal calculation unavailable");
      setResult(await response.json() as Projection);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass" aria-label="Goal-based investment planner">
    <div className="sectionhead"><div><small className="section-kicker">GOAL PLANNING LAB</small><h2>Goal-based investment planner</h2></div><span className="tag">ILLUSTRATIVE ONLY</span></div>
    <p className="muted tiny">Explore a target using a fixed assumed annual return, end-of-month contributions and monthly compounding. No live prices or return predictions.</p>
    <form onSubmit={calculate} className="atlas-compact-form atlas-goal-form"><div className="atlas-goal-grid">
      <label>Target amount (INR)<input aria-label="Goal target amount" type="number" min="1" max="1000000000" value={target} onChange={e=>setTarget(e.target.value)}/></label>
      <label>Starting savings (INR)<input aria-label="Starting savings" type="number" min="0" value={initial} onChange={e=>setInitial(e.target.value)}/></label>
      <label>Monthly contribution (INR)<input aria-label="Monthly contribution" type="number" min="0" value={monthly} onChange={e=>setMonthly(e.target.value)}/></label>
      <label>Time horizon (months)<input aria-label="Time horizon in months" type="number" min="1" max="600" value={months} onChange={e=>setMonths(e.target.value)}/></label>
      <label>Assumed annual return (%)<input aria-label="Assumed annual return" type="number" min="-30" max="30" step="0.1" value={rate} onChange={e=>setRate(e.target.value)}/></label>
      </div><div className="atlas-form-actions"><button className="primary" type="submit" disabled={loading}>{loading?"Calculating…":"Calculate goal"}</button></div>
    </form>
    {error&&<p role="alert">{error}</p>}
    {result&&<div aria-label="Goal projection results">
      <p><strong>{result.status==="TARGET_MET"?"Target met under assumptions":"Target shortfall under assumptions"}</strong></p>
      <p>Projected balance: <strong>{inr(result.projected_value)}</strong> · Target: {inr(result.target_amount)}</p>
      <p>Contributed principal: {inr(result.contributed_principal)} · Hypothetical growth: {inr(result.hypothetical_growth)}</p>
      <p>Shortfall: {inr(result.shortfall)} · Monthly contribution needed from start: <strong>{inr(result.required_monthly_contribution)}</strong></p>
      <div className="tablewrap"><table><thead><tr><th>MONTH</th><th>PROJECTED VALUE</th><th>CONTRIBUTED PRINCIPAL</th></tr></thead><tbody>
        {result.checkpoints.map(p=><tr key={p.month}><td>{p.month}</td><td>{inr(p.projected_value)}</td><td>{inr(p.total_contributions)}</td></tr>)}
      </tbody></table></div>
      <p className="muted tiny">{result.notice}</p>
    </div>}
  </section>;
}
