import {visiblePolling} from "./visiblePolling";
import {useEffect,useState,type ReactNode} from "react";
import AutomaticInstitutionalActivity,{type InstitutionalActivity} from "./AutomaticInstitutionalActivity";
import {RecentCompanyNews,type Article} from "./AutomaticCompanyNews";

type Candidate={id:number;symbol:string;exchange:string;as_of:string;change_1d_percent:number;momentum_20d_percent:number|null};
type FundPick={fund:{identifier:string;name:string};score:number};
type HistoricalFund={scheme_code:number;scheme_name:string;cagr_3y_percent:number;nav_date:string};
type Horizon="SWING"|"SHORT_TERM"|"LONG_TERM";
type Result={horizons?:Partial<Record<Horizon,{status:string;candidates:{id:number;symbol:string;exchange:string;as_of:string}[]}>>;historical_coverage?:{items?:HistoricalFund[]};eligible_count?:number;universe_size?:number;top_gainers?:Candidate[];momentum_leaders?:Candidate[];top_performers?:FundPick[];growth_outlook?:FundPick[];coverage?:{name_matched_schemes:number};blockers?:string[];notice?:string};
type Briefing={status:string;ready_sections:number;total_sections:number;market:{eligible_histories:number;sampled_instruments:number;outlook_status:string};horizons:Partial<Record<Horizon,{displayed_watch_count:number;ai_reviewed_count:number;conflicting_evidence_count:number;qualified_count:number|null}>>;funds:{growth_pick_count:number|null;historical_watch_count:number;ready_categories:number;total_categories:number};institutional:{status:string;latest_date?:string;fii_direction?:string;dii_direction?:string};leading_evidence_gaps:{code:string;watch_count:number}[];notice:string};
type Snapshot={daily_briefing?:Briefing;recent_company_news?:Article[];institutional_activity?:InstitutionalActivity;enabled:boolean;interval_seconds:number;sections:{section:string;status:string;generated_at:string|null;attempted_at:string|null;result:Result|null}[]};
const labels:Record<string,string>={NSE:"NSE",BSE:"BSE",LARGE_CAP:"Large cap",MID_CAP:"Mid cap",SMALL_CAP:"Small cap",FLEXI_CAP:"Flexi cap",INDEX:"Index funds",LARGE_MID_CAP:"Large & mid cap",MULTI_CAP:"Multi cap",AGGRESSIVE_HYBRID:"Aggressive hybrid",CORPORATE_BOND:"Corporate bond",SHORT_DURATION:"Short duration"};
const percent=(value:number|null)=>value==null?"—":(value>0?"+":"")+value.toFixed(2)+"%";
const stamp=(value:string|null)=>value?new Date(value).toLocaleString("en-IN",{timeZone:"Asia/Kolkata",dateStyle:"medium",timeStyle:"short"})+" IST":"Not yet refreshed";
export default function AutonomousOverview({children,onPortfolio,onFunds,onSettings,onHorizon}:{children:ReactNode;onPortfolio:()=>void;onFunds:()=>void;onSettings:()=>void;onHorizon?:(horizon:Horizon)=>void}){
 const [data,setData]=useState<Snapshot|null>(null);
 const [error,setError]=useState(false);
 const [manual,setManual]=useState(false);
 useEffect(()=>visiblePolling(async signal=>{
  try{
   const response=await fetch("/intelligence/api/v1/intelligence/research/overview",{cache:"no-store",signal});
   if(!response.ok)throw Error();
   const body:Snapshot=await response.json();if(!Array.isArray(body.sections))throw Error();
   if(!signal.aborted){setData(body);setError(false);}
  }catch{if(!signal.aborted)setError(true);}
 },30000),[]);
 const market=data?.sections.filter(row=>row.section==="NSE"||row.section==="BSE")||[];
 const funds=data?.sections.filter(row=>row.section!=="NSE"&&row.section!=="BSE")||[];
 const current=!!data?.enabled&&!error;
 const readyMarkets=current?market.filter(row=>row.status==="READY"):[];
 const horizonLinks:{id:Horizon;title:string}[]=[{id:"SWING",title:"Swing"},{id:"SHORT_TERM",title:"Short term"},{id:"LONG_TERM",title:"Long term"}];
 return <section className="autonomous-overview glass" aria-label="Automatic research overview">
   <header className="autonomous-header"><div><small className="section-kicker">YOUR DAILY INTELLIGENCE</small><h2>Research overview</h2><p>ATLAS checks available market history and fund evidence automatically. Review the results, not the data-entry tools.</p></div><span className="tag">{error?"SERVICE UNAVAILABLE":data?.enabled===false?"AUTOMATION OFF":data?"BACKGROUND RESEARCH":"LOADING"}</span></header>
   {error&&<p role="alert" className="notice warning-notice">Research service unavailable. Previously displayed observations may be outdated. <button type="button" className="secondary" onClick={onSettings}>Check connections</button></p>}
   {!data&&!error&&<p role="status">Loading the latest saved research…</p>}
   {data?.enabled===false&&<p className="notice warning-notice">Background research is disabled. Check the local configuration in Settings.</p>}
   {current&&data?.daily_briefing&&<DailyBriefing report={data.daily_briefing} onFunds={onFunds} onSettings={onSettings}/>}
   {onHorizon&&<div className="research-shortcuts" aria-label="Automatic equity research shortcuts">{horizonLinks.map(({id,title})=>{const groups=readyMarkets.flatMap(row=>row.result?.horizons?.[id]?[row.result.horizons[id]!]:[]);const count=groups.reduce((n,group)=>n+(group.status==="TECHNICAL_WATCH_ONLY"?group.candidates.length:0),0);return <button key={id} type="button" className="research-shortcut" onClick={()=>onHorizon(id)}><strong>{title}</strong><span>{groups.length?`${count} technical watches`:"Current research pending"}</span><small>Open research →</small></button>;})}</div>}
   <div className="autonomous-grid">
    <div className="autonomous-section"><h3>Market watch</h3><p className="muted">Daily-history observations, not trade signals.</p>
      {market.map(row=>{const ready=row.status==="READY"&&!error&&data?.enabled===true;const picks=(row.result?.momentum_leaders||[]).slice(0,3);return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?(row.result?.eligible_count||0)+" / "+(row.result?.universe_size||0)+" eligible":!current?"UNAVAILABLE":row.status.replace(/_/g," ")}</span></header><small>{stamp(row.generated_at)}</small>{ready&&picks.length?<ul>{picks.map(item=><li key={item.id}><div><strong>{item.symbol}</strong><small>{item.as_of} · 20-day momentum</small></div><b>{percent(item.momentum_20d_percent)}</b></li>)}</ul>:<p>{ready?"No qualifying momentum observations in the current sample.":row.status==="FAILED"?"Refresh failed; awaiting the next attempt.":"Awaiting a current research snapshot."}</p>}</article>})}
    </div>
    <div className="autonomous-section"><h3>Mutual fund research</h3><p className="muted">Strict evidence-based qualification; no forced picks.</p>
      {funds.map(row=>{const ready=row.status==="READY"&&!error&&data?.enabled===true;const picks=row.result?.growth_outlook||[];const history=row.result?.historical_coverage?.items||[];return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?picks.length+" growth picks":!current?"UNAVAILABLE":row.status}</span></header>{ready&&picks.length?<ul>{picks.slice(0,5).map(item=><li key={item.fund.identifier}>{item.fund.name}</li>)}</ul>:<p>{ready?"No growth picks meet the verified evidence requirements.":row.status==="FAILED"?"Refresh failed; will retry.":"Research pending."}</p>}{ready&&history.length>0&&<><p className="muted tiny">Historical watch only</p><ul>{history.slice(0,2).map(item=><li key={item.scheme_code}><div><strong>{item.scheme_name}</strong><small>{item.nav_date} · 3-year CAGR</small></div><b>{percent(item.cagr_3y_percent)}</b></li>)}</ul></>}</article>})}
      <button type="button" className="secondary" onClick={onFunds}>View fund research</button>
    </div>
   </div>
   {current&&(data?.institutional_activity||!!data?.recent_company_news?.length)&&<details className="overview-market-context"><summary>Institutional activity &amp; company news</summary>{data?.institutional_activity&&<AutomaticInstitutionalActivity data={data.institutional_activity}/>}
    {!!data?.recent_company_news?.length&&<RecentCompanyNews articles={data.recent_company_news}/>}</details>}
   <div className="autonomous-footer"><button type="button" className="primary" onClick={onPortfolio}>Review my portfolio</button><button type="button" className="secondary" onClick={onSettings}>Data and connections</button><button type="button" className="secondary" aria-expanded={manual} onClick={()=>setManual(!manual)}>{manual?"Hide research tools":"Open research tools"}</button></div>
   {manual&&children}
 </section>;
}

