import {useEffect, useState} from "react";

type Fund = {scheme_code:string;scheme_name:string;nav:string;nav_date:string;nav_date_status:string;as_of:string;freshness_status:string;stale:boolean;source:string};
type Status = {scheme_count:number;latest_nav_date:string|null;mode:string;automatic_collection_enabled:boolean;blocker:string|null;source:string;last_refresh_at:string|null;last_refresh_status:string;scheduler?:{next_run_at:string|null}};
type Detail = {
  identifier:string;scheme_name:string;source:string;scheme_type:string|null;plan:string|null;dividend_type:string|null;
  nav:{value:string;declared_date:string|null;date_status:string;catalog_observed_at:string;catalog_freshness:string};
  trading_terms:Record<string,string|number|boolean|null>;
  performance:{observation_count:number;trailing_returns_percent:Record<string,string|null>;status:string};
  portfolio:{top_holdings:null;market_cap_allocation:null;sector_allocation:null;status:string};
  costs:{expense_ratio:null;exit_load:null;status:string};rating:{value:null;agency:null;status:string};
  research_factors:{factor:string;status:string;value:string|null}[];
  recommendation:{status:string;label:string;reason:string};notice:string;
};
const BASE="/intelligence/api/v1/intelligence/mutual-funds";
const readable=(value:string)=>value.replace(/_/g," ").toLowerCase().replace(/^./,c=>c.toUpperCase());
const when=(value:string)=>new Intl.DateTimeFormat("en-IN",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Kolkata"}).format(new Date(value));
const money=(value:string|number|null)=>value===null||value===0?"Not specified":new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(Number(value));

export default function NavCatalog() {
  const [q,setQ]=useState("");
  const [items,setItems]=useState<Fund[]>([]);
  const [status,setStatus]=useState<Status|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [version,setVersion]=useState(0);
  const [detail,setDetail]=useState<Detail|null>(null);
  const [detailLoading,setDetailLoading]=useState(false);
  const [detailError,setDetailError]=useState("");
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
  async function refreshNow() {
    setBusy(true);setMessage("");
    try {
      const response=await fetch(BASE+"/refresh",{method:"POST"});
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Refresh failed");
      setMessage("Updated "+data.parsed+" schemes from the daily Upstox fund file.");
      setVersion(n=>n+1);
    } catch(e){setMessage(e instanceof Error?e.message:"Refresh failed")}
    finally{setBusy(false)}
  }
  async function openFund(fund:Fund) {
    setDetailLoading(true);setDetailError("");setDetail(null);
    try{
      const response=await fetch(BASE+"/details/"+encodeURIComponent(fund.scheme_code));
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Fund details unavailable");
      setDetail(data as Detail);
    }catch(e){setDetailError(e instanceof Error?e.message:"Fund details unavailable")}
    finally{setDetailLoading(false)}
  }
  return <section className="panel glass" aria-label="Mutual fund NAV catalog">
    <div className="sectionhead"><div><h2>Mutual fund NAV explorer</h2>
      <p>Search the validated daily provider catalog or your manually imported AMFI records. NAVs are end-of-day values, not live market quotes.</p></div></div>
    <p><strong>{status?.scheme_count??"—"}</strong> schemes · NAV date: {status?.latest_nav_date??(status?.scheme_count?"Not supplied by source":"No data")} · {status?.automatic_collection_enabled?"Automatic daily refresh":"Manual import"}</p>
    {status?.automatic_collection_enabled&&<div className="mf-catalog-status"><span>Source: documented Upstox mutual-fund instrument file</span><span>Daily refresh: about 6:30 AM IST</span><button className="secondary" type="button" disabled={busy} onClick={()=>void refreshNow()}>{busy?"Refreshing…":"Refresh now"}</button></div>}
    <label>Search by scheme name or code
      <input aria-label="Search mutual fund schemes" value={q} onChange={e=>setQ(e.target.value)} placeholder="e.g. Nifty 50 Index Fund" maxLength={100}/>
    </label>
    <label>Import official AMFI NAV text file (local only)
      <input aria-label="Import AMFI NAV text file" type="file" accept=".txt,text/plain" disabled={busy} onChange={e=>{void importFile(e.target.files?.[0]);e.target.value=""}}/>
    </label>
    <p role="status">{message}</p>
    <p>No Upstox account or token is required for the daily public catalog. An authenticated account is required only for importing your personal holdings.</p>
    <div className="tablewrap mf-catalog-table"><table><thead><tr><th>Scheme ID / ISIN</th><th>Scheme</th><th>NAV (₹)</th><th>As of</th><th>Freshness</th></tr></thead>
      <tbody>{items.map(f=><tr key={f.source+f.scheme_code}><td>{f.scheme_code}</td><td><button className="mf-fund-link" type="button" onClick={()=>void openFund(f)}>{f.scheme_name}<small>View fund details →</small></button></td><td>{f.nav}</td><td>{f.nav_date_status==="DECLARED"?f.nav_date:when(f.as_of)}</td><td>{f.nav_date_status==="DECLARED"?(f.stale?"Older NAV":"Recent NAV"):f.stale?"Catalog stale · NAV date unavailable":"Catalog checked recently · NAV date unavailable"}</td></tr>)}
        {!items.length&&<tr><td colSpan={5}>No imported schemes match this search.</td></tr>}</tbody></table></div>
    {detailLoading&&<div className="mf-detail-loading" role="status">Loading verified fund details…</div>}
    {detailError&&<div className="mf-attention" role="alert"><span>!</span><div><strong>Fund details unavailable</strong><p>{detailError}</p></div></div>}
    {detail&&<section className="mf-fund-detail" aria-label={`${detail.scheme_name} details`}>
      <header><div><small className="section-kicker">FUND RESEARCH DETAILS</small><h3>{detail.scheme_name}</h3><p>{detail.identifier} · {detail.scheme_type??"Category not supplied"} · {detail.plan?readable(detail.plan):"Plan not supplied"}</p></div><button type="button" className="secondary" onClick={()=>setDetail(null)}>Close</button></header>
      <div className="mf-detail-metrics">
        <article><span>Last published NAV</span><strong>₹{Number(detail.nav.value).toLocaleString("en-IN")}</strong><small>{detail.nav.declared_date??"NAV date not supplied"}</small></article>
        <article><span>Catalog checked</span><strong>{when(detail.nav.catalog_observed_at)}</strong><small>{detail.nav.catalog_freshness.toLowerCase()}</small></article>
        <article><span>Dated history</span><strong>{detail.performance.observation_count} observation{detail.performance.observation_count===1?"":"s"}</strong><small>{readable(detail.performance.status)}</small></article>
        <article><span>Recommendation</span><strong className="mf-blocked">Blocked</strong><small>Verified factors are incomplete</small></article>
      </div>
      <div className="mf-detail-grid">
        <section><h4>Purchase information</h4><dl><div><dt>Purchase available</dt><dd>{detail.trading_terms.purchase_allowed===true?"Yes":detail.trading_terms.purchase_allowed===false?"No":"Not supplied"}</dd></div><div><dt>Redemption available</dt><dd>{detail.trading_terms.redemption_allowed===true?"Yes":detail.trading_terms.redemption_allowed===false?"No":"Not supplied"}</dd></div><div><dt>Minimum purchase</dt><dd>{money(detail.trading_terms.minimum_purchase_amount as number|null)}</dd></div><div><dt>Additional purchase</dt><dd>{money(detail.trading_terms.additional_purchase_amount as number|null)}</dd></div><div><dt>Settlement</dt><dd>{String(detail.trading_terms.settlement_type??"Not supplied")}</dd></div></dl></section>
        <section><h4>Returns</h4><div className="mf-return-grid">{Object.entries(detail.performance.trailing_returns_percent).map(([period,value])=><div key={period}><span>{period.toUpperCase()}</span><strong>{value===null?"—":`${Number(value).toFixed(2)}%`}</strong></div>)}</div><p>{detail.performance.status==="AVAILABLE"?"Calculated only from stored dated NAV observations.":"ATLAS is collecting daily observations. Longer-period returns will appear only when enough dated history exists."}</p></section>
        <section><h4>Portfolio and market-cap mix</h4><div className="mf-missing-evidence"><strong>Not supplied by the connected source</strong><p>Top holdings, sectors and large/mid/small-cap allocation require a verified portfolio-disclosure source.</p></div></section>
        <section><h4>Costs and independent rating</h4><div className="mf-missing-evidence"><strong>No licensed rating or cost feed</strong><p>Expense ratio, exit load and agency rating are not inferred from the fund name or NAV.</p></div></section>
      </div>
      <section className="mf-factor-panel"><div><small className="section-kicker">MULTI-FACTOR CHECK</small><h4>What ATLAS can verify</h4></div><div className="mf-factor-list">{detail.research_factors.map(f=><article key={f.factor}><span>{f.factor}</span><strong>{f.value===null?readable(f.status):f.value+"%"}</strong></article>)}</div><div className="mf-recommendation-blocked"><strong>{detail.recommendation.label}</strong><p>{detail.recommendation.reason}</p></div></section>
    </section>}
  </section>;
}
