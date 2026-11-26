import {visiblePolling} from "./visiblePolling";
import "./overview.css";
import {useEffect,useState,type ReactNode} from "react";
import AutomaticInstitutionalActivity,{type InstitutionalActivity} from "./AutomaticInstitutionalActivity";
import {RecentCompanyNews,type Article} from "./AutomaticCompanyNews";

type Candidate={id:number;symbol:string;exchange:string;as_of:string;change_1d_percent:number;momentum_20d_percent:number|null};
type FundPick={fund:{identifier:string;name:string};score:number};
type HistoricalFund={scheme_code:number;scheme_name:string;cagr_3y_percent:number;nav_date:string};
type Horizon="SWING"|"SHORT_TERM"|"LONG_TERM";
type Result={horizons?:Partial<Record<Horizon,{status:string;candidates:{id:number;symbol:string;exchange:string;as_of:string}[]}>>;historical_coverage?:{items?:HistoricalFund[]};eligible_count?:number;universe_size?:number;top_gainers?:Candidate[];momentum_leaders?:Candidate[];top_performers?:FundPick[];growth_outlook?:FundPick[];coverage?:{name_matched_schemes:number};blockers?:string[];notice?:string};
type DecisionWatch={isin:string;exchange:string;id:number;symbol:string;as_of:string;horizon:Horizon;review_findings:string[];unresolved_requirement_count:number};
type DecisionContext={horizons:Partial<Record<Horizon,{selected_watches:DecisionWatch[];qualified_count:number|null;status:string}>>;review_company_count:number;review_companies:{isin:string;symbol:string;horizons:Horizon[];findings:string[];observations:{exchange:string;as_of:string}[]}[];regime:{status:string;as_of?:string;trend?:string;volatility_regime?:string;agreement?:string};global_coverage:{available_count:number;total_count:number}|null;notice:string};
type Briefing={decision_context?:DecisionContext;news_headline_count?:number;status:string;ready_sections:number;total_sections:number;market:{eligible_histories:number;sampled_instruments:number;outlook_status:string};horizons:Partial<Record<Horizon,{displayed_watch_count:number;ai_reviewed_count:number;conflicting_evidence_count:number;qualified_count:number|null}>>;funds:{growth_pick_count:number|null;historical_watch_count:number;ready_categories:number;total_categories:number};institutional:{status:string;latest_date?:string;fii_direction?:string;dii_direction?:string};leading_evidence_gaps:{code:string;watch_count:number}[];notice:string};
type FxItem={pair:string;status:string;as_of?:string;rate?:number;basis?:string;changes?:{observations:number;start_date:string;end_date:string;percent:number}[]};
type FxContext={status:string;retrieved_at?:string;items:FxItem[];notice:string};
type MacroSource={source:string;status:string;retrieved_at?:string;items:{series:string;label:string;unit:string;status:string;as_of:string|null;value:number|null;changes:{observations:number;start_date:string;end_date:string;value:number;unit:string}[]}[]};
type MacroContext={status:string;sources:MacroSource[];notice:string};
type GlobalMarketContext={status:string;notice:string;items:{series:string;label:string;source:string;unit:string;status:string;as_of?:string|null;value?:number|null;changes:{observations:number;start_date:string;end_date:string;percent:number}[]}[]};
type GlobalContext={status:string;available_count:number;total_count:number;groups:{group:string;available_count:number;total_count:number;items:{key:string;label:string;source:string;as_of:string;change:{start_date:string;end_date:string;value:number;unit:string}|null}[]}[];notice:string};
type GlobalReleaseContext={status:string;sources:{source:string;label:string;status:string;retrieved_at?:string;event_count?:number}[];events:{id:string;headline:string;source_name:string;source_url:string;published_at:string;topics:string[];geography:string}[];notice:string};
type ReleaseMatch={status:string;headline?:string;source_url?:string;published_at?:string;notice:string};
type EconomicCalendar={status:string;source_url:string;retrieved_at?:string;events:{id:string;headline:string;topic:string;scheduled_at:string;status:string;review_window:boolean;release_match?:ReleaseMatch}[];notice:string};
type RegimeReport={status:string;trend?:string;volatility_regime?:string;as_of?:string;benchmark_change_60_percent?:number;volatility_20_annualized_percent?:number;breadth?:{status:string;advancing?:number;declining?:number;unchanged?:number;matched_count?:number;selected_count?:number;direction?:string};agreement?:string;institutional?:{status:string;fii?:string;dii?:string};global_coverage?:{available_count:number;total_count:number};notice:string};
type Snapshot={market_regime?:RegimeReport;economic_calendar?:EconomicCalendar;global_releases?:GlobalReleaseContext;global_context?:GlobalContext;global_markets?:GlobalMarketContext;global_macro?:MacroContext;global_fx?:FxContext;daily_briefing?:Briefing;recent_company_news?:Article[];institutional_activity?:InstitutionalActivity;enabled:boolean;interval_seconds:number;sections:{section:string;status:string;generated_at:string|null;attempted_at:string|null;result:Result|null}[]};
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
 const briefing=current?data?.daily_briefing:undefined;
 const compact=!!briefing;
 const hasEvents=!!(data?.economic_calendar||data?.global_releases);
 const hasGlobal=!!(data?.market_regime||data?.global_context||data?.global_fx||data?.global_macro||data?.global_markets);
 const horizonLinks:{id:Horizon;title:string}[]=[{id:"SWING",title:"Swing"},{id:"SHORT_TERM",title:"Short term"},{id:"LONG_TERM",title:"Long term"}];
 return <section className="autonomous-overview glass" aria-label="Automatic research overview">
   <header className="autonomous-header"><div><small className="section-kicker">YOUR DAILY INTELLIGENCE</small><h2>Research overview</h2><p>ATLAS checks available market history and fund evidence automatically. Review the results, not the data-entry tools.</p></div><span className="tag">{error?"SERVICE UNAVAILABLE":data?.enabled===false?"AUTOMATION OFF":data?"BACKGROUND RESEARCH":"LOADING"}</span></header>
   {error&&<p role="alert" className="notice warning-notice">Research service unavailable. Previously displayed observations may be outdated. <button type="button" className="secondary" onClick={onSettings}>Check connections</button></p>}
   {!data&&!error&&<p role="status">Loading the latest saved research…</p>}
   {data?.enabled===false&&<p className="notice warning-notice">Background research is disabled. Check the local configuration in Settings.</p>}
   {briefing&&<DailyBriefing report={briefing} onFunds={onFunds} onSettings={onSettings} onPortfolio={onPortfolio} onHorizon={onHorizon}/>}
   {onHorizon&&!briefing?.decision_context&&<div className="research-shortcuts" aria-label="Automatic equity research shortcuts">{horizonLinks.map(({id,title})=>{const groups=readyMarkets.flatMap(row=>row.result?.horizons?.[id]?[row.result.horizons[id]!]:[]);const count=groups.reduce((n,group)=>n+(group.status==="TECHNICAL_WATCH_ONLY"?group.candidates.length:0),0);return <button key={id} type="button" className="research-shortcut" onClick={()=>onHorizon(id)}><strong>{title}</strong><span>{groups.length?`${count} technical watches`:"Current research pending"}</span><small>Open research →</small></button>;})}</div>}
   <OverviewGroup compact={compact} title="Market and fund observation details" description="Momentum samples, all fund categories and their current evidence status">
   <div className="autonomous-grid">
    <div className="autonomous-section"><h3>Market watch</h3><p className="muted">Daily-history observations, not trade signals.</p>
      {market.map(row=>{const ready=row.status==="READY"&&!error&&data?.enabled===true;const picks=(row.result?.momentum_leaders||[]).slice(0,3);return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?(row.result?.eligible_count||0)+" / "+(row.result?.universe_size||0)+" eligible":!current?"UNAVAILABLE":row.status.replace(/_/g," ")}</span></header><small>{stamp(row.generated_at)}</small>{ready&&picks.length?<ul>{picks.map(item=><li key={item.id}><div><strong>{item.symbol}</strong><small>{item.as_of} · 20-day momentum</small></div><b>{percent(item.momentum_20d_percent)}</b></li>)}</ul>:<p>{ready?"No qualifying momentum observations in the current sample.":row.status==="FAILED"?"Refresh failed; awaiting the next attempt.":"Awaiting a current research snapshot."}</p>}</article>})}
    </div>
    <div className="autonomous-section"><h3>Mutual fund research</h3><p className="muted">Strict evidence-based qualification; no forced picks.</p>
      {funds.map(row=>{const ready=row.status==="READY"&&!error&&data?.enabled===true;const picks=row.result?.growth_outlook||[];const history=row.result?.historical_coverage?.items||[];return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?picks.length+" growth picks":!current?"UNAVAILABLE":row.status}</span></header>{ready&&picks.length?<ul>{picks.slice(0,5).map(item=><li key={item.fund.identifier}>{item.fund.name}</li>)}</ul>:<p>{ready?"No growth picks meet the verified evidence requirements.":row.status==="FAILED"?"Refresh failed; will retry.":"Research pending."}</p>}{ready&&history.length>0&&<><p className="muted tiny">Historical watch only</p><ul>{history.slice(0,2).map(item=><li key={item.scheme_code}><div><strong>{item.scheme_name}</strong><small>{item.nav_date} · 3-year CAGR</small></div><b>{percent(item.cagr_3y_percent)}</b></li>)}</ul></>}</article>})}
      <button type="button" className="secondary" onClick={onFunds}>View fund research</button>
    </div>
   </div>
   </OverviewGroup>
   {current&&hasEvents&&<OverviewGroup compact={compact} title="Economic events and announcements" description="Scheduled releases and separately published source-linked announcements">
    {data?.economic_calendar&&<EconomicCalendarPanel report={data.economic_calendar}/>}
    {data?.global_releases&&<GlobalReleasePanel report={data.global_releases}/>}
   </OverviewGroup>}
   {current&&hasGlobal&&<OverviewGroup compact={compact} title="Detailed market regime and global evidence" description="Benchmark trend, sample breadth, currencies, oil, yields, indices and metals">
    {data?.market_regime&&<MarketRegimePanel report={data.market_regime}/>}
    {data?.global_context&&<GlobalResearchSummary report={data.global_context}/>}
    {data?.global_fx&&<GlobalFxContext report={data.global_fx}/>}
    {data?.global_macro&&<GlobalMacroContext report={data.global_macro}/>}
    {data?.global_markets&&<GlobalMarketsContext report={data.global_markets}/>}
   </OverviewGroup>}
   {current&&(data?.institutional_activity||!!data?.recent_company_news?.length)&&<details className="overview-market-context"><summary>Institutional activity &amp; company news</summary>{data?.institutional_activity&&<AutomaticInstitutionalActivity data={data.institutional_activity}/>}
    {!!data?.recent_company_news?.length&&<RecentCompanyNews articles={data.recent_company_news}/>}</details>}
   <div className="autonomous-footer"><button type="button" className="primary" onClick={onPortfolio}>Review my portfolio</button><button type="button" className="secondary" onClick={onSettings}>Data and connections</button><button type="button" className="secondary" aria-expanded={manual} onClick={()=>setManual(!manual)}>{manual?"Hide research tools":"Open research tools"}</button></div>
   {manual&&children}
 </section>;
}

