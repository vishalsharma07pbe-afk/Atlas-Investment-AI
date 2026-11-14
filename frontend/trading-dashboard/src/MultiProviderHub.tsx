import React,{useEffect,useState} from "react";
type Source={code:string;datasets:string[];transport:string;authorized:boolean;state:string;live:boolean};
type Health={checked_at:string;sources:Source[];live_feed_verified:boolean;notice:string};
type Item={symbol:string;value:string;observed_at:string;source:string;freshness:string;live:boolean};
type Lookup={items:Item[];status:string;live:boolean;notice?:string};
export default function MultiProviderHub(){
  const [health,setHealth]=useState<Health|null>(null);
  const [query,setQuery]=useState("");
  const [type,setType]=useState("MUTUAL_FUND");
  const [result,setResult]=useState<Lookup|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  useEffect(()=>{const controller=new AbortController();fetch("/intelligence/api/v1/intelligence/data-hub/sources",{signal:controller.signal}).then(r=>{if(!r.ok)throw Error("Provider status unavailable");return r.json()}).then(setHealth).catch(e=>{if(e.name!=="AbortError")setError(String(e))});return ()=>controller.abort()},[]);
  async function search(e:React.FormEvent){e.preventDefault();setLoading(true);setError("");setResult(null);try{
    const response=await fetch("/intelligence/api/v1/intelligence/data-hub/search?asset_type="+encodeURIComponent(type)+"&query="+encodeURIComponent(query.trim()));
    if(!response.ok)throw Error("Search failed ("+response.status+")");
    setResult(await response.json());
  }catch(e){setError(String(e))}finally{setLoading(false)}}
  return <section className="panel glass" aria-label="Multi-provider market data hub">
    <div className="sectionhead"><div><h2>Market data hub</h2><p>Research-only provider routing. Every observation identifies its source and freshness; no unverified live prices.</p></div></div>
    <form onSubmit={search} className="control-grid control-grid-3">
      <label className="field">Asset type<select value={type} onChange={e=>setType(e.target.value)}><option value="MUTUAL_FUND">Mutual fund</option><option value="EQUITY">Equity</option></select></label>
      <label className="field">Scheme code, name or ticker<input value={query} maxLength={100} onChange={e=>setQuery(e.target.value)} placeholder="Search validated local data" required/></label>
      <div className="form-actions"><button type="submit" className="primary" disabled={loading||!query.trim()}>{loading?"Searching…":"Search data"}</button></div>
    </form>
    {error&&<p role="alert">{error}</p>}
    <p role="status">Live market feed: <strong>Not verified</strong>. Automated provider failover remains blocked pending access and usage rights.</p>
    {health&&<div className="tablewrap"><table><thead><tr><th>Provider</th><th>Coverage</th><th>Access</th><th>Status</th></tr></thead><tbody>{health.sources.map(s=><tr key={s.code}><td>{s.code}</td><td>{s.datasets.join(", ")}</td><td>{s.transport}</td><td>{s.state.replace(/_/g," ")}</td></tr>)}</tbody></table></div>}
    {result&&<><p role="status">Search status: {result.status.replace(/_/g," ")} · {result.items.length} validated observations</p>
      {result.notice&&<p>{result.notice}</p>}
      {result.items.length>0&&<div className="tablewrap"><table><thead><tr><th>Scheme code</th><th>NAV</th><th>As of</th><th>Source</th><th>Freshness</th></tr></thead><tbody>{result.items.map((x,i)=><tr key={x.symbol+"-"+i}><td>{x.symbol}</td><td>{x.value}</td><td>{x.observed_at}</td><td>{x.source}</td><td>{x.freshness}</td></tr>)}</tbody></table></div>}</>}
  </section>
}
