import React,{useState} from "react";
type Outcome={source_name:string;report_id:string;rating:string;published_on:string;horizon_end:string;observed_price_return_pct_unverified:string|null;blockers:string[]};
type Result={status:string;reports_reviewed:number;horizon_days:number;outcomes:Outcome[];notice:string};
export default function ResearchOutcomes(){
  const [instrument,setInstrument]=useState("");
  const [reports,setReports]=useState("[]");
  const [prices,setPrices]=useState("[]");
  const [days,setDays]=useState(90);
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function run(){
    setError("");setResult(null);
    let r:unknown,p:unknown;
    try{r=JSON.parse(reports);p=JSON.parse(prices);if(!Array.isArray(r)||!Array.isArray(p))throw Error("array");}
    catch{setError("Reports and prices must be JSON arrays.");return;}
    if(!instrument.trim()){setError("Enter an instrument identifier.");return;}
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/research/brokers/outcomes",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({instrument_id:instrument.trim(),reports:r,prices:p,horizon_days:days})});
      if(!response.ok)throw Error("Outcome review rejected. Check dates, instruments and price fields.");
      const value:Result=await response.json();
      if(value.status!=="HISTORICAL_OUTCOME_REVIEW_ONLY")throw Error("Unexpected response.");
      setResult(value);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">HISTORICAL RESEARCH · OUTCOME REVIEW</small><h2>Broker recommendation follow-through</h2></div><span className="tag">UNVERIFIED DATA</span></div>
    <p className="muted tiny">Compare supplied dated broker reports with supplied dated closing prices. Entry prices must be after publication and evaluation horizons must have elapsed. Returns are illustrative, not verified analyst accuracy.</p>
    <label htmlFor="outcome-instrument">Instrument identifier</label>
    <input id="outcome-instrument" aria-label="Outcome instrument identifier" value={instrument} onChange={e=>setInstrument(e.target.value)}/>
    <label htmlFor="outcome-horizon">Evaluation horizon (calendar days)</label>
    <input id="outcome-horizon" aria-label="Outcome horizon days" type="number" min={5} max={730} value={days} onChange={e=>setDays(Number(e.target.value))}/>
    <label htmlFor="outcome-reports">Research reports JSON</label>
    <textarea id="outcome-reports" aria-label="Outcome reports JSON" rows={3} value={reports} onChange={e=>setReports(e.target.value)}/>
    <label htmlFor="outcome-prices">Daily prices JSON</label>
    <textarea id="outcome-prices" aria-label="Outcome prices JSON" rows={3} value={prices} onChange={e=>setPrices(e.target.value)}/>
    <button className="primary" disabled={loading} onClick={run}>{loading?"Reviewing…":"Review historical outcomes"}</button>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<div role="status"><p className="muted tiny">Reports reviewed: {result.reports_reviewed} · Horizon: {result.horizon_days} calendar days</p>
      <div className="tablewrap"><table><thead><tr><th>BROKER</th><th>REPORT</th><th>RATING</th><th>PUBLICATION</th><th>UNVERIFIED RETURN</th><th>QUALITY FLAGS</th></tr></thead><tbody>
        {result.outcomes.map((r,i)=><tr key={r.report_id+":"+i}><td>{r.source_name}</td><td>{r.report_id}</td><td>{r.rating}</td><td>{r.published_on}</td><td>{r.observed_price_return_pct_unverified===null?"—":r.observed_price_return_pct_unverified+"%"}</td><td>{r.blockers.join(" · ").replace(/_/g," ")}</td></tr>)}
        {!result.outcomes.length&&<tr><td colSpan={6}>No reports supplied.</td></tr>}
      </tbody></table></div><p className="muted tiny">{result.notice}</p></div>}
  </section>;
}
