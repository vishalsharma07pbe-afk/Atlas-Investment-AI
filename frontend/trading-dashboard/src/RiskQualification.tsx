import {useState} from "react";

type Result={status:string;failures:string[];as_of?:string;observations?:{
  trend:string;rsi_14:number;atr_percent_of_close:number;relative_volume_20:number;warnings:string[];
};notice:string};

export default function RiskQualification({instrumentId}:{instrumentId:number}){
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function run(){
    setLoading(true);setResult(null);setError("");
    try{
      const response=await fetch(`/intelligence/api/v1/intelligence/risk-qualification/${instrumentId}`);
      if(!response.ok)throw Error("Risk qualification service unavailable.");
      setResult(await response.json());
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">STRICT EVIDENCE GATES</small><h2>Research risk qualification</h2></div><span className="tag">NO TRADE SIGNALS</span></div>
    <p className="muted tiny">Checks historical data freshness, completeness and consistency, then displays technical risk observations. Passing these checks does not qualify a trade.</p>
    <button className="primary" disabled={loading} onClick={run}>{loading?"Checking…":"Run risk checks"}</button>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<div role="status">
      <p><strong>{result.status.replace(/_/g," ")}</strong>{result.as_of?" · "+result.as_of:""}</p>
      {result.failures.length>0&&<p className="notice">Blocked: {result.failures.join(", ").replace(/_/g," ")}</p>}
      {result.observations?.trend&&<div className="research-grid">
        <div><span>Trend</span><strong>{result.observations.trend.replace(/_/g," ")}</strong></div>
        <div><span>RSI 14</span><strong>{result.observations.rsi_14}</strong></div>
        <div><span>ATR % of close</span><strong>{result.observations.atr_percent_of_close}%</strong></div>
        <div><span>Relative volume</span><strong>{result.observations.relative_volume_20}</strong></div>
      </div>}
      {result.observations?.warnings?.length?<p className="notice">Risk observations: {result.observations.warnings.join(", ").replace(/_/g," ")}</p>:null}
      <p className="muted tiny">{result.notice}</p>
    </div>}
  </section>;
}
