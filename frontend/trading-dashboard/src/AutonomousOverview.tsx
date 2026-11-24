import {useEffect,useState,type ReactNode} from "react";

type Candidate={id:number;symbol:string;exchange:string;as_of:string;change_1d_percent:number;momentum_20d_percent:number|null};
type FundPick={fund:{identifier:string;name:string};score:number};
type Result={eligible_count?:number;universe_size?:number;top_gainers?:Candidate[];momentum_leaders?:Candidate[];top_performers?:FundPick[];growth_outlook?:FundPick[];coverage?:{name_matched_schemes:number};blockers?:string[];notice?:string};
type Snapshot={enabled:boolean;interval_seconds:number;sections:{section:string;status:string;generated_at:string|null;attempted_at:string|null;result:Result|null}[]};
const labels:Record<string,string>={NSE:"NSE",BSE:"BSE",LARGE_CAP:"Large cap",MID_CAP:"Mid cap",SMALL_CAP:"Small cap",FLEXI_CAP:"Flexi cap",INDEX:"Index funds"};
const percent=(value:number|null)=>value==null?"—":(value>0?"+":"")+value.toFixed(2)+"%";
const stamp=(value:string|null)=>value?new Date(value).toLocaleString("en-IN",{timeZone:"Asia/Kolkata",dateStyle:"medium",timeStyle:"short"})+" IST":"Not yet refreshed";
export default function AutonomousOverview({children,onPortfolio,onFunds,onSettings}:{children:ReactNode;onPortfolio:()=>void;onFunds:()=>void;onSettings:()=>void}){
 const [data,setData]=useState<Snapshot|null>(null);
 const [error,setError]=useState(false);
 const [manual,setManual]=useState(false);
 useEffect(()=>{
   let active=true;let pending=false;const controller=new AbortController();
   async function load(){
     if(pending)return;pending=true;
     try{const response=await fetch("/intelligence/api/v1/intelligence/research/overview",{cache:"no-store",signal:controller.signal});if(!response.ok)throw Error();const body:Snapshot=await response.json();if(!Array.isArray(body.sections))throw Error();if(active){setData(body);setError(false);}}
     catch{if(active)setError(true);}finally{pending=false;}
   }
   void load();const timer=window.setInterval(load,30000);
   return()=>{active=false;controller.abort();window.clearInterval(timer);};
 },[]);
 const market=data?.sections.filter(row=>row.section==="NSE"||row.section==="BSE")||[];
 const funds=data?.sections.filter(row=>row.section!=="NSE"&&row.section!=="BSE")||[];
 return <section className="autonomous-overview glass" aria-label="Automatic research overview">
   <header className="autonomous-header"><div><small className="section-kicker">YOUR DAILY INTELLIGENCE</small><h2>Research overview</h2><p>ATLAS checks available market history and fund evidence automatically. Review the results, not the data-entry tools.</p></div><span className="tag">{error?"SERVICE UNAVAILABLE":data?.enabled===false?"AUTOMATION OFF":data?"BACKGROUND RESEARCH":"LOADING"}</span></header>
   {error&&<p role="alert" className="notice warning-notice">Research service unavailable. Previously displayed observations may be outdated. <button type="button" className="secondary" onClick={onSettings}>Check connections</button></p>}
   {!data&&!error&&<p role="status">Loading the latest saved research…</p>}
   {data?.enabled===false&&<p className="notice warning-notice">Background research is disabled. Check the local configuration in Settings.</p>}
   <div className="autonomous-grid">
    <div className="autonomous-section"><h3>Market watch</h3><p className="muted">Daily-history observations, not trade signals.</p>
      {market.map(row=>{const ready=row.status==="READY"&&!error;const picks=(row.result?.momentum_leaders||[]).slice(0,5);return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?(row.result?.eligible_count||0)+" / "+(row.result?.universe_size||0)+" eligible":row.status.replaceAll("_"," ")}</span></header><small>{stamp(row.generated_at)}</small>{ready&&picks.length?<ul>{picks.map(item=><li key={item.id}><div><strong>{item.symbol}</strong><small>{item.as_of} · 20-day momentum</small></div><b>{percent(item.momentum_20d_percent)}</b></li>)}</ul>:<p>{ready?"No qualifying momentum observations in the current sample.":row.status==="FAILED"?"Refresh failed; awaiting the next attempt.":"Awaiting a current research snapshot."}</p>}</article>})}
    </div>
    <div className="autonomous-section"><h3>Mutual fund research</h3><p className="muted">Strict evidence-based qualification; no forced picks.</p>
      {funds.map(row=>{const ready=row.status==="READY"&&!error;const picks=row.result?.growth_outlook||[];return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?picks.length+" growth picks":row.status}</span></header>{ready&&picks.length?<ul>{picks.slice(0,5).map(item=><li key={item.fund.identifier}>{item.fund.name}</li>)}</ul>:<p>{ready?"No growth picks meet the verified evidence requirements.":row.status==="FAILED"?"Refresh failed; will retry.":"Research pending."}</p>}</article>})}
      <button type="button" className="secondary" onClick={onFunds}>View fund research</button>
    </div>
   </div>
   <div className="autonomous-footer"><button type="button" className="primary" onClick={onPortfolio}>Review my portfolio</button><button type="button" className="secondary" onClick={onSettings}>Data and connections</button><button type="button" className="secondary" aria-expanded={manual} onClick={()=>setManual(!manual)}>{manual?"Hide research tools":"Open research tools"}</button></div>
   {manual&&children}
 </section>;
}
