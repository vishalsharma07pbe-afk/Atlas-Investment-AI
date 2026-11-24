import {useEffect,useState} from "react";
type Item={scheme_code:number;scheme_name:string;nav:number;nav_date:string;cagr_1y_percent:number;cagr_3y_percent:number;drawdown_3y_percent:number;observations:number;sources:string[]};
type Watch={category:string;status:string;universe_count:number;sample_count:number;eligible_count:number;items:Item[];automatic_collection_enabled:boolean;notice:string};
const pct=(x:number)=>x.toFixed(2)+"%";
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
 return <section className="panel glass fund-history-watch" aria-label="Automatic historical fund research">
  <div className="sectionhead"><div><small className="section-kicker">AUTOMATIC NAV RESEARCH</small><h3>Historical performance watch</h3><p className="muted tiny">Direct Growth plans in the selected AMFI category. Historical comparison, not a qualified recommendation.</p></div></div>
  {error?<p role="alert">Historical evidence unavailable.</p>:!current?<p role="status">Loading saved historical evidence…</p>:<>
   <p className="muted tiny">{current.eligible_count} eligible out of {current.sample_count} sampled · {current.universe_count} category matches</p>
   {current.items.length?<div className="horizon-cards">{current.items.map(item=><article className="horizon-card" key={item.scheme_code}><h3>{item.scheme_name}</h3><p className="muted tiny">Scheme {item.scheme_code} · NAV ₹{item.nav.toFixed(2)} · {item.nav_date}</p><dl><div><dt>1-year CAGR</dt><dd>{pct(item.cagr_1y_percent)}</dd></div><div><dt>3-year CAGR</dt><dd>{pct(item.cagr_3y_percent)}</dd></div><div><dt>3-year observed drawdown</dt><dd>{pct(item.drawdown_3y_percent)}</dd></div><div><dt>NAV observations</dt><dd>{item.observations}</dd></div></dl><p className="muted tiny">Sources: {item.sources.join(" · ")}</p></article>)}</div>:<p>{current.automatic_collection_enabled?"ATLAS is collecting dated NAV history automatically. No funds yet meet the history gate.":"Historical collection is disabled or data permissions are not confirmed. Existing evidence remains usable."}</p>}
   <p className="muted tiny">{current.notice}</p>
  </>}
 </section>;
}
