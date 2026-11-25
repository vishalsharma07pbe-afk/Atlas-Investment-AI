import {visiblePolling} from "./visiblePolling";
import {useEffect,useState,type ReactNode} from "react";
import WatchOutcomeHistory from "./WatchOutcomeHistory";
import IntradayResearch from "./IntradayResearch";
import AdvancedSection from "./AdvancedSection";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
import AutomaticCompanyNews,{type NewsEvidence} from "./AutomaticCompanyNews";

export type Horizon="INTRADAY"|"SWING"|"SHORT_TERM"|"LONG_TERM";
type AiReview={reviews:{provider:string;findings:{statement:string;evidence_ids:string[]}[]}[];reviewed_at:string;notice:string};
type CandidateReliability={status:string;blockers:string[];warnings:string[];prospective_status:string;notice:string};
type ResearchConclusion={status:string;summary:string;blockers:string[];warnings:string[];evidence:Record<string,string>;reassessment_conditions:string[];notice:string};
type RegimeResearch={status:string;lookback_observations:number;threshold_percent:number;classified_trades:number;total_trades:number;groups:{regime:string;trades:number;small_sample:boolean;cost_scenarios:{cost_bps_per_side:number;mean_trade_return_percent:number;win_rate_percent:number;wins:number;losses:number;flat:number}[]}[];notice:string};
type ExecutionResearch={status:string;positions:number;lookback_observations:number;participation_limit_percent:number;zero_volume_endpoint_positions:number;notional_scenarios:{entry_notional_inr:number;within_proxy_limit:number;exceeds_proxy_limit:number;unknown:number}[];base_friction_bps_per_side:number;friction_scenarios:{extra_bps_per_side:number;total_bps_per_side:number;net_return_percent:number;max_drawdown_percent:number}[];notice:string};
type ChronologicalValidation={status:string;eligible_folds:number;observed_folds:number;no_signal_folds:number;folds:{fold:number;status:string;exposure_start:string;test_end:string;trades:number;small_sample:boolean;cost_scenarios:{cost_bps_per_side:number;net_return_percent:number;net_same_stock_buy_hold_percent:number;gross_nifty50_price_index_percent?:number;net_difference_vs_nifty50_pp?:number;max_drawdown_percent:number}[]}[];cost_summaries:{cost_bps_per_side:number;positive_folds:number;negative_folds:number;flat_folds:number;worst_observed_return_percent:number;best_observed_return_percent:number}[];notice:string};
type CalendarContinuity={status:string;calendar_days:number;regular_sessions:number;missing_sessions:number;unexpected_observations:number;unknown_days:number;special_days:number;missing_dates:string[];unexpected_dates:string[];unknown_dates:string[];special_dates:string[];notice:string};
type HistoryProvenance={calendar_continuity?:CalendarContinuity;status:string;history_observations:number;first_date:string;last_date:string;overlap_observations:number;changed_observations:number;changed_dates:string[];corporate_action_status:string;notice:string};
type MatchedReplay={history_provenance?:HistoryProvenance;execution_research?:ExecutionResearch;chronological_validation?:ChronologicalValidation;market_regime_research?:RegimeResearch;market_benchmark_status?:string;as_of:string;trades:number;small_sample:boolean;cost_scenarios:{cost_bps_per_side:number;net_return_percent:number;max_drawdown_percent:number;gross_nifty50_price_index_percent?:number;net_difference_vs_nifty50_pp?:number}[];notice:string};
type Pivot={price:number;observed_on:string;confirmed_on:string};
type PriceStructure={status:string;scenario_status:string;support:Pivot[];resistance:Pivot[];indicators?:Record<string,number>;weekly?:{status:string;last_observed_date?:string;week_count?:number;trend?:string;sma_10?:number;sma_20?:number|null};scenario:{reference_close:number;lower_reference:number;upper_reference:number;cost_bps_per_side:number;downside_percent:number;upside_percent:number;reward_to_risk:number}|null;notice:string};
type Candidate={price_structure?:PriceStructure;research_conclusion?:ResearchConclusion;matched_strategy_replay?:MatchedReplay;research_reliability?:CandidateReliability;news_evidence?:NewsEvidence;company_evidence?:CompanyEvidence;ai_review?:AiReview;id:number;symbol:string;exchange:string;as_of:string;close:number;rank_score:number;review_horizon:string;history_count:number;atr_percent:number;median_daily_traded_value:number;reasons:string[];warnings:string[]};
type HorizonResult={status:string;candidates:Candidate[];matched_count:number;evaluated_count:number;blockers:string[];exclusions:Record<string,number>};
type ActionPreview={symbol:string;exchange:string;first_date:string;as_of:string;observations:number;actions:{ex_date:string;action_type:string;post_shares_per_pre_share:string}[];change_1d_percent:number|null;change_20_observation_percent:number|null;window_price_change_percent:number;notice:string};
type ActionReview={normalized_preview_count:number;withheld_count:number;previews:ActionPreview[];notice:string};
type Section={section:string;status:string;generated_at:string|null;result:{universe_size:number;eligible_count:number;corporate_action_review?:ActionReview;discovery_coverage?:{recent_registry_count:number;selected_count:number;calendar_status?:string;expected_session?:string|null;expected_session_count?:number|null};history_coverage?:Partial<Record<Horizon,{minimum_observations:number;eligible_histories:number}>>;skipped?:Record<string,number>;horizons?:Partial<Record<Horizon,HorizonResult>>}|null};
type ReplayCost={gross_nifty50_price_index_percent?:number;net_difference_vs_nifty50_pp?:number;net_same_stock_buy_hold_percent?:number;net_difference_vs_same_stock_pp?:number;cost_bps_per_side:number;net_return_percent:number;matched_gross_exposure_return_percent:number;max_drawdown_percent:number;win_rate_percent:number|null;wins:number;losses:number;flat:number};
type ReplayItem={history_provenance?:HistoryProvenance;execution_research?:ExecutionResearch;chronological_validation?:ChronologicalValidation;market_regime_research?:RegimeResearch;exchange:string;symbol:string;as_of:string;trades:number;holding_sessions:number;test_start:string;test_end:string;gross_buy_hold_percent:number;small_sample:boolean;cost_scenarios:ReplayCost[]};
type Validation={status?:string;sample_count?:number;horizons?:Partial<Record<Horizon,{counts:Record<string,number>;observed_instruments:number;items:ReplayItem[];calendar_withheld?:(CalendarContinuity&{symbol:string;exchange:string})[]}>>;notice?:string};
type ReliabilityCohort={status:string;selected_mature_watches:number;observed_outcomes:number;distinct_observed_isins:number;coverage_percent:number;overlap_excluded:number;immature_excluded:number;incompatible_excluded:number;invalid_excluded:number;blockers:string[];cost_scenarios:{cost_bps_per_side:number;mean_net_change_percent:number;median_net_change_percent:number;positive_count:number;negative_count:number;flat_count:number}[];notice:string};
type Snapshot={research_reliability?:{status?:string;horizons?:Partial<Record<Horizon,ReliabilityCohort>>;notice?:string};strategy_validation?:Validation;enabled:boolean;sections:Section[];automatic_ai_status?:string;automatic_company_status?:string;automatic_news_status?:string};
const titles:Record<Horizon,string>={INTRADAY:"Intraday research",SWING:"Swing trading research",SHORT_TERM:"Short-term equity research",LONG_TERM:"Long-term investment research"};
const descriptions:Record<Horizon,string>={INTRADAY:"Completed current-session candle research. Live liquidity and event risk are not independently verified.",SWING:"Daily trend, relative volume and volatility checks for potential multi-session setups.",SHORT_TERM:"Medium-term trend and 60-session momentum. Fundamental and event research must still confirm each watch candidate.",LONG_TERM:"200-session price trend and longer-term momentum. A technical watch is not a business-quality or fair-value assessment."};
const words=(value:string)=>value.toLowerCase().replace(/_/g," ");
const money=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);

