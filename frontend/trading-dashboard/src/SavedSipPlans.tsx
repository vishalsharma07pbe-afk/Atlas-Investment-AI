import {useEffect,useRef,useState} from "react";

type Fund={scheme_code:number;scheme_name:string;nav:number|null;nav_date:string|null};
type Sip={id:string;scheme_code:number;scheme_name:string;monthly_amount:number;start_date:string;next_installment_date:string;active:boolean};
const today=()=>new Date().toISOString().slice(0,10);
const money=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(value);

export default function SavedSipPlans(){
 const [plans,setPlans]=useState<Sip[]>([]),[query,setQuery]=useState(""),[matches,setMatches]=useState<Fund[]>([]);
 const [selected,setSelected]=useState<Fund|null>(null),[amount,setAmount]=useState("5000"),[date,setDate]=useState(today());
 const [loading,setLoading]=useState(false),[notice,setNotice]=useState("");
 const searchId=useRef(0);
 async function load(){const response=await fetch("/api/v1/research-workspace/sip-plans",{cache:"no-store"});if(!response.ok)throw Error("Saved SIPs are unavailable");setPlans(await response.json());}
 useEffect(()=>{void load().catch(e=>setNotice(e.message));},[]);
 useEffect(()=>{
  const term=query.trim();if(term.length<2||selected?.scheme_name===query){setMatches([]);return;}
  const id=++searchId.current;const timer=window.setTimeout(async()=>{try{const response=await fetch("/api/v1/mutual-funds/search?q="+encodeURIComponent(term));if(!response.ok)throw Error();const rows=await response.json();if(id===searchId.current)setMatches(rows.slice(0,8));}catch{if(id===searchId.current)setMatches([]);}},180);
  return()=>window.clearTimeout(timer);
 },[query,selected?.scheme_name]);
 async function save(event:React.FormEvent){event.preventDefault();if(!selected){setNotice("Choose a fund from the suggestions first.");return;}setLoading(true);setNotice("");try{const response=await fetch("/api/v1/research-workspace/sip-plans",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({schemeCode:selected.scheme_code,schemeName:selected.scheme_name,monthlyAmount:Number(amount),startDate:date,nextInstallmentDate:date,active:true})});if(!response.ok)throw Error((await response.json().catch(()=>null))?.message||"SIP could not be saved");await load();setSelected(null);setQuery("");setNotice("SIP plan saved. ATLAS tracks it here; it does not place a broker order.");}catch(e){setNotice(e instanceof Error?e.message:"SIP could not be saved");}finally{setLoading(false);}}
 async function toggle(plan:Sip){await fetch(`/api/v1/research-workspace/sip-plans/${plan.id}/active`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({active:!plan.active})});await load();}
 async function remove(plan:Sip){if(!confirm(`Delete the saved SIP for ${plan.scheme_name}?`))return;await fetch(`/api/v1/research-workspace/sip-plans/${plan.id}`,{method:"DELETE"});await load();}
 return <section className="mf-card glass sip-manager" aria-label="Saved mutual fund SIPs">
  <div className="mf-card-head"><div><small className="section-kicker">MY MONTHLY INVESTMENTS</small><h2>Saved SIPs</h2></div><span>{plans.filter(x=>x.active).length} active</span></div>
  <p className="muted tiny">Save the SIPs you already run or plan to start. ATLAS tracks the schedule locally; it never places an order.</p>
  <form className="sip-quick-form" onSubmit={save}>
   <label className="sip-fund-search"><span>Fund name or scheme code</span><input value={query} onChange={e=>{setQuery(e.target.value);setSelected(null);}} placeholder="Start typing HDFC, Parag Parikh…" autoComplete="off" required/>{matches.length>0&&<div className="sip-suggestions" role="listbox">{matches.map(f=><button type="button" key={f.scheme_code} onClick={()=>{setSelected(f);setQuery(f.scheme_name);setMatches([]);}}><strong>{f.scheme_name}</strong><small>Code {f.scheme_code}{f.nav?` · NAV ${f.nav}`:""}</small></button>)}</div>}</label>
   <label><span>Monthly amount</span><input type="number" min="1" step="1" value={amount} onChange={e=>setAmount(e.target.value)} required/></label>
   <label><span>Next SIP date</span><input type="date" value={date} onChange={e=>setDate(e.target.value)} required/></label>
   <button className="primary" disabled={loading||!selected}>{loading?"Saving…":"Save SIP"}</button>
  </form>
  {notice&&<p className="holding-notice" role="status">{notice}</p>}
  <div className="sip-list">{plans.map(plan=><article key={plan.id} className={plan.active?"":"paused"}><div><strong>{plan.scheme_name}</strong><small>Scheme {plan.scheme_code} · next {new Date(plan.next_installment_date+"T00:00:00").toLocaleDateString("en-IN")}</small></div><b>{money(Number(plan.monthly_amount))}<small>/month</small></b><div><button className="secondary" type="button" onClick={()=>void toggle(plan)}>{plan.active?"Pause":"Resume"}</button><button className="danger" type="button" onClick={()=>void remove(plan)}>Delete</button></div></article>)}{!plans.length&&<div className="mf-empty"><strong>No SIP saved yet</strong><p>Choose a fund above and save your first monthly plan.</p></div>}</div>
 </section>;
}
