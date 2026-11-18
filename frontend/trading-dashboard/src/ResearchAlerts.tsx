import {useState} from "react";

type Alert={metric:string;threshold:number;observed:number;triggered:boolean;as_of:string};
type Result={status:string;failures:string[];alerts:Alert[];triggered_count?:number;notice:string};
const metrics=["CLOSE_ABOVE","CLOSE_BELOW","RSI_ABOVE","RSI_BELOW","RELATIVE_VOLUME_ABOVE"];

export default function ResearchAlerts({instrumentId}:{instrumentId:number}){
  const [metric,setMetric]=useState("CLOSE_ABOVE"),[threshold,setThreshold]=useState("100");
  const [result,setResult]=useState<Result|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
  async function evaluate(){
    setError("");setResult(null);
    const value=Number(threshold);
    if(!Number.isFinite(value)||value<=0||(metric.startsWith("RSI_")&&value>100)){
      setError("Enter a valid positive threshold (RSI maximum 100).");return;
    }
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/research-alerts/evaluate",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({instrument_id:instrumentId,rules:[{metric,threshold:value}],max_age_days:7})
      });
      if(!response.ok)throw Error("Alert evaluation unavailable or invalid.");
      setResult(await response.json());
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">ON-DEMAND RESEARCH ALERTS</small><h2>Daily threshold checks</h2></div><span className="tag">NO PUSH DELIVERY</span></div>
    <p className="muted tiny">Evaluate a threshold against the latest validated daily candle and indicators. Checks run only when clicked; they do not watch markets or send notifications.</p>
    <div className="searchbar"><select aria-label="Alert metric" value={metric} onChange={e=>setMetric(e.target.value)}>
      {metrics.map(m=><option key={m} value={m}>{m.replace(/_/g," ")}</option>)}
    </select><input aria-label="Alert threshold" type="number" min="0.01" step="any" value={threshold} onChange={e=>setThreshold(e.target.value)}/>
      <button className="primary" disabled={loading} onClick={evaluate}>{loading?"Evaluating…":"Evaluate alert"}</button>
    </div>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<div role="status">
      <p><strong>{result.status.replace(/_/g," ")}</strong></p>
      {result.failures.length>0&&<p>Blocked: {result.failures.join(", ").replace(/_/g," ")}</p>}
      {result.alerts.map((a,i)=><p key={i}>{a.metric.replace(/_/g," ")} {a.threshold}: observed {a.observed} on {a.as_of} — <strong>{a.triggered?"Threshold met":"Not met"}</strong></p>)}
      <p className="muted tiny">{result.notice}</p>
    </div>}
  </section>;
}