function ProspectiveReliability({report}:{report?:ReliabilityCohort}){
 return <section className="panel glass" aria-label="Prospective research reliability">
  <div className="sectionhead"><div><h3>Prospective watch reliability</h3><p className="muted tiny">Outcomes measured after original watch publication, not historical replay.</p></div><span className="tag">NOT CALIBRATED</span></div>
  {!report?<p>Prospective evidence unavailable.</p>:<>
   <p>{words(report.status)} · {report.observed_outcomes}/{report.selected_mature_watches} mature watches observed · {report.distinct_observed_isins} distinct ISINs · {report.coverage_percent}% coverage</p>
   <p className="muted tiny">Excluded: {report.overlap_excluded} overlapping, {report.immature_excluded} immature, {report.incompatible_excluded} incompatible, {report.invalid_excluded} invalid.</p>
   {report.blockers.length>0&&<p>Evidence gaps: {report.blockers.map(words).join(" · ")}.</p>}
   {report.cost_scenarios.length>0&&<details><summary>Illustrative friction sensitivity</summary><div className="tablewrap"><table><thead><tr><th>Cost per side</th><th>Mean net change</th><th>Median net change</th><th>Positive / negative / flat</th></tr></thead><tbody>{report.cost_scenarios.map(row=><tr key={row.cost_bps_per_side}><td>{row.cost_bps_per_side} bps</td><td>{row.mean_net_change_percent}%</td><td>{row.median_net_change_percent}%</td><td>{row.positive_count} / {row.negative_count} / {row.flat_count}</td></tr>)}</tbody></table></div></details>}
   <p className="muted tiny">{report.notice}</p>
  </>}
 </section>;
}

