import {useEffect,useState} from "react";
type Item={scheme_code:number;scheme_name:string;nav:number;nav_date:string;cagr_1y_percent:number;cagr_3y_percent:number;drawdown_3y_percent:number;observations:number;sources:string[];weekly_volatility_percent?:number;worst_rolling_52w_annualized_percent?:number;positive_rolling_52w_percent?:number;rolling_windows?:number;return_to_drawdown?:number|null;sample_peer_percentile?:number};
type Watch={category:string;status:string;universe_count:number;sample_count:number;eligible_count:number;items:Item[];risk_adjusted_items?:Item[];comparison_date?:string|null;weekly_risk_eligible_count?:number;automatic_collection_enabled:boolean;notice:string};
const pct=(x:number|null|undefined)=>x==null?"—":x.toFixed(2)+"%";
export default function FundHistoricalWatch({category}:{category:string}){
 const [data,setData]=useState<Watch|null>(null),[error,setError]=useState(false);
 useEffect(()=>{let active=true,pending=false;const controller=new AbortController();setData(null);setError(false);
  async function load(){if(pending)return;pending=true;try{
    const r=await fetch("/api/v1/mutual-funds/historical-watch?category="+encodeURIComponent(category),{cache:"no-store",signal:controller.signal});
    if(!r.ok)throw Error();const body:Watch=await r.json();if(body.category!==category||!Array.isArray(body.items))throw Error();
    if(active){setData(body);setError(false);}
   }catch{if(active){setData(null);setError(true);}}finally{pending=false;}}
  void load();const timer=window.setInterval(load,60000);return()=>{active=false;controller.abort();window.clearInterval(timer);};
 },[category]);
 const current=data?.category===category?data:null;
 const [ranking,setRanking]=useState<"RETURN"|"RISK">("RETURN");
 const selected=ranking==="RISK"&&category!=="INDEX"?current?.risk_adjusted_items||[]:current?.items||[];
 return <section className="panel glass fund-history-watch" aria-label="Automatic historical fund research">
  <div className="sectionhead"><div><small className="section-kicker">AUTOMATIC NAV RESEARCH</small><h3>Historical performance watch</h3><p className="muted tiny">Direct Growth plans in the selected AMFI category. Historical comparison, not a qualified recommendation.</p></div></div>
  {error?<p role="alert">Historical evidence unavailable.</p>:!current?<p role="status">Loading saved historical evidence…</p>:<>
   <p className="muted tiny">{current.eligible_count} eligible out of {current.sample_count} sampled · {current.universe_count} category matches</p>
   {current.comparison_date&&<p className="muted tiny">Shared official NAV date: {current.comparison_date} · {current.weekly_risk_eligible_count??0} with usable weekly risk history</p>}
   {category!=="INDEX"&&<div role="group" aria-label="Historical ranking"><button type="button" className="secondary" aria-pressed={ranking==="RETURN"} onClick={()=>setRanking("RETURN")}>Trailing returns</button><button type="button" className="secondary" aria-pressed={ranking==="RISK"} onClick={()=>setRanking("RISK")}>Return versus drawdown</button></div>}
   {selected.length?<div className="horizon-cards">{selected.map(item=><article className="horizon-card" key={item.scheme_code}><h3>{item.scheme_name}</h3><p className="muted tiny">Scheme {item.scheme_code} · NAV ₹{item.nav.toFixed(2)} · {item.nav_date}</p><dl><div><dt>1-year CAGR</dt><dd>{pct(item.cagr_1y_percent)}</dd></div><div><dt>3-year CAGR</dt><dd>{pct(item.cagr_3y_percent)}</dd></div><div><dt>3-year observed drawdown</dt><dd>{pct(item.drawdown_3y_percent)}</dd></div><div><dt>NAV observations</dt><dd>{item.observations}</dd></div></dl><details><summary>Risk and consistency details</summary><dl><div><dt>Weekly annualized volatility proxy</dt><dd>{pct(item.weekly_volatility_percent)}</dd></div><div><dt>Worst rolling 52-week annualized return</dt><dd>{pct(item.worst_rolling_52w_annualized_percent)}</dd></div><div><dt>Positive rolling 52-week windows</dt><dd>{pct(item.positive_rolling_52w_percent)} ({item.rolling_windows??0} windows)</dd></div><div><dt>CAGR / observed drawdown</dt><dd>{item.return_to_drawdown==null?"—":item.return_to_drawdown.toFixed(2)+"×"}</dd></div><div><dt>Sample return percentile</dt><dd>{pct(item.sample_peer_percentile)}</dd></div></dl><p className="muted tiny">Weekly NAV anchors are approximate; overlapping rolling windows are not independent. Sample percentile is not a full-category rating. Missing metrics are not zero.</p></details><p className="muted tiny">Sources: {item.sources.join(" · ")}</p></article>)}</div>:<p>{ranking==="RISK"&&current.items.length?"No comparable funds meet the return-to-drawdown gate.":current.automatic_collection_enabled?"ATLAS is collecting dated NAV history automatically. No funds yet meet the history gate.":"Historical collection is disabled or data permissions are not confirmed. Existing evidence remains usable."}</p>}
   <p className="muted tiny">{current.notice}</p>
  </>}
 </section>;
}
