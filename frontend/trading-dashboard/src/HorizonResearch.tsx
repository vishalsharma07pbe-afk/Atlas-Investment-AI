import {BracketView,BracketSummaryView,type BracketEvidence,type BracketSummary} from "./BracketResearchView";
import {CalibrationView,ScoreEvidenceView,type CalibrationReport,type ScoreEvidence} from "./ScoreCalibrationView";
import OfficialSectorView,{type OfficialSectorEvidence} from "./OfficialSectorView";
import SectorPriceView,{type SectorPriceEvidence} from "./SectorPriceView";
import FinancialFilingView,{type FilingEvidence} from "./FinancialFilingView";
import {EvidenceBars} from "./TerminalCharts";
import {visiblePolling} from "./visiblePolling";
import {useEffect,useRef,useState,type ReactNode} from "react";
import WatchOutcomeHistory from "./WatchOutcomeHistory";
import IntradayResearch from "./IntradayResearch";
import AdvancedSection from "./AdvancedSection";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
import AutomaticCompanyNews,{type NewsEvidence} from "./AutomaticCompanyNews";

export type Horizon="INTRADAY"|"SWING"|"SHORT_TERM"|"LONG_TERM";
export type WatchReportTarget={exchange:string;id:number;isin:string;as_of:string};
type ClaimComparison={status:string;matched_count:number;contradicted_count:number;rejected_count:number;duplicate_count:number;shared_matches:{path:string;providers:string[]}[];conflicts:{path:string;matching_providers:string[];contradicting_providers:string[]}[];notice:string};
type CommitteeCoverage={claim_comparison?:ClaimComparison;status:string;configured_count:number;reviewed_count:number;members:{provider:string;role:string;status:string;cited_domains:string[]}[];available_domains:string[];cited_domains:string[];uncited_domains:string[];agreement_status:string;notice:string};
type AiReview={committee?:CommitteeCoverage;reviews:{provider:string;role?:string;findings:{statement:string;evidence_ids:string[]}[]}[];reviewed_at:string;notice:string};
type CandidateReliability={status:string;blockers:string[];warnings:string[];prospective_status:string;notice:string};
type ResearchConclusion={report_version?:string;qualification_status?:string;supporting_evidence?:string[];next_evidence_checks?:string[];status:string;summary:string;blockers:string[];warnings:string[];evidence:Record<string,string>;reassessment_conditions:string[];notice:string};
type RegimeResearch={status:string;lookback_observations:number;threshold_percent:number;classified_trades:number;total_trades:number;groups:{regime:string;trades:number;small_sample:boolean;cost_scenarios:{cost_bps_per_side:number;mean_trade_return_percent:number;win_rate_percent:number;wins:number;losses:number;flat:number}[]}[];notice:string};
type ExecutionResearch={status:string;positions:number;lookback_observations:number;participation_limit_percent:number;zero_volume_endpoint_positions:number;notional_scenarios:{entry_notional_inr:number;within_proxy_limit:number;exceeds_proxy_limit:number;unknown:number}[];base_friction_bps_per_side:number;friction_scenarios:{extra_bps_per_side:number;total_bps_per_side:number;net_return_percent:number;max_drawdown_percent:number}[];notice:string};
type ChronologicalValidation={status:string;eligible_folds:number;observed_folds:number;no_signal_folds:number;folds:{fold:number;status:string;exposure_start:string;test_end:string;trades:number;small_sample:boolean;cost_scenarios:{cost_bps_per_side:number;net_return_percent:number;net_same_stock_buy_hold_percent:number;gross_nifty50_price_index_percent?:number;net_difference_vs_nifty50_pp?:number;max_drawdown_percent:number}[]}[];cost_summaries:{cost_bps_per_side:number;positive_folds:number;negative_folds:number;flat_folds:number;worst_observed_return_percent:number;best_observed_return_percent:number}[];notice:string};
type CalendarContinuity={status:string;calendar_days:number;regular_sessions:number;missing_sessions:number;unexpected_observations:number;unknown_days:number;special_days:number;missing_dates:string[];unexpected_dates:string[];unknown_dates:string[];special_dates:string[];notice:string};
type ListingEvidence={status:string;listed_on:string|null;delisted_on:string|null;registry_source:string|null;registry_revision:string|null;universe_basis:string;historical_universe_verified:boolean;notice:string};
type HistoryProvenance={listing_evidence?:ListingEvidence;calendar_continuity?:CalendarContinuity;status:string;history_observations:number;first_date:string;last_date:string;overlap_observations:number;changed_observations:number;changed_dates:string[];corporate_action_status:string;notice:string};
type JointCost={cost_bps_per_side:number;mean_trade_return_percent:number;median_trade_return_percent:number;worst_trade_return_percent:number;worst_position_drawdown_percent:number;win_rate_percent:number;wins:number;losses:number;flat:number};
type JointGroup={trend:string;volatility_regime:string;trades:number;small_sample:boolean;cost_scenarios:JointCost[]};
type JointRegimeResearch={status:string;classified_trades:number;total_trades:number;unknown_trades:number;groups:JointGroup[];notice:string};
type CurrentRegimeReplay={status:string;as_of:string;trend:string;volatility_regime:string;trades:number;cost_scenarios:JointCost[];notice:string};
type MatchedReplay={bracket_replay?:BracketSummary;joint_regime_research?:JointRegimeResearch;history_provenance?:HistoryProvenance;execution_research?:ExecutionResearch;chronological_validation?:ChronologicalValidation;market_regime_research?:RegimeResearch;market_benchmark_status?:string;as_of:string;trades:number;small_sample:boolean;cost_scenarios:{cost_bps_per_side:number;net_return_percent:number;max_drawdown_percent:number;gross_nifty50_price_index_percent?:number;net_difference_vs_nifty50_pp?:number}[];notice:string};
type Pivot={price:number;observed_on:string;confirmed_on:string};
type RiskSensitivity={status:string;observed_gap_count:number;worst_adverse_open_gap_percent:number;worst_adverse_gap_date:string|null;assumed_gap_floor_percent:number;stress_gap_percent:number;stressed_lower_reference:number;illustrative_ratio:number;scenarios:{cost_bps_per_side:number;upside_percent:number;downside_percent:number;stressed_downside_percent:number;reward_to_risk:number|null;stressed_reward_to_risk:number|null;illustrative_price_ceiling:number|null;stressed_price_ceiling:number|null;reference_meets_ratio:boolean;reference_meets_stressed_ratio:boolean}[];notice:string};
type PriceStructure={risk_sensitivity?:RiskSensitivity|null;status:string;scenario_status:string;support:Pivot[];resistance:Pivot[];indicators?:Record<string,number>;weekly?:{status:string;last_observed_date?:string;week_count?:number;trend?:string;sma_10?:number;sma_20?:number|null};scenario:{reference_close:number;lower_reference:number;upper_reference:number;cost_bps_per_side:number;downside_percent:number;upside_percent:number;reward_to_risk:number}|null;notice:string};
type FollowEvent={direction:string;status:string;signal_date:string;boundary:number;signal_close:number;break_percent:number;relative_volume:number;volume_context:string;followup_count:number;reentry_date:string|null};
type Followthrough={status:string;as_of?:string;events:FollowEvent[];notice:string};
type BreakoutReview={evaluated_count:number;event_listing_count:number;items:{id:number;symbol:string;exchange:string;as_of:string;followthrough:Followthrough}[];notice:string};
type Pressure={breakout_followthrough?:Followthrough;status:string;as_of?:string;relative_volume?:number;change_percent?:number;close_range_position?:number|null;prior_median_traded_value?:number;adjustment_status?:string;findings:string[];notice:string};
type PressureRow={id:number;symbol:string;exchange:string;as_of:string;price_volume_pressure:Pressure;deal_evidence?:DealEvidence};
type PressureReview={evaluated_count:number;flagged_count:number;downside_items:PressureRow[];upside_items:PressureRow[];notice:string};
type DealEvidence={same_date_groups?:{deal_type:string;buy_quantity:string;sell_quantity:string}[];same_date_notice?:string;status:string;latest_date:string;groups:{deal_type:string;record_count:number;buy_quantity:string;sell_quantity:string;buy_reported_value_inr:string;sell_reported_value_inr:string}[];recent_records:{trade_date:string;deal_type:string;client_name:string;side:string;quantity:string;price_inr:string;source_report:string}[];notice:string};
type GlobalExposure={status:string;sector?:string;industry?:string;questions:{factor:string;indicator:string;as_of:string;change:{start_date:string;end_date:string;value:number;unit:string};question:string}[];missing_factors:string[];notice:string};
type QualificationGate={domain:string;status:string;requirements:string[]};
type StockQualification={status:string;gates:QualificationGate[];blockers:string[];review_findings:string[];notice:string};
type WatchReference={exchange:string;id:number;isin:string};
type CompanySelection={unique_company_count:number;unidentified_listing_count:number;conflicting_listing_count:number;cross_venue_company_count:number;review_company_count:number;ready_markets:string[];watch_refs:WatchReference[];preliminary_watch_refs?:WatchReference[];notice:string};
type CompanyContext={listing_count:number;venues:string[];blockers:string[];review_findings:string[];status:string};
type QualificationSummary={selection?:CompanySelection;status:string;reviewed_count:number;review_required_count:number;qualified_count:number|null;recommendations:unknown[];leading_blockers:{code:string;count:number}[];notice:string};
type ReportCloseHistory={adjustment_status:string;as_of:string;points:{date:string;close:number}[]};
type CompanyVenueContext={status:string;preferred_exchange:string|null;representative_exchange:string;observed_venues:string[];screen_matching_venues:string[];venue_observations:{exchange:string;as_of:string|null;close:number|null;turnover_proxy_cr:number|null;security_state:string;quote:{spread_percent:number;observed_at:string}|null}[];review_findings:string[];notice:string};
type Candidate={bracket_research?:BracketEvidence;score_evidence?:ScoreEvidence;official_sector_benchmark?:OfficialSectorEvidence;sector_price_context?:SectorPriceEvidence;independent_financial_evidence?:FilingEvidence;exchange_surveillance?:{status:string;report_date:string;source_url:string;findings:string[];notice:string};company_venue_context?:CompanyVenueContext;report_close_history?:ReportCloseHistory;isin?:string;selection_company_context?:CompanyContext;stock_qualification?:StockQualification;current_regime_replay?:CurrentRegimeReplay;global_exposure?:GlobalExposure;price_volume_pressure?:Pressure;deal_evidence?:DealEvidence;price_structure?:PriceStructure;research_conclusion?:ResearchConclusion;matched_strategy_replay?:MatchedReplay;research_reliability?:CandidateReliability;news_evidence?:NewsEvidence;company_evidence?:CompanyEvidence;ai_review?:AiReview;id:number;symbol:string;exchange:string;as_of:string;close:number;rank_score:number;review_horizon:string;history_count:number;atr_percent:number;median_daily_traded_value:number;reasons:string[];warnings:string[]};
type HorizonResult={status:string;candidates:Candidate[];matched_count:number;evaluated_count:number;blockers:string[];exclusions:Record<string,number>};
type ActionPreview={symbol:string;exchange:string;first_date:string;as_of:string;observations:number;actions:{ex_date:string;action_type:string;post_shares_per_pre_share:string}[];change_1d_percent:number|null;change_20_observation_percent:number|null;window_price_change_percent:number;notice:string};
type ActionReview={normalized_preview_count:number;withheld_count:number;previews:ActionPreview[];notice:string};
type Section={section:string;status:string;generated_at:string|null;result:{breakout_review?:BreakoutReview;price_volume_review?:PressureReview;universe_size:number;eligible_count:number;corporate_action_review?:ActionReview;company_research_coverage?:{distinct_eligible_isins:number;fresh_cached_reports:number;section_counts:Record<string,number>;notice:string};discovery_coverage?:{recent_registry_count:number;selected_count:number;calendar_status?:string;expected_session?:string|null;expected_session_count?:number|null};history_coverage?:Partial<Record<Horizon,{minimum_observations:number;eligible_histories:number}>>;skipped?:Record<string,number>;horizons?:Partial<Record<Horizon,HorizonResult>>}|null};
type ReplayCost={gross_nifty50_price_index_percent?:number;net_difference_vs_nifty50_pp?:number;net_same_stock_buy_hold_percent?:number;net_difference_vs_same_stock_pp?:number;cost_bps_per_side:number;net_return_percent:number;matched_gross_exposure_return_percent:number;max_drawdown_percent:number;win_rate_percent:number|null;wins:number;losses:number;flat:number};
type ReplayItem={joint_regime_research?:JointRegimeResearch;history_provenance?:HistoryProvenance;execution_research?:ExecutionResearch;chronological_validation?:ChronologicalValidation;market_regime_research?:RegimeResearch;exchange:string;symbol:string;as_of:string;trades:number;holding_sessions:number;test_start:string;test_end:string;gross_buy_hold_percent:number;small_sample:boolean;cost_scenarios:ReplayCost[]};
type Validation={status?:string;sample_count?:number;horizons?:Partial<Record<Horizon,{counts:Record<string,number>;observed_instruments:number;items:ReplayItem[];calendar_withheld?:(CalendarContinuity&{symbol:string;exchange:string})[];listing_withheld?:(ListingEvidence&{symbol:string;exchange:string})[]}>>;notice?:string};
type ReliabilityCohort={risk_path_summary?:{observed_paths:number;outcomes_without_path:number;coverage_percent:number;worst_entry_downside_percent:number|null;worst_close_drawdown_percent:number|null;notice:string};benchmark_summary?:{matched_outcomes:number;outcomes_without_benchmark:number;coverage_percent:number;mean_gross_price_index_percent:number|null;cost_scenarios:{cost_bps_per_side:number;mean_net_minus_price_index_pp:number;median_net_minus_price_index_pp:number;outperformed_count:number;underperformed_count:number;equal_count:number}[];notice:string};status:string;selected_mature_watches:number;observed_outcomes:number;distinct_observed_isins:number;coverage_percent:number;overlap_excluded:number;immature_excluded:number;incompatible_excluded:number;invalid_excluded:number;legacy_or_unverified_observed?:number;blockers:string[];cost_scenarios:{cost_bps_per_side:number;mean_net_change_percent:number;median_net_change_percent:number;positive_count:number;negative_count:number;flat_count:number}[];notice:string};
type Snapshot={bracket_research?:{horizons?:Partial<Record<Horizon,BracketSummary>>};score_calibration?:{horizons?:Partial<Record<Horizon,CalibrationReport>>};stock_qualification?:{horizons:Partial<Record<Horizon,QualificationSummary>>};research_reliability?:{status?:string;horizons?:Partial<Record<Horizon,ReliabilityCohort>>;notice?:string};strategy_validation?:Validation;enabled:boolean;sections:Section[];automatic_ai_status?:string;automatic_company_status?:string;automatic_news_status?:string};
const titles:Record<Horizon,string>={INTRADAY:"Intraday research",SWING:"Swing trading research",SHORT_TERM:"Short-term equity research",LONG_TERM:"Long-term investment research"};
const descriptions:Record<Horizon,string>={INTRADAY:"Completed current-session candle research. Live liquidity and event risk are not independently verified.",SWING:"Daily trend, relative volume and volatility checks for potential multi-session setups.",SHORT_TERM:"Medium-term trend and 60-session momentum. Fundamental and event research must still confirm each watch candidate.",LONG_TERM:"200-session price trend and longer-term momentum. A technical watch is not a business-quality or fair-value assessment."};
const words=(value:string)=>value.toLowerCase().replace(/_/g," ");
const money=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);