function CalendarAudit({audit}:{audit:CalendarContinuity}){
 return <div><p>{words(audit.status)} · {audit.regular_sessions} stored regular sessions across {audit.calendar_days} calendar days.</p>
  <p>{audit.missing_sessions} missing sessions · {audit.unexpected_observations} unexpected observations · {audit.unknown_days} unknown days · {audit.special_days} unsupported special days.</p>
  {[["Missing",audit.missing_dates],["Unexpected",audit.unexpected_dates],["Unknown",audit.unknown_dates],["Special",audit.special_dates]].map(([label,dates])=>Array.isArray(dates)&&dates.length>0?<p key={String(label)}>{label} dates (up to 10): {dates.join(", ")}</p>:null)}
  <p className="muted tiny">{audit.notice}</p>
 </div>;
}

function HistoryProvenanceDetails({audit}:{audit?:HistoryProvenance}){
 if(!audit)return null;
 return <details className="notice"><summary>Historical evidence provenance</summary>
  <p>{audit.history_observations} observations · {audit.first_date} to {audit.last_date}</p>
  <p>{words(audit.status)} · {audit.overlap_observations} overlapping observations · {audit.changed_observations} changed observations.</p>
  {audit.changed_dates.length>0&&<p>Changed dates (up to 10): {audit.changed_dates.join(", ")}. Revised results are not attached to current stock watches on this pass.</p>}
  <p>Corporate actions: {words(audit.corporate_action_status)}.</p>
  {audit.calendar_continuity&&<CalendarAudit audit={audit.calendar_continuity}/> }
  <p className="muted tiny">{audit.notice}</p>
 </details>;
}

function ExecutionDiagnostics({research}:{research?:ExecutionResearch}){
 if(!research)return null;
 return <details className="notice"><summary>Historical liquidity and execution stress</summary>
  <p>{research.positions} simulated positions · {research.zero_volume_endpoint_positions} with zero-volume entry or exit observations.</p>
  <p className="muted tiny">Fixed hypothetical starting notionals; {research.lookback_observations}-observation prior median and realized full-day traded-value proxy, illustrative {research.participation_limit_percent}% participation threshold.</p>
  <div className="tablewrap"><table><thead><tr><th>Hypothetical entry value</th><th>Within proxy limit</th><th>Exceeds proxy limit / zero volume</th><th>Unknown</th></tr></thead><tbody>{research.notional_scenarios.map(s=><tr key={s.entry_notional_inr}><td>{money(s.entry_notional_inr)}</td><td>{s.within_proxy_limit}</td><td>{s.exceeds_proxy_limit}</td><td>{s.unknown}</td></tr>)}</tbody></table></div>
  {research.friction_scenarios.length>0&&<div className="tablewrap"><table><thead><tr><th>Additional friction per side</th><th>Total assumed friction per side</th><th>Net simulated return</th><th>Maximum drawdown</th></tr></thead><tbody>{research.friction_scenarios.map(s=><tr key={s.extra_bps_per_side}><td>{s.extra_bps_per_side} bps</td><td>{s.total_bps_per_side} bps</td><td>{s.net_return_percent}%</td><td>{s.max_drawdown_percent}%</td></tr>)}</tbody></table></div>}
  <p className="muted tiny">{research.notice}</p>
 </details>;
}