function OverviewGroup({compact,title,description,children}:{compact:boolean;title:string;description:string;children:ReactNode}){
 // Older snapshots without the briefing keep their existing expanded evidence.
 // Native disclosure state remains intact across ordinary polling updates.
 if(!compact)return <>{children}</>;
 return <details className="overview-evidence-group"><summary><span><strong>{title}</strong><small>{description}</small></span><span className="overview-disclosure-label" aria-hidden="true"/></summary><div className="overview-evidence-body">{children}</div></details>;
}

function DailyBriefing({report,onFunds,onSettings,onPortfolio,onHorizon}:{report:Briefing;onFunds:()=>void;onSettings:()=>void;onPortfolio:()=>void;onHorizon?:(horizon:Horizon)=>void}){
 const watches=Object.values(report.horizons).reduce((n,h)=>n+(h?.displayed_watch_count??0),0);
 const reviewed=Object.values(report.horizons).reduce((n,h)=>n+(h?.ai_reviewed_count??0),0);
 const conflicts=Object.values(report.horizons).reduce((n,h)=>n+(h?.conflicting_evidence_count??0),0);
 const words=(value:string)=>value.toLowerCase().replace(/_/g," ");
 return <section className="autonomous-result" aria-label="Daily research briefing">
  <header><strong>Daily research briefing</strong><span>{report.ready_sections}/{report.total_sections} sections current</span></header>
  <p>{report.ready_sections===0?"Research is pending. No current decision evidence yet.":report.market.eligible_histories+" / "+report.market.sampled_instruments+" sampled daily histories eligible. Market regime not yet validated for strategy suitability."}</p>
  <p><strong>Equity:</strong> {watches} displayed horizon watches · {reviewed} with AI commentary · {conflicts} with conflicting evidence. Full investment qualification is not available yet.</p>
  <p><strong>Funds:</strong> {report.funds.growth_pick_count===null?"Research pending":report.funds.growth_pick_count+" growth picks in current categories"} · {report.funds.historical_watch_count} historical watch observations. <button className="secondary" type="button" onClick={onFunds}>Review funds</button></p>
  {report.institutional.status==="RECENT_PAIRED_OBSERVATIONS"?<p><strong>Institutional:</strong> FII {words(report.institutional.fii_direction||"UNKNOWN")}; DII {words(report.institutional.dii_direction||"UNKNOWN")} over five reported dates through {report.institutional.latest_date}. Not a directional forecast.</p>:<p>Comparable recent institutional flows unavailable.</p>}
  {report.leading_evidence_gaps.length>0&&<details><summary>Why research remains watch-only</summary><ul>{report.leading_evidence_gaps.map(g=><li key={g.code}>{words(g.code)} · {g.watch_count} watch observations</li>)}</ul><button type="button" className="secondary" onClick={onSettings}>Review data coverage</button></details>}
  {report.decision_context&&<DecisionBriefing context={report.decision_context} newsCount={report.news_headline_count} onPortfolio={onPortfolio} onHorizon={onHorizon}/>}
  <small>{report.notice}</small>
 </section>;
}