function ProspectiveReliability({report}:{report?:ReliabilityCohort}){
 return <section className="panel glass" aria-label="Prospective research reliability">
  <div className="sectionhead"><div><h3>Prospective watch reliability</h3><p className="muted tiny">Outcomes measured after original watch publication, not historical replay.</p></div><span className="tag">NOT CALIBRATED</span></div>
  {!report?<p>Prospective evidence unavailable.</p>:<>
   <p>{words(report.status)} · {report.observed_outcomes}/{report.selected_mature_watches} mature watches observed · {report.distinct_observed_isins} distinct ISINs · {report.coverage_percent}% coverage</p>
   {report.legacy_or_unverified_observed!=null&&<p className="muted tiny">{report.legacy_or_unverified_observed} legacy or unverified observed outcomes excluded from current metrics; retained in the selected mature-watch denominator.</p>}
   <p className="muted tiny">Excluded: {report.overlap_excluded} overlapping, {report.immature_excluded} immature, {report.incompatible_excluded} incompatible, {report.invalid_excluded} invalid.</p>
   {report.blockers.length>0&&<p>Evidence gaps: {report.blockers.map(words).join(" · ")}.</p>}
   {report.risk_path_summary&&<details><summary>Observed closing downside · {report.risk_path_summary.observed_paths} matched paths</summary><p>{report.risk_path_summary.coverage_percent}% of selected mature watches · {report.risk_path_summary.outcomes_without_path} observed returns without path evidence.</p><p>Worst entry downside: {report.risk_path_summary.worst_entry_downside_percent==null?"Unavailable":report.risk_path_summary.worst_entry_downside_percent+"%"} · Worst closing drawdown: {report.risk_path_summary.worst_close_drawdown_percent==null?"Unavailable":report.risk_path_summary.worst_close_drawdown_percent+"%"}</p><p className="muted tiny">{report.risk_path_summary.notice}</p></details>}
   {report.benchmark_summary&&<details><summary>Matched Nifty 50 price-index comparison · {report.benchmark_summary.matched_outcomes} observations</summary><p>{report.benchmark_summary.coverage_percent}% of selected mature watches · {report.benchmark_summary.outcomes_without_benchmark} observed returns without matched index evidence.</p>{report.benchmark_summary.mean_gross_price_index_percent!=null&&<p>Mean gross price-index change: {report.benchmark_summary.mean_gross_price_index_percent}%</p>}{report.benchmark_summary.cost_scenarios.map(row=><p key={row.cost_bps_per_side}>{row.cost_bps_per_side} bps per side · Mean net difference {row.mean_net_minus_price_index_pp} pp · Median {row.median_net_minus_price_index_pp} pp · Above / below / equal: {row.outperformed_count} / {row.underperformed_count} / {row.equal_count}</p>)}<p className="muted tiny">{report.benchmark_summary.notice}</p></details>}
   {report.cost_scenarios.length>0&&<details><summary>Illustrative friction sensitivity</summary><div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Cost per side"><table><thead><tr><th>Cost per side</th><th>Mean net change</th><th>Median net change</th><th>Positive / negative / flat</th></tr></thead><tbody>{report.cost_scenarios.map(row=><tr key={row.cost_bps_per_side}><td>{row.cost_bps_per_side} bps</td><td>{row.mean_net_change_percent}%</td><td>{row.median_net_change_percent}%</td><td>{row.positive_count} / {row.negative_count} / {row.flat_count}</td></tr>)}</tbody></table></div></details>}
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

function ListingAudit({audit}:{audit:ListingEvidence}){
 return <div><p>Listing evidence: {words(audit.status)}.</p>
  <p>Recorded listing: {audit.listed_on??"Unavailable"} · Recorded delisting: {audit.delisted_on??"Not recorded"}.</p>
  {audit.registry_source&&<p>Registry source: {audit.registry_source} · Revision: {audit.registry_revision??"Unavailable"}</p>}
  {!audit.historical_universe_verified&&<p>Historical universe not verified — current active-registry sample only.</p>}
  {audit.status==="LISTING_EVIDENCE_UNAVAILABLE"&&<p>Descriptive replay only; not attached to current stock watches.</p>}
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
  {audit.listing_evidence&&<ListingAudit audit={audit.listing_evidence}/> }
  <p className="muted tiny">{audit.notice}</p>
 </details>;
}

function ExecutionDiagnostics({research}:{research?:ExecutionResearch}){
 if(!research)return null;
 return <details className="notice"><summary>Historical liquidity and execution stress</summary>
  <p>{research.positions} simulated positions · {research.zero_volume_endpoint_positions} with zero-volume entry or exit observations.</p>
  <p className="muted tiny">Fixed hypothetical starting notionals; {research.lookback_observations}-observation prior median and realized full-day traded-value proxy, illustrative {research.participation_limit_percent}% participation threshold.</p>
  <div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Hypothetical entry value"><table><thead><tr><th>Hypothetical entry value</th><th>Within proxy limit</th><th>Exceeds proxy limit / zero volume</th><th>Unknown</th></tr></thead><tbody>{research.notional_scenarios.map(s=><tr key={s.entry_notional_inr}><td>{money(s.entry_notional_inr)}</td><td>{s.within_proxy_limit}</td><td>{s.exceeds_proxy_limit}</td><td>{s.unknown}</td></tr>)}</tbody></table></div>
  {research.friction_scenarios.length>0&&<div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Additional friction per side"><table><thead><tr><th>Additional friction per side</th><th>Total assumed friction per side</th><th>Net simulated return</th><th>Maximum drawdown</th></tr></thead><tbody>{research.friction_scenarios.map(s=><tr key={s.extra_bps_per_side}><td>{s.extra_bps_per_side} bps</td><td>{s.total_bps_per_side} bps</td><td>{s.net_return_percent}%</td><td>{s.max_drawdown_percent}%</td></tr>)}</tbody></table></div>}
  <p className="muted tiny">{research.notice}</p>
 </details>;
}

function ChronologicalResearch({research}:{research?:ChronologicalValidation}){
 if(!research)return null;
 return <section className="notice"><strong>Repeated chronological test windows</strong>
  <p>{research.observed_folds}/{research.eligible_folds} windows with simulated positions · {research.no_signal_folds} without signals.</p>
  {research.eligible_folds===0?<p>Insufficient history for two complete nonoverlapping holding windows.</p>:<>
   <div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Exposure dates"><table><thead><tr><th>Exposure dates</th><th>Positions</th><th>Cost per side</th><th>Net simulated return</th><th>Net same-stock reference</th><th>Gross Nifty 50 index</th><th>Maximum drawdown</th></tr></thead><tbody>{research.folds.flatMap(fold=>fold.cost_scenarios.length?fold.cost_scenarios.map(cost=><tr key={fold.fold+":"+cost.cost_bps_per_side}><td>{fold.exposure_start} to {fold.test_end}</td><td>{fold.trades}{fold.small_sample?" · small sample":""}</td><td>{cost.cost_bps_per_side} bps</td><td>{cost.net_return_percent}%</td><td>{cost.net_same_stock_buy_hold_percent}%</td><td>{cost.gross_nifty50_price_index_percent==null?"Unavailable":cost.gross_nifty50_price_index_percent+"%"}</td><td>{cost.max_drawdown_percent}%</td></tr>):[<tr key={fold.fold}><td>{fold.exposure_start} to {fold.test_end}</td><td>{fold.trades}</td><td colSpan={5}>No signals — no return estimate</td></tr>])}</tbody></table></div>
   {research.cost_summaries.map(cost=><p className="tiny" key={cost.cost_bps_per_side}>{cost.cost_bps_per_side} bps: {cost.positive_folds} positive, {cost.negative_folds} negative, {cost.flat_folds} flat observed windows · range {cost.worst_observed_return_percent}% to {cost.best_observed_return_percent}%</p>)}
  </>}
  <p className="muted tiny">{research.notice}</p>
 </section>;
}

function MarketRegimeResearch({research}:{research?:RegimeResearch}){
 if(!research)return null;
 return <section className="notice"><strong>Signal-date market trend cohorts</strong>
  <p>{research.classified_trades}/{research.total_trades} positions classified · {research.lookback_observations} observed-session lookback · ±{research.threshold_percent}% illustrative Nifty 50 price trend thresholds.</p>
  <div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Trend at signal"><table><thead><tr><th>Trend at signal</th><th>Positions</th><th>Cost per side</th><th>Mean net position return</th><th>Wins / losses / flat</th></tr></thead><tbody>{research.groups.flatMap(group=>group.cost_scenarios.length?group.cost_scenarios.map(cost=><tr key={group.regime+cost.cost_bps_per_side}><td>{words(group.regime)}{group.small_sample?" · small sample":""}</td><td>{group.trades}</td><td>{cost.cost_bps_per_side} bps</td><td>{cost.mean_trade_return_percent}%</td><td>{cost.wins} / {cost.losses} / {cost.flat}</td></tr>):[<tr key={group.regime}><td>{words(group.regime)}</td><td>{group.trades}</td><td colSpan={3}>Unavailable</td></tr>])}</tbody></table></div>
  <p className="muted tiny">{research.notice}</p>
 </section>;
}

function StrategyValidation({data,horizon}:{data:Validation;horizon:Horizon}){
 const result=data.horizons?.[horizon];
 return <section className="panel glass" aria-label="Automatic historical strategy validation">
  <div className="sectionhead"><div><h3>Historical strategy replay</h3><p className="muted tiny">Existing fixed rules tested on later chronological data, not a forecast.</p></div><span className="tag">RESEARCH ONLY</span></div>
  <p>{data.sample_count??0} recently attempted registry instruments · {result?.observed_instruments??0} instruments with completed simulated positions</p>
  {result&&<p className="muted tiny">{Object.entries(result.counts).map(([state,count])=>words(state)+": "+count).join(" · ")}</p>}
  {result?.listing_withheld?.map(item=><details className="notice" key={item.exchange+":"+item.symbol+":listing"}><summary>{item.symbol} · {item.exchange} · listing evidence withheld</summary><ListingAudit audit={item}/></details>)}
  {result?.calendar_withheld?.map(item=><details className="notice" key={item.exchange+":"+item.symbol}><summary>{item.symbol} · {item.exchange} · historical calendar evidence withheld</summary><CalendarAudit audit={item}/></details>)}
  {!result?.items.length?<p>No usable replay results yet. Adjusted, validated history, usable recorded corporate-action context, matched stored sessions and a sufficient holdout window are required.</p>:result.items.map(item=><details key={item.exchange+":"+item.symbol}><summary>{item.symbol} · {item.exchange} · {item.trades} simulated positions{item.small_sample?" · small sample":""}</summary>
   <p>{item.test_start} to {item.test_end} · {item.holding_sessions} session holding window · gross same-asset buy and hold {item.gross_buy_hold_percent}%.</p>
   <div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Cost per side"><table><thead><tr><th>Cost per side</th><th>Net simulated return</th><th>Net same-stock buy &amp; hold</th><th>Difference (pp)</th><th>Nifty 50 price index (gross)</th><th>Net strategy minus index (pp)</th><th>Maximum drawdown</th><th>Win rate</th><th>Wins / losses / flat</th></tr></thead><tbody>{item.cost_scenarios.map(cost=><tr key={cost.cost_bps_per_side}><td>{cost.cost_bps_per_side} bps</td><td>{cost.net_return_percent}%</td><td>{cost.net_same_stock_buy_hold_percent==null?"Unavailable":cost.net_same_stock_buy_hold_percent+"%"}</td><td>{cost.net_difference_vs_same_stock_pp==null?"Unavailable":cost.net_difference_vs_same_stock_pp+" pp"}</td><td>{cost.gross_nifty50_price_index_percent==null?"Unavailable":cost.gross_nifty50_price_index_percent+"%"}</td><td>{cost.net_difference_vs_nifty50_pp==null?"Unavailable":cost.net_difference_vs_nifty50_pp+" pp"}</td><td>{cost.max_drawdown_percent}%</td><td>{cost.win_rate_percent===null?"—":cost.win_rate_percent+"%"}</td><td>{cost.wins} / {cost.losses} / {cost.flat}</td></tr>)}</tbody></table></div>
   <HistoryProvenanceDetails audit={item.history_provenance}/>
   <ExecutionDiagnostics research={item.execution_research}/>
   <ChronologicalResearch research={item.chronological_validation}/>
   <MarketRegimeResearch research={item.market_regime_research}/>
   <JointRegimeResearchView research={item.joint_regime_research}/>
   <p className="muted tiny">Same holdout interval, one buy-and-hold round trip versus the strategy's simulated round trips. Illustrative all-in costs; not actual broker fees. Nifty 50 is a gross price-index reference (not total return or executable), shown only for matching observed dates. Net strategy minus gross index is not alpha.</p>
  </details>)}
  <p className="muted tiny">{data.notice||"Historical validation unavailable or disabled."} Existing recommendation blockers remain unchanged.</p>
 </section>;
}

export default function HorizonResearch({horizon,children,onSettings,reportTarget}:{horizon:Horizon;children:ReactNode;onSettings:()=>void;reportTarget?:WatchReportTarget}){
 const [data,setData]=useState<Snapshot|null>(null);
 const [error,setError]=useState(false);
 const requestedDetails=useRef<HTMLDetailsElement|null>(null);
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
 const available=ready.flatMap(s=>s.result!.horizons![horizon]!.candidates);
 const selection=data?.stock_qualification?.horizons[horizon]?.selection;
 const ranked=selection?selection.watch_refs.flatMap(ref=>{const matches=available.filter(c=>c.exchange===ref.exchange&&c.id===ref.id&&c.isin===ref.isin);return matches.length===1?matches:[];}).slice(0,5):available.sort((a,b)=>b.rank_score-a.rank_score||a.exchange.localeCompare(b.exchange)||a.symbol.localeCompare(b.symbol)).slice(0,5);
 const preliminary=selection?(selection.preliminary_watch_refs??[]).flatMap(ref=>{const matches=available.filter(c=>c.exchange===ref.exchange&&c.id===ref.id&&c.isin===ref.isin);return matches.length===1?matches:[];}).slice(0,5):[];
 const preliminaryOnly=ranked.length===0&&preliminary.length>0;
 const displayed=preliminaryOnly?preliminary:ranked;
 const blockers=[...new Set(ready.flatMap(s=>s.result!.horizons![horizon]!.blockers))];
 // A briefing reference is never resolved by ticker or by a different venue.
 // Require exactly one current server-selected candidate; older snapshots
 // without canonical selection cannot confirm the requested report.
 const requestedMatches=reportTarget&&selection?ranked.filter(c=>c.exchange===reportTarget.exchange&&c.id===reportTarget.id&&c.isin===reportTarget.isin):[];
 const requested=requestedMatches.length===1?requestedMatches[0]:undefined;
 const requestedKey=requested?requested.exchange+":"+requested.id+":"+requested.isin:null;
 useEffect(()=>{
  if(!reportTarget||!requestedKey||!requestedDetails.current)return;
  const details=requestedDetails.current;
  details.open=true;
  details.querySelector("summary")?.focus({preventScroll:true});
  details.scrollIntoView?.({block:"start",behavior:"auto"});
 },[reportTarget,requestedKey]);
 return <section className="horizon-workspace" aria-label={titles[horizon]}>
  <section className="panel glass horizon-hero">
   <div className="sectionhead"><div><small className="section-kicker">AUTOMATIC RESEARCH</small><h2>{titles[horizon]}</h2><p>{descriptions[horizon]}</p></div><span className="tag">{horizon!=="INTRADAY"&&error?"UNAVAILABLE":horizon!=="INTRADAY"&&data?.enabled===false?"AUTOMATION OFF":"RESEARCH ONLY"}</span></div>
   {horizon!=="INTRADAY"&&<>
   {!data&&!error&&<p role="status">Loading saved research…</p>}
   {error&&<p role="alert" className="notice warning-notice">Research service is unavailable. No previous candidates are shown as current.</p>}
   {data?.enabled===false&&<p className="notice warning-notice">Automatic research is disabled.</p>}
   <div className="terminal-research-metrics" aria-label="Current research coverage"><article><span>Selected technical watches</span><strong>{data?.enabled&&!error?ranked.length:"—"}</strong></article><article><span>Markets with current evidence</span><strong>{data?.enabled&&!error?ready.length:"—"}</strong></article><article><span>Qualification in reviewed sample</span><strong>{data?.enabled&&!error?data.stock_qualification?.horizons[horizon]?.qualified_count??"Pending":"—"}</strong></article><article><span>Evidence requirements</span><strong>{data?.enabled&&!error?blockers.length:"—"}</strong></article></div><details className="terminal-coverage-details"><summary>Market coverage and source diagnostics</summary><div className="horizon-coverage">{sections.map(s=><div key={s.section}><strong>{s.section}</strong><span>{ready.includes(s)?(s.result?.eligible_count||0)+" / "+(s.result?.universe_size||0)+" daily histories eligible":s.status==="READY"?"Waiting for horizon refresh":words(s.status)}</span>{ready.includes(s)&&s.result?.company_research_coverage&&<small>{s.result.company_research_coverage.fresh_cached_reports} / {s.result.company_research_coverage.distinct_eligible_isins} distinct eligible companies with fresh reported business evidence (not qualified picks)</small>}{ready.includes(s)&&s.result?.discovery_coverage&&<small>{s.result.discovery_coverage.selected_count} selected from {s.result.discovery_coverage.recent_registry_count} active equities with recent completed data</small>}{ready.includes(s)&&s.result?.discovery_coverage?.expected_session_count!=null&&<small>{s.result.discovery_coverage.expected_session_count} recent registry equities match the expected session</small>}{ready.includes(s)&&s.result?.history_coverage?.[horizon]&&<small>{s.result.history_coverage[horizon]?.eligible_histories} usable histories with at least {s.result.history_coverage[horizon]?.minimum_observations} observations (before strategy filters)</small>}{ready.includes(s)&&s.result?.discovery_coverage?.calendar_status&&<small>{s.result.discovery_coverage.calendar_status==="PUBLISHED_SESSION"?"Expected completed session: "+s.result.discovery_coverage.expected_session:"Calendar not verified · calendar-day freshness only"}</small>}{ready.includes(s)&&!!s.result?.skipped?.RAW_CORPORATE_ACTION&&<small>{s.result.skipped.RAW_CORPORATE_ACTION} raw histories excluded for recorded corporate actions</small>}</div>)}</div>
   {ready.map(s=>{const review=s.result?.corporate_action_review;return review&&(review.normalized_preview_count>0||review.withheld_count>0)?<details key={s.section}><summary>{s.section} · corporate action diagnostics ({review.normalized_preview_count} previews, {review.withheld_count} withheld)</summary><p>{review.notice}</p>{review.previews.map(p=><article key={p.exchange+":"+p.symbol}><strong>{p.symbol} · known-action price-only preview</strong><p>{p.first_date} – {p.as_of} · {p.observations} observations</p><ul>{p.actions.map(a=><li key={a.ex_date}>{words(a.action_type)} · {a.ex_date} · {a.post_shares_per_pre_share} post-event shares per pre-event share</li>)}</ul><p>Normalized daily price change: {p.change_1d_percent===null?"Unavailable":p.change_1d_percent+"%"} · 20-observation change: {p.change_20_observation_percent===null?"Unavailable":p.change_20_observation_percent+"%"} · Window price change: {p.window_price_change_percent}%</p><p className="muted tiny">{p.notice}</p></article>)}</details>:null;})}
   {ready.map(s=>s.result?.breakout_review&&<BreakoutSample key={s.section} market={s.section} report={s.result.breakout_review}/>)}
   {ready.map(s=>s.result?.price_volume_review&&<PressureSample key={s.section} market={s.section} review={s.result.price_volume_review}/>)}
   <p className="muted tiny">Bounded registry sample, prioritized by latest completed daily traded value; not a whole-market ranking. Missing source evidence is never replaced with estimates.</p></details>
   </>}
  </section>
  {horizon==="INTRADAY"?<IntradayResearch/>:<section className="panel glass horizon-results">
   {data?.enabled&&!error&&data.stock_qualification?.horizons[horizon]&&<QualificationSummaryView report={data.stock_qualification.horizons[horizon]!}/>}
   {displayed.length>0&&<EvidenceBars title="Observed ATR as percentage of price (not a risk rating)" rows={displayed.map(c=>({label:c.symbol+" · "+c.exchange,value:c.atr_percent}))} neutral format={v=>"ATR "+v.toFixed(2)+"%"}/>}<div className="sectionhead"><div><h3>{preliminaryOnly?"Raw-price research observations":"Technical watch candidates"}</h3><p className="muted tiny">{preliminaryOnly?"No strict adjusted-history watches are available. These current technical observations use unadjusted prices and do not qualify for the strategy or recommendations.":selection?"Up to five distinct ISINs from the available NSE/BSE shortlists; research watches, not recommendations.":"Up to five observations across the available NSE/BSE samples."}</p></div></div>
   {reportTarget&&<div className="notice" role="status">{!data&&!error?"Resolving the selected report…":requested?(requested.as_of===reportTarget.as_of?"Opened the selected stock report from the briefing.":"The selected stock has a refreshed observation: "+requested.as_of+" (briefing: "+reportTarget.as_of+"). The report below uses current evidence."):"The requested stock report is not available in the current canonical shortlist. No substitute report was opened. You can review the current watches below."}</div>}
   {displayed.length?<div className="horizon-cards">{displayed.map((candidate,index)=><article className="horizon-card" key={candidate.exchange+":"+candidate.id}>
    <header><div><small>#{index+1} · {candidate.exchange}</small><h3>{candidate.symbol}</h3></div><strong>{money(candidate.close)}</strong></header>
    <p className="muted tiny">Daily close · {candidate.as_of}</p><p>{candidate.review_horizon}</p>
    <dl><div><dt>ATR / price</dt><dd>{candidate.atr_percent.toFixed(2)}%</dd></div><div><dt>History</dt><dd>{candidate.history_count} sessions</dd></div></dl>
    <p className="muted tiny">Technical rule score: {candidate.rank_score} · not a probability.</p>
    {candidate.score_evidence&&<ScoreEvidenceView report={candidate.score_evidence}/>}
    {candidate.stock_qualification&&<p><strong>{words(candidate.stock_qualification.status)}</strong> · {candidate.stock_qualification.blockers.length} unresolved requirements · {candidate.stock_qualification.review_findings.length} review findings</p>}
    <details key={horizon+":"+candidate.exchange+":"+candidate.id+":"+(candidate.isin||"")} ref={candidate===requested?requestedDetails:undefined} className="notice stock-report-disclosure"><summary>Open complete stock research report</summary>
    <StockReportContext candidate={candidate}/>
    <details><summary>Why this appears &amp; risks</summary><ul>{candidate.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul><p>{candidate.warnings.join(" ")}</p><p className="muted tiny">Median historical daily traded value: {money(candidate.median_daily_traded_value)}</p></details>
    {candidate.company_venue_context&&<details><summary>Exchange evidence · {candidate.company_venue_context.observed_venues.join(" + ")}</summary><p>Research representative: {candidate.company_venue_context.representative_exchange}. {words(candidate.company_venue_context.status)}.</p><div className="tablewrap"><table><thead><tr><th>Venue</th><th>Observed close</th><th>Historical turnover proxy (Cr)</th><th>Observed quote spread</th><th>Security state</th></tr></thead><tbody>{candidate.company_venue_context.venue_observations.map(v=><tr key={v.exchange}><td>{v.exchange}</td><td>{v.close==null?"—":money(v.close)+" · "+v.as_of}</td><td>{v.turnover_proxy_cr==null?"—":v.turnover_proxy_cr.toFixed(2)}</td><td>{v.quote?v.quote.spread_percent.toFixed(2)+"% · "+v.quote.observed_at:"—"}</td><td>{words(v.security_state)}</td></tr>)}</tbody></table></div><p className="muted tiny">{candidate.company_venue_context.notice}</p></details>}
    {candidate.selection_company_context&&<CompanyContextView report={candidate.selection_company_context}/>}
    {candidate.official_sector_benchmark&&<OfficialSectorView report={candidate.official_sector_benchmark}/>}
    {candidate.sector_price_context&&<SectorPriceView report={candidate.sector_price_context}/>}
    {candidate.independent_financial_evidence&&<FinancialFilingView report={candidate.independent_financial_evidence}/>}
    {candidate.exchange_surveillance&&<details><summary>Independent NSE regulatory cautions</summary><p><a href={candidate.exchange_surveillance.source_url} target="_blank" rel="noreferrer">Regulatory file · {candidate.exchange_surveillance.report_date}</a> · {words(candidate.exchange_surveillance.status)}</p><ul>{candidate.exchange_surveillance.findings.map(f=><li key={f}>{words(f)}</li>)}</ul><small>{candidate.exchange_surveillance.notice}</small></details>}
    {candidate.stock_qualification&&<StockQualificationView report={candidate.stock_qualification}/>}
    {candidate.price_volume_pressure&&<PressureDetails pressure={candidate.price_volume_pressure} deals={candidate.deal_evidence}/>}
    {candidate.bracket_research&&<BracketView report={candidate.bracket_research}/>}
    {candidate.matched_strategy_replay?.bracket_replay&&<BracketSummaryView report={candidate.matched_strategy_replay.bracket_replay} title="Matched historical bracket cases"/>}
    {candidate.price_structure&&<PriceStructureDetails evidence={candidate.price_structure}/>}
    {candidate.research_reliability&&<details><summary>{candidate.research_reliability.status==="REVIEW_CONFLICTING_EVIDENCE"?"Conflicting evidence · review needed":"Evidence reliability · watch only"}</summary>
     {candidate.research_reliability.warnings.length>0&&<ul>{candidate.research_reliability.warnings.map(w=><li key={w}>{words(w)}</li>)}</ul>}
     <p>Unresolved requirements: {candidate.research_reliability.blockers.map(words).join(" · ")||"Full strategy validation still required"}.</p>
     <p className="muted tiny">{candidate.research_reliability.notice}</p>
    </details>}
    {candidate.research_conclusion&&<div className="notice"><strong>{candidate.research_conclusion.status==="REVIEW_REQUIRED"?"Review required":"Research conclusion · watch only"}</strong><p>{candidate.research_conclusion.summary}</p>{candidate.research_conclusion.supporting_evidence&&candidate.research_conclusion.supporting_evidence.length>0&&<><strong>Supporting reported evidence</strong><ul>{candidate.research_conclusion.supporting_evidence.map(f=><li key={f}>{words(f)}</li>)}</ul></>}{candidate.research_conclusion.warnings.length>0&&<p><strong>Evidence requiring review:</strong> {candidate.research_conclusion.warnings.length} finding(s).</p>}<details><summary>Complete evidence &amp; reassessment</summary><dl>{Object.entries(candidate.research_conclusion.evidence).map(([key,value])=><div key={key}><dt>{words(key)}</dt><dd>{words(value)}</dd></div>)}</dl>{candidate.research_conclusion.warnings.length>0&&<ul>{candidate.research_conclusion.warnings.map(w=><li key={w}>{words(w)}</li>)}</ul>}<p>Remaining qualification requirements: {candidate.research_conclusion.blockers.map(words).join(" · ")||"Full qualification not established"}.</p>{candidate.research_conclusion.next_evidence_checks&&candidate.research_conclusion.next_evidence_checks.length>0&&<><strong>Next evidence checks</strong><ul>{candidate.research_conclusion.next_evidence_checks.map(f=><li key={f}>{words(f)}</li>)}</ul></>}<ul>{candidate.research_conclusion.reassessment_conditions.map(condition=><li key={condition}>{condition}</li>)}</ul><small>{candidate.research_conclusion.notice}</small></details></div>}
    {candidate.current_regime_replay&&<CurrentRegimeView report={candidate.current_regime_replay}/>}
    {candidate.matched_strategy_replay&&<details><summary>Same-stock historical replay · {candidate.matched_strategy_replay.trades} simulated positions</summary><p>Through {candidate.matched_strategy_replay.as_of}{candidate.matched_strategy_replay.small_sample?" · small sample":""}</p>{candidate.matched_strategy_replay.cost_scenarios.map(cost=><p key={cost.cost_bps_per_side}>{cost.cost_bps_per_side} bps per side · net simulated return {cost.net_return_percent}% · drawdown {cost.max_drawdown_percent}%{cost.gross_nifty50_price_index_percent!=null&&<> · Nifty 50 gross price index {cost.gross_nifty50_price_index_percent}% · net minus index {cost.net_difference_vs_nifty50_pp} pp</>}</p>)}<HistoryProvenanceDetails audit={candidate.matched_strategy_replay.history_provenance}/><ExecutionDiagnostics research={candidate.matched_strategy_replay.execution_research}/><ChronologicalResearch research={candidate.matched_strategy_replay.chronological_validation}/><MarketRegimeResearch research={candidate.matched_strategy_replay.market_regime_research}/><JointRegimeResearchView research={candidate.matched_strategy_replay.joint_regime_research}/><p className="muted tiny">{candidate.matched_strategy_replay.notice}</p></details>}
    {candidate.deal_evidence&&<details><summary>Reported bulk / block deal observations</summary><p>Latest matched disclosure: {candidate.deal_evidence.latest_date}</p>{candidate.deal_evidence.groups.map(g=><p key={g.deal_type}>{g.deal_type}: {g.record_count} disclosed sides · buy quantity {g.buy_quantity} · sell quantity {g.sell_quantity} · reported buy value ₹{g.buy_reported_value_inr} · reported sell value ₹{g.sell_reported_value_inr}</p>)}<div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Date"><table><thead><tr><th>Date</th><th>Type</th><th>Reported client</th><th>Side</th><th>Quantity</th><th>Price (INR)</th><th>Report reference</th></tr></thead><tbody>{candidate.deal_evidence.recent_records.map((d,i)=><tr key={i}><td>{d.trade_date}</td><td>{d.deal_type}</td><td>{d.client_name}</td><td>{d.side}</td><td>{d.quantity}</td><td>{d.price_inr}</td><td>{d.source_report}</td></tr>)}</tbody></table></div><p className="muted tiny">{candidate.deal_evidence.notice}</p></details>}
    {candidate.global_exposure&&<GlobalExposureDetails report={candidate.global_exposure}/>}
    <CompanyEvidenceCard evidence={candidate.company_evidence} status={data?.automatic_company_status}/>
    <AutomaticCompanyNews evidence={candidate.news_evidence} status={data?.automatic_news_status}/>
    {candidate.ai_review?.reviews.length?<details><summary>Automatic AI evidence review ({candidate.ai_review.reviews.length} provider{candidate.ai_review.reviews.length===1?"":"s"})</summary>{candidate.ai_review.reviews.map(review=><div key={review.provider}><strong>{review.provider}{review.role?" · "+words(review.role):""}</strong><ul>{review.findings.map((finding,i)=><li key={i}>{finding.statement} <small>[{finding.evidence_ids.join(", ")}]</small></li>)}</ul></div>)}{candidate.ai_review.committee&&<CommitteeCoverageView report={candidate.ai_review.committee}/>}<p className="muted tiny">COMPANY = explicitly scoped venue and horizon observations; OBS = primary dated technical observations; FUND = reported annual financial trends; REPLAY = same-stock historical simulation; OWN = quarterly ownership; VAL = undated peer multiples; NEWS = headline topic observations; GLOBAL = separately dated macro changes; REGIME = observed benchmark trend/volatility; FLOWS = market-level reported flow directions; LIMITS = missing verification. {candidate.ai_review.notice}</p></details>:<p className="muted tiny">{data?.automatic_ai_status==="ENABLED"?"AI review pending or unavailable.":data?.automatic_ai_status==="NO_CONFIGURED_PROVIDER"?"No permitted AI provider configured.":"Automatic AI review unavailable or disabled."}</p>}
    </details>
   </article>)}</div>:<div className="research-empty"><strong>{ready.length?"No technical candidates meet the current rules":"Waiting for current research"}</strong><p>The background engine will reassess available evidence automatically. No manual scan is required.</p></div>}
   {blockers.length>0&&<p className="notice warning-notice">Still required before a complete investment verdict: {blockers.map(words).join(" · ")}.</p>}
   <button type="button" className="secondary" onClick={onSettings}>Check data connections</button>
  </section>
  }
  {horizon!=="INTRADAY"&&data?.enabled&&!error&&data.research_reliability&&<ProspectiveReliability report={data.research_reliability.horizons?.[horizon]}/>}
  {horizon!=="INTRADAY"&&data?.enabled&&!error&&data.score_calibration?.horizons?.[horizon]&&<CalibrationView report={data.score_calibration.horizons[horizon]!}/>}
  {horizon!=="INTRADAY"&&data?.enabled&&!error&&data.bracket_research?.horizons?.[horizon]&&<BracketSummaryView report={data.bracket_research.horizons[horizon]!} title="Prospective bracket validation"/>}
  {horizon!=="INTRADAY"&&data?.enabled&&!error&&data.strategy_validation&&<StrategyValidation data={data.strategy_validation} horizon={horizon}/>}
  {horizon!=="INTRADAY"&&<AdvancedSection title="Research history and outcomes" description="Automatically tracked dated technical watches"><WatchOutcomeHistory horizon={horizon}/></AdvancedSection>}
  <details className="advanced-tools glass" key={horizon}><summary><span><strong>Advanced research tools</strong><small>Optional detailed analysis and evidence review</small></span><b>Open tools</b></summary>{/* Closed tools stay available without loading their workflows. */}<DeferredTools>{children}</DeferredTools></details>
 </section>;
}
function StockReportContext({candidate}:{candidate:Candidate}){
 const company=candidate.isin&&candidate.company_evidence?.isin===candidate.isin?candidate.company_evidence:undefined;
 const profile=company?.sections?.profile?.data;
 const history=candidate.report_close_history;
 const points=history?.points;
 const usable=history&&Array.isArray(points)&&points.length>=2&&points.length<=30&&
  ["ADJUSTED","RAW_UNADJUSTED"].includes(history.adjustment_status)&&history.as_of===candidate.as_of&&
  points.every((p,i)=>/^\d{4}-\d{2}-\d{2}$/.test(p.date)&&Number.isFinite(p.close)&&p.close>0&&(i===0||p.date>points[i-1].date))&&
  points[points.length-1].date===candidate.as_of&&points[points.length-1].close===candidate.close;
 const availableSources=Object.entries(company?.sections||{}).filter(([,section])=>section.status==="AVAILABLE"&&section.source?.provider==="UPSTOX");
 return <section aria-label="Stock report identity and source evidence">
  <h4>Stock identity and evidence dates</h4>
  <p>{candidate.symbol} · {candidate.exchange} · ISIN {candidate.isin||"unavailable"}</p>
  <p>Reported company: {profile?.company_name||"Unavailable"} · Sector: {profile?.sector||"Unavailable"} · Industry: {profile?.industry||"Unavailable"}</p>
  <p>Price observation: {candidate.as_of} · daily close, not a live quote.</p>
  {usable&&points&&history?<ObservedCloseChart points={points} adjustment={history.adjustment_status}/>:<p className="muted tiny">Historical chart unavailable for this observation; no prices inferred.</p>}
  <details><summary>Source references and retrieval dates</summary>
   <p>Technical observations: local stored daily candle history through {candidate.as_of}. Provider and independent session continuity are not certified by this chart.</p>
   {availableSources.length?<ul>{availableSources.map(([name,section])=><li key={name}>{words(name)} · {section.source?.provider} · retrieved {section.source?.retrieved_at||"unknown"} · {section.source?.endpoint||"provider endpoint not recorded"}</li>)}</ul>:<p>Matched company source references unavailable.</p>}
   <p>Company news: {candidate.news_evidence?words(candidate.news_evidence.status)+" · retrieved "+candidate.news_evidence.retrieved_at:"Unavailable"}. Original article links are in Recent company news when present.</p>
   <p>Historical replay: {candidate.matched_strategy_replay?.as_of===candidate.as_of?"Same-observation simulated history through "+candidate.as_of:"Matched replay unavailable"}.</p>
   <p>AI review: {candidate.ai_review?.reviewed_at||"Unavailable"} · supplementary; cited assertions are not independent source verification.</p>
   <p className="muted tiny">Retrieval dates are not financial reporting periods. Missing evidence stays unavailable; this report does not certify an investment recommendation.</p>
  </details>
 </section>;
}
function ObservedCloseChart({points,adjustment}:{points:ReportCloseHistory["points"];adjustment:string}){
 const lo=Math.min(...points.map(p=>p.close)),hi=Math.max(...points.map(p=>p.close));
 const xy=points.map((p,i)=>({x:12+276*i/(points.length-1),y:hi===lo?55:98-86*(p.close-lo)/(hi-lo)}));
 return <figure style={{margin:"12px 0"}}>
  <figcaption>Recorded daily closes · {points.length} observations · {words(adjustment)}</figcaption>
  <svg viewBox="0 0 300 110" role="img" aria-label="Recorded daily close history" style={{width:"100%",maxHeight:180}}>
   <line x1="12" x2="288" y1="98" y2="98" stroke="currentColor" opacity=".25"/>
   {xy.map((p,i)=><circle key={points[i].date} cx={p.x} cy={p.y} r="2.4" fill="currentColor"><title>{points[i].date}: {money(points[i].close)}</title></circle>)}
  </svg>
  <p>{points[0].date}: {money(points[0].close)} · {points[points.length-1].date}: {money(points[points.length-1].close)}</p>
  <p className="muted tiny">Observed range {money(lo)} – {money(hi)}. Points are spaced by observation order, not calendar time; gaps are not filled. Raw prices may be affected by corporate actions.</p>
 </figure>;
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
 {evidence.risk_sensitivity&&<RiskSensitivityView report={evidence.risk_sensitivity}/>}
 <p className="muted tiny">{evidence.notice}</p></details>;
}

function PressureDetails({pressure,deals}:{pressure:Pressure;deals?:DealEvidence}){
 return <div><strong>{pressure.findings.length?pressure.findings.map(words).join(" · "):words(pressure.status)}</strong>{pressure.relative_volume!=null&&<p>{pressure.as_of} · {pressure.change_percent}% close change · {pressure.relative_volume}× preceding median volume · {words(pressure.adjustment_status??"UNKNOWN")} prices</p>}
 {deals?.same_date_groups?.map(g=><p key={g.deal_type}>Same-date reported {g.deal_type} sides: buy {g.buy_quantity} shares · sell {g.sell_quantity} shares</p>)}{deals?.same_date_notice&&<p>{deals.same_date_notice}</p>}{pressure.breakout_followthrough&&<FollowthroughView report={pressure.breakout_followthrough}/>}<p className="muted tiny">{pressure.notice}</p></div>;
}
function PressureSample({market,review}:{market:string;review:PressureReview}){
 return <details><summary>{market} · unusual price and volume ({review.flagged_count} of {review.evaluated_count} assessed)</summary><p>{review.notice}</p>{([["Downside review",review.downside_items],["Upside review",review.upside_items]] as const).map(([title,rows])=><section key={title}><h4>{title}</h4>{rows.length?rows.map(row=><article key={row.id}><strong>{row.symbol}</strong><PressureDetails pressure={row.price_volume_pressure} deals={row.deal_evidence}/></article>):<p>No displayed finding in this assessed sample.</p>}</section>)}</details>;
}

function GlobalExposureDetails({report}:{report:GlobalExposure}){
 return <details><summary>Global sector exposure research</summary>{report.sector&&<p>Reported sector: {report.sector}{report.industry?" · "+report.industry:""}</p>}{report.questions.length?<ul>{report.questions.map(q=><li key={q.factor}><strong>{q.indicator}</strong> · {q.as_of} · {q.change.value>0?"+":""}{q.change.value.toFixed(2)}{q.change.unit==="BASIS_POINTS"?" bp":"%"} over 5 observed dates<p>{q.question}</p></li>)}</ul>:<p>No supported sector exposure question with current evidence.</p>}{report.missing_factors.length>0&&<p>Missing relevant evidence: {report.missing_factors.map(words).join(", ")}</p>}<p className="muted tiny">{report.notice}</p></details>;
}

function JointCosts({costs}:{costs:JointCost[]}){
 if(!costs.length)return <p>No observed positions in this cohort.</p>;
 return <div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Cost per side"><table><thead><tr><th>Cost per side</th><th>Mean / median net return</th><th>Worst net position</th><th>Worst position drawdown</th><th>Win rate</th><th>Wins / losses / flat</th></tr></thead><tbody>{costs.map(c=><tr key={c.cost_bps_per_side}><td>{c.cost_bps_per_side} bps</td><td>{c.mean_trade_return_percent}% / {c.median_trade_return_percent}%</td><td>{c.worst_trade_return_percent}%</td><td>{c.worst_position_drawdown_percent}%</td><td>{c.win_rate_percent}%</td><td>{c.wins} / {c.losses} / {c.flat}</td></tr>)}</tbody></table></div>;
}
function JointRegimeResearchView({research}:{research?:JointRegimeResearch}){
 if(!research)return null;
 return <section className="notice"><strong>Trend and volatility strategy cohorts</strong><p>{research.classified_trades}/{research.total_trades} positions classified · {research.unknown_trades} unclassified</p>{research.groups.map(g=><details key={g.trend+g.volatility_regime}><summary>{words(g.trend)} · {words(g.volatility_regime)} · {g.trades} positions{g.small_sample?" · small sample":""}</summary><JointCosts costs={g.cost_scenarios}/></details>)}<p className="muted tiny">{research.notice}</p></section>;
}
function CurrentRegimeView({report}:{report:CurrentRegimeReplay}){
 return <details><summary>Current regime historical comparison</summary><p>{report.as_of} · {words(report.trend)} · {words(report.volatility_regime)} · {report.trades} historical positions · {words(report.status)}</p><JointCosts costs={report.cost_scenarios}/><p className="muted tiny">{report.notice}</p></details>;
}

function CommitteeCoverageView({report}:{report:CommitteeCoverage}){
 return <section className="notice" aria-label="AI committee coverage"><strong>Independent AI research committee</strong><p>{report.reviewed_count}/{report.configured_count} configured reviews returned · {words(report.status)}</p><div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Provider"><table><thead><tr><th>Provider</th><th>Assigned review role</th><th>Status</th><th>Cited domains</th></tr></thead><tbody>{report.members.map(m=><tr key={m.provider}><td>{m.provider}</td><td>{words(m.role)}</td><td>{words(m.status)}</td><td>{m.cited_domains.join(", ")||"None"}</td></tr>)}</tbody></table></div><p>Uncited available domains: {report.uncited_domains.join(", ")||"None"} · Claim comparison: {words(report.agreement_status)}</p>{report.claim_comparison&&<ClaimAuditView report={report.claim_comparison}/>}<p className="muted tiny">{report.notice}</p></section>;
}

function ClaimAuditView({report}:{report:ClaimComparison}){
 return <div><strong>Exact evidence claim checks</strong><p>{report.matched_count} matching · {report.contradicted_count} contradicted · {report.rejected_count} unsupported or malformed · {report.duplicate_count} duplicate assertions withheld</p>
 {report.conflicts.length>0&&<div><strong>Conflicting assertions</strong><ul>{report.conflicts.map(c=><li key={c.path}>{c.path} · Matching: {c.matching_providers.join(", ")} · Contradicted: {c.contradicting_providers.join(", ")}</li>)}</ul></div>}
 {report.shared_matches.length>0&&<details><summary>Shared matching observations ({report.shared_matches.length})</summary><ul>{report.shared_matches.map(m=><li key={m.path}>{m.path} · {m.providers.join(", ")}</li>)}</ul></details>}
 <p className="muted tiny">{report.notice}</p></div>;
}

function QualificationSummaryView({report}:{report:QualificationSummary}){
 return <section className="notice" aria-label="Investment qualification results"><strong>Qualified investment opportunities</strong><p>{report.qualified_count===null?"Qualification unavailable":report.qualified_count+" qualified"} · {report.reviewed_count} technical watches assessed · {report.review_required_count} with review findings</p><p>{words(report.status)}. No technical watch is promoted automatically.</p>{report.selection&&<p>{report.selection.unique_company_count} distinct identified companies · {report.selection.cross_venue_company_count} on both venues · {report.selection.review_company_count} companies with review findings · {report.selection.unidentified_listing_count} unidentified listings · {report.selection.conflicting_listing_count} conflicting listings withheld. Coverage: {report.selection.ready_markets.join(", ")||"None"}. {report.selection.notice}</p>}{report.leading_blockers.length>0&&<details><summary>Leading qualification requirements</summary><ul>{report.leading_blockers.map(g=><li key={g.code}>{words(g.code)} · {g.count} watches</li>)}</ul></details>}<p className="muted tiny">{report.notice}</p></section>;
}
function StockQualificationView({report}:{report:StockQualification}){
 return <details className="notice"><summary>Investment qualification · {words(report.status)}</summary><div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Evidence domain"><table><thead><tr><th>Evidence domain</th><th>Assessment</th><th>Remaining requirements</th></tr></thead><tbody>{report.gates.map(g=><tr key={g.domain}><td>{words(g.domain)}</td><td>{words(g.status)}</td><td>{g.requirements.map(words).join(" · ")||"None in this domain"}</td></tr>)}</tbody></table></div>{report.review_findings.length>0&&<><strong>Review findings</strong><ul>{report.review_findings.map(f=><li key={f}>{words(f)}</li>)}</ul></>}<p className="muted tiny">{report.notice}</p></details>;
}

function CompanyContextView({report}:{report:CompanyContext}){
 return <details className="notice"><summary>Company-level selection · {words(report.status)}</summary><p>{report.listing_count} observed listings · {report.venues.join(", ")}</p><p>Combined qualification requirements: {report.blockers.map(words).join(" · ")||"None reported"}</p>{report.review_findings.length>0&&<ul>{report.review_findings.map(f=><li key={f}>{words(f)}</li>)}</ul>}<p className="muted tiny">Evidence gaps and review findings from all reviewed listings are retained. The displayed listing is a technical watch, not an execution venue recommendation.</p></details>;
}

function RiskSensitivityView({report}:{report:RiskSensitivity}){
 const value=(n:number|null)=>n===null?"Unavailable":money(n);
 const ratio=(n:number|null)=>n===null?"Unavailable":n.toFixed(2)+"×";
 return <section className="notice" aria-label="Historical cost and gap stress"><h4>Historical cost and gap stress</h4><p>{report.observed_gap_count} observed open gaps · largest adverse gap {report.worst_adverse_open_gap_percent}%{report.worst_adverse_gap_date?" on "+report.worst_adverse_gap_date:""} · assumed floor {report.assumed_gap_floor_percent}%.</p><p>Illustrative lower-reference stress: {report.stress_gap_percent}% · stressed lower reference {money(report.stressed_lower_reference)}. Ratio assumption {report.illustrative_ratio}:1.</p><div className="tablewrap" tabIndex={0} role="region" aria-label="Scrollable evidence table: Cost per side"><table><thead><tr><th>Cost per side</th><th>Net upside</th><th>Downside / stressed</th><th>Reward / risk</th><th>Stressed ratio</th><th>Mathematical price ceiling</th><th>Stressed ceiling</th></tr></thead><tbody>{report.scenarios.map(s=><tr key={s.cost_bps_per_side}><td>{s.cost_bps_per_side} bps</td><td>{s.upside_percent}%</td><td>{s.downside_percent}% / {s.stressed_downside_percent}%</td><td>{ratio(s.reward_to_risk)}</td><td>{ratio(s.stressed_reward_to_risk)}</td><td>{value(s.illustrative_price_ceiling)}</td><td>{value(s.stressed_price_ceiling)}</td></tr>)}</tbody></table></div><p className="muted tiny">{report.notice}</p></section>;
}

function FollowthroughView({report}:{report:Followthrough}){
 return <div><strong>Breakout follow-through research</strong>{report.events.length?<ul>{report.events.map(e=><li key={e.signal_date+e.direction}>{words(e.direction)} · {words(e.status)} · signal {e.signal_date} · frozen boundary {money(e.boundary)} · signal close {money(e.signal_close)} · {e.break_percent}% boundary displacement · {e.relative_volume}× prior median volume ({words(e.volume_context)}) · {e.followup_count} subsequent observations{e.reentry_date?" · re-entry "+e.reentry_date:""}</li>)}</ul>:<p>{report.status==="OBSERVED_FOLLOWTHROUGH"?"No qualifying boundary break in the examined recent observations.":"Follow-through evidence unavailable."}</p>}<p className="muted tiny">{report.notice}</p></div>;
}
function BreakoutSample({market,report}:{market:string;report:BreakoutReview}){
 return <details><summary>{market} · breakout follow-through ({report.event_listing_count} of {report.evaluated_count} assessed)</summary>{report.items.map(i=><article key={i.id}><strong>{i.symbol}</strong><FollowthroughView report={i.followthrough}/></article>)}<p className="muted tiny">{report.notice}</p></details>;
}