function DailyBriefing({report,onFunds,onSettings}:{report:Briefing;onFunds:()=>void;onSettings:()=>void}){
 const watches=Object.values(report.horizons).reduce((n,h)=>n+(h?.displayed_watch_count??0),0);
 const reviewed=Object.values(report.horizons).reduce((n,h)=>n+(h?.ai_reviewed_count??0),0);
 const conflicts=Object.values(report.horizons).reduce((n,h)=>n+(h?.conflicting_evidence_count??0),0);
 const words=(value:string)=>value.toLowerCase().replace(/_/g," ");
 return <section className="autonomous-result" aria-label="Daily research briefing">
  <header><strong>Daily research briefing</strong><span>{report.ready_sections}/{report.total_sections} sections current</span></header>
  <p>{report.ready_sections===0?"Research is pending. No current decision evidence yet.":report.market.eligible_histories+" / "+report.market.sampled_instruments+" sampled daily histories eligible. Market regime not yet validated."}</p>
  <p><strong>Equity:</strong> {watches} displayed horizon watches · {reviewed} with AI commentary · {conflicts} with conflicting evidence. Full investment qualification is not available yet.</p>
  <p><strong>Funds:</strong> {report.funds.growth_pick_count===null?"Research pending":report.funds.growth_pick_count+" growth picks in current categories"} · {report.funds.historical_watch_count} historical watch observations. <button className="secondary" type="button" onClick={onFunds}>Review funds</button></p>
  {report.institutional.status==="RECENT_PAIRED_OBSERVATIONS"?<p><strong>Institutional:</strong> FII {words(report.institutional.fii_direction||"UNKNOWN")}; DII {words(report.institutional.dii_direction||"UNKNOWN")} over five reported dates through {report.institutional.latest_date}. Not a directional forecast.</p>:<p>Comparable recent institutional flows unavailable.</p>}
  {report.leading_evidence_gaps.length>0&&<details><summary>Why research remains watch-only</summary><ul>{report.leading_evidence_gaps.map(g=><li key={g.code}>{words(g.code)} · {g.watch_count} watch observations</li>)}</ul><button type="button" className="secondary" onClick={onSettings}>Review data coverage</button></details>}
  <small>{report.notice}</small>
 </section>;
}
