import React,{useEffect,useState} from "react";

type Dataset={code:string;label:string;records:number;latest_observed_at:string|null;age:number|null;age_unit:string;freshness_threshold:number;status:string;ingestion_mode:string;independently_verified:boolean;automatic_collection_enabled:boolean;usable_as_live_market_data:boolean};
type Readiness={generated_at:string;status:string;provider_mode:string;live_market_data_connected:boolean;automatic_research_enabled:boolean;actionable_recommendations_enabled:boolean;blockers:string[];datasets:Dataset[];notice:string};

export default function DataReadiness(){
  const [data,setData]=useState<Readiness|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);
    fetch("/intelligence/api/v1/intelligence/data-readiness",{signal:controller.signal})
      .then(r=>{if(!r.ok)throw Error("Readiness service returned "+r.status);return r.json()})
      .then((result:Readiness)=>{setData(result);setError("")})
      .catch(e=>{if(e.name!=="AbortError"){setError("Cannot verify source readiness: "+String(e.message));setData(null)}})
      .finally(()=>setLoading(false));
    return ()=>controller.abort();
  },[refresh]);
  return <section className="panel glass" aria-label="Source readiness">
    <div className="sectionhead"><div><h2>Data source readiness</h2>
      <p>Independent freshness, provenance and access checks. Local evidence never counts as a licensed live feed.</p></div>
      <button type="button" onClick={()=>setRefresh(n=>n+1)} disabled={loading}>Refresh status</button></div>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p role="status">Checking local data readiness…</p>}
    {data&&<>
      <p role="status"><strong>Automatic market research: blocked</strong> · Provider: {data.provider_mode} · Live market feed: not verified</p>
      <p>Last checked: {new Date(data.generated_at).toLocaleString("en-IN")}</p>
      <div className="tablewrap"><table><thead><tr><th>Dataset</th><th>Records</th><th>Latest observation</th><th>Freshness</th><th>Collection</th></tr></thead>
        <tbody>{data.datasets.map(d=><tr key={d.code}>
          <td>{d.label}</td><td>{d.records}</td><td>{d.latest_observed_at??"No records"}</td>
          <td>{d.status.replaceAll("_"," ")}{d.age!==null?" ("+d.age+" "+d.age_unit+" old)":""}</td>
          <td>Manual only</td>
        </tr>)}</tbody></table></div>
      <p><strong>Activation blockers:</strong> {data.blockers.map(x=>x.replaceAll("_"," ")).join(" · ")}</p>
      <p>{data.notice}</p>
    </>}
  </section>;
}