function DecisionBriefing({context,newsCount,onPortfolio,onHorizon}:{context:DecisionContext;newsCount?:number;onPortfolio:()=>void;onHorizon?:(horizon:Horizon)=>void}){
 const words=(v:string)=>v.toLowerCase().replace(/_/g," ");
 const order:Horizon[]=["SWING","SHORT_TERM","LONG_TERM"];
 return <section aria-label="Today's evidence review">
  <h3>Today's evidence review</h3>
  <p>{context.regime.status==="OBSERVED_BENCHMARK_REGIME"?"Observed Nifty 50 trend: "+words(context.regime.trend||"UNAVAILABLE")+" · "+(context.regime.as_of||"date unavailable"):"Observed benchmark trend unavailable."} {context.regime.agreement==="OPPOSING_DAILY_BREADTH_REVIEW"&&"Daily sample breadth opposes the longer trend; review the differing horizons."} Not a forecast.</p>
  <p>{context.global_coverage?context.global_coverage.available_count+"/"+context.global_coverage.total_count+" dated global indicators":"Global indicator coverage unavailable"} · {newsCount===undefined?"Company headline coverage unavailable":newsCount+" returned company headlines"}; no absence-of-risk inference.</p>
  <div className="overview-review-heading"><h4>Companies requiring evidence review</h4><span>{context.review_company_count} distinct companies</span></div>
  <p>Among selected watches only; not a severity ranking.</p>
  {context.review_companies.map(item=><details className="overview-company-review" key={item.isin}><summary>{item.symbol} · {item.findings.length} findings · {item.horizons.map(words).join(", ")}</summary><p>{item.observations.map(o=>o.exchange+" "+o.as_of).join(" · ")}</p><ul>{item.findings.map(f=><li key={f}>{words(f)}</li>)}</ul></details>)}
  <h4>Selected technical watches by horizon</h4>
  <div className="overview-horizon-grid">{order.map(h=>{const result=context.horizons[h];return <article className="overview-horizon-card" key={h}><strong className="overview-horizon-title">{words(h)}</strong><p>{result?result.selected_watches.length+" selected watches · "+(result.qualified_count===null?"Qualification unavailable":result.qualified_count+" qualified in the reviewed sample"):"Current selection unavailable"}</p>{result?.selected_watches.length?<details><summary>View {result.selected_watches.length} selected observations</summary><ul>{result.selected_watches.map(w=><li key={w.isin}><div><strong>{w.symbol} · {w.exchange}</strong><small>{w.as_of} · {w.unresolved_requirement_count} unresolved requirements</small></div></li>)}</ul></details>:null}{onHorizon&&<button className="secondary" type="button" onClick={()=>onHorizon(h)}>Review {words(h)} research</button>}</article>;})}</div>
  <div className="overview-private-review"><p><strong>Private portfolio:</strong> open the owner-scoped Portfolio Doctor for holding-specific risks and changes.</p><button className="secondary" type="button" onClick={onPortfolio}>Open private portfolio review</button></div>
  <small>{context.notice}</small>
 </section>;
}

