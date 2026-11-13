import React,{useState} from "react";
type Field="initial_amount"|"monthly_contribution"|"months"|"annual_return_percent"|"annual_expense_ratio_percent"|"contribution_fee_percent"|"monthly_flat_fee";
type Point={month:number;without_fees:string;after_fees:string;fee_drag:string};
type Result={without_fees:string;after_fees:string;fee_drag:string;expense_ratio_charges:string;contribution_charges:string;flat_charges:string;total_charges:string;checkpoints:Point[];notice:string};
const inr=(n:string)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(Number(n));
const fields:{key:Field;label:string;min:number;max:number;step:string}[]=[
  {key:"initial_amount",label:"Starting amount (INR)",min:0,max:1e9,step:"0.01"},
  {key:"monthly_contribution",label:"Monthly contribution (INR)",min:0,max:1e7,step:"0.01"},
  {key:"months",label:"Duration (months)",min:1,max:600,step:"1"},
  {key:"annual_return_percent",label:"Assumed annual return (%)",min:-30,max:30,step:"0.01"},
  {key:"annual_expense_ratio_percent",label:"Annual expense ratio (%)",min:0,max:5,step:"0.01"},
  {key:"contribution_fee_percent",label:"Contribution charge (%)",min:0,max:5,step:"0.01"},
  {key:"monthly_flat_fee",label:"Monthly flat charge (INR)",min:0,max:10000,step:"0.01"}];
const defaults:Record<Field,string>={initial_amount:"100000",monthly_contribution:"10000",months:"36",annual_return_percent:"8",annual_expense_ratio_percent:"1",contribution_fee_percent:"0",monthly_flat_fee:"0"};
export default function FeeImpact(){
  const [form,setForm]=useState(defaults);
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function calculate(e:React.FormEvent){
    e.preventDefault();setResult(null);setError("");
    if(fields.some(f=>!form[f.key].trim()||!Number.isFinite(Number(form[f.key]))||Number(form[f.key])<f.min||Number(form[f.key])>f.max)||
       !Number.isInteger(Number(form.months))){
      setError("Enter valid amounts, rates and a whole-number duration.");return;
    }
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/planning/fee-impact",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});
      if(!response.ok)throw Error("Fee impact calculation unavailable");
      setResult(await response.json() as Result);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass" aria-label="Investment fee impact calculator">
    <div className="sectionhead"><div><small className="section-kicker">COST ANALYSIS LAB</small><h2>Investment fees & compounding</h2></div><span className="tag">HYPOTHETICAL</span></div>
    <p className="muted tiny">Compare a no-fee scenario with user-supplied expense ratios and charges. No actual product pricing is implied.</p>
    <form onSubmit={calculate}>
      {fields.map(f=><label key={f.key}>{f.label}<input aria-label={f.label} type="number" required min={f.min} max={f.max} step={f.step} value={form[f.key]} onChange={e=>setForm(old=>({...old,[f.key]:e.target.value}))}/></label>)}
      <button type="submit" className="primary" disabled={loading}>{loading?"Calculating…":"Calculate fee impact"}</button>
    </form>
    {error&&<p role="alert">{error}</p>}
    {result&&<div aria-label="Fee impact results">
      <p>No-fee balance: <strong>{inr(result.without_fees)}</strong> · After-fee balance: <strong>{inr(result.after_fees)}</strong></p>
      <p>Compounded fee drag: <strong>{inr(result.fee_drag)}</strong> · Direct charges: {inr(result.total_charges)}</p>
      <p>Expense ratio charges: {inr(result.expense_ratio_charges)} · Contribution charges: {inr(result.contribution_charges)} · Flat charges: {inr(result.flat_charges)}</p>
      <div className="tablewrap"><table><thead><tr><th>MONTH</th><th>NO FEES</th><th>AFTER FEES</th><th>FEE DRAG</th></tr></thead><tbody>
        {result.checkpoints.map(p=><tr key={p.month}><td>{p.month}</td><td>{inr(p.without_fees)}</td><td>{inr(p.after_fees)}</td><td>{inr(p.fee_drag)}</td></tr>)}
      </tbody></table></div>
      <p className="muted tiny">{result.notice}</p>
    </div>}
  </section>;
}
