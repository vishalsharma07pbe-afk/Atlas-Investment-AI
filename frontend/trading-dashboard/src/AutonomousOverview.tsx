import InvestmentAnalystPanel,{type InvestmentAnalysis} from "./InvestmentAnalystPanel";
import {MarketTiles,EvidenceBars} from "./TerminalCharts";
import {CoverageMeter} from "./ResearchVisuals";
import SteadyMomentumCard,{type SteadyScreen,type EliteTarget} from "./SteadyMomentumCard";
import {visiblePolling} from "./visiblePolling";
import "./overview.css";
import type {WatchReportTarget} from "./HorizonResearch";
import {useEffect,useState,type ReactNode} from "react";
import AutomaticInstitutionalActivity,{type InstitutionalActivity} from "./AutomaticInstitutionalActivity";
import {RecentCompanyNews,type Article} from "./AutomaticCompanyNews";

type Candidate={id:number;symbol:string;exchange:string;as_of:string;change_1d_percent:number;momentum_20d_percent:number|null};
type FundPick={fund:{identifier:string;name:string};score:number};
type HistoricalFund={scheme_code:number;scheme_name:string;cagr_3y_percent:number;nav_date:string};
type Horizon="SWING"|"SHORT_TERM"|"LONG_TERM";
type Result={historical_research_shortlist?:{items:{identifier:string;name:string;nav_date:string;score:number;weekly_cagr_percent:number;relative_risk:string;status:string;qualified:false}[];status:string};skipped?:Record<string,number>;discovery_coverage?:{calendar_status?:string;expected_session?:string|null;expected_session_count?:number|null};qualification_counts?:{evaluated_count:number;growth_eligible_count:number;growth_missing_gate_counts:Record<string,number>}|null;horizons?:Partial<Record<Horizon,{status:string;candidates:{id:number;symbol:string;exchange:string;as_of:string}[]}>>;historical_coverage?:{items?:HistoricalFund[]};eligible_count?:number;universe_size?:number;top_gainers?:Candidate[];momentum_leaders?:Candidate[];top_performers?:FundPick[];growth_outlook?:FundPick[];coverage?:{name_matched_schemes:number};blockers?:string[];notice?:string};
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
type UnifiedDecision={status:string;equity_company_count:number|null;equity_review_count:number|null;ai_reviewed_company_count:number|null;equity_companies:{isin:string;symbol:string;state:string;observations:{exchange:string;horizon:string;as_of:string;review_findings:string[];blockers:string[];ai:{status:string;reviewed_count:number|null}}[]}[];fund_categories:{category:string;state:string;reviewed_count:number|null;growth_withheld_count:number|null;driver_reviews?:{identifier:string;state:string;ai_status:string}[];historical_watches:{identifier:string;name:string;nav_date:string}[];leading_blockers:{code:string;count:number}[]}[];notice:string};
type EarningsValidation={status:string;pending_count:number|null;quarter_cohorts:{target_quarter:string;published_count:number;observed_count:number;revised_count:number;coverage_percent:number;status:string;metrics:{metric:string;persistence_mean_error_pp:number|null;unchanged_mean_error_pp:number|null;lower_error_count:number}[]}[];notice:string};
type HistoricalDisplay={section:string;status:string;generated_at:string;current_status:string;metric:string;observations:{label:string;observed_date:string;value_percent:number}[];qualification_eligible:false;notice:string};
type Snapshot={investment_analyst?:InvestmentAnalysis;historical_display?:HistoricalDisplay[];forward_earnings_validation?:EarningsValidation;unified_decision?:UnifiedDecision;steady_momentum?:SteadyScreen;market_regime?:RegimeReport;economic_calendar?:EconomicCalendar;global_releases?:GlobalReleaseContext;global_context?:GlobalContext;global_markets?:GlobalMarketContext;global_macro?:MacroContext;global_fx?:FxContext;daily_briefing?:Briefing;recent_company_news?:Article[];institutional_activity?:InstitutionalActivity;enabled:boolean;interval_seconds:number;sections:{section:string;status:string;generated_at:string|null;attempted_at:string|null;error_code?:string|null;result:Result|null}[]};
const labels:Record<string,string>={NSE:"NSE",BSE:"BSE",LARGE_CAP:"Large cap",MID_CAP:"Mid cap",SMALL_CAP:"Small cap",FLEXI_CAP:"Flexi cap",INDEX:"Index funds",LARGE_MID_CAP:"Large & mid cap",MULTI_CAP:"Multi cap",AGGRESSIVE_HYBRID:"Aggressive hybrid",CORPORATE_BOND:"Corporate bond",SHORT_DURATION:"Short duration"};
const percent=(value:number|null)=>typeof value!=="number"||!Number.isFinite(value)?"—":(value>0?"+":"")+value.toFixed(2)+"%";
const stamp=(value:string|null)=>value&&Number.isFinite(Date.parse(value))?new Date(value).toLocaleString("en-IN",{timeZone:"Asia/Kolkata",dateStyle:"medium",timeStyle:"short"})+" IST":"Not yet refreshed";
export default function AutonomousOverview({children,onPortfolio,onFunds,onSettings,onHorizon,onOpenStock}:{children:ReactNode;onOpenStock?:(target:EliteTarget)=>void;onPortfolio:()=>void;onFunds:()=>void;onSettings:()=>void;onHorizon?:(horizon:Horizon,target?:WatchReportTarget)=>void}){
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
 const unified=current?data?.unified_decision:undefined;
 const compact=!!briefing;
 const momentum=readyMarkets.flatMap(row=>(row.result?.momentum_leaders??[]).slice(0,5)).filter(c=>typeof c.momentum_20d_percent==="number"&&Number.isFinite(c.momentum_20d_percent)).sort((a,b)=>b.momentum_20d_percent!-a.momentum_20d_percent!||a.exchange.localeCompare(b.exchange)||a.id-b.id);
 const [allMomentum,setAllMomentum]=useState(false);
 const hasEquityEvidence=readyMarkets.some(row=>(row.result?.eligible_count??0)>0)||!!briefing&&briefing.market.eligible_histories>0;
 const activeFunds=funds.filter(row=>current&&row.status==="READY"&&((row.result?.growth_outlook?.length??0)>0||(row.result?.historical_coverage?.items?.length??0)>0||(row.result?.historical_research_shortlist?.items?.length??0)>0));
 const fundLimit=Math.max(1,market.length);
 const shownFunds=[...activeFunds].sort((a,b)=>Number((b.result?.growth_outlook?.length??0)>0)-Number((a.result?.growth_outlook?.length??0)>0)).slice(0,fundLimit);
 const [showSources,setShowSources]=useState(false);
 const hasEvents=!!(data?.economic_calendar||data?.global_releases);
 const hasGlobal=!!(data?.market_regime||data?.global_context||data?.global_fx||data?.global_macro||data?.global_markets);
 const horizonLinks:{id:Horizon;title:string}[]=[{id:"SWING",title:"Swing"},{id:"SHORT_TERM",title:"Short term"},{id:"LONG_TERM",title:"Long term"}];
 return <section className="autonomous-overview glass" aria-label="Automatic research overview">
   <header className="autonomous-header"><div><small className="section-kicker">YOUR DAILY INTELLIGENCE</small><h2>Research overview</h2><p>Latest market, fund and company research.</p></div><span className="tag">{error?"SERVICE UNAVAILABLE":data?.enabled===false?"AUTOMATION OFF":data?"BACKGROUND RESEARCH":"LOADING"}</span></header>
   {error&&<p role="alert" className="notice warning-notice">Research service unavailable. Previously displayed observations may be outdated. <button type="button" className="secondary" onClick={onSettings}>Check connections</button></p>}
   {!data&&!error&&<p role="status">Loading the latest saved research…</p>}
   {data?.enabled===false&&<p className="notice warning-notice">Background research is disabled. Check the local configuration in Settings.</p>}
   {current&&data?.investment_analyst&&<InvestmentAnalystPanel report={data.investment_analyst} onOpenStock={onOpenStock} onFunds={onFunds} onPortfolio={onPortfolio}/>}
   {current&&data?.steady_momentum&&<SteadyMomentumCard report={data.steady_momentum} onSettings={onSettings} onOpen={onOpenStock}/>}
   {momentum.length>0&&<section className="visual-research-panel" aria-label="Momentum leaders"><div className="sectionhead"><div><h3>Momentum leaders</h3><small>20-session observed price change · limited coverage · not buy signals</small></div>{momentum.length>5&&<button type="button" className="secondary" aria-expanded={allMomentum} onClick={()=>setAllMomentum(!allMomentum)}>{allMomentum?"Show fewer":"View all "+momentum.length}</button>}</div><EvidenceBars title="Observed 20-session momentum" rows={momentum.slice(0,allMomentum?10:5).map(c=>({label:c.symbol+" · "+c.exchange,value:c.momentum_20d_percent}))}/><details><summary>Dates &amp; source observations</summary><MarketTiles title="Momentum observations" items={momentum.map(c=>({key:c.exchange+":"+c.id,label:c.symbol+" · "+c.exchange,exchange:c.exchange,date:c.as_of,value:c.momentum_20d_percent}))} period="20-session price change"/></details></section>}
   {current&&briefing&&!hasEquityEvidence&&!data?.steady_momentum&&<div className="research-status-line" aria-label="Equity research availability"><strong>Equity research is not ready</strong><button type="button" className="secondary" onClick={onSettings}>Data coverage</button></div>}
   {current&&!!data?.historical_display?.length&&<section className="visual-research-panel" aria-label="Last valid historical observations">
    <div className="sectionhead"><div><h3>Last valid observations</h3><small>Historical only · not current opportunities</small></div><span className="tag">READ ONLY</span></div>
    <p className="muted">The latest research has no usable observation for these sections. Previous observations remain visible without entering current rankings or qualification.</p>
    <div className="autonomous-grid">{data.historical_display.filter(row=>row.status==="HISTORICAL_DISPLAY_ONLY"&&row.qualification_eligible===false&&Array.isArray(row.observations)&&row.observations.length>0).map(row=><article className="autonomous-result" key={row.section}>
      <header><strong>{labels[row.section]??row.section}</strong><span>HISTORICAL</span></header><small>Saved {stamp(row.generated_at)} · {row.current_status==="READY"?"No current observations":row.current_status.toLowerCase()}</small>
      <EvidenceBars title={row.metric==="20_SESSION_PRICE_CHANGE"?"Past 20-session price change":"Past 3-year CAGR"} rows={row.observations.map(o=>({label:o.label,value:o.value_percent}))}/>
      <ul>{row.observations.map(o=><li key={o.label+":"+o.observed_date}><div><strong>{o.label}</strong><small>Observed {o.observed_date}</small></div><b>{percent(o.value_percent)}</b></li>)}</ul>
    </article>)}</div>
   </section>}
   {briefing&&<DailyBriefing report={briefing} onFunds={onFunds} onSettings={onSettings} onPortfolio={onPortfolio} onHorizon={onHorizon}/>}
   {unified?.status==="RESEARCH_CONTEXT_AVAILABLE"&&<UnifiedDecisionDesk report={unified} onFunds={onFunds} onPortfolio={onPortfolio}/>}
   {current&&data?.forward_earnings_validation?.status==="PROSPECTIVE_EXPERIMENT"&&<EarningsValidationView report={data.forward_earnings_validation}/>}
   {onHorizon&&!briefing?.decision_context&&<div className="research-shortcuts" aria-label="Automatic equity research shortcuts">{horizonLinks.map(({id,title})=>{const groups=readyMarkets.flatMap(row=>row.result?.horizons?.[id]?[row.result.horizons[id]!]:[]);const count=groups.reduce((n,group)=>n+(group.status==="TECHNICAL_WATCH_ONLY"?group.candidates.length:0),0);return <button key={id} type="button" className="research-shortcut" onClick={()=>onHorizon(id)}><strong>{title}</strong><span>{groups.length?`${count} technical watches`:"Current research pending"}</span><small>Open research →</small></button>;})}</div>}
   {current&&(market.length>0||funds.length>0||!briefing)&&<OverviewGroup compact={compact} title="Market and fund observation details" description="Momentum samples, all fund categories and their current evidence status">
   <div className={"autonomous-grid"+(compact?" overview-balanced-preview":"")}>
    <div className="autonomous-section"><h3>Market watch</h3><p className="muted">Daily-history observations, not trade signals.</p>
      {(compact?market.filter(row=>row.status==="READY"&&(row.result?.momentum_leaders?.length??0)>0):market).map(row=>{const ready=row.status==="READY"&&!error&&data?.enabled===true;const picks=(row.result?.momentum_leaders||[]).slice(0,3);return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?(row.result?.eligible_count||0)+" / "+(row.result?.universe_size||0)+" eligible":!current?"UNAVAILABLE":row.status.replace(/_/g," ")}</span></header><small>{stamp(row.generated_at)}</small>{ready&&picks.length?<ul>{picks.map(item=><li key={item.id}><div><strong>{item.symbol}</strong><small>{item.as_of} · 20-day momentum</small></div><b>{percent(item.momentum_20d_percent)}</b></li>)}</ul>:<p>{ready?"No qualifying momentum observations in the current sample.":row.status==="FAILED"?"Refresh failed; awaiting the next attempt.":"Awaiting a current research snapshot."}</p>}</article>})}
    </div>
    <div className="autonomous-section"><h3>Mutual fund research</h3><p className="muted">Strict evidence-based qualification; no forced picks.</p>
      {(compact?shownFunds:funds).map(row=>{const ready=row.status==="READY"&&!error&&data?.enabled===true;const picks=row.result?.growth_outlook||[];const history=row.result?.historical_coverage?.items||[];const shortlist=row.result?.historical_research_shortlist?.items||[];return <article key={row.section} className="autonomous-result"><header><strong>{labels[row.section]}</strong><span>{ready?picks.length+" growth picks":!current?"UNAVAILABLE":row.status}</span></header>{ready&&picks.length?<ul>{picks.slice(0,compact?1:5).map(item=><li key={item.fund.identifier}>{item.fund.name}</li>)}</ul>:<p>{ready?"No growth picks meet the verified evidence requirements.":row.status==="FAILED"?"Refresh failed; will retry.":"Research pending."}</p>}{ready&&shortlist.length>0&&(!compact||picks.length===0)&&<><p className="muted tiny">Matched historical research shortlist</p><ul>{shortlist.slice(0,compact?1:3).map(item=><li key={item.identifier}><div><strong>{item.name}</strong><small>{item.nav_date} · historical peer score {item.score.toFixed(1)}/100</small></div><b>{percent(item.weekly_cagr_percent)}</b></li>)}</ul></>}{ready&&shortlist.length===0&&history.length>0&&(!compact||picks.length===0)&&<><p className="muted tiny">Historical watch only</p><ul>{history.slice(0,compact?1:2).map(item=><li key={item.scheme_code}><div><strong>{item.scheme_name}</strong><small>{item.nav_date} · 3-year CAGR</small></div><b>{percent(item.cagr_3y_percent)}</b></li>)}</ul></>}</article>})}
      {compact&&!shownFunds.length&&<small className="muted">Fund research pending.</small>}
      <button type="button" className="secondary overview-full-list" onClick={onFunds}>{compact&&activeFunds.length>shownFunds.length?`View full fund list (${activeFunds.length} categories with observations)`:"View fund research"}</button>
    </div>
   </div>
   </OverviewGroup>}
   
   {current&&hasEvents&&(!compact||!!data?.economic_calendar?.events.length||!!data?.global_releases?.events.length)&&<OverviewGroup compact={compact} title="Economic events and announcements" description="Scheduled releases and separately published source-linked announcements">
    {data?.economic_calendar&&(!compact||data.economic_calendar.events.length>0)&&<EconomicCalendarPanel report={data.economic_calendar}/>}
    {data?.global_releases&&(!compact||data.global_releases.events.length>0)&&<GlobalReleasePanel report={data.global_releases}/>}
   </OverviewGroup>}
   {current&&hasGlobal&&(!compact||data?.market_regime?.status==="OBSERVED_BENCHMARK_REGIME"||(data?.global_context?.available_count??0)>0||data?.global_fx?.items.some(i=>typeof i.rate==="number"&&Number.isFinite(i.rate))||data?.global_macro?.sources.some(s=>s.items.some(i=>i.value!=null&&Number.isFinite(i.value)))||data?.global_markets?.items.some(i=>i.value!=null&&Number.isFinite(i.value)))&&<OverviewGroup compact={compact} title="Detailed market regime and global evidence" description="Benchmark trend, sample breadth, currencies, oil, yields, indices and metals">
    {data?.market_regime&&(!compact||data.market_regime.status==="OBSERVED_BENCHMARK_REGIME")&&<MarketRegimePanel report={data.market_regime}/>}
    {data?.global_context&&(!compact||data.global_context.available_count>0)&&<GlobalResearchSummary report={data.global_context}/>}
    {data?.global_fx&&(!compact||data.global_fx.items.some(i=>typeof i.rate==="number"&&Number.isFinite(i.rate)))&&<GlobalFxContext report={data.global_fx}/>}
    {data?.global_macro&&(!compact||data.global_macro.sources.some(s=>s.items.some(i=>i.value!=null&&Number.isFinite(i.value))))&&<GlobalMacroContext report={data.global_macro}/>}
    {data?.global_markets&&(!compact||data.global_markets.items.some(i=>i.value!=null&&Number.isFinite(i.value)))&&<GlobalMarketsContext report={data.global_markets}/>}
   </OverviewGroup>}
   {current&&((data?.institutional_activity&&(!compact||data.institutional_activity.status!=="DISABLED_OR_NOT_AUTHORIZED"))||!!data?.recent_company_news?.length)&&<details className="overview-market-context"><summary>Institutional activity &amp; company news</summary>{data?.institutional_activity&&<AutomaticInstitutionalActivity data={data.institutional_activity} compact={compact}/>}
    {!!data?.recent_company_news?.length&&<RecentCompanyNews articles={data.recent_company_news}/>}</details>}
   {current&&briefing&&<details className="overview-evidence-group overview-source-diagnostics" onToggle={e=>setShowSources(e.currentTarget.open)}><summary><span><strong>Research coverage &amp; missing data</strong><small>Data readiness · source details</small></span><span className="overview-disclosure-label" aria-hidden="true"/></summary>{showSources&&<div className="overview-evidence-body"><ResearchCoverage market={market} funds={funds} data={data!} onSettings={onSettings}/></div>}</details>}
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

