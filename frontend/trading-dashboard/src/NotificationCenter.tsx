import React,{useEffect,useState} from "react";
type Alert={id:string;revision_key?:string;freshness?:"STALE"|"RECENT"|"NOT_APPLICABLE";category:string;title:string;description:string;event_date:string|null;published_at:string;source_name:string;source_url:string;subscription_total_x:string|null;subscription_as_of:string|null};
type Summary={ids:string[];revision_keys?:string[];total:number;live_feed_connected:boolean};
const BASE="/intelligence/api/v1/intelligence/notifications";
const KEY="atlas:read-alert-ids";
function savedIds():string[]{try{const v=JSON.parse(localStorage.getItem(KEY)||"[]");return Array.isArray(v)?v.filter(x=>typeof x==="string"):[];}catch{return [];}}
export default function NotificationCenter(){
  const [ids,setIds]=useState<string[]>([]);
  const [category,setCategory]=useState("ALL");
  const [seen,setSeen]=useState<string[]>(savedIds);
  const [open,setOpen]=useState(false);
  const [alerts,setAlerts]=useState<Alert[]|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState("");
  const [summaryError,setSummaryError]=useState(false);
  useEffect(()=>{
    const controller=new AbortController();
    fetch(BASE+"/summary",{signal:controller.signal})
      .then(async response=>{if(!response.ok)throw Error("Unavailable");return response.json() as Promise<Summary>;})
      .then(value=>{if(!controller.signal.aborted)setIds(value.revision_keys??value.ids);})
      .catch(()=>{if(!controller.signal.aborted)setSummaryError(true);});
    return ()=>controller.abort();
  },[]);
  const count=ids.filter(id=>!seen.includes(id)).length;
  async function toggle(){
    if(open){setOpen(false);return;}
    setOpen(true);setLoading(true);setError("");
    try{
      const response=await fetch(BASE,{cache:"no-store"});
      if(!response.ok)throw Error("Notification details unavailable.");
      const value:{alerts:Alert[]}=await response.json();
      setAlerts(value.alerts);
      const updated=[...new Set([...seen,...value.alerts.map(a=>a.revision_key??a.id)])].slice(-500);
      setSeen(updated);localStorage.setItem(KEY,JSON.stringify(updated));
      setIds(value.alerts.map(a=>a.revision_key??a.id));
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <div className="atlas-notifications">
    <button className="atlas-bell" type="button" aria-label={`Notifications, ${count} unread`} aria-expanded={open} onClick={toggle}>
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg>
      {count>0&&<span className="atlas-notification-count">{count>99?"99+":count}</span>}
      {summaryError&&<span className="atlas-notification-warning" title="Alert count unavailable">!</span>}
    </button>
    {open&&<><button type="button" className="atlas-notification-backdrop" aria-label="Close notifications" onClick={()=>setOpen(false)}/>
      <section className="atlas-notification-panel glass" aria-label="Notification center">
        <div className="atlas-notification-heading"><div><strong>Notifications</strong><small>IPOs · subscription · market events</small></div><button type="button" aria-label="Close notifications" onClick={()=>setOpen(false)}>×</button></div>
        {!loading&&!error&&alerts&&<div className="atlas-notification-filters"><label htmlFor="notification-filter">Filter</label><select id="notification-filter" value={category} onChange={e=>setCategory(e.target.value)}><option value="ALL">All notifications</option><option value="IPO_UPCOMING">Upcoming IPOs</option><option value="IPO_SUBSCRIPTION">IPO subscriptions</option><option value="IPO_ALLOTMENT">IPO allotments</option><option value="MARKET_EVENT">Market events</option><option value="CORPORATE_ACTION">Corporate actions</option><option value="RESEARCH_UPDATE">Research updates</option><option value="RISK_WARNING">Risk warnings</option></select></div>}
        {loading&&<p role="status">Loading notifications…</p>}
        {error&&<p role="alert">{error}</p>}
        {!loading&&!error&&alerts?.length===0&&<p className="muted tiny">No verified local alerts available. Live IPO and subscription feeds are not connected yet.</p>}
        {!loading&&!error&&alerts?.filter(a=>category==="ALL"||a.category===category).map(a=><article className="atlas-notification-item" key={a.id}>
          <div className="atlas-notification-category">{a.category.replace(/_/g," ")}</div>
          <strong>{a.title}</strong><p>{a.description}</p>
          {a.event_date&&<small>Event: {a.event_date}</small>}
          {a.subscription_total_x!==null&&<p>Subscription: {a.subscription_total_x}× · As of {a.subscription_as_of??"unknown"} {a.freshness==="STALE"&&<strong className="atlas-stale-label">STALE SNAPSHOT — do not treat as live</strong>}</p>}
          <small>Published {new Date(a.published_at).toLocaleString("en-IN")} · {a.source_name}</small>
          <a href={a.source_url} target="_blank" rel="noopener noreferrer">Source</a>
        </article>)}
        {!loading&&!error&&alerts&&alerts.length>0&&alerts.every(a=>category!=="ALL"&&a.category!==category)&&<p className="muted tiny">No alerts in this category.</p>}
        <p className="muted tiny">Alerts are loaded only when opened. Badge checks lightweight local metadata; no background market scraping.</p>
      </section></>}
  </div>;
}
