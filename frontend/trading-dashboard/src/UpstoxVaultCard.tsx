import {useEffect,useState} from "react";

function defaultExpiry(){return "";}


export default function UpstoxVaultCard({onConnected}:{onConnected?:()=>void|Promise<void>}){
 const [token,setToken]=useState(""),[expiresAt,setExpiresAt]=useState(defaultExpiry),[busy,setBusy]=useState(false),[notice,setNotice]=useState(""),[credentialRevision,setCredentialRevision]=useState(0);
 async function save(event:React.FormEvent){event.preventDefault();setBusy(true);setNotice("");try{const expiry=new Date(expiresAt);if(!Number.isFinite(expiry.getTime())||expiry<=new Date())throw Error("Choose the real future expiry shown for this token.");const response=await fetch("/api/v1/broker/upstox/token",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({accessToken:token,expiresAt:expiry.toISOString()})});if(!response.ok)throw Error((await response.json().catch(()=>null))?.message||"The token could not be stored.");setToken("");setCredentialRevision(value=>value+1);setNotice("Token stored securely. Provider access is verified only when a request succeeds.");await onConnected?.();}catch(error){setNotice(error instanceof Error?error.message:"Connection failed");}finally{setBusy(false);}}
 return <section className="panel glass provider-connect-card" aria-label="Connect Upstox">
  <div><small className="section-kicker">OPTIONAL BROKER ACCOUNT ACCESS</small><h2>Broker holdings synchronization</h2><p>Your configured Analytics Token is used for market research and pricing. Account-specific broker imports require authorized portfolio access (Analytics Token with a whitelisted static IP, or a valid standard access token). Saved holdings do not need account access to receive market prices.</p></div>
  <details className="terminal-broker-credentials"><summary>Manage optional account credential</summary><form onSubmit={save}><label><span>Access token</span><input aria-label="Upstox access token" type="password" autoComplete="off" value={token} onChange={event=>setToken(event.target.value)} placeholder="Paste locally—not in chat" required/></label><label><span>Token expiry</span><input aria-label="Upstox token expiry" type="datetime-local" value={expiresAt} onChange={event=>setExpiresAt(event.target.value)} required/></label><button className="primary" disabled={busy||!token}>{busy?"Connecting…":"Save and connect"}</button></form></details>
  {notice&&<p className="holding-notice" role="status">{notice}</p>}
  <AutomaticHoldingsSync key={credentialRevision}/>
  <small className="muted">Enter the actual expiry shown by Upstox. This credential is encrypted and is only necessary for account-specific access; market pricing uses the configured read-only market-data connection.</small>
 </section>;
}

type SyncStatus={enabled:boolean;status:string;token_expires_at:string|null;last_attempt_at:string|null;last_success_at:string|null;next_attempt_at:string|null;error_code:string|null};
const SYNC_URL="/api/v1/broker/upstox/holdings-sync";
function validStatus(value:unknown):value is SyncStatus{
 return !!value&&typeof value==="object"&&"enabled" in value&&typeof value.enabled==="boolean"&&"status" in value&&typeof value.status==="string";
}
export function AutomaticHoldingsSync(){
 const [state,setState]=useState<SyncStatus|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
 useEffect(()=>{
  const controller=new AbortController();
  async function read(){
   try{const response=await fetch(SYNC_URL,{signal:controller.signal});if(!response.ok)throw Error();
    const value:unknown=await response.json();if(!validStatus(value))throw Error();
    if(!controller.signal.aborted)setState(value);
   }catch{if(!controller.signal.aborted)setError("Automatic sync status unavailable.");}
  }
  void read();return ()=>controller.abort();
 },[]);
 async function action(enabled?:boolean){
  setBusy(true);setError("");
  try{
   const response=await fetch(SYNC_URL,enabled===undefined?undefined:{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled})});
   if(!response.ok)throw Error();
   const value:unknown=await response.json();if(!validStatus(value))throw Error();
   setState(value);
  }catch{setError("Unable to update automatic sync. Check its status before retrying.");}finally{setBusy(false);}
 }
 const format=(value:string|null|undefined)=>value?new Date(value).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"}):"—";
 const blocked=state&&["TOKEN_EXPIRED","TOKEN_REQUIRED","REAUTH_REQUIRED","ACCESS_REJECTED"].includes(state.status);
 return <div className="provider-connect-card" aria-label="Automatic holdings synchronization">
   <h3>Automatic holdings synchronization</h3>
   <p className="muted tiny">Optional: reconcile broker-synced equity positions every 30 minutes when an authorized token is available. A successful complete snapshot may remove broker positions no longer held. Manual holdings are protected. No orders are placed.</p>
   {state&&<><p role="status">Automatic sync: {state.status.replace(/_/g," ")}</p>
     <p className="muted tiny">Last successful sync (IST): {format(state.last_success_at)} · Next eligible attempt (IST): {format(state.next_attempt_at)}</p>
     {state.error_code&&<p className="muted tiny">Last issue: {state.error_code.replace(/_/g," ")}</p>}
     {blocked&&<p>Review broker access or save a newly authorized token. ATLAS cannot renew access on your behalf.</p>}</>}
   <div className="form-actions">
     {state&&<button type="button" className="primary" disabled={busy} onClick={()=>void action(!state.enabled)}>{state.enabled?"Disable automatic holdings sync":"Enable automatic holdings sync"}</button>}
     <button type="button" disabled={busy} onClick={()=>void action()}>Refresh sync status</button>
   </div>
   {error&&<p role="alert">{error}</p>}
 </div>;
}