function GlobalFxContext({report}:{report:FxContext}){
 return <section className="autonomous-result" aria-label="Global currency context"><header><strong>Global currency context</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 <p className="muted tiny">European Central Bank · daily reference rates, not live quotes. {report.retrieved_at&&"Retrieved "+stamp(report.retrieved_at)}</p>
 {report.items.length?<div className="tablewrap"><table><thead><tr><th>Pair</th><th>Reference date</th><th>Quote per base unit</th><th>1 / 5 / 20 observed-date changes</th></tr></thead><tbody>{report.items.map(item=><tr key={item.pair}><td>{item.pair.replace("_","/")}<small> · {item.basis==="DERIVED_ECB_CROSS"?"ATLAS cross-rate":"ECB reference"}</small></td><td>{item.as_of??"Unavailable"}</td><td>{item.rate?.toFixed(4)??"Unavailable"}</td><td>{[1,5,20].map(n=>{const found=item.changes?.find(c=>c.observations===n);return found?percent(found.percent):"—";}).join(" / ")}</td></tr>)}</tbody></table></div>:<p>Currency reference evidence unavailable or not enabled.</p>}
 <p className="muted tiny">{report.notice}</p></section>;
}

function GlobalMacroContext({report}:{report:MacroContext}){
 return <section className="autonomous-result" aria-label="Global oil and interest-rate context"><header><strong>Global oil and interest-rate context</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 {report.sources.map(source=><div key={source.source}><p><strong>{source.source}</strong> · {source.status.toLowerCase().replace(/_/g," ")} {source.retrieved_at&&" · "+stamp(source.retrieved_at)}</p>{source.items.length>0&&<div className="tablewrap"><table><thead><tr><th>Indicator</th><th>Observation date</th><th>Value</th><th>1 / 5 / 20 observed-date changes</th></tr></thead><tbody>{source.items.map(item=><tr key={item.series}><td>{item.label}</td><td>{item.as_of??"Unavailable"}</td><td>{item.value==null?"Unavailable":item.value.toFixed(2)+(item.unit==="PERCENT"?"%":" USD/bbl")}</td><td>{[1,5,20].map(n=>{const v=item.changes.find(x=>x.observations===n);return v?(v.value>0?"+":"")+v.value.toFixed(2)+(v.unit==="BASIS_POINTS"?" bp":"%"):"—";}).join(" / ")}</td></tr>)}</tbody></table></div>}</div>)}
 <p className="muted tiny">{report.notice}</p></section>;
}

