import {useEffect,useState,type FormEvent} from "react";
import {visiblePolling} from "./visiblePolling";

type Input={name:string;targetAmount:string;reservedAmount:string;balanceDate:string;deadline:string;monthlyContribution:string};
type Progress={status:string;remainingMonthEnds:number;recordedProgressPercent:number;recordedGap:number;zeroGrowthProjectedBalance:number|null;zeroGrowthShortfall:number|null;requiredMonthlyContribution:number|null;additionalMonthlyContribution:number|null};
type Goal={id:string;name:string;targetAmount:number;reservedAmount:number;balanceDate:string;deadline:string;monthlyContribution:number;progress:Progress};
type Report={as_of:string;goals:Goal[];notice:string};
const endpoint="/api/v1/portfolio/goals";
const money=(n:number|null)=>n==null?"Unavailable":new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(n);
const blank=(date:string):Input=>({name:"",targetAmount:"",reservedAmount:"0",balanceDate:date,deadline:"",monthlyContribution:"0"});
const labels:Record<string,string>={RECORDED_TARGET_FUNDED:"Recorded target funded",FUNDED_UNDER_ZERO_GROWTH:"Funded under zero-growth assumptions",FUNDING_SHORTFALL:"Funding shortfall",NO_REMAINING_MONTH_ENDS:"No remaining contribution dates",STALE_RECORDED_BALANCE:"Update recorded balance"};
export default function GoalMonitor(){
 const [report,setReport]=useState<Report|null>(null);
 const [form,setForm]=useState<Input|null>(null);
 const [editing,setEditing]=useState<string|null>(null);
 const [removing,setRemoving]=useState<string|null>(null);
 const [error,setError]=useState("");
 const [loadError,setLoadError]=useState(false);
 const [busy,setBusy]=useState(false);
 const [revision,setRevision]=useState(0);
 useEffect(()=>visiblePolling(async signal=>{
   try{
     const response=await fetch(endpoint,{cache:"no-store",signal});
     if(!response.ok)throw Error();
     const data=await response.json() as Report;
     if(!Array.isArray(data.goals))throw Error();
     if(!signal.aborted){setReport(data);setLoadError(false);}
   }catch{if(!signal.aborted){setReport(null);setLoadError(true);}}
 },60000),[revision]);
 function edit(goal:Goal){
   setEditing(goal.id);setError("");setRemoving(null);
   setForm({name:goal.name,targetAmount:String(goal.targetAmount),reservedAmount:String(goal.reservedAmount),
     balanceDate:goal.balanceDate,deadline:goal.deadline,monthlyContribution:String(goal.monthlyContribution)});
 }
 async function save(event:FormEvent){
   event.preventDefault();if(!form||busy)return;
   setError("");setBusy(true);
   try{
     const response=await fetch(editing?endpoint+"/"+editing:endpoint,{method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});
     if(!response.ok)throw Error(response.status===409?"Goal limit reached or concurrent change. Refresh and retry.":"Goal could not be saved. Check amounts and dates.");
     setForm(null);setEditing(null);setReport(null);setRevision(v=>v+1);
   }catch(e){setError(e instanceof Error?e.message:"Goal could not be saved.");}finally{setBusy(false);}
 }
 async function remove(id:string){
   if(busy)return;setBusy(true);setError("");
   try{
     const response=await fetch(endpoint+"/"+id,{method:"DELETE"});
     if(!response.ok)throw Error("Goal could not be removed.");
     setRemoving(null);setForm(null);setEditing(null);setReport(null);setRevision(v=>v+1);
   }catch(e){setError(e instanceof Error?e.message:"Goal could not be removed.");}finally{setBusy(false);}
 }
 return <section className="panel glass" aria-label="Saved goal monitoring">
   <div className="sectionhead"><div><small className="section-kicker">PRIVATE FINANCIAL GOALS</small><h2>Goal progress & funding gaps</h2></div>{report&&!form&&<button className="secondary" type="button" disabled={busy||report.goals.length>=10} onClick={()=>{setEditing(null);setRemoving(null);setError("");setForm(blank(report.as_of));}}>Add goal</button>}</div>
   {loadError?<p role="alert">Saved goals unavailable. <button type="button" className="secondary" onClick={()=>setRevision(v=>v+1)}>Retry</button></p>:!report?<p role="status">Loading saved goals…</p>:<>
     {report.goals.length===0&&<p>No saved goals. Set a target, deadline and explicitly reserved savings once to begin monitoring.</p>}
     {report.goals.map(g=><article className="doctor-item" key={g.id}>
       <header><div><strong>{g.name}</strong><small>Deadline {g.deadline} · Balance recorded {g.balanceDate}</small></div><span className={g.progress.status==="FUNDING_SHORTFALL"||g.progress.status==="STALE_RECORDED_BALANCE"||g.progress.status==="NO_REMAINING_MONTH_ENDS"?"doctor-warning":"doctor-neutral"}>{labels[g.progress.status]??g.progress.status}</span></header>
       <p>Recorded reserved balance: <strong>{money(g.reservedAmount)}</strong> / {money(g.targetAmount)} · {g.progress.recordedProgressPercent.toFixed(2)}%</p>
       <progress aria-label={g.name+" recorded progress"} max={100} value={Math.min(100,g.progress.recordedProgressPercent)}/>
       <p>Remaining recorded gap: {money(g.progress.recordedGap)} · Future month-end contributions: {g.progress.remainingMonthEnds}</p>
       <div className="doctor-stats"><div><span>Planned monthly</span><strong>{money(g.monthlyContribution)}</strong></div><div><span>Required monthly (zero growth)</span><strong>{money(g.progress.requiredMonthlyContribution)}</strong></div><div><span>Projected shortfall (zero growth)</span><strong>{money(g.progress.zeroGrowthShortfall)}</strong></div></div>
       <p>Projected balance: {money(g.progress.zeroGrowthProjectedBalance)} · Additional monthly amount: {money(g.progress.additionalMonthlyContribution)}</p>
       <div className="atlas-form-actions"><button className="secondary" type="button" disabled={busy} onClick={()=>edit(g)}>Update goal / balance</button>
       {removing===g.id?<><button className="secondary" type="button" disabled={busy} onClick={()=>remove(g.id)}>Confirm removal</button><button className="secondary" type="button" disabled={busy} onClick={()=>setRemoving(null)}>Cancel removal</button></>:<button className="secondary" type="button" disabled={busy} onClick={()=>setRemoving(g.id)}>Remove goal</button>}</div>
     </article>)}
     <p className="muted tiny">Calculated {report.as_of} IST. {report.notice}</p>
   </>}
   {form&&<form className="atlas-compact-form atlas-goal-form" onSubmit={save}><div className="atlas-goal-grid">
     <label>Goal name<input required maxLength={80} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label>
     <label>Target amount (INR)<input type="number" min="0.01" max="1000000000" step="0.01" required value={form.targetAmount} onChange={e=>setForm({...form,targetAmount:e.target.value})}/></label>
     <label>Reserved amount (INR)<input type="number" min="0" max="1000000000" step="0.01" required value={form.reservedAmount} onChange={e=>setForm({...form,reservedAmount:e.target.value})}/></label>
     <label>Balance recorded on<input type="date" required max={report?.as_of} value={form.balanceDate} onChange={e=>setForm({...form,balanceDate:e.target.value})}/></label>
     <label>Goal deadline<input type="date" required value={form.deadline} onChange={e=>setForm({...form,deadline:e.target.value})}/></label>
     <label>Planned monthly contribution (INR)<input type="number" min="0" max="10000000" step="0.01" required value={form.monthlyContribution} onChange={e=>setForm({...form,monthlyContribution:e.target.value})}/></label>
     </div><p className="muted tiny">Only enter savings earmarked for this goal. Do not count the same savings in multiple goals.</p>
     <div className="atlas-form-actions"><button type="submit" className="primary" disabled={busy}>{busy?"Saving…":"Save goal"}</button><button type="button" className="secondary" disabled={busy} onClick={()=>{setForm(null);setEditing(null);setError("");}}>Cancel</button></div>
   </form>}
   {error&&<p role="alert">{error}</p>}
 </section>;
}
