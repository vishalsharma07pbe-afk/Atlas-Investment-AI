import {useEffect,useState} from "react";
type Item={symbol:string;exchange:string;observed_date:string;published_at:string;maturity_date:string;status:string;outcome:{entry_date:string;exit_date:string;observed_price_return_pct:number;source_code:string;evidence_version?:string;calendar_status?:string;corporate_action_status?:string;observations?:number}|null};
type Result={horizon:string;counts:Record<string,number>;items:Item[];notice:string};
export default function WatchOutcomeHistory({horizon}:{horizon:"SWING"|"SHORT_TERM"|"LONG_TERM"}){
 const [data,setData]=useState<Result|null>(null),[error,setError]=useState(false);
 useEffect(()=>{
  let active=true,pending=false;const controller=new AbortController();setData(null);setError(false);
  async function load(){if(pending)return;pending=true;try{const r=await fetch("/intelligence/api/v1/intelligence/research/watch-outcomes?horizon="+horizon,{cache:"no-store",signal:controller.signal});if(!r.ok)throw Error();const body:Result=await r.json();if(body.horizon!==horizon||!Array.isArray(body.items))throw Error();if(active){setData(body);setError(false);}}catch{if(active){setData(null);setError(true);}}finally{pending=false;}}
  void load();const timer=window.setInterval(load,60000);return()=>{active=false;controller.abort();window.clearInterval(timer);};
 },[horizon]);
 return <section className="panel glass" aria-label="Automatic watch outcome history"><div className="sectionhead"><div><small className="section-kicker">CONTINUOUS EVALUATION</small><h3>Research history and observed outcomes</h3></div></div>
 {error?<p role="alert">Research history unavailable.</p>:!data?<p role="status">Loading watch history…</p>:<><p className="muted tiny">{Object.entries(data.counts).map(([status,n])=>n+" "+status.toLowerCase().replace(/_/g," ")).join(" · ")||"No published observations yet."}</p>
 {data.items.length>0&&<div className="tablewrap"><table><thead><tr><th>Stock</th><th>Observed</th><th>Review date</th><th>Status</th><th>Observed change</th></tr></thead><tbody>{data.items.map(item=><tr key={item.exchange+":"+item.symbol+":"+item.observed_date}><td>{item.exchange}:{item.symbol}</td><td>{item.observed_date}</td><td>{item.maturity_date}</td><td>{item.status.replace(/_/g," ")}</td><td>{item.outcome?<>{item.outcome.observed_price_return_pct.toFixed(2)+"% · "+item.outcome.entry_date+" – "+item.outcome.exit_date+" · "+item.outcome.source_code}<small className="muted">{item.outcome.evidence_version==="WATCH-SESSION-EVIDENCE-2"&&item.outcome.calendar_status==="STORED_SESSIONS_MATCHED"&&item.outcome.corporate_action_status==="NO_RECORDED_CROSSING_ACTION"?" · Stored sessions matched ("+item.outcome.observations+" observations); no recorded crossing action":" · Legacy evidence — excluded from current reliability metrics"}</small></>:"—"}</td></tr>)}</tbody></table></div>}
 <p className="muted tiny">{data.notice}</p></>}
 </section>;
}
