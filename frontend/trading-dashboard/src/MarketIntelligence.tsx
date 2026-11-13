import React,{useState} from "react";

type Row={id:number;symbol:string;exchange:string;as_of:string;close:number;change_1d_percent:number;momentum_20d_percent:number;relative_volume_20:number|null;rsi_14:number;trend:string;atr_percent_of_close:number;flags:string[]};
type Overview={status:string;universe_size:number;eligible_count:number;skipped:Record<string,number>;breadth:{advancing:number;declining:number;unchanged:number};top_gainers:Row[];top_losers:Row[];momentum_leaders:Row[];volume_leaders:Row[];anomaly_watch:Row[];notice:string};

export default function MarketIntelligence(){
  const [exchange,setExchange]=useState("");
  const [result,setResult]=useState<Overview|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function run(){
    setLoading(true);setError("");setResult(null);
    try{
      const params=new URLSearchParams({limit:"20",max_age_days:"7"});
      if(exchange)params.set("exchange",exchange);
      const response=await fetch("/intelligence/api/v1/intelligence/market/overview?"+params);
      if(!response.ok)throw Error("Market intelligence unavailable; no data substituted.");
      const payload:Overview=await response.json();
      if(payload.status!=="RESEARCH_ONLY")throw Error("Unexpected market intelligence response.");
      setResult(payload);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  function table(title:string,rows:Row[]){
    return <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">DAILY SAMPLE · VERIFIED LOCAL CANDLES</small><h2>{title}</h2></div></div>
      <div className="tablewrap"><table><thead><tr><th>SYMBOL</th><th>DATE</th><th>CLOSE</th><th>1D %</th><th>20D %</th><th>REL VOL</th><th>RSI</th><th>OBSERVATIONS</th></tr></thead><tbody>
        {rows.map(r=><tr key={r.exchange+":"+r.id}><td className="symbol">{r.exchange}:{r.symbol}</td><td>{r.as_of}</td><td>{r.close.toFixed(2)}</td><td>{r.change_1d_percent.toFixed(2)}%</td><td>{r.momentum_20d_percent.toFixed(2)}%</td><td>{r.relative_volume_20?.toFixed(2)??"—"}</td><td>{r.rsi_14.toFixed(2)}</td><td>{r.flags.length?r.flags.join(" · ").replace(/_/g," "):r.trend.replace(/_/g," ")}</td></tr>)}
        {!rows.length&&<tr><td colSpan={8} className="empty">No qualifying validated daily records.</td></tr>}
      </tbody></table></div></section>;
  }
  return <div>
    <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">ON-DEMAND · MARKET INTELLIGENCE</small><h2>Market overview</h2></div><span className="tag">RESEARCH ONLY</span></div>
      <p className="muted tiny">Sampled daily breadth, momentum, relative volume, and potential failed-breakout observations. At most 20 instruments per request; requires 50 daily candles and recent, consistent adjustments. Not live, exchange-wide, or a trade recommendation.</p>
      <div className="searchbar"><select aria-label="Market exchange" value={exchange} onChange={e=>setExchange(e.target.value)}><option value="">NSE + BSE</option><option>NSE</option><option>BSE</option></select><button className="primary" disabled={loading} onClick={run}>{loading?"Analyzing…":"Analyze daily market"}</button></div>
      {error&&<p role="alert" className="error">{error}</p>}
      {result&&<div role="status" className="muted tiny"><p>Eligible: {result.eligible_count}/{result.universe_size}. Advancing: {result.breadth.advancing} · Declining: {result.breadth.declining} · Unchanged: {result.breadth.unchanged}.</p><p>Excluded: {Object.entries(result.skipped).map(([k,v])=>k.replace(/_/g," ")+": "+v).join(" · ")}.</p><p>{result.notice}</p></div>}
    </section>
    {result&&<>{table("Top gainers in sample",result.top_gainers)}{table("Top decliners in sample",result.top_losers)}{table("Momentum leaders",result.momentum_leaders)}{table("Relative volume leaders",result.volume_leaders)}{table("Anomaly watch · heuristic candidates",result.anomaly_watch)}</>}
  </div>;
}