function GlobalMarketsContext({report}:{report:GlobalMarketContext}){
 return <section className="autonomous-result" aria-label="International indices and metals"><header><strong>International indices and metals</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 {report.items.length?<div className="tablewrap"><table><thead><tr><th>Indicator / source</th><th>Reference date</th><th>Value</th><th>1 / 5 / 20 observed-date changes</th></tr></thead><tbody>{report.items.map(item=><tr key={item.series}><td>{item.label}<small> · {item.source}</small></td><td>{item.as_of??"Unavailable"}</td><td>{item.value==null?item.status.toLowerCase().replace(/_/g," "):item.value.toLocaleString("en-IN",{maximumFractionDigits:2})+(item.unit==="INDEX_POINTS"?" points":" USD")}</td><td>{[1,5,20].map(n=>{const v=item.changes.find(x=>x.observations===n);return v?percent(v.percent):"—";}).join(" / ")}</td></tr>)}</tbody></table></div>:<p>International market evidence unavailable.</p>}
 <p className="muted tiny">{report.notice}</p></section>;
}

function GlobalResearchSummary({report}:{report:GlobalContext}){
 return <section className="autonomous-result" aria-label="Integrated global research"><header><strong>Integrated global research</strong><span>{report.available_count}/{report.total_count} dated indicators</span></header>
 {report.groups.map(g=><details key={g.group}><summary>{g.group.replace(/_/g," ").toLowerCase()} · {g.available_count}/{g.total_count} available</summary>{g.items.length?<ul>{g.items.map(item=><li key={item.key}><div><strong>{item.label}</strong><small>{item.source} · {item.as_of}</small></div><b>{item.change?(item.change.value>0?"+":"")+item.change.value.toFixed(2)+(item.change.unit==="BASIS_POINTS"?" bp":"%")+" over 5 observed dates":"Change unavailable"}</b></li>)}</ul>:<p>Current evidence unavailable.</p>}</details>)}
 <p className="muted tiny">{report.notice}</p></section>;
}

