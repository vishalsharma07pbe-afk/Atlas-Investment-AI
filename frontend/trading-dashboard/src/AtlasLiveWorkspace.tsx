import React,{useEffect,useState} from "react";
type Session={access_token:string;expires_in:number};
type Row=Record<string,unknown>;
const endpoint="/api/v1";
const SESSION_KEY="atlas:auth-session";
type StoredSession={access_token:string;expires_at:number};
function readSession():string|null{
 try{const raw=sessionStorage.getItem(SESSION_KEY);if(!raw)return null;const saved=JSON.parse(raw) as StoredSession;if(typeof saved.access_token!=="string"||!Number.isFinite(saved.expires_at)||saved.expires_at<=Date.now()){sessionStorage.removeItem(SESSION_KEY);return null;}return saved.access_token;}catch{sessionStorage.removeItem(SESSION_KEY);return null;}
}
function clearSession(){sessionStorage.removeItem(SESSION_KEY);}
function saveSession(session:Session){sessionStorage.setItem(SESSION_KEY,JSON.stringify({access_token:session.access_token,expires_at:Date.now()+Math.max(0,session.expires_in-30)*1000}));}
export function AtlasLiveWorkspace(){
 const [token,setToken]=useState<string|null>(readSession);
 const [identity,setIdentity]=useState<Row|null>(null);
 const [email,setEmail]=useState("");
 const [password,setPassword]=useState("");
 const [mode,setMode]=useState<"login"|"register">("login");
 const [section,setSection]=useState<"stocks"|"funds"|"ai">("stocks");
 const [query,setQuery]=useState("");
 const [results,setResults]=useState<Row[]>([]);
 const [freshness,setFreshness]=useState<Row|null>(null);
 const [report,setReport]=useState<Row|null>(null);
 const [providers,setProviders]=useState<Row|null>(null);
 const [upstoxToken,setUpstoxToken]=useState("");
 const [expiresAt,setExpiresAt]=useState("");
 const [notice,setNotice]=useState("");
 const [authPending,setAuthPending]=useState(false);
 async function request(path:string,init:RequestInit={}):Promise<any>{
  const response=await fetch(endpoint+path,{...init,headers:{...(init.body?{"Content-Type":"application/json"}:{}),...(token?{Authorization:"Bearer "+token}:{}),...init.headers}});
  if(!response.ok)throw Error("Request failed: "+response.status);
  return response.json();
 }
 async function login(e:React.FormEvent){
  e.preventDefault();
  if(authPending)return;
  setAuthPending(true);setNotice("");
  try{
   if(mode==="register"){
    await request("/auth/register",{method:"POST",body:JSON.stringify({email,password})});
   }
   const result:Session=await request("/auth/login",{method:"POST",body:JSON.stringify({email,password})});
   if(!result.access_token||!Number.isFinite(result.expires_in)||result.expires_in<=0)throw Error("Invalid login session returned by server.");
   saveSession(result);setToken(result.access_token);setPassword("");setNotice("");
  }catch(error){
   const message=String(error);
   if(mode==="register"&&message.includes("409"))setNotice("This email is already registered. Sign in with your existing password.");
   else if(message.includes("401"))setNotice("Email or password is incorrect. Check your credentials and try again.");
   else if(message.includes("429"))setNotice("Too many login attempts. Wait a minute and try again.");
   else setNotice(message);
  }finally{setAuthPending(false);}
 }
 useEffect(()=>{if(!token){setIdentity(null);setFreshness(null);return;}
  let active=true;
  const headers={Authorization:"Bearer "+token};
  Promise.all([fetch(endpoint+"/auth/me",{headers}),fetch(endpoint+"/system/freshness",{headers})]).then(async ([a,b])=>{
   if(!a.ok)throw Error("Session expired");
   if(active){setIdentity(await a.json());if(b.ok)setFreshness(await b.json());}
  }).catch(()=>{if(active){clearSession();setToken(null);setNotice("Session expired. Sign in again.");}});
  return()=>{active=false;};
 },[token]);
 async function logout(){try{await request("/auth/logout",{method:"POST"});}catch{/* Clear local session even if revoke is unavailable */}clearSession();setToken(null);setResults([]);setReport(null);}
 async function search(){try{const path=section==="funds"?"/mutual-funds/search":"/instruments/search";setResults(await request(path+"?q="+encodeURIComponent(query)));setNotice("");}catch(e){setNotice(String(e));}}
 async function analyze(){try{const symbol=query.trim().toUpperCase();if(!/^[A-Z0-9._&-]{1,40}$/.test(symbol))throw Error("Enter a valid symbol");setProviders(await request("/ai/providers/health"));setReport(await request("/ai/analyze/"+encodeURIComponent(symbol),{method:"POST",body:JSON.stringify({symbol,market:"NSE"})}));}catch(e){setNotice(String(e));}}
 async function connect(){try{await request("/broker/upstox/token",{method:"POST",body:JSON.stringify({accessToken:upstoxToken,expiresAt})});setUpstoxToken("");setNotice("Upstox token stored in encrypted vault.");}catch(e){setNotice(String(e));}}
 async function sync(){try{const data=await request("/portfolio/sync/upstox",{method:"POST"});setNotice("Holdings synchronized: "+String(data.synced));}catch(e){setNotice(String(e));}}
 const equity=(freshness?.instruments as Row[]|undefined)||[];
 const funds=(freshness?.mutualFunds as Row[]|undefined)||[];
 const stale=[...equity.filter(r=>r.alert_id!=null),...funds.filter(r=>r.stale===true)];
 return <section className="panel glass" aria-label="ATLAS Live Workspace">
  <div className="sectionhead"><div><small className="section-kicker">AUTHENTICATED RESEARCH</small><h2>Live Market &amp; Mutual Fund Explorer</h2></div></div>
  {!token?<form onSubmit={login} className="atlas-auth-form" aria-label="ATLAS account access">
   <div className="atlas-auth-intro"><span className="atlas-auth-eyebrow">SECURE ACCOUNT ACCESS</span><h3>{mode==="login"?"Welcome back":"Create your account"}</h3><p>{mode==="login"?"Sign in to explore your private market research workspace.":"Set up your private ATLAS research account."}</p></div>
   <label className="atlas-auth-field" htmlFor="atlas-account-email"><span>Email address</span><input id="atlas-account-email" aria-label="Account email" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={e=>setEmail(e.target.value)} required/></label>
   <label className="atlas-auth-field" htmlFor="atlas-account-password"><span>Password</span><input id="atlas-account-password" aria-label="Account password" type="password" autoComplete={mode==="register"?"new-password":"current-password"} placeholder={mode==="register"?"Create a secure password":"Enter your password"} value={password} onChange={e=>setPassword(e.target.value)} required minLength={12}/>{mode==="register"&&<small>Use at least 12 characters.</small>}</label>
   <button className="primary atlas-auth-submit" type="submit" disabled={authPending}>{authPending?"Please wait…":mode==="login"?"Sign in":"Create account"}</button>
   <p className="atlas-auth-switch">{mode==="login"?"New to ATLAS?":"Already have an account?"} <button type="button" disabled={authPending} onClick={()=>{setMode(mode==="login"?"register":"login");setNotice("");}}>{mode==="login"?"Create an account":"Sign in instead"}</button></p>
  </form>:<>
   <p>Signed in: {String(identity?.email||"Checking session…")} <button onClick={logout}>Logout</button></p>
   {stale.length>0?<div role="alert" className="notice warning-notice">{stale.length} stale equity or mutual-fund feeds detected. Verify source timestamps before relying on results.</div>:!freshness?<div role="alert" className="notice warning-notice">Freshness unconfigured or unavailable. Do not assume data is live.</div>:<p>Freshness monitored. Data may still be delayed.</p>}
   <div className="form"><h3>Upstox token vault</h3><input aria-label="Upstox access token" type="password" autoComplete="off" value={upstoxToken} onChange={e=>setUpstoxToken(e.target.value)} placeholder="Authorized read-only token"/>
   <input aria-label="Upstox token expiry" type="datetime-local" value={expiresAt} onChange={e=>setExpiresAt(e.target.value)}/>
   <button onClick={connect} disabled={!upstoxToken||!expiresAt}>Save token to vault</button><button onClick={sync}>Sync my Upstox holdings</button></div>
   <nav aria-label="Live research tabs">{(["stocks","funds","ai"] as const).map(t=><button key={t} aria-current={section===t?"page":undefined} onClick={()=>{setSection(t);setResults([]);setReport(null);}}>{t==="stocks"?"Market Explorer":t==="funds"?"Mutual Fund Explorer":"AI Committee"}</button>)}</nav>
   <div className="form"><input aria-label="Research search" value={query} onChange={e=>setQuery(e.target.value)} placeholder={section==="funds"?"Fund name or scheme code":"Stock symbol"}/>
    {section==="ai"?<button onClick={analyze}>Analyze with AI committee</button>:<button onClick={search}>Search {section==="stocks"?"stocks":"mutual funds"}</button>}</div>
   {results.length>0&&<div className="tablewrap"><table><tbody>{results.map((r,i)=><tr key={i}><td>{String(r.trading_symbol||r.scheme_name||"")}</td><td>{String(r.isin||r.scheme_code||"")}</td></tr>)}</tbody></table></div>}
   {section==="ai"&&<><h3>Provider health</h3><pre>{providers?JSON.stringify(providers,null,2):"Not checked"}</pre><h3>AI committee report</h3><pre aria-label="AI committee report">{report?JSON.stringify(report,null,2):"Run analysis to see a report."}</pre></>}
  </>}
  {notice&&<p role="status">{notice}</p>}
 </section>;
}