function ChronologicalResearch({research}:{research?:ChronologicalValidation}){
 if(!research)return null;
 return <section className="notice"><strong>Repeated chronological test windows</strong>
  <p>{research.observed_folds}/{research.eligible_folds} windows with simulated positions · {research.no_signal_folds} without signals.</p>
  {research.eligible_folds===0?<p>Insufficient history for two complete nonoverlapping holding windows.</p>:<>
   <div className="tablewrap"><table><thead><tr><th>Exposure dates</th><th>Positions</th><th>Cost per side</th><th>Net simulated return</th><th>Net same-stock reference</th><th>Gross Nifty 50 index</th><th>Maximum drawdown</th></tr></thead><tbody>{research.folds.flatMap(fold=>fold.cost_scenarios.length?fold.cost_scenarios.map(cost=><tr key={fold.fold+":"+cost.cost_bps_per_side}><td>{fold.exposure_start} to {fold.test_end}</td><td>{fold.trades}{fold.small_sample?" · small sample":""}</td><td>{cost.cost_bps_per_side} bps</td><td>{cost.net_return_percent}%</td><td>{cost.net_same_stock_buy_hold_percent}%</td><td>{cost.gross_nifty50_price_index_percent==null?"Unavailable":cost.gross_nifty50_price_index_percent+"%"}</td><td>{cost.max_drawdown_percent}%</td></tr>):[<tr key={fold.fold}><td>{fold.exposure_start} to {fold.test_end}</td><td>{fold.trades}</td><td colSpan={5}>No signals — no return estimate</td></tr>])}</tbody></table></div>
   {research.cost_summaries.map(cost=><p className="tiny" key={cost.cost_bps_per_side}>{cost.cost_bps_per_side} bps: {cost.positive_folds} positive, {cost.negative_folds} negative, {cost.flat_folds} flat observed windows · range {cost.worst_observed_return_percent}% to {cost.best_observed_return_percent}%</p>)}
  </>}
  <p className="muted tiny">{research.notice}</p>
 </section>;
}

function MarketRegimeResearch({research}:{research?:RegimeResearch}){
 if(!research)return null;
 return <section className="notice"><strong>Signal-date market trend cohorts</strong>
  <p>{research.classified_trades}/{research.total_trades} positions classified · {research.lookback_observations} observed-session lookback · ±{research.threshold_percent}% illustrative Nifty 50 price trend thresholds.</p>
  <div className="tablewrap"><table><thead><tr><th>Trend at signal</th><th>Positions</th><th>Cost per side</th><th>Mean net position return</th><th>Wins / losses / flat</th></tr></thead><tbody>{research.groups.flatMap(group=>group.cost_scenarios.length?group.cost_scenarios.map(cost=><tr key={group.regime+cost.cost_bps_per_side}><td>{words(group.regime)}{group.small_sample?" · small sample":""}</td><td>{group.trades}</td><td>{cost.cost_bps_per_side} bps</td><td>{cost.mean_trade_return_percent}%</td><td>{cost.wins} / {cost.losses} / {cost.flat}</td></tr>):[<tr key={group.regime}><td>{words(group.regime)}</td><td>{group.trades}</td><td colSpan={3}>Unavailable</td></tr>])}</tbody></table></div>
  <p className="muted tiny">{research.notice}</p>
 </section>;
}

