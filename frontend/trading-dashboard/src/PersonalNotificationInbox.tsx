import {useEffect,useState} from "react";
const BASE="/api/v1/research-workspace/notifications";
type Notice={id:string;title:string;message:string;event_type:string;occurred_at:string;read_at:string|null};
export default function PersonalNotificationInbox({onRead}:{onRead:()=>void}){
 const [items,setItems]=useState<Notice[]|null>(null),[error,setError]=useState(false),[busy,setBusy]=useState<string|null>(null);
 useEffect(()=>{
  let active=true;const controller=new AbortController();
  void (async()=>{try{const r=await fetch(BASE,{cache:"no-store",signal:controller.signal});if(!r.ok)throw Error();const rows=await r.json();if(!Array.isArray(rows))throw Error();if(active)setItems(rows);}catch{if(active)setError(true);}})();
  return()=>{active=false;controller.abort();};
 },[]);
 async function markRead(id:string){
  setBusy(id);setError(false);
  try{const response=await fetch(BASE+"/"+encodeURIComponent(id)+"/read",{method:"PATCH"});if(!response.ok)throw Error();setItems(rows=>rows?.map(row=>row.id===id?{...row,read_at:new Date().toISOString()}:row)||[]);onRead();}
  catch{setError(true);}finally{setBusy(null);}
 }
 return <section className="personal-notification-inbox" aria-label="My investment alerts">
  <h3>My investment alerts</h3><p className="muted tiny">Automatic portfolio review and saved price/NAV alerts. Read state is stored in your account.</p>
  {error&&<p role="alert">Personal alerts could not be updated. Reopen notifications to retry.</p>}
  {!items&&!error&&<p role="status">Loading investment alerts…</p>}
  {items?.length===0&&<p>No personal alerts recorded yet.</p>}
  {items?.map(row=><article key={row.id} className="atlas-notification-item"><small>{row.event_type.replace(/_/g," ")}</small><strong>{row.title}</strong><p>{row.message}</p><small>{new Date(row.occurred_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST</small>{row.read_at?<small>Read</small>:<button type="button" className="secondary" disabled={busy!==null} onClick={()=>void markRead(row.id)}>Mark read</button>}</article>)}
 </section>;
}
