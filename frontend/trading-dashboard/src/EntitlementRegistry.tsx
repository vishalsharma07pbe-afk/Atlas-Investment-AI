import React,{useEffect,useState} from "react";
type Entry={source_id:string;dataset:string;mode:string;purpose:string;valid_until:string;reviewed_at:string;expired:boolean;independently_verified:boolean};
type Summary={status:string;manifest_error:string|null;sources:Entry[];automatic_collection_enabled:boolean;notice:string};
type Preflight={status:string;blockers:string[];matching_declarations:number;unexpired_declarations:number;automatic_collection_enabled:boolean;notice:string};
const ROOT="/intelligence/api/v1/intelligence/entitlements";
const DATASETS=["EQUITY_QUOTES","EQUITY_DAILY","MF_NAV","INSTITUTIONAL_FLOWS","GLOBAL_NEWS"];
const MODES=["MANUAL_IMPORT","AUTOMATED_FETCH","STREAM"];
export default function EntitlementRegistry(){
 const [data,setData]=useState<Summary|null>(null),[error,setError]=useState("");
 const [dataset,setDataset]=useState("EQUITY_QUOTES"),[mode,setMode]=useState("STREAM");
 const [preflight,setPreflight]=useState<Preflight|null>(null),[refresh,setRefresh]=useState(0);
 useEffect(()=>{const controller=new AbortController();
 fetch(ROOT,{signal:controller.signal}).then(r=>{if(!r.ok)throw Error("Status "+r.status);return r.json()})
 .then(x=>{setData(x);setError("")}).catch(e=>{if(e.name!=="AbortError")setError(String(e.message))});
 return ()=>controller.abort()},[refresh]);
 useEffect(()=>{const controller=new AbortController();
 fetch(ROOT+"/preflight?dataset="+encodeURIComponent(dataset)+"&mode="+encodeURIComponent(mode),{signal:controller.signal})
 .then(r=>{if(!r.ok)throw Error("Preflight "+r.status);return r.json()})
 .then(setPreflight).catch(e=>{if(e.name!=="AbortError")setError(String(e.message))});
 return ()=>controller.abort()},[dataset,mode,refresh]);
 return <section className="panel glass" aria-label="Provider entitlement review">
 <div className="sectionhead"><div><h2>Provider entitlement preflight</h2><p>Review local permission declarations before planning an ingestion adapter. Declarations do not activate feeds.</p></div>
 <button type="button" onClick={()=>setRefresh(n=>n+1)}>Recheck</button></div>
 {error&&<p role="alert">Entitlement review unavailable: {error}</p>}
 <p role="status"><strong>Automated collection: blocked</strong> · {data?.manifest_error??"Declaration review only"}</p>
 <div style={{display:"flex",gap:"12px",flexWrap:"wrap"}}>
 <label>Dataset <select aria-label="Dataset scope" value={dataset} onChange={e=>setDataset(e.target.value)}>{DATASETS.map(d=><option key={d}>{d}</option>)}</select></label>
 <label>Mode <select aria-label="Ingestion mode" value={mode} onChange={e=>setMode(e.target.value)}>{MODES.map(m=><option key={m}>{m}</option>)}</select></label></div>
 {preflight&&<p>Preflight: <strong>{preflight.status.replace(/_/g," ")}</strong> · {preflight.blockers.join(" · ").replace(/_/g," ")}. Matching declarations: {preflight.matching_declarations}.</p>}
 <div className="tablewrap"><table><thead><tr><th>Source</th><th>Dataset</th><th>Mode</th><th>Purpose</th><th>Expires</th><th>Verification</th></tr></thead>
 <tbody>{data?.sources.map(e=><tr key={e.source_id}><td>{e.source_id}</td><td>{e.dataset}</td><td>{e.mode}</td><td>{e.purpose}</td><td>{e.valid_until}</td><td>{e.expired?"Expired":"Unverified"}</td></tr>)}
 {!data?.sources.length&&<tr><td colSpan={6}>No valid entitlement declarations configured.</td></tr>}</tbody></table></div>
 <p>{data?.notice??"Provider status is not yet available."}</p>
 </section>
}
