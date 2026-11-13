import React,{useState} from "react";
type Report={status:string;ingestion_authorized:boolean;dry_run:boolean;records_examined:number;instruments_examined:number;latest_trade_date:string;blockers:string[];notice:string};
const example=JSON.stringify({provider:"UPSTOX",source_reference:"Authorized test fixture",rights_confirmed:false,entitlement_confirmed:false,instrument_mapping_confirmed:false,candles:[{instrument_key:"NSE_EQ|123",trade_date:"2026-11-13",open:100,high:110,low:90,close:105,volume:100}]},null,2);
const secretKey = /^(?:access[_-]?token|refresh[_-]?token|api[_-]?key|api[_-]?secret|client[_-]?secret|authorization|password|bearer[_-]?token)$/i;
export function containsCredentialFields(value:unknown):boolean {
 if(Array.isArray(value)) return value.some(containsCredentialFields);
 if(value !== null && typeof value === "object") return Object.entries(value).some(([key, nested]) => secretKey.test(key) || containsCredentialFields(nested));
 return false;
}
export default function ProviderBatchPreflight(){
 const [input,setInput]=useState(example);const [report,setReport]=useState<Report|null>(null);
 const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 async function inspect(){
  setLoading(true);setError("");setReport(null);
  try{
   const response=await fetch("/intelligence/api/v1/intelligence/providers/batch-preflight",{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
   });
   if(!response.ok)throw Error("Invalid provider batch; check schema, OHLC bounds and dates");
   const payload:Report=await response.json();
   if(payload.status!=="BLOCKED"||payload.ingestion_authorized!==false||payload.dry_run!==true||!Array.isArray(payload.blockers))throw Error("Unexpected provider preflight response; treat ingestion as blocked");
   setReport(payload);
  }catch(e){setError(e instanceof Error?e.message:"Preflight unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Provider batch preflight">
  <div className="sectionhead"><div><small className="section-kicker">PROVIDER INGESTION · DRY RUN</small><h2>Validate a prospective market-data batch</h2></div><span className="tag">NO DATA WRITES</span></div>
  <p className="muted tiny">Test OHLCV source freshness, instrument mapping and entitlement declarations. Example data is synthetic, not a real market feed. Credential-like JSON keys are rejected before transmission; never paste API tokens or secrets.</p>
  <label htmlFor="provider-batch-json">Provider batch JSON</label><textarea id="provider-batch-json" rows={8} style={{width:"100%"}} value={input} onChange={e=>setInput(e.target.value)}/>
  <button className="secondary" disabled={loading} onClick={inspect}>{loading?"Validating…":"Run dry-run preflight"}</button>
  {error&&<p role="alert">{error}</p>}
  {report&&<div role="status"><p><strong>{report.status}</strong> · {report.records_examined} records · {report.instruments_examined} instruments · Latest {report.latest_trade_date}</p>
   <ul>{report.blockers.map(reason=><li key={reason}>{reason.replace(/_/g," ")}</li>)}</ul>
   <p className="muted tiny">{report.notice}</p>
  </div>}
 </section>;
}
