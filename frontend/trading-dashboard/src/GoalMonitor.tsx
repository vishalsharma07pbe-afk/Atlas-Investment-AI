import {useEffect,useState,type FormEvent} from "react";
import {visiblePolling} from "./visiblePolling";

type Input={name:string;targetAmount:string;reservedAmount:string;balanceDate:string;deadline:string;monthlyContribution:string};
type Progress={status:string;remainingMonthEnds:number;recordedProgressPercent:number|null;recordedGap:number|null;zeroGrowthProjectedBalance:number|null;zeroGrowthShortfall:number|null;requiredMonthlyContribution:number|null;additionalMonthlyContribution:number|null};
type LinkedHolding={holdingId:number;symbol:string;assetType:string;status:string;recordedValue:number|null};
type Goal={id:string;name:string;targetAmount:number;reservedAmount:number;balanceDate:string;deadline:string;monthlyContribution:number;progress:Progress;funding?:{linkedValue:number|null;totalRecordedFunding:number|null;holdings:LinkedHolding[]}};
type GoalRisk={status:string;daysToDeadline:number;reservedSavings:number;equityValue:number|null;fundValue:number|null;grossWithdrawalGap:number|null;projectedWithdrawalGap:number|null;grossFundingNotCoveredByAssignedHoldings:number|null;recordedFundingSurplus:number|null;reviewPriority:string;notice:string;scenarios:{kind:string;equityDeclinePercent:number;fundDeclinePercent:number;hypotheticalLoss:number;stressedRecordedFunding:number;projectedFunding:number;projectedShortfall:number;requiredMonthlyContribution:number|null;additionalMonthlyContribution:number|null}[]};
type Report={goalRisk?:Record<string,GoalRisk>;as_of:string;goals:Goal[];availableHoldings?:{holdingId:number;symbol:string;assetType:string}[];notice:string};
const endpoint="/api/v1/portfolio/goals";
const money=(n:number|null)=>n==null?"Unavailable":new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",minimumFractionDigits:0,maximumFractionDigits:2}).format(n);
const blank=(date:string):Input=>({name:"",targetAmount:"",reservedAmount:"0",balanceDate:date,deadline:"",monthlyContribution:"0"});
const labels:Record<string,string>={RECORDED_TARGET_FUNDED:"Recorded target funded",FUNDED_UNDER_ZERO_GROWTH:"Funded under zero-growth assumptions",FUNDING_SHORTFALL:"Funding shortfall",NO_REMAINING_MONTH_ENDS:"No remaining contribution dates",STALE_RECORDED_BALANCE:"Update recorded balance",INCOMPLETE_LINKED_VALUATION:"Linked valuation unavailable"};
function GoalRiskDigest({risk}:{risk:GoalRisk}){
 const labels:Record<string,string>={NEAR_DEADLINE_FUNDING_REVIEW:"Review funding before deadline",DOWNSIDE_FUNDING_REVIEW:"Review downside funding risk",BASELINE_FUNDING_REVIEW:"Review baseline funding",MONITOR:"Monitor",REVIEW_EVIDENCE:"Review missing evidence"};
 return <details className="thesis-digest"><summary>Goal stress & withdrawal readiness · {labels[risk.reviewPriority]??risk.reviewPriority}</summary>
  <p>{risk.daysToDeadline<0?"Deadline passed":risk.daysToDeadline===0?"Deadline today":risk.daysToDeadline+" days to deadline"}</p>
  {risk.status==="INSUFFICIENT_FUNDING_EVIDENCE"?<p>Stress and withdrawal research withheld until assigned valuations and reserved balance are current.</p>:<>
   <p>Recorded direct equity: {money(risk.equityValue)} · Recorded funds: {money(risk.fundValue)}</p>
   <p>Target less recorded reserved savings: {money(risk.grossWithdrawalGap)} · After planned future contributions: {money(risk.projectedWithdrawalGap)}</p>
   <p>Recorded gap beyond assigned holdings: {money(risk.grossFundingNotCoveredByAssignedHoldings)} · Recorded funding surplus: {money(risk.recordedFundingSurplus)}</p>
   {risk.scenarios.length===0?<p>No positive assigned investment exposure to stress.</p>:<div className="tablewrap"><table><thead><tr><th>Independent shock</th><th>Hypothetical loss</th><th>Stressed recorded funding</th><th>Projected deadline funding</th><th>Projected gap</th><th>Monthly needed</th><th>Additional monthly</th></tr></thead><tbody>
    {risk.scenarios.map(s=><tr key={s.kind}><td>{s.equityDeclinePercent>0?"Equity −"+s.equityDeclinePercent+"%":""}{s.equityDeclinePercent>0&&s.fundDeclinePercent>0?" / ":""}{s.fundDeclinePercent>0?"Fund NAV −"+s.fundDeclinePercent+"%":""}</td><td>{money(s.hypotheticalLoss)}</td><td>{money(s.stressedRecordedFunding)}</td><td>{money(s.projectedFunding)}</td><td>{money(s.projectedShortfall)}</td><td>{money(s.requiredMonthlyContribution)}</td><td>{money(s.additionalMonthlyContribution)}</td></tr>)}
   </tbody></table></div>}
  </>}
  <p className="muted tiny">{risk.notice}</p>
 </details>;
}
export default function GoalMonitor(){
 const [report,setReport]=useState<Report|null>(null);
 const [form,setForm]=useState<Input|null>(null);
 const [editing,setEditing]=useState<string|null>(null);
 const [removing,setRemoving]=useState<string|null>(null);
 const [error,setError]=useState("");
 const [loadError,setLoadError]=useState(false);
 const [busy,setBusy]=useState(false);
 const [revision,setRevision]=useState(0);
 const [assignment,setAssignment]=useState<{goal:string;holding:string;confirmed:boolean}|null>(null);
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
 async function link(goal:string,holding:string,remove:boolean){
   if(busy||!holding||(!remove&&!assignment?.confirmed))return;
   setBusy(true);setError("");
   try{
     const response=await fetch(endpoint+"/"+goal+"/holdings/"+holding,remove?{method:"DELETE"}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmSeparateBalance:true})});
     if(!response.ok)throw Error("Assignment unavailable. Check ownership, existing assignments and limits.");
     setAssignment(null);setReport(null);setRevision(v=>v+1);
   }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 return <section className="panel glass" aria-label="Saved goal monitoring">
   <div className="sectionhead"><div><small className="section-kicker">PRIVATE FINANCIAL GOALS</small><h2>Goal progress & funding gaps</h2></div>{report&&!form&&<button className="secondary" type="button" disabled={busy||report.goals.length>=10} onClick={()=>{setEditing(null);setRemoving(null);setError("");setForm(blank(report.as_of));}}>Add goal</button>}</div>
   {loadError?<p role="alert">Saved goals unavailable. <button type="button" className="secondary" onClick={()=>setRevision(v=>v+1)}>Retry</button></p>:!report?<p role="status">Loading saved goals…</p>:<>
     {report.goals.length===0&&<p>No saved goals. Set a target, deadline and explicitly reserved savings once to begin monitoring.</p>}
     {report.goals.map(g=><article className="doctor-item" key={g.id}>
       <header><div><strong>{g.name}</strong><small>Deadline {g.deadline} · Balance recorded {g.balanceDate}</small></div><span className={g.progress.status==="FUNDING_SHORTFALL"||g.progress.status==="STALE_RECORDED_BALANCE"||g.progress.status==="NO_REMAINING_MONTH_ENDS"||g.progress.status==="INCOMPLETE_LINKED_VALUATION"?"doctor-warning":"doctor-neutral"}>{labels[g.progress.status]??g.progress.status}</span></header>
       <p>Recorded reserved balance: <strong>{money(g.reservedAmount)}</strong> / {money(g.targetAmount)}</p>
       {g.progress.recordedProgressPercent!=null?<><p>{g.progress.recordedProgressPercent.toFixed(2)}% recorded funding</p><progress aria-label={g.name+" recorded progress"} max={100} value={Math.min(100,g.progress.recordedProgressPercent)}/></>:<p>Combined progress unavailable until linked valuations are complete.</p>}
       <p>Remaining recorded gap: {money(g.progress.recordedGap)} · Future month-end contributions: {g.progress.remainingMonthEnds}</p>
       <div className="doctor-stats"><div><span>Planned monthly</span><strong>{money(g.monthlyContribution)}</strong></div><div><span>Required monthly (zero growth)</span><strong>{money(g.progress.requiredMonthlyContribution)}</strong></div><div><span>Projected shortfall (zero growth)</span><strong>{money(g.progress.zeroGrowthShortfall)}</strong></div></div>
       <p>Projected balance: {money(g.progress.zeroGrowthProjectedBalance)} · Additional monthly amount: {money(g.progress.additionalMonthlyContribution)}</p>
       {g.funding&&<div className="thesis-digest"><p>Linked investments: {money(g.funding.linkedValue)} · Combined recorded funding: {money(g.funding.totalRecordedFunding)}</p>
       {g.funding.holdings.length>0&&<div className="tablewrap"><table><thead><tr><th>Assigned investment</th><th>Recorded value</th><th>Status</th><th>Action</th></tr></thead><tbody>{g.funding.holdings.map(h=><tr key={h.holdingId}><td>{h.symbol} · {h.assetType}</td><td>{money(h.recordedValue)}</td><td>{h.status.replace(/_/g," ").toLowerCase()}</td><td><button type="button" className="secondary" disabled={busy} onClick={()=>link(g.id,String(h.holdingId),true)}>Unassign {h.symbol}</button></td></tr>)}</tbody></table></div>}
       {assignment?.goal===g.id?<div className="atlas-compact-form"><label>Unassigned investment <select value={assignment.holding} onChange={e=>setAssignment({...assignment,holding:e.target.value})}><option value="">Choose holding</option>{(report.availableHoldings??[]).map(h=><option key={h.holdingId} value={h.holdingId}>{h.symbol} · {h.assetType}</option>)}</select></label>
       <label><input type="checkbox" checked={assignment.confirmed} onChange={e=>setAssignment({...assignment,confirmed:e.target.checked})}/> Reserved savings exclude assigned holdings and other goals.</label>
       <div className="atlas-form-actions"><button type="button" className="primary" disabled={busy||!assignment.confirmed||!assignment.holding} onClick={()=>link(g.id,assignment.holding,false)}>Confirm whole-holding assignment</button><button type="button" className="secondary" disabled={busy} onClick={()=>setAssignment(null)}>Cancel assignment</button></div></div>:<button type="button" className="secondary" disabled={busy||!report.availableHoldings?.length} onClick={()=>setAssignment({goal:g.id,holding:"",confirmed:false})}>Assign holding</button>}</div>}
       {report.goalRisk?.[g.id]&&<GoalRiskDigest risk={report.goalRisk[g.id]}/>}
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
     </div><p className="muted tiny">Only enter savings earmarked for this goal, excluding assigned holdings. Do not count the same savings in multiple goals.</p>
     <div className="atlas-form-actions"><button type="submit" className="primary" disabled={busy}>{busy?"Saving…":"Save goal"}</button><button type="button" className="secondary" disabled={busy} onClick={()=>{setForm(null);setEditing(null);setError("");}}>Cancel</button></div>
   </form>}
   {error&&<p role="alert">{error}</p>}
 </section>;
}
