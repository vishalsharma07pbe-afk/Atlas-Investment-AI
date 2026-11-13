import React,{useState} from "react";

type Row={id:number;symbol:string;exchange:string;as_of:string;close:number;change_1d_percent:number;momentum_20d_percent:number|null;relative_volume_20:number|null;rsi_14:number|null};
type Result={universe_size:number;eligible_count:number;skipped:Record<string,number>;top_gainers:Row[];top_losers:Row[];momentum_leaders:Row[];notice:string};

export default function DailyScreener(){
  const [exchange,setExchange]=useState("");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function run(){
    setLoading(true);setError("");setResult(null);
    try{
      const params=new URLSearchParams({limit:"20",max_age_days:"7"});
      if(exchange)params.set("exchange",exchange);
      const response=await fetch("/intelligence/api/v1/intelligence/screener/daily?"+params);
      if(!response.ok)throw Error("Daily screener is unavailable.");
      setResult(await response.json());
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  function table(title:string,rows:Row[]){
    return <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">DAILY OBSERVATIONS</small><h2>{title}</h2></div></div>
      <div className="tablewrap"><table><thead><tr><th>SYMBOL</th><th>DATE</th><th>CLOSE</th><th>1D %</th><th>20D %</th><th>REL VOL</th><th>RSI</th></tr></thead><tbody>
        {rows.map(r=><tr key={r.id}><td className="symbol">{r.exchange}:{r.symbol}</td><td>{r.as_of}</td><td>{r.close.toFixed(2)}</td><td>{r.change_1d_percent.toFixed(2)}%</td><td>{r.momentum_20d_percent?.toFixed(2)??"—"}</td><td>{r.relative_volume_20?.toFixed(2)??"—"}</td><td>{r.rsi_14?.toFixed(2)??"—"}</td></tr>)}
        {!rows.length&&<tr><td colSpan={7} className="empty">No qualifying validated daily records.</td></tr>}
      </tbody></table></div></section>;
  }
  return <div>
    <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">ON-DEMAND · VALIDATED DAILY DATA</small><h2>Market screener</h2></div><span className="tag">RESEARCH ONLY</span></div>
      <p className="muted tiny">Screens at most 20 registry instruments per request. Data older than seven calendar days, insufficient histories and mixed corporate-action adjustments are excluded. Not live or a whole-market ranking.</p>
      <div className="searchbar"><select aria-label="Screener exchange" value={exchange} onChange={e=>setExchange(e.target.value)}><option value="">NSE + BSE</option><option>NSE</option><option>BSE</option></select><button className="primary" disabled={loading} onClick={run}>{loading?"Screening…":"Run daily screener"}</button></div>
      {error&&<p role="alert" className="error">{error}</p>}
      {result&&<p role="status" className="muted tiny">Eligible: {result.eligible_count} of {result.universe_size} sampled instruments. Excluded: {Object.entries(result.skipped).map(([k,v])=>k.replace(/_/g," ")+": "+v).join(" · ")}. {result.notice}</p>}
    </section>
    {result&&<>{table("Top daily gainers in sample",result.top_gainers)}{table("Top daily decliners in sample",result.top_losers)}{table("20-day momentum leaders in sample",result.momentum_leaders)}</>}
  </div>;
}
