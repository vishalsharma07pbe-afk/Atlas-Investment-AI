import React,{useState} from "react";
type Diagnostics={status:"CONFIGURED"|"BLOCKED";authorization_request_performed:boolean;live_stream_connected:boolean;blockers:string[];notice:string};
export default function UpstoxAuthorization(){
 const [result,setResult]=useState<Diagnostics|null>(null);
 const [error,setError]=useState("");
 const [loading,setLoading]=useState(false);
 async function inspect(){
   setLoading(true);setError("");setResult(null);
   try{
     const response=await fetch("/intelligence/api/v1/intelligence/providers/upstox/feed-authorization-readiness");
     if(!response.ok)throw Error("Upstox configuration diagnostics unavailable");
     const payload:Diagnostics=await response.json();
     if(!["CONFIGURED","BLOCKED"].includes(payload.status)||!Array.isArray(payload.blockers))throw Error("Invalid diagnostics");
     setResult(payload);
   }catch(e){setError(String(e));}finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Upstox feed authorization">
   <div className="sectionhead"><div><small className="section-kicker">UPSTOX V3 · READ ONLY</small><h2>Live feed authorization readiness</h2></div><span className="tag">NO LIVE QUOTES</span></div>
   <p className="muted tiny">Check local provider configuration without exposing tokens or initiating a provider connection. CONFIGURED does not mean connected.</p>
   <button className="secondary" disabled={loading} onClick={inspect}>{loading?"Checking…":"Check Upstox configuration"}</button>
   {error&&<p role="alert">{error}</p>}
   {result&&<div role="status"><p><strong>{result.status}</strong> · Stream {result.live_stream_connected?"connected":"not connected"}</p>
     {result.blockers.length>0&&<ul>{result.blockers.map(x=><li key={x}>{x.replace(/_/g," ")}</li>)}</ul>}
     <p className="muted tiny">{result.notice}</p>
   </div>}
 </section>;
}