function DailyBriefing({report,onFunds,onSettings,onPortfolio,onHorizon}:{report:Briefing;onFunds:()=>void;onSettings:()=>void;onPortfolio:()=>void;onHorizon?:(horizon:Horizon,target?:WatchReportTarget)=>void}){
 const watches=Object.values(report.horizons).reduce((n,h)=>n+(h?.displayed_watch_count??0),0);
 const hasDecisionWatches=Object.values(report.decision_context?.horizons??{}).some(h=>(h?.selected_watches.length??0)>0);
 const reviewed=Object.values(report.horizons).reduce((n,h)=>n+(h?.ai_reviewed_count??0),0);
 const conflicts=Object.values(report.horizons).reduce((n,h)=>n+(h?.conflicting_evidence_count??0),0);
 const words=(value:string)=>value.toLowerCase().replace(/_/g," ");
 const funds=report.funds.growth_pick_count??0;
 return <section className="autonomous-result visual-research-panel" aria-label="Daily research briefing">
  <header><strong>Daily research briefing</strong><button className="secondary" type="button" onClick={onSettings}>Data coverage</button></header>
  {(report.market.eligible_histories>0||watches>0||funds>0)&&<div className="research-visual-grid" aria-label="Research coverage summary">
    <CoverageMeter label="Validated stock histories" value={report.market.eligible_histories} total={report.market.sampled_instruments}/>
    {watches>0&&<div className="research-kpi"><small>Technical watches</small><strong>{watches}</strong><small>{reviewed?reviewed+" AI reviewed":"AI review pending"}{conflicts?" · "+conflicts+" conflicts":""}</small></div>}
    {funds>0&&<div className="research-kpi"><small>Qualified fund growth picks</small><strong>{funds}</strong></div>}
  </div>}
  <div className="research-visual-grid">
   {report.funds.historical_watch_count>0&&<button type="button" className="research-kpi research-kpi-button" onClick={onFunds}><small>Historical fund observations</small><strong>{report.funds.historical_watch_count}</strong><span>Review funds →</span></button>}
   {report.institutional.status==="RECENT_PAIRED_OBSERVATIONS"&&<><div className="research-kpi"><small>FII · 5 reported dates</small><strong className={report.institutional.fii_direction==="NET_BUYING"?"positive":report.institutional.fii_direction==="NET_SELLING"?"negative":""}>{words(report.institutional.fii_direction||"UNKNOWN")}</strong><small>{report.institutional.latest_date}</small></div><div className="research-kpi"><small>DII · 5 reported dates</small><strong className={report.institutional.dii_direction==="NET_BUYING"?"positive":report.institutional.dii_direction==="NET_SELLING"?"negative":""}>{words(report.institutional.dii_direction||"UNKNOWN")}</strong><small>{report.institutional.latest_date}</small></div></>}
  </div>
  {report.decision_context&&(hasDecisionWatches||report.decision_context.review_company_count>0||report.decision_context.regime.status==="OBSERVED_BENCHMARK_REGIME")&&<DecisionBriefing context={report.decision_context} newsCount={report.news_headline_count} onPortfolio={onPortfolio} onHorizon={onHorizon}/>}
  <details><summary>Research scope &amp; qualification</summary><p>{report.ready_sections}/{report.total_sections} snapshots refreshed; not full-market coverage. {report.market.eligible_histories}/{report.market.sampled_instruments} selected histories validated.</p>{watches>0&&<p>{watches} displayed horizon watches · {reviewed} with AI commentary · {conflicts} conflicting. Full investment qualification is not available yet.</p>}<p>{funds} qualified fund growth picks. {report.notice}</p>{report.leading_evidence_gaps.length>0&&<ul>{report.leading_evidence_gaps.map(g=><li key={g.code}>{words(g.code)} · {g.watch_count} watch observations</li>)}</ul>}</details>
 </section>;
}

