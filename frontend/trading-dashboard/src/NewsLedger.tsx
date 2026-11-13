import React,{useEffect,useState} from "react";
type Item={headline:string;source_name:string;source_url:string;published_at:string;geography:string;event_type:string;sentiment:string;freshness:string};
type Response={events:Item[];event_count:number;fresh_count:number;notice:string};
const base="/intelligence/api/v1/intelligence/news/ledger";
export default function NewsLedger(){
 const [rows,setRows]=useState<Response|null>(null);
 const [region,setRegion]=useState("ALL");
 const [headline,setHeadline]=useState("");
 const [publisher,setPublisher]=useState("");
 const [url,setUrl]=useState("");
 const [published,setPublished]=useState("");
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const [version,setVersion]=useState(0);
 useEffect(()=>{
   const controller=new AbortController();
   const params=new URLSearchParams({limit:"100",max_age_hours:"72"});
   if(region!=="ALL")params.set("geography",region);
   fetch(base+"?"+params,{signal:controller.signal})
     .then(r=>{if(!r.ok)throw Error("News ledger unavailable");return r.json()})
     .then(setRows).catch(e=>{if(e.name!=="AbortError")setError("News ledger unavailable")});
   return ()=>controller.abort();
 },[region,version]);
 async function save(e:React.FormEvent){
   e.preventDefault();setError("");setBusy(true);
   try{
     const timestamp=new Date(published);
     if(!Number.isFinite(timestamp.getTime()))throw Error("Invalid publication time");
     const response=await fetch(base,{method:"POST",headers:{"Content-Type":"application/json"},
       body:JSON.stringify({events:[{headline,source_name:publisher,source_url:url,
         published_at:timestamp.toISOString(),geography:region==="ALL"?"GLOBAL":region,
         event_type:"OTHER",sentiment:"UNKNOWN",sentiment_method:"USER_LABELLED"}]})});
     if(!response.ok)throw Error("Evidence rejected ("+response.status+")");
     setHeadline("");setPublisher("");setUrl("");setPublished("");setVersion(n=>n+1);
   }catch(e){setError(String(e))}finally{setBusy(false)}
 }
 return <section className="panel glass" aria-label="Global news evidence ledger">
   <div className="sectionhead"><div><h2>Global news evidence ledger</h2><p>Persistent, source-attributed, manually entered news. No live feed or independent fact-checking.</p></div></div>
   <form className="form" onSubmit={save}>
     <input aria-label="Ledger headline" placeholder="Article headline" minLength={8} maxLength={300} required value={headline} onChange={e=>setHeadline(e.target.value)}/>
     <input aria-label="Ledger publisher" placeholder="Publisher" minLength={3} maxLength={120} required value={publisher} onChange={e=>setPublisher(e.target.value)}/>
     <input aria-label="Ledger source URL" type="url" pattern="https://.*" placeholder="https://publisher.example/article" required value={url} onChange={e=>setUrl(e.target.value)}/>
     <label>Publication time <input aria-label="Ledger publication time" type="datetime-local" required value={published} onChange={e=>setPublished(e.target.value)}/></label>
     <button className="primary" disabled={busy}>{busy?"Saving…":"Save evidence"}</button>
   </form>
   {error&&<p role="alert" className="error">{error}</p>}
   <label>Geography <select aria-label="Ledger geography filter" value={region} onChange={e=>setRegion(e.target.value)}>
     {["ALL","GLOBAL","INDIA","US","EUROPE","ASIA_OTHER","OTHER"].map(v=><option key={v}>{v}</option>)}
   </select></label>
   <p role="status">Records: {rows?.event_count??"—"} · Fresh (72 hours): {rows?.fresh_count??"—"}</p>
   <div className="tablewrap"><table><thead><tr><th>Headline</th><th>Source</th><th>Published</th><th>Region</th><th>Sentiment</th><th>Freshness</th></tr></thead>
   <tbody>{rows?.events.map((x,i)=><tr key={x.source_url+x.published_at+i}><td><a href={x.source_url} target="_blank" rel="noopener noreferrer">{x.headline}</a></td><td>{x.source_name}</td><td>{x.published_at}</td><td>{x.geography}</td><td>{x.sentiment}</td><td>{x.freshness}</td></tr>)}
   {!rows?.events.length&&<tr><td colSpan={6}>No saved evidence for this region.</td></tr>}</tbody></table></div>
 </section>;
}
