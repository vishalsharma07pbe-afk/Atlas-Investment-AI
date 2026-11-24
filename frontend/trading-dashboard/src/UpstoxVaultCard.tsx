import {useState} from "react";

function defaultExpiry(){const value=new Date();value.setHours(23,59,0,0);const local=new Date(value.getTime()-value.getTimezoneOffset()*60_000);return local.toISOString().slice(0,16);}

export default function UpstoxVaultCard({onConnected}:{onConnected?:()=>void|Promise<void>}){
 const [token,setToken]=useState(""),[expiresAt,setExpiresAt]=useState(defaultExpiry),[busy,setBusy]=useState(false),[notice,setNotice]=useState("");
 async function save(event:React.FormEvent){event.preventDefault();setBusy(true);setNotice("");try{const expiry=new Date(expiresAt);if(!Number.isFinite(expiry.getTime())||expiry<=new Date())throw Error("Choose the real future expiry shown for this token.");const response=await fetch("/api/v1/broker/upstox/token",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({accessToken:token,expiresAt:expiry.toISOString()})});if(!response.ok)throw Error((await response.json().catch(()=>null))?.message||"The token could not be stored.");setToken("");setNotice("Connected securely. ATLAS will now refresh your saved stocks automatically.");await onConnected?.();}catch(error){setNotice(error instanceof Error?error.message:"Connection failed");}finally{setBusy(false);}}
 return <section className="panel glass provider-connect-card" aria-label="Connect Upstox">
  <div><small className="section-kicker">ONE-TIME PROVIDER STEP</small><h2>Connect today’s Upstox access</h2><p>Save the authorized read-only token in the encrypted vault. It is never shown again or sent to the browser after saving.</p></div>
  <form onSubmit={save}><label><span>Access token</span><input aria-label="Upstox access token" type="password" autoComplete="off" value={token} onChange={event=>setToken(event.target.value)} placeholder="Paste locally—not in chat" required/></label><label><span>Token expiry</span><input aria-label="Upstox token expiry" type="datetime-local" value={expiresAt} onChange={event=>setExpiresAt(event.target.value)} required/></label><button className="primary" disabled={busy||!token}>{busy?"Connecting…":"Save and connect"}</button></form>
  {notice&&<p className="holding-notice" role="status">{notice}</p>}
  <small className="muted">Upstox controls token expiry. When it expires, ATLAS cannot safely refresh quotes until a new authorized token is saved.</small>
 </section>;
}