function DecisionBriefing({context,newsCount,onPortfolio,onHorizon}:{context:DecisionContext;newsCount?:number;onPortfolio:()=>void;onHorizon?:(horizon:Horizon,target?:WatchReportTarget)=>void}){
 const words=(v:string)=>v.toLowerCase().replace(/_/g," ");
 const order:Horizon[]=["SWING","SHORT_TERM","LONG_TERM"];
 const active=order.filter(h=>!!context.horizons[h]?.selected_watches.length);
 return <section aria-label="Today's evidence review">
  <h3>Today's evidence review</h3>
  <div className="research-visual-grid">{context.regime.status==="OBSERVED_BENCHMARK_REGIME"&&<div className="research-kpi"><small>Nifty 50 trend</small><strong>{words(context.regime.trend||"UNAVAILABLE")}</strong><small>{context.regime.as_of}</small></div>}
  {context.global_coverage&&context.global_coverage.available_count>0&&<CoverageMeter label="Dated global indicators" value={context.global_coverage.available_count} total={context.global_coverage.total_count}/>}
  {!!newsCount&&<div className="research-kpi"><small>Company headlines</small><strong>{newsCount}</strong></div>}</div>
  {context.regime.agreement==="OPPOSING_DAILY_BREADTH_REVIEW"&&<p className="muted tiny">Daily breadth opposes the longer trend.</p>}
  {context.review_companies.length>0&&<><h4>Company evidence to review</h4>{context.review_companies.map(item=><details className="overview-company-review" key={item.isin}><summary>{item.symbol} · {item.findings.length} findings · {item.horizons.map(words).join(", ")}</summary><p>{item.observations.map(o=>o.exchange+" "+o.as_of).join(" · ")}</p><ul>{item.findings.map(f=><li key={f}>{words(f)}</li>)}</ul></details>)}</>}
  {active.length>0&&<><h4>Technical watches by horizon</h4><div className="overview-horizon-grid">{active.map(h=>{const result=context.horizons[h]!;return <article className="overview-horizon-card" key={h}><strong className="overview-horizon-title">{words(h)}</strong><strong className="research-big-number">{result.selected_watches.length}</strong><small>Technical watches · {result.qualified_count===null?"qualification unavailable":result.qualified_count+" qualified in the reviewed sample"}</small><details><summary>View {result.selected_watches.length} selected observations</summary><ul>{result.selected_watches.map(w=><li key={w.isin}><div><strong>{w.symbol} · {w.exchange}</strong><small>{w.as_of} · {w.unresolved_requirement_count} unresolved requirements</small></div>{onHorizon&&<button type="button" className="secondary overview-report-link" aria-label={"Open "+w.symbol+" "+w.exchange+" research report"} onClick={()=>onHorizon(h,{exchange:w.exchange,id:w.id,isin:w.isin,as_of:w.as_of})}>Open report</button>}</li>)}</ul></details>{onHorizon&&<button className="secondary" type="button" onClick={()=>onHorizon(h)}>Review {words(h)} research</button>}</article>;})}</div></>}
  <div className="overview-private-review"><button className="secondary" type="button" onClick={onPortfolio}>Open private portfolio review</button>{onHorizon&&order.filter(h=>!active.includes(h)).map(h=><button className="secondary" key={h} type="button" onClick={()=>onHorizon(h)}>Review {words(h)} research</button>)}</div>
  <details><summary>Evidence limitations</summary><p>{context.global_coverage?context.global_coverage.available_count+"/"+context.global_coverage.total_count+" dated global indicators":"Global indicator coverage unavailable"}. {context.notice}</p></details>
 </section>;
}

