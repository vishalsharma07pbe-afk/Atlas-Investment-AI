import React, {useEffect, useState} from "react";

type Fund = {scheme_code:number;scheme_name:string;nav:string;nav_date:string;stale:boolean;source:string};
type Status = {scheme_count:number;latest_nav_date:string|null;mode:string;blocker:string};
const BASE="/intelligence/api/v1/intelligence/mutual-funds";

export default function NavCatalog() {
  const [q,setQ]=useState("");
  const [items,setItems]=useState<Fund[]>([]);
  const [status,setStatus]=useState<Status|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [version,setVersion]=useState(0);
  useEffect(()=>{
    let cancelled=false;
    fetch(BASE+"/status").then(r=>{if(!r.ok)throw Error("Catalog unavailable");return r.json()})
      .then(data=>{if(!cancelled)setStatus(data)}).catch(()=>{if(!cancelled)setMessage("NAV service unavailable")});
    return ()=>{cancelled=true};
  },[version]);
  useEffect(()=>{
    const controller=new AbortController();
    const timer=setTimeout(()=>{
      fetch(BASE+"/search?q="+encodeURIComponent(q)+"&limit=50",{signal:controller.signal})
        .then(r=>{if(!r.ok)throw Error("Search unavailable");return r.json()})
        .then(data=>setItems(data.items)).catch(e=>{if(e.name!=="AbortError")setMessage("NAV search unavailable")});
    },250);
    return ()=>{clearTimeout(timer);controller.abort()};
  },[q,version]);
  async function importFile(file:File|undefined) {
    if(!file)return;
    if(file.size>8_000_000){setMessage("File exceeds 8 MB limit");return}
    setBusy(true);setMessage("");
    try {
      const response=await fetch(BASE+"/import",{method:"POST",headers:{"Content-Type":"text/plain; charset=utf-8"},body:file});
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Import failed");
      setMessage("Imported "+data.parsed+" schemes; "+data.invalid_rows+" invalid rows skipped.");
      setVersion(n=>n+1);
    } catch(e){setMessage(e instanceof Error?e.message:"Import failed")}
    finally{setBusy(false)}
  }
  return <section className="panel glass" aria-label="Mutual fund NAV catalog">
    <div className="sectionhead"><div><h2>Mutual fund NAV explorer</h2>
      <p>Search validated, locally imported AMFI NAV records. These are end-of-day NAVs, not live market quotes.</p></div></div>
    <p><strong>{status?.scheme_count??"—"}</strong> schemes · Latest NAV date: {status?.latest_nav_date??"No data"} · Manual import only</p>
    <label>Search by scheme name or code
      <input aria-label="Search mutual fund schemes" value={q} onChange={e=>setQ(e.target.value)} placeholder="e.g. Nifty 50 Index Fund" maxLength={100}/>
    </label>
    <label>Import official AMFI NAV text file (local only)
      <input aria-label="Import AMFI NAV text file" type="file" accept=".txt,text/plain" disabled={busy} onChange={e=>{void importFile(e.target.files?.[0]);e.target.value=""}}/>
    </label>
    <p role="status">{message}</p>
    <p>Automatic downloads are disabled pending source usage-rights confirmation. No Upstox account or token is required for manual import.</p>
    <div className="tablewrap"><table><thead><tr><th>Scheme code</th><th>Scheme</th><th>NAV (₹)</th><th>As of</th><th>Freshness</th></tr></thead>
      <tbody>{items.map(f=><tr key={f.scheme_code}><td>{f.scheme_code}</td><td>{f.scheme_name}</td><td>{f.nav}</td><td>{f.nav_date}</td><td>{f.stale?"Older NAV":"Recent NAV"}</td></tr>)}
        {!items.length&&<tr><td colSpan={5}>No imported schemes match this search.</td></tr>}</tbody></table></div>
  </section>;
}
