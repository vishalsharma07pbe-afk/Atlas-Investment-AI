import {useEffect,useRef,useState} from "react";
import {visiblePolling} from "./visiblePolling";
const BASE="/api/v1/research-workspace/notifications";
type Notice={id:string;title:string;message:string;event_type:string;occurred_at:string;read_at:string|null};
export default function PersonalNotificationInbox({onRead}:{onRead:()=>void}){
 const [items,setItems]=useState<Notice[]|null>(null),[error,setError]=useState(false),[busy,setBusy]=useState<string|null>(null);
 const confirmed=useRef(new Map<string,string>());
 const active=useRef(false);
 useEffect(()=>{
  active.current=true;
  const stop=visiblePolling(async signal=>{
   try{
    const r=await fetch(BASE,{cache:"no-store",signal});
    if(!r.ok)throw Error();
    const rows:Notice[]=await r.json();
    if(!Array.isArray(rows)||rows.some(row=>!row||typeof row.id!=="string"))throw Error();
    if(signal.aborted)return;
    setItems(rows.map(row=>({...row,read_at:row.read_at??confirmed.current.get(row.id)??null})));
    for(const row of rows)if(row.read_at)confirmed.current.delete(row.id);
    setError(false);
   }catch{if(!signal.aborted)setError(true);}
  },60000);
  return()=>{active.current=false;stop();};
 },[]);
 async function markRead(id:string){
  setBusy(id);setError(false);
  try{
   const response=await fetch(BASE+"/"+encodeURIComponent(id)+"/read",{method:"PATCH"});
   if(!response.ok)throw Error();
   if(!active.current)return;
   const stamp=new Date().toISOString();
   confirmed.current.set(id,stamp);
   setItems(rows=>rows?.map(row=>row.id===id?{...row,read_at:stamp}:row)||[]);
   onRead();
  }catch{if(active.current)setError(true);}finally{if(active.current)setBusy(null);}
 }
 return <section className="personal-notification-inbox" aria-label="My investment alerts">
  <h3>My investment alerts</h3><p className="muted tiny">Automatic portfolio review and saved price/NAV alerts. Read state is stored in your account.</p>
  {error&&<p role="alert">Personal alerts could not be updated. Retrying while open.</p>}
  {!items&&!error&&<p role="status">Loading investment alerts…</p>}
  {items?.length===0&&<p>No personal alerts recorded yet.</p>}
  {!error&&items?.map(row=><article key={row.id} className="atlas-notification-item"><small>{row.event_type.replace(/_/g," ")}</small><strong>{row.title}</strong><p>{row.message}</p><small>{new Date(row.occurred_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST</small>{row.read_at?<small>Read</small>:<button type="button" className="secondary" disabled={busy!==null} onClick={()=>void markRead(row.id)}>Mark read</button>}</article>)}
 </section>;
}