function GlobalFxContext({report}:{report:FxContext}){
 return <section className="autonomous-result" aria-label="Global currency context"><header><strong>Global currency context</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 <p className="muted tiny">European Central Bank · daily reference rates, not live quotes. {report.retrieved_at&&"Retrieved "+stamp(report.retrieved_at)}</p>
 {report.items.length?<div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Pair"><table><thead><tr><th>Pair</th><th>Reference date</th><th>Quote per base unit</th><th>1 / 5 / 20 observed-date changes</th></tr></thead><tbody>{report.items.map(item=><tr key={item.pair}><td>{item.pair.replace("_","/")}<small> · {item.basis==="DERIVED_ECB_CROSS"?"ATLAS cross-rate":"ECB reference"}</small></td><td>{item.as_of??"Unavailable"}</td><td>{item.rate?.toFixed(4)??"Unavailable"}</td><td>{[1,5,20].map(n=>{const found=item.changes?.find(c=>c.observations===n);return found?percent(found.percent):"—";}).join(" / ")}</td></tr>)}</tbody></table></div>:<p>Currency reference evidence unavailable or not enabled.</p>}
 <p className="muted tiny">{report.notice}</p></section>;
}

function GlobalMacroContext({report}:{report:MacroContext}){
 return <section className="autonomous-result" aria-label="Global oil and interest-rate context"><header><strong>Global oil and interest-rate context</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 {report.sources.map(source=><div key={source.source}><p><strong>{source.source}</strong> · {source.status.toLowerCase().replace(/_/g," ")} {source.retrieved_at&&" · "+stamp(source.retrieved_at)}</p>{source.items.length>0&&<div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Indicator"><table><thead><tr><th>Indicator</th><th>Observation date</th><th>Value</th><th>1 / 5 / 20 observed-date changes</th></tr></thead><tbody>{source.items.map(item=><tr key={item.series}><td>{item.label}</td><td>{item.as_of??"Unavailable"}</td><td>{item.value==null?"Unavailable":item.value.toFixed(2)+(item.unit==="PERCENT"?"%":" USD/bbl")}</td><td>{[1,5,20].map(n=>{const v=item.changes.find(x=>x.observations===n);return v?(v.value>0?"+":"")+v.value.toFixed(2)+(v.unit==="BASIS_POINTS"?" bp":"%"):"—";}).join(" / ")}</td></tr>)}</tbody></table></div>}</div>)}
 <p className="muted tiny">{report.notice}</p></section>;
}

function GlobalMarketsContext({report}:{report:GlobalMarketContext}){
 return <section className="autonomous-result" aria-label="International indices and metals"><header><strong>International indices and metals</strong><span>{report.status.toLowerCase().replace(/_/g," ")}</span></header>
 {report.items.length?<div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Indicator / source"><table><thead><tr><th>Indicator / source</th><th>Reference date</th><th>Value</th><th>1 / 5 / 20 observed-date changes</th></tr></thead><tbody>{report.items.map(item=><tr key={item.series}><td>{item.label}<small> · {item.source}</small></td><td>{item.as_of??"Unavailable"}</td><td>{item.value==null?item.status.toLowerCase().replace(/_/g," "):item.value.toLocaleString("en-IN",{maximumFractionDigits:2})+(item.unit==="INDEX_POINTS"?" points":" USD")}</td><td>{[1,5,20].map(n=>{const v=item.changes.find(x=>x.observations===n);return v?percent(v.percent):"—";}).join(" / ")}</td></tr>)}</tbody></table></div>:<p>International market evidence unavailable.</p>}
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
 {report.breadth?.matched_count!=null&&<BreadthGraphic advancing={report.breadth.advancing} declining={report.breadth.declining} unchanged={report.breadth.unchanged}/>} 
 {report.breadth?.matched_count!=null?<p>Matched adjusted NSE sample: {report.breadth.advancing} advancing · {report.breadth.declining} declining · {report.breadth.unchanged} unchanged · {report.breadth.matched_count}/{report.breadth.selected_count} selected · {words(report.breadth.status)}</p>:<p>Comparable adjusted sample breadth unavailable.</p>}
 <p>Trend / daily breadth context: {words(report.agreement??"UNAVAILABLE")}</p>
 {report.institutional?.fii&&<p>Same latest session, five-session reported flows: FII {words(report.institutional.fii)} · DII {words(report.institutional.dii??"UNAVAILABLE")}</p>}
 </>:<p>Insufficient current calendar-matched benchmark history.</p>}
 {report.global_coverage&&<p>Separate global context: {report.global_coverage.available_count}/{report.global_coverage.total_count} dated indicators. Not synchronized with the Indian close.</p>}
 <p className="muted tiny">{report.notice}</p></section>;
}

function BreadthGraphic({advancing,declining,unchanged}:{advancing?:number;declining?:number;unchanged?:number}){
 const values=[advancing,declining,unchanged];
 if(!values.every(v=>typeof v==="number"&&Number.isFinite(v)&&v>=0))return null;
 const counts=values as number[];const total=counts.reduce((a,b)=>a+b,0);if(total<=0)return null;
 return <figure className="terminal-breadth" aria-label="Observed sample breadth"><div className="terminal-breadth-track" aria-hidden="true">{counts.map((n,i)=><span key={i} className={["gain","loss","flat"][i]} style={{flexBasis:(n/total*100)+"%"}}/>)}</div><figcaption>{["Advancing","Declining","Unchanged"].map((label,i)=><span key={label}><i className={["gain","loss","flat"][i]}/>{label} <strong>{counts[i]}</strong></span>)}</figcaption></figure>;
}

function ResearchCoverage({market,funds,data,onSettings}:{market:Snapshot["sections"];funds:Snapshot["sections"];data:Snapshot;onSettings:()=>void}){
 const reason:Record<string,string>={NO_HISTORY:"Insufficient daily history",STALE:"Old price history",INVALID:"Invalid or inconsistent observations",MIXED_ADJUSTMENT:"Mixed price adjustment basis",RAW_CORPORATE_ACTION:"Corporate action requires reconciliation",SESSION_MISMATCH:"Latest close does not match expected market session"};
 const pretty=(s:string)=>s.toLowerCase().replace(/_/g," ");
 const gates=new Map<string,number>();
 for(const row of funds)if(row.status==="READY")for(const [key,n] of Object.entries(row.result?.qualification_counts?.growth_missing_gate_counts??{}))if(Number.isFinite(n)&&n>0)gates.set(key,(gates.get(key)??0)+n);
 const globalSources=[{name:"Benchmark history",status:data.market_regime?.status},{name:"Currency reference rates",status:data.global_fx?.status},{name:"Oil and yields",status:data.global_macro?.status},{name:"International indices and metals",status:data.global_markets?.status},{name:"Economic calendar",status:data.economic_calendar?.status},{name:"Official announcements",status:data.global_releases?.status}];
 return <section className="overview-coverage" aria-label="Research source coverage">
 <h3>Stock history eligibility</h3>{market.map(row=><article key={row.section}><strong>{row.section}</strong><small>{row.status==="READY"?"Snapshot refreshed":pretty(row.status)} · {stamp(row.generated_at)}</small>{row.status==="READY"&&row.result?<><p>{row.result.eligible_count??"Unknown"} of {row.result.universe_size??"unknown"} histories eligible.</p>{row.result.discovery_coverage&&<p>Calendar: {row.result.discovery_coverage.expected_session??"Expected session unverified"}</p>}<ul>{Object.entries(row.result.skipped??{}).filter(([,n])=>Number.isFinite(n)&&n>0).map(([key,n])=><li key={key}><span>{reason[key]??pretty(key)}</span><strong>{n}</strong></li>)}</ul></>:<p>{row.error_code==="UNDERLYING_OBSERVATION_STALE"?"Stored observations are no longer current for the expected session.":row.error_code==="RESEARCH_REFRESH_FAILED"?"The research refresh failed; automatic retry is pending.":"Waiting for a current successful research snapshot."}</p>}</article>)}
 <div className="research-visual-grid"><div className="research-kpi"><small>Fund evidence requirements missing</small><strong>{gates.size}</strong><small>Distinct gate types, not scheme count</small></div><div className="research-kpi"><small>Global indicators</small><strong>{data.global_context?data.global_context.available_count+" / "+data.global_context.total_count:"—"}</strong><small>Dated observations</small></div></div><details><summary>Fund qualification blockers</summary>{gates.size?<ul>{[...gates].sort((a,b)=>b[1]-a[1]).map(([key,n])=><li key={key}><span>{pretty(key)}</span><strong>{n} scheme checks</strong></li>)}</ul>:<p>Detailed qualification counts not yet available.</p>}</details>
 <details><summary>Global source status</summary><ul>{globalSources.map(s=><li key={s.name}><span>{s.name}</span><strong>{s.status?pretty(s.status):"Not yet collected"}</strong></li>)}</ul></details>
 <button type="button" className="secondary" onClick={onSettings}>Open data connections</button>
 </section>;
}

function UnifiedDecisionDesk({report,onFunds,onPortfolio}:{report:UnifiedDecision;onFunds:()=>void;onPortfolio:()=>void}){
 const label=(value:string)=>value.replace(/_/g," ").toLowerCase();
 return <section className="autonomous-result visual-research-panel" aria-label="Unified research decisions">
  <header><strong>Unified research decisions</strong><span>Evidence first</span></header>
  <div className="research-visual-grid">
   <div className="research-kpi"><small>Companies reviewed</small><strong>{report.equity_company_count??"—"}</strong><small>Distinct company identities</small></div>
   <div className="research-kpi"><small>Need further review</small><strong>{report.equity_review_count??"—"}</strong></div>
   <div className="research-kpi"><small>AI-reviewed companies</small><strong>{report.ai_reviewed_company_count??"—"}</strong><small>Checked observations, not confidence</small></div>
  </div>
  {!!report.equity_companies.length&&<details><summary>Company decision evidence ({report.equity_companies.length})</summary>{report.equity_companies.slice(0,15).map(c=><article className="autonomous-result" key={c.isin}><header><strong>{c.symbol}</strong><span>{label(c.state)}</span></header><ul>{c.observations.map((o,i)=><li key={i}><div><strong>{o.exchange} · {label(o.horizon)}</strong><small>{o.as_of} · {o.blockers.length} mandatory gaps · {label(o.ai.status)}</small>{!!o.review_findings.length&&<small>{o.review_findings.map(label).join("; ")}</small>}</div></li>)}</ul></article>)}</details>}
  {!!report.fund_categories.length&&<details><summary>Fund research decisions ({report.fund_categories.length} categories)</summary><ul>{report.fund_categories.map(f=><li key={f.category}><div><strong>{label(f.category)}</strong><small>{f.reviewed_count??"Unknown"} assessed · {f.growth_withheld_count??"Unknown"} growth decisions withheld · {f.historical_watches.length} historical watches</small>{!!f.driver_reviews?.length&&<small>{f.driver_reviews.length} earnings driver reviews · {f.driver_reviews.filter(d=>d.ai_status!=="UNAVAILABLE").length} AI claim reviews available</small>}</div></li>)}</ul><button type="button" className="secondary" onClick={onFunds}>Open fund research</button></details>}
  <button type="button" className="secondary" onClick={onPortfolio}>Open private portfolio decisions</button>
  <p className="muted tiny">{report.notice}</p>
 </section>;
}

function EarningsValidationView({report:r}:{report:EarningsValidation}){
 const fmt=(n:number|null)=>n==null?"—":n.toFixed(2)+" pp";
 return <details className="autonomous-result"><summary>Prospective quarterly earnings baseline validation</summary><p>{r.pending_count??"—"} pending observations. Not analyst forecasts.</p>{r.quarter_cohorts.map(q=><section key={q.target_quarter}><h4>{q.target_quarter} · {q.observed_count}/{q.published_count} outcomes</h4><p>{q.coverage_percent}% coverage · {q.revised_count} revised bases · {q.status.replace(/_/g," ").toLowerCase()}</p><div className="tablewrap"><table><thead><tr><th>Metric</th><th>Growth persistence mean error</th><th>Unchanged seasonal baseline mean error</th><th>Lower error count</th></tr></thead><tbody>{q.metrics.map(m=><tr key={m.metric}><td>{m.metric.replace(/_/g," ")}</td><td>{fmt(m.persistence_mean_error_pp)}</td><td>{fmt(m.unchanged_mean_error_pp)}</td><td>{m.lower_error_count}</td></tr>)}</tbody></table></div></section>)}<p className="muted tiny">{r.notice}</p></details>;
}
