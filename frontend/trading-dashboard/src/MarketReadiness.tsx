import {useState} from "react";
type Report={status:"READY"|"BLOCKED";research_signals_enabled:boolean;blockers:string[];latest_source_date:string|null;source_age_calendar_days:number|null;instrument_count:number|null;candle_count:number|null;notice:string};
export default function MarketReadiness(){
  const [report,setReport]=useState<Report|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function check(){
    setLoading(true);setError("");setReport(null);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/market/readiness");
      if(!response.ok)throw Error("Readiness evaluation unavailable; treat market signals as blocked.");
      const payload:Report=await response.json();
      if(!["READY","BLOCKED"].includes(payload.status)||!Array.isArray(payload.blockers))throw Error("Invalid readiness response.");
      setReport(payload);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass" aria-label="Market data readiness">
    <div className="sectionhead"><div><small className="section-kicker">FAIL-CLOSED DATA QUALITY</small><h2>Market signal readiness gate</h2></div><span className="tag">READ ONLY</span></div>
    <p className="muted tiny">Checks backend-recorded coverage, unresolved quality events, source dates and verified live-feed status. A passing review is not trading authorization.</p>
    <button className="secondary" disabled={loading} onClick={check}>{loading?"Checking…":"Check market readiness"}</button>
    {error&&<p role="alert">{error}</p>}
    {report&&<div role="status"><p><strong>{report.status}</strong> · Research signals {report.research_signals_enabled?"eligible for further checks":"blocked"}</p>
      <p className="muted tiny">Instruments: {report.instrument_count??"unknown"} · Candles: {report.candle_count??"unknown"} · Latest source: {report.latest_source_date??"unknown"} · Age: {report.source_age_calendar_days??"unknown"} days</p>
      {report.blockers.length>0&&<ul>{report.blockers.map(reason=><li key={reason}>{reason.replace(/_/g," ")}</li>)}</ul>}
      <p className="muted tiny">{report.notice}</p>
    </div>}
  </section>;
}