function StrategyValidation({data,horizon}:{data:Validation;horizon:Horizon}){
 const result=data.horizons?.[horizon];
 return <section className="panel glass" aria-label="Automatic historical strategy validation">
  <div className="sectionhead"><div><h3>Historical strategy replay</h3><p className="muted tiny">Existing fixed rules tested on later chronological data, not a forecast.</p></div><span className="tag">RESEARCH ONLY</span></div>
  <p>{data.sample_count??0} recently attempted registry instruments · {result?.observed_instruments??0} instruments with completed simulated positions</p>
  {result&&<p className="muted tiny">{Object.entries(result.counts).map(([state,count])=>words(state)+": "+count).join(" · ")}</p>}
  {result?.calendar_withheld?.map(item=><details className="notice" key={item.exchange+":"+item.symbol}><summary>{item.symbol} · {item.exchange} · historical calendar evidence withheld</summary><CalendarAudit audit={item}/></details>)}
  {!result?.items.length?<p>No usable replay results yet. Adjusted, validated history, usable recorded corporate-action context, matched stored sessions and a sufficient holdout window are required.</p>:result.items.map(item=><details key={item.exchange+":"+item.symbol}><summary>{item.symbol} · {item.exchange} · {item.trades} simulated positions{item.small_sample?" · small sample":""}</summary>
   <p>{item.test_start} to {item.test_end} · {item.holding_sessions} session holding window · gross same-asset buy and hold {item.gross_buy_hold_percent}%.</p>
   <div className="tablewrap"><table><thead><tr><th>Cost per side</th><th>Net simulated return</th><th>Net same-stock buy &amp; hold</th><th>Difference (pp)</th><th>Nifty 50 price index (gross)</th><th>Net strategy minus index (pp)</th><th>Maximum drawdown</th><th>Win rate</th><th>Wins / losses / flat</th></tr></thead><tbody>{item.cost_scenarios.map(cost=><tr key={cost.cost_bps_per_side}><td>{cost.cost_bps_per_side} bps</td><td>{cost.net_return_percent}%</td><td>{cost.net_same_stock_buy_hold_percent==null?"Unavailable":cost.net_same_stock_buy_hold_percent+"%"}</td><td>{cost.net_difference_vs_same_stock_pp==null?"Unavailable":cost.net_difference_vs_same_stock_pp+" pp"}</td><td>{cost.gross_nifty50_price_index_percent==null?"Unavailable":cost.gross_nifty50_price_index_percent+"%"}</td><td>{cost.net_difference_vs_nifty50_pp==null?"Unavailable":cost.net_difference_vs_nifty50_pp+" pp"}</td><td>{cost.max_drawdown_percent}%</td><td>{cost.win_rate_percent===null?"—":cost.win_rate_percent+"%"}</td><td>{cost.wins} / {cost.losses} / {cost.flat}</td></tr>)}</tbody></table></div>
   <HistoryProvenanceDetails audit={item.history_provenance}/>
   <ExecutionDiagnostics research={item.execution_research}/>
   <ChronologicalResearch research={item.chronological_validation}/>
   <MarketRegimeResearch research={item.market_regime_research}/>
   <p className="muted tiny">Same holdout interval, one buy-and-hold round trip versus the strategy's simulated round trips. Illustrative all-in costs; not actual broker fees. Nifty 50 is a gross price-index reference (not total return or executable), shown only for matching observed dates. Net strategy minus gross index is not alpha.</p>
  </details>)}
  <p className="muted tiny">{data.notice||"Historical validation unavailable or disabled."} Existing recommendation blockers remain unchanged.</p>
 </section>;
}

