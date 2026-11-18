import {useEffect,useState} from "react";
import type {AuthIdentity} from "./AuthGate";
type Row=Record<string,unknown>;
const endpoint="/api/v1";
export function AtlasLiveWorkspace({identity}:{identity:AuthIdentity}){
 const [section,setSection]=useState<"stocks"|"funds"|"ai">("stocks");
 const [query,setQuery]=useState("");
 const [results,setResults]=useState<Row[]>([]);
 const [freshness,setFreshness]=useState<Row|null|undefined>(undefined);
 const [report,setReport]=useState<Row|null>(null);
 const [providers,setProviders]=useState<Row|null>(null);
 const [upstoxToken,setUpstoxToken]=useState("");
 const [expiresAt,setExpiresAt]=useState("");
 const [notice,setNotice]=useState("");
 async function request(path:string,init:RequestInit={}):Promise<any>{
  const response=await fetch(endpoint+path,{...init,credentials:"same-origin",headers:{...(init.body?{"Content-Type":"application/json"}:{}),...init.headers}});
  if(!response.ok)throw Error("Request failed: "+response.status);
  return response.json();
 }
 useEffect(()=>{
  let active=true;
  fetch(endpoint+"/system/freshness",{credentials:"same-origin"}).then(async response=>{if(active&&response.ok)setFreshness(await response.json());})
   .catch(()=>{if(active)setFreshness(null);});
  return()=>{active=false;};
 },[]);
 async function search(){try{const path=section==="funds"?"/mutual-funds/search":"/instruments/search";setResults(await request(path+"?q="+encodeURIComponent(query)));setNotice("");}catch(e){setNotice(String(e));}}
 async function analyze(){try{const symbol=query.trim().toUpperCase();if(!/^[A-Z0-9._&-]{1,40}$/.test(symbol))throw Error("Enter a valid symbol");setProviders(await request("/ai/providers/health"));setReport(await request("/ai/analyze/"+encodeURIComponent(symbol),{method:"POST",body:JSON.stringify({symbol,market:"NSE"})}));}catch(e){setNotice(String(e));}}
 async function connect(){try{await request("/broker/upstox/token",{method:"POST",body:JSON.stringify({accessToken:upstoxToken,expiresAt})});setUpstoxToken("");setNotice("Upstox token stored in encrypted vault.");}catch(e){setNotice(String(e));}}
 async function sync(){try{const data=await request("/portfolio/sync/upstox",{method:"POST"});setNotice("Holdings synchronized: "+String(data.synced));}catch(e){setNotice(String(e));}}
 const equity=(freshness?.instruments as Row[]|undefined)||[];
 const funds=(freshness?.mutualFunds as Row[]|undefined)||[];
 const stale=[...equity.filter(r=>r.alert_id!=null),...funds.filter(r=>r.stale===true)];
 return <section className="panel glass live-workspace" aria-label="ATLAS Live Workspace">
  <div className="sectionhead"><div><small className="section-kicker">AUTHENTICATED RESEARCH</small><h2>Live Market &amp; Mutual Fund Explorer</h2></div><span className="tag">PRIVATE WORKSPACE</span></div>
   <div className="live-workspace-context"><p className="signed-in-context">Signed in as <strong>{identity.email}</strong></p>
   {stale.length>0?<div role="alert" className="notice warning-notice">{stale.length} stale equity or mutual-fund feeds detected. Verify source timestamps before relying on results.</div>:freshness===null?<div role="alert" className="notice warning-notice">Freshness unconfigured or unavailable. Do not assume data is live.</div>:freshness?<p className="muted tiny">Freshness is monitored, but provider data may still be delayed.</p>:<p className="muted tiny">Checking source freshness…</p>}</div>
   <div className="live-vault">
    <div className="live-vault-heading"><div><small className="section-kicker">READ-ONLY PROVIDER ACCESS</small><h3>Upstox token vault</h3></div><p>Stored locally and never displayed after saving.</p></div>
    <div className="live-vault-grid"><label><span>Access token</span><input aria-label="Upstox access token" type="password" autoComplete="off" value={upstoxToken} onChange={e=>setUpstoxToken(e.target.value)} placeholder="Authorized read-only token"/></label>
    <label><span>Token expiry</span><input aria-label="Upstox token expiry" type="datetime-local" value={expiresAt} onChange={e=>setExpiresAt(e.target.value)}/></label></div>
    <div className="compact-form-actions live-vault-actions"><button className="primary" onClick={connect} disabled={!upstoxToken||!expiresAt}>Save token to vault</button><button className="secondary" onClick={sync}>Sync Upstox holdings</button></div>
   </div>
   <div className="live-tabs" role="tablist" aria-label="Live research tabs">{(["stocks","funds","ai"] as const).map(t=><button type="button" role="tab" key={t} aria-selected={section===t} className={section===t?"active":""} onClick={()=>{setSection(t);setResults([]);setReport(null);}}>{t==="stocks"?"Market Explorer":t==="funds"?"Mutual Fund Explorer":"AI Committee"}</button>)}</div>
   <div className="live-search"><input aria-label="Research search" value={query} onChange={e=>setQuery(e.target.value)} placeholder={section==="funds"?"Fund name or scheme code":"Stock symbol"}/>
    {section==="ai"?<button className="primary" onClick={analyze}>Analyze with AI committee</button>:<button className="primary" onClick={search}>Search {section==="stocks"?"stocks":"mutual funds"}</button>}</div>
   {results.length>0&&<div className="tablewrap"><table><tbody>{results.map((r,i)=><tr key={i}><td>{String(r.trading_symbol||r.scheme_name||"")}</td><td>{String(r.isin||r.scheme_code||"")}</td></tr>)}</tbody></table></div>}
   {section==="ai"&&<><h3>Provider health</h3><pre>{providers?JSON.stringify(providers,null,2):"Not checked"}</pre><h3>AI committee report</h3><pre aria-label="AI committee report">{report?JSON.stringify(report,null,2):"Run analysis to see a report."}</pre></>}
  {notice&&<p role="status">{notice}</p>}
 </section>;
}