function GlobalReleasePanel({report}:{report:GlobalReleaseContext}){
 return <section className="autonomous-result" aria-label="Official global economic announcements"><header><strong>Official global economic announcements</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 {report.events.length?<ul>{report.events.map(e=><li key={e.id}><div><a href={e.source_url} target="_blank" rel="noopener noreferrer">{e.headline}</a><small>{e.source_name} · {stamp(e.published_at)} · {e.geography}</small><small>{e.topics.map(t=>t.toLowerCase().replace(/_/g," ")).join(" · ")||"General announcement"}</small></div></li>)}</ul>:<p>No recent usable published announcement in the enabled feeds.</p>}
 <details><summary>Official feed coverage</summary>{report.sources.map(s=><p key={s.source}>{s.label} · {s.status.toLowerCase().replace(/_/g," ")}{s.retrieved_at?" · "+stamp(s.retrieved_at):""}</p>)}</details><p className="muted tiny">{report.notice}</p></section>;
}

function EconomicCalendarPanel({report}:{report:EconomicCalendar}){
 return <section className="autonomous-result" aria-label="Upcoming economic release calendar"><header><strong>Upcoming economic release calendar</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 <p className="muted tiny">US Bureau of Labor Statistics · scheduled time in IST · <a href={report.source_url} target="_blank" rel="noopener noreferrer">Official calendar</a>{report.retrieved_at&&" · retrieved "+stamp(report.retrieved_at)}</p>
 {report.events.length?<ul>{report.events.map(e=><li key={e.id}><div><strong>{e.headline}</strong><small>{stamp(e.scheduled_at)} · {e.status.toLowerCase().replace(/_/g," ")}</small>{e.review_window&&<small>Upcoming within 24 hours · review event exposure</small>}{e.release_match&&<div><small>{e.release_match.status.toLowerCase().replace(/_/g," ")}</small>{e.release_match.source_url&&<p><a href={e.release_match.source_url} target="_blank" rel="noopener noreferrer">{e.release_match.headline}</a> · {stamp(e.release_match.published_at??null)}</p>}<small>{e.release_match.notice}</small></div>}</div></li>)}</ul>:<p>No usable scheduled events in the current coverage window.</p>}
 <p className="muted tiny">{report.notice}</p></section>;
}

function MarketRegimePanel({report}:{report:RegimeReport}){
 const words=(v:string)=>v.toLowerCase().replace(/_/g," ");
 return <section className="autonomous-result" aria-label="Observed market regime"><header><strong>Observed market regime</strong><span>{words(report.status)}</span></header>
 {report.status==="OBSERVED_BENCHMARK_REGIME"?<><p><strong>Nifty 50 · {words(report.trend??"UNAVAILABLE")}</strong> · {report.as_of} · 60-session price change {percent(report.benchmark_change_60_percent??null)}</p>
 <p>20-session annualized historical volatility: {percent(report.volatility_20_annualized_percent??null)} · {words(report.volatility_regime??"UNAVAILABLE")}</p>
 {report.breadth?.matched_count!=null?<p>Matched adjusted NSE sample: {report.breadth.advancing} advancing · {report.breadth.declining} declining · {report.breadth.unchanged} unchanged · {report.breadth.matched_count}/{report.breadth.selected_count} selected · {words(report.breadth.status)}</p>:<p>Comparable adjusted sample breadth unavailable.</p>}
 <p>Trend / daily breadth context: {words(report.agreement??"UNAVAILABLE")}</p>
 {report.institutional?.fii&&<p>Same latest session, five-session reported flows: FII {words(report.institutional.fii)} · DII {words(report.institutional.dii??"UNAVAILABLE")}</p>}
 </>:<p>Insufficient current calendar-matched benchmark history.</p>}
 {report.global_coverage&&<p>Separate global context: {report.global_coverage.available_count}/{report.global_coverage.total_count} dated indicators. Not synchronized with the Indian close.</p>}
 <p className="muted tiny">{report.notice}</p></section>;
}
