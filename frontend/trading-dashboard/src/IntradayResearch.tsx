import {useEffect,useState} from "react";
type Item={id:number;symbol:string;exchange:string;pattern:string;bar_end:string;close:number;vwap_proxy:number;relative_volume:number;session_change_percent:number;mean_bar_range_percent:number;prior_session_high_so_far:number;bar_count:number};
type Result={status:string;generated_at:string;open_exchanges:string[];examined:number;eligible:number;candidates:Item[];warnings:Item[];notice:string};
const pct=(n:number)=>n.toFixed(2)+"%";
export default function IntradayResearch(){
 const [data,setData]=useState<Result|null>(null),[error,setError]=useState(false);
 useEffect(()=>{let active=true,pending=false;const controller=new AbortController();
  async function load(){if(pending)return;pending=true;try{const response=await fetch("/api/v1/market-data/intraday-research",{cache:"no-store",signal:controller.signal});if(!response.ok)throw Error();const result:Result=await response.json();if(!Array.isArray(result.candidates)||!Array.isArray(result.warnings))throw Error();if(active){setData(result);setError(false);}}catch{if(active){setData(null);setError(true);}}finally{pending=false;}}
  void load();const timer=window.setInterval(load,30000);return()=>{active=false;controller.abort();window.clearInterval(timer);};
 },[]);
 function card(item:Item){return <article className="horizon-card" key={item.exchange+":"+item.id}><h3>{item.symbol} · {item.exchange}</h3><p className="muted tiny">Completed bar: {new Date(item.bar_end).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST</p><dl><div><dt>Close</dt><dd>₹{item.close.toFixed(2)}</dd></div><div><dt>Session VWAP proxy</dt><dd>₹{item.vwap_proxy.toFixed(2)}</dd></div><div><dt>Latest / prior bar volume</dt><dd>{item.relative_volume.toFixed(2)}×</dd></div><div><dt>Session price change</dt><dd>{pct(item.session_change_percent)}</dd></div><div><dt>Mean bar range</dt><dd>{pct(item.mean_bar_range_percent)}</dd></div><div><dt>Completed bars</dt><dd>{item.bar_count}</dd></div></dl></article>;}
 return <section className="panel glass" aria-label="Current-session intraday research"><div className="sectionhead"><div><h3>Current-session research</h3><p className="muted tiny">Completed 15-minute candles · bounded sample · not trade signals</p></div></div>
 {error?<p role="alert">Intraday evidence unavailable; fresh intraday bars required.</p>:!data?<p role="status">Loading current-session observations…</p>:<>
 <p>{data.status==="NOT_AUTHORIZED"?"Authorized intraday collection is not enabled.":data.status==="SESSION_CLOSED_OR_UNVERIFIED"?"Market session closed or not verified.":data.eligible+" eligible of "+data.examined+" observed instruments."}</p>
 <h4>Volume-confirmed breakout watches</h4>
 {data.candidates.length?<div className="horizon-cards">{data.candidates.map(card)}</div>:<p>No qualifying observations.</p>}
 <h4>Possible failed breakouts</h4>
 {data.warnings.length?<div className="horizon-cards">{data.warnings.map(card)}</div>:<p>No qualifying failed-breakout observations.</p>}
 <p className="muted tiny">{data.notice}</p>
 </>}
 </section>;
}
