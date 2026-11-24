import {FormEvent,useCallback,useEffect,useState} from "react";
type Rule={id:string;name:string;alert_type:string;target_identifier:string;enabled:boolean};
type Notice={id:string;title:string;message:string;source_code:string|null;occurred_at:string;read_at:string|null;delivery_status:string};

export default function PersonalAlerts(){
  const [rules,setRules]=useState<Rule[]>([]),[notices,setNotices]=useState<Notice[]>([]);
  const [name,setName]=useState(""),[type,setType]=useState("PRICE"),[target,setTarget]=useState(""),[operator,setOperator]=useState("AT_OR_ABOVE"),[value,setValue]=useState("");
  const [message,setMessage]=useState("");
  const load=useCallback(async()=>{
    try{const [ruleResponse,noticeResponse]=await Promise.all([fetch("/api/v1/research-workspace/alerts",{cache:"no-store"}),fetch("/api/v1/research-workspace/notifications",{cache:"no-store"})]);
      if(ruleResponse.ok)setRules(await ruleResponse.json());if(noticeResponse.ok)setNotices(await noticeResponse.json());
    }catch{/* Local API unavailable; retain visible empty state. */}
  },[]);
  useEffect(()=>{void load();},[load]);
  const save=async(event:FormEvent)=>{
    event.preventDefault();setMessage("");
    const response=await fetch("/api/v1/research-workspace/alerts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,alertType:type,targetIdentifier:target,condition:{operator,value:Number(value)},enabled:true})});
    if(!response.ok){setMessage("Alert could not be saved. Check the target and threshold.");return;}
    setName("");setTarget("");setValue("");setMessage("Alert saved. It will use only validated local observations.");await load();
  };
  const remove=async(id:string)=>{await fetch(`/api/v1/research-workspace/alerts/${id}`,{method:"DELETE"});await load();};
  const markRead=async(id:string)=>{await fetch(`/api/v1/research-workspace/notifications/${id}/read`,{method:"PATCH"});await load();};
  return <section className="personal-alerts" aria-labelledby="personal-alerts-title">
    <div><small className="section-kicker">SMART ALERTS</small><h2 id="personal-alerts-title">My price &amp; NAV alerts</h2></div>
    <p className="muted tiny">Alerts are evaluated against stored, source-attributed observations. They are not trading instructions and cannot place orders.</p>
    <form className="personal-alert-form" onSubmit={event=>void save(event)}>
      <label>Name<input value={name} maxLength={100} onChange={event=>setName(event.target.value)} required/></label>
      <label>Data<select value={type} onChange={event=>setType(event.target.value)}><option value="PRICE">Stock price</option><option value="NAV">Mutual fund NAV</option></select></label>
      <label>{type==="PRICE"?"Symbol / instrument key":"AMFI scheme code"}<input value={target} maxLength={120} onChange={event=>setTarget(event.target.value)} required/></label>
      <label>Rule<select value={operator} onChange={event=>setOperator(event.target.value)}><option value="AT_OR_ABOVE">At or above</option><option value="ABOVE">Above</option><option value="AT_OR_BELOW">At or below</option><option value="BELOW">Below</option></select></label>
      <label>Threshold<input type="number" min="0" step="0.0001" value={value} onChange={event=>setValue(event.target.value)} required/></label>
      <button type="submit">Save alert</button>
    </form>
    {message&&<p className="muted tiny" role="status">{message}</p>}
    <div className="personal-alert-columns">
      <div><h3>Active rules</h3>{rules.map(rule=><article key={rule.id}><div><strong>{rule.name}</strong><small>{rule.alert_type} · {rule.target_identifier}</small></div><button type="button" className="danger" onClick={()=>void remove(rule.id)}>Remove</button></article>)}{!rules.length&&<p className="muted tiny">No saved alerts.</p>}</div>
      <div><h3>Notification history</h3>{notices.map(notice=><article key={notice.id} className={notice.read_at?"read":""}><div><strong>{notice.title}</strong><small>{notice.message} · {new Date(notice.occurred_at).toLocaleString("en-IN")}</small></div>{!notice.read_at&&<button type="button" onClick={()=>void markRead(notice.id)}>Mark read</button>}</article>)}{!notices.length&&<p className="muted tiny">No alert has triggered from validated data.</p>}</div>
    </div>
  </section>;
}
