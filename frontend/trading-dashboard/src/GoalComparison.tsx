import React,{useState} from "react";
type Scenario={name:string;monthly:string;months:string;rate:string};
type Result={name:string;status:string;projected_value:string;shortfall:string;required_monthly_contribution:string;contributed_principal:string};
const inr=(value:string)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(Number(value));
export default function GoalComparison(){
  const [target,setTarget]=useState("1000000");
  const [initial,setInitial]=useState("0");
  const [scenarios,setScenarios]=useState<Scenario[]>([
    {name:"Conservative",monthly:"10000",months:"36",rate:"4"},
    {name:"Base",monthly:"10000",months:"36",rate:"8"},
    {name:"Optimistic",monthly:"10000",months:"36",rate:"12"}]);
  const [results,setResults]=useState<Result[]|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const change=(i:number,key:keyof Scenario,value:string)=>setScenarios(old=>old.map((s,j)=>i===j?{...s,[key]:value}:s));
  async function submit(e:React.FormEvent){
    e.preventDefault();setError("");setResults(null);
    const names=scenarios.map(s=>s.name.trim().toLowerCase());
    if(new Set(names).size!==names.length||names.some(n=>!n)){setError("Scenario names must be unique and nonempty.");return;}
    if(scenarios.some(s=>!Number.isInteger(Number(s.months))||Number(s.months)<1||Number(s.months)>600||
      Number(s.monthly)<0||Number(s.monthly)>1e7||Number(s.rate)<-30||Number(s.rate)>30)){
      setError("Check scenario months, monthly contributions and assumed returns.");return;}
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/planning/goal-comparison",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({scenarios:scenarios.map(s=>({name:s.name,parameters:{
          target_amount:target,initial_amount:initial,monthly_contribution:s.monthly,
          months:Number(s.months),annual_return_percent:s.rate}}))})});
      if(!response.ok)throw Error("Scenario comparison unavailable");
      const data=await response.json() as {scenarios:Result[]};
      setResults(data.scenarios);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass" aria-label="Goal scenario comparison">
    <div className="sectionhead"><div><small className="section-kicker">SCENARIO LAB</small><h2>Compare savings scenarios</h2></div><span className="tag">NOT A FORECAST</span></div>
    <p className="muted tiny">Compare 2–5 hypothetical plans. Assumed returns are not probabilities or expected market performance.</p>
    <form onSubmit={submit} className="atlas-compact-form"><div className="atlas-form-row">
      <label>Target (INR)<input aria-label="Comparison target" type="number" min="1" max="1000000000" value={target} onChange={e=>setTarget(e.target.value)}/></label>
      <label>Starting savings (INR)<input aria-label="Comparison starting savings" type="number" min="0" max="1000000000" value={initial} onChange={e=>setInitial(e.target.value)}/></label>
      </div><div className="atlas-scenario-grid">{scenarios.map((s,i)=><fieldset className="atlas-scenario-card" key={i}><legend>Scenario {i+1}</legend><div className="atlas-scenario-fields">
        <label>Name<input aria-label={`Scenario name ${i+1}`} maxLength={60} value={s.name} onChange={e=>change(i,"name",e.target.value)}/></label>
        <label>Monthly INR<input aria-label={`Scenario monthly ${i+1}`} type="number" min="0" max="10000000" value={s.monthly} onChange={e=>change(i,"monthly",e.target.value)}/></label>
        <label>Months<input aria-label={`Scenario months ${i+1}`} type="number" min="1" max="600" value={s.months} onChange={e=>change(i,"months",e.target.value)}/></label>
        <label>Assumed annual %<input aria-label={`Scenario return ${i+1}`} type="number" min="-30" max="30" step="0.1" value={s.rate} onChange={e=>change(i,"rate",e.target.value)}/></label>
        </div><button className="secondary" type="button" disabled={scenarios.length<=2} onClick={()=>setScenarios(old=>old.filter((_,j)=>j!==i))}>Remove scenario</button>
      </fieldset>)}</div>
      <div className="atlas-form-actions"><button className="secondary" type="button" disabled={scenarios.length>=5} onClick={()=>setScenarios(old=>[...old,{name:`Scenario ${old.length+1}`,monthly:"10000",months:"36",rate:"8"}])}>Add scenario</button>
      <button className="primary" type="submit" disabled={loading}>{loading?"Comparing…":"Compare scenarios"}</button></div>
    </form>
    {error&&<p role="alert">{error}</p>}
    {results&&<div aria-label="Scenario comparison results"><div className="tablewrap"><table><thead><tr><th>SCENARIO</th><th>PROJECTED</th><th>PRINCIPAL</th><th>SHORTFALL</th><th>MONTHLY NEEDED</th></tr></thead><tbody>
      {results.map(r=><tr key={r.name}><td>{r.name}</td><td>{inr(r.projected_value)}</td><td>{inr(r.contributed_principal)}</td><td>{inr(r.shortfall)}</td><td>{inr(r.required_monthly_contribution)}</td></tr>)}
    </tbody></table></div><p className="muted tiny">Illustrative fixed-rate arithmetic only; no fees, taxes, inflation, volatility or personalized advice.</p></div>}
  </section>;
}