export default function HorizonResearch({horizon,children,onSettings}:{horizon:Horizon;children:ReactNode;onSettings:()=>void}){
 const [data,setData]=useState<Snapshot|null>(null);
 const [error,setError]=useState(false);
 useEffect(()=>{
  if(horizon==="INTRADAY")return;
  return visiblePolling(async signal=>{
   try{
    const response=await fetch("/intelligence/api/v1/intelligence/research/overview",{cache:"no-store",signal});
    if(!response.ok)throw Error();
    const result:Snapshot=await response.json();if(!Array.isArray(result.sections))throw Error();
    if(!signal.aborted){setData(result);setError(false);}
   }catch{if(!signal.aborted)setError(true);}
  },30000);
 },[horizon]);
 const sections=data?.sections.filter(s=>s.section==="NSE"||s.section==="BSE")||[];
 const ready=sections.filter(s=>s.status==="READY"&&data?.enabled&&!error&&s.result?.horizons?.[horizon]);
 const ranked=ready.flatMap(s=>s.result!.horizons![horizon]!.candidates).sort((a,b)=>b.rank_score-a.rank_score||a.exchange.localeCompare(b.exchange)||a.symbol.localeCompare(b.symbol)).slice(0,5);
 const blockers=[...new Set(ready.flatMap(s=>s.result!.horizons![horizon]!.blockers))];
 return <section className="horizon-workspace" aria-label={titles[horizon]}>
  <section className="panel glass horizon-hero">
   <div className="sectionhead"><div><small className="section-kicker">AUTOMATIC RESEARCH</small><h2>{titles[horizon]}</h2><p>{descriptions[horizon]}</p></div><span className="tag">{horizon!=="INTRADAY"&&error?"UNAVAILABLE":horizon!=="INTRADAY"&&data?.enabled===false?"AUTOMATION OFF":"RESEARCH ONLY"}</span></div>
   {horizon!=="INTRADAY"&&<>
   {!data&&!error&&<p role="status">Loading saved research…</p>}
   {error&&<p role="alert" className="notice warning-notice">Research service is unavailable. No previous candidates are shown as current.</p>}
   {data?.enabled===false&&<p className="notice warning-notice">Automatic research is disabled.</p>}
   <div className="horizon-coverage">{sections.map(s=><div key={s.section}><strong>{s.section}</strong><span>{ready.includes(s)?(s.result?.eligible_count||0)+" / "+(s.result?.universe_size||0)+" daily histories eligible":s.status==="READY"?"Waiting for horizon refresh":words(s.status)}</span>{ready.includes(s)&&s.result?.discovery_coverage&&<small>{s.result.discovery_coverage.selected_count} selected from {s.result.discovery_coverage.recent_registry_count} active equities with recent completed data</small>}{ready.includes(s)&&s.result?.discovery_coverage?.expected_session_count!=null&&<small>{s.result.discovery_coverage.expected_session_count} recent registry equities match the expected session</small>}{ready.includes(s)&&s.result?.history_coverage?.[horizon]&&<small>{s.result.history_coverage[horizon]?.eligible_histories} usable histories with at least {s.result.history_coverage[horizon]?.minimum_observations} observations (before strategy filters)</small>}{ready.includes(s)&&s.result?.discovery_coverage?.calendar_status&&<small>{s.result.discovery_coverage.calendar_status==="PUBLISHED_SESSION"?"Expected completed session: "+s.result.discovery_coverage.expected_session:"Calendar not verified · calendar-day freshness only"}</small>}{ready.includes(s)&&!!s.result?.skipped?.RAW_CORPORATE_ACTION&&<small>{s.result.skipped.RAW_CORPORATE_ACTION} raw histories excluded for recorded corporate actions</small>}</div>)}</div>
   {ready.map(s=>{const review=s.result?.corporate_action_review;return review&&(review.normalized_preview_count>0||review.withheld_count>0)?<details key={s.section}><summary>{s.section} · corporate action diagnostics ({review.normalized_preview_count} previews, {review.withheld_count} withheld)</summary><p>{review.notice}</p>{review.previews.map(p=><article key={p.exchange+":"+p.symbol}><strong>{p.symbol} · known-action price-only preview</strong><p>{p.first_date} – {p.as_of} · {p.observations} observations</p><ul>{p.actions.map(a=><li key={a.ex_date}>{words(a.action_type)} · {a.ex_date} · {a.post_shares_per_pre_share} post-event shares per pre-event share</li>)}</ul><p>Normalized daily price change: {p.change_1d_percent===null?"Unavailable":p.change_1d_percent+"%"} · 20-observation change: {p.change_20_observation_percent===null?"Unavailable":p.change_20_observation_percent+"%"} · Window price change: {p.window_price_change_percent}%</p><p className="muted tiny">{p.notice}</p></article>)}</details>:null;})}
   <p className="muted tiny">Bounded registry sample, prioritized by latest completed daily traded value; not a whole-market ranking. Missing source evidence is never replaced with estimates.</p>
   </>}
  </section>
  {horizon==="INTRADAY"?<IntradayResearch/>:<section className="panel glass horizon-results">
   <div className="sectionhead"><div><h3>Technical watch candidates</h3><p className="muted tiny">Up to five observations across the available NSE/BSE samples.</p></div></div>
   {ranked.length?<div className="horizon-cards">{ranked.map((candidate,index)=><article className="horizon-card" key={candidate.exchange+":"+candidate.id}>
    <header><div><small>#{index+1} · {candidate.exchange}</small><h3>{candidate.symbol}</h3></div><strong>{money(candidate.close)}</strong></header>
    <p className="muted tiny">Daily close · {candidate.as_of}</p><p>{candidate.review_horizon}</p>
    <dl><div><dt>ATR / price</dt><dd>{candidate.atr_percent.toFixed(2)}%</dd></div><div><dt>History</dt><dd>{candidate.history_count} sessions</dd></div></dl>
    <details><summary>Why this appears &amp; risks</summary><ul>{candidate.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul><p>{candidate.warnings.join(" ")}</p><p className="muted tiny">Median historical daily traded value: {money(candidate.median_daily_traded_value)}</p></details>
    {candidate.price_structure&&<PriceStructureDetails evidence={candidate.price_structure}/>}
    {candidate.research_reliability&&<details><summary>{candidate.research_reliability.status==="REVIEW_CONFLICTING_EVIDENCE"?"Conflicting evidence · review needed":"Evidence reliability · watch only"}</summary>
     {candidate.research_reliability.warnings.length>0&&<ul>{candidate.research_reliability.warnings.map(w=><li key={w}>{words(w)}</li>)}</ul>}
     <p>Unresolved requirements: {candidate.research_reliability.blockers.map(words).join(" · ")||"Full strategy validation still required"}.</p>
     <p className="muted tiny">{candidate.research_reliability.notice}</p>
    </details>}
    {candidate.research_conclusion&&<div className="notice"><strong>{candidate.research_conclusion.status==="REVIEW_REQUIRED"?"Review required":"Research conclusion · watch only"}</strong><p>{candidate.research_conclusion.summary}</p><details><summary>Complete evidence &amp; reassessment</summary><dl>{Object.entries(candidate.research_conclusion.evidence).map(([key,value])=><div key={key}><dt>{words(key)}</dt><dd>{words(value)}</dd></div>)}</dl>{candidate.research_conclusion.warnings.length>0&&<ul>{candidate.research_conclusion.warnings.map(w=><li key={w}>{words(w)}</li>)}</ul>}<p>Remaining qualification requirements: {candidate.research_conclusion.blockers.map(words).join(" · ")||"Full qualification not established"}.</p><ul>{candidate.research_conclusion.reassessment_conditions.map(condition=><li key={condition}>{condition}</li>)}</ul><small>{candidate.research_conclusion.notice}</small></details></div>}
    {candidate.matched_strategy_replay&&<details><summary>Same-stock historical replay · {candidate.matched_strategy_replay.trades} simulated positions</summary><p>Through {candidate.matched_strategy_replay.as_of}{candidate.matched_strategy_replay.small_sample?" · small sample":""}</p>{candidate.matched_strategy_replay.cost_scenarios.map(cost=><p key={cost.cost_bps_per_side}>{cost.cost_bps_per_side} bps per side · net simulated return {cost.net_return_percent}% · drawdown {cost.max_drawdown_percent}%{cost.gross_nifty50_price_index_percent!=null&&<> · Nifty 50 gross price index {cost.gross_nifty50_price_index_percent}% · net minus index {cost.net_difference_vs_nifty50_pp} pp</>}</p>)}<HistoryProvenanceDetails audit={candidate.matched_strategy_replay.history_provenance}/><ExecutionDiagnostics research={candidate.matched_strategy_replay.execution_research}/><ChronologicalResearch research={candidate.matched_strategy_replay.chronological_validation}/><MarketRegimeResearch research={candidate.matched_strategy_replay.market_regime_research}/><p className="muted tiny">{candidate.matched_strategy_replay.notice}</p></details>}
    <CompanyEvidenceCard evidence={candidate.company_evidence} status={data?.automatic_company_status}/>
    <AutomaticCompanyNews evidence={candidate.news_evidence} status={data?.automatic_news_status}/>
    {candidate.ai_review?.reviews.length?<details><summary>Automatic AI evidence review ({candidate.ai_review.reviews.length} provider{candidate.ai_review.reviews.length===1?"":"s"})</summary>{candidate.ai_review.reviews.map(review=><div key={review.provider}><strong>{review.provider}</strong><ul>{review.findings.map((finding,i)=><li key={i}>{finding.statement} <small>[{finding.evidence_ids.join(", ")}]</small></li>)}</ul></div>)}<p className="muted tiny">OBS = dated technical observations; FUND = reported annual financial trends; REPLAY = same-stock historical simulation; LIMITS = missing research evidence. {candidate.ai_review.notice}</p></details>:<p className="muted tiny">{data?.automatic_ai_status==="ENABLED"?"AI review pending or unavailable.":data?.automatic_ai_status==="NO_CONFIGURED_PROVIDER"?"No permitted AI provider configured.":"Automatic AI review unavailable or disabled."}</p>}
   </article>)}</div>:<div className="research-empty"><strong>{ready.length?"No technical candidates meet the current rules":"Waiting for current research"}</strong><p>The background engine will reassess available evidence automatically. No manual scan is required.</p></div>}
   {blockers.length>0&&<p className="notice warning-notice">Still required before a complete investment verdict: {blockers.map(words).join(" · ")}.</p>}
   <button type="button" className="secondary" onClick={onSettings}>Check data connections</button>
  </section>
  }
  {horizon!=="INTRADAY"&&data?.enabled&&!error&&data.research_reliability&&<ProspectiveReliability report={data.research_reliability.horizons?.[horizon]}/>}
  {horizon!=="INTRADAY"&&data?.enabled&&!error&&data.strategy_validation&&<StrategyValidation data={data.strategy_validation} horizon={horizon}/>}
  {horizon!=="INTRADAY"&&<AdvancedSection title="Research history and outcomes" description="Automatically tracked dated technical watches"><WatchOutcomeHistory horizon={horizon}/></AdvancedSection>}
  <details className="advanced-tools glass" key={horizon}><summary><span><strong>Advanced research tools</strong><small>Optional detailed analysis and evidence review</small></span><b>Open tools</b></summary>{/* Closed tools stay available without loading their workflows. */}<DeferredTools>{children}</DeferredTools></details>
 </section>;
}
function DeferredTools({children}:{children:ReactNode}){
 // Existing tools are preserved. Explicitly mount only after user request.
 const [open,setOpen]=useState(false);
 return <div className="advanced-tools-content">{open?children:<button type="button" className="secondary" onClick={()=>setOpen(true)}>Load detailed tools</button>}</div>;
}

function PriceStructureDetails({evidence}:{evidence:PriceStructure}){
 return <details><summary>Price structure &amp; risk scenarios</summary>
 {evidence.status==="HISTORICAL_STRUCTURE"?<><dl>{Object.entries(evidence.indicators??{}).map(([key,value])=><div key={key}><dt>{words(key)}</dt><dd>{key==="historical_volatility_20"?(value*100).toFixed(2)+"%":value.toFixed(2)}</dd></div>)}</dl>
 {(["support","resistance"] as const).map(kind=><div key={kind}><strong>{kind==="support"?"Confirmed support below close":"Confirmed resistance above close"}</strong>{evidence[kind].length?<ul>{evidence[kind].map(p=><li key={p.observed_on}>{money(p.price)} · observed {p.observed_on} · confirmed {p.confirmed_on}</li>)}</ul>:<p>No confirmed reference level.</p>}</div>)}
 {evidence.weekly?.status==="OBSERVED_WEEK_AGGREGATES"?<p>Observed-week trend: {words(evidence.weekly.trend??"UNKNOWN")} · through {evidence.weekly.last_observed_date} · {evidence.weekly.week_count} weeks. Not calendar-verified complete weekly bars.</p>:<p>Weekly trend evidence unavailable.</p>}
 </>:<p>Price structure evidence unavailable.</p>}
 {evidence.scenario?<><h4>Illustrative historical geometry</h4><dl><div><dt>Dated reference close</dt><dd>{money(evidence.scenario.reference_close)}</dd></div><div><dt>Lower reference</dt><dd>{money(evidence.scenario.lower_reference)}</dd></div><div><dt>Upper reference</dt><dd>{money(evidence.scenario.upper_reference)}</dd></div><div><dt>Illustrative downside</dt><dd>{evidence.scenario.downside_percent.toFixed(2)}%</dd></div><div><dt>Illustrative upside</dt><dd>{evidence.scenario.upside_percent.toFixed(2)}%</dd></div><div><dt>Reward / risk</dt><dd>{evidence.scenario.reward_to_risk.toFixed(2)}×</dd></div></dl><p>Assumed cost: {evidence.scenario.cost_bps_per_side} bps each side.</p></>:<p>Scenario withheld: {words(evidence.scenario_status)}.</p>}
 <p className="muted tiny">{evidence.notice}</p></details>;
}
