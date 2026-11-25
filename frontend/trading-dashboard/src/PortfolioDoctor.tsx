import PortfolioBenchmarkRisk,{type BenchmarkRisk} from "./PortfolioBenchmarkRisk";
import {visiblePolling} from "./visiblePolling";
import {useEffect,useState} from "react";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
import AutomaticCompanyNews,{type NewsEvidence} from "./AutomaticCompanyNews";

type Thesis={status:string;company_evidence:CompanyEvidence|null;news_evidence:NewsEvidence|null;ai_status:string;ai_review:{provider:string;findings:{statement:string;evidence_ids:string[]}[];notice:string}|null};
type FundHistory={scheme_name:string;nav:number;nav_date:string;cagr_3y_percent:number;drawdown_3y_percent:number;weekly_volatility_percent?:number;sources:string[];notice:string};
type ThesisFinding={statement:string;source:string};
type ThesisSummary={status:string;risks:ThesisFinding[];observations:ThesisFinding[];review_prompts:ThesisFinding[];gaps:string[];notice:string};
type ThesisChange={metric:string;previous_period:string;current_period:string;previous_direction:string;current_direction:string;observed_at:string};
type FundThesisEvidence={status:string;notice:string;disclosure:{scheme_name:string;source:string;plan:string;ter_percent?:number|null;ter_date?:string|null;riskometer?:string|null;benchmark?:string|null;aum_cr_all_plans?:number|null;aum_date?:string|null;fund_managers?:string|null;exit_load?:string|null;document_date?:string|null;conflicts?:string[]};portfolio?:{portfolio_date:string;source:string;exact_listed_equity_weight_percent:number;top_10_exact_equity_weight_percent:number;top_holdings?:{isin:string;name:string;weight_percent:number}[];underlying_research?:{status:string;annual_statement_weight_percent?:number;deterioration_review_weight_percent?:number;notice:string};notice:string}|null};
type FundThesisChange={metric:string;previousDate:string;currentDate:string;previousValue:string;currentValue:string;attention:string;observedAt:string};
type OwnershipChange={category:string;previousDate:string;currentDate:string;previousPercent:number;currentPercent:number;changePp:number;attention:string;observedAt:string};
type HoldingReview={ownership_changes?:OwnershipChange[];ownership_monitor_status?:string;fund_thesis_changes?:FundThesisChange[];fund_monitor_status?:string;fund_thesis_evidence?:FundThesisEvidence;thesis_changes?:ThesisChange[];thesis_monitor_status?:string;thesis_summary?:ThesisSummary;thesis_evidence?:Thesis;fund_history_evidence?:FundHistory;id:number;symbol:string;asset_type:string;exchange:string|null;status:"REVIEW_REQUIRED"|"MONITOR"|"EVIDENCE_GAP";weight_percent:number|null;recorded_return_percent:number|null;evidence_date:string|null;history_count:number;change_20_observations_percent:number|null;recent_peak_change_percent:number|null;findings:string[];missing_evidence:string[]};
type Exposure={label:string;weight_percent:number};
type CostSensitivity={status:string;basis_points_per_side:number[];scenarios:{label:string;purchaseNotional:number;saleNotional:number;grossNotional:number;additionalCashBeforeCost:number;estimates:{basisPointsPerSide:number;hypotheticalCost:number;costPercentOfRecordedValue:number;additionalCashIncludingCost:number}[]}[];notice:string};
type AllocationResearch={cost_sensitivity?:CostSensitivity;status:string;recorded_value?:number;current_largest_percent?:number;current_top_three_percent?:number;single_identity_review_threshold_percent:number;top_three_review_threshold_percent:number;scenarios:{hypotheticalNewIdentities:number;additionalCapital:number;equalNewInvestmentAmount:number;projectedLargestPercent:number;projectedTopThreePercent:number;hypotheticalRedistributedCapital:number;redistributedPercent:number}[];notice:string};
type ExposureStress={status:string;recorded_value?:number;scenarios:{kind:string;title:string;shocks:{exposure:string;label:string;assumedChangePercent:number;recordedExposure:number;valueChange:number}[];changeAmount:number;changePercent:number;stressedValue:number}[];withheld:string[];notice:string};
type LookThrough={sector_status?:string;sector_classified_portfolio_percent?:number;sector_unclassified_mapped_value?:number;sector_review_count?:number;sector_count?:number;sector_notice?:string;sector_exposures?:{sector:string;directValue:number;indirectValue:number;estimatedValue:number;portfolioPercent:number;reviewConcentration:boolean}[];risk_observation_count?:number;status:string;portfolio_date?:string;matched_fund_value_percent?:number;mapped_portfolio_percent?:number;unmodeled_value?:number;matched_scheme_count?:number;mapped_equity_count?:number;overlap_pair_count?:number;exposures:{isin:string;directValue:number;indirectValue:number;estimatedValue:number;portfolioPercent:number;contributingSchemes:number}[];overlap_pairs:{schemeA:string;schemeB:string;sameUnderlyingFund:boolean;commonEquities:number;sharedWeightPercent:number;coverageA:number;coverageB:number}[];notice:string};
type Diversification={look_through?:LookThrough;exposure_stress?:ExposureStress;allocation_research?:AllocationResearch;status:string;unpriced_count:number;unresolved_identity_count:number;resolved_identity_count:number;top_three_resolved_weight_percent:number|null;asset_exposure:Exposure[];direct_equity_sector_exposure:Exposure[];fund_category_exposure:Exposure[];sector_coverage_percent:number|null;fund_category_coverage_percent:number|null;review_prompts:string[];notice:string};
type AllocationValidation={status:string;selection_count?:number;holdout_count?:number;selection_from?:string;selection_through?:string;holdout_from?:string;holdout_through?:string;selected_kind?:string;comparison?:string;holdout_volatility_difference_pp?:number;metrics:{kind:string;selectionVolatilityPercent:number;holdoutVolatilityPercent:number;holdoutMeanPercent:number}[];notice:string};
type HistoricalAllocation={cost_sensitivity?:CostSensitivity;chronological_validation?:AllocationValidation;equity_identity_count?:number;fund_identity_count?:number;nav_sources?:Record<string,string>;status:string;observations?:number;first_date?:string;last_date?:string;direct_equity_value?:number;lowest_observed_variability?:string;alternatives:{kind:string;sampleMeanPercent:number;sampleVolatilityPercent:number;largestWeightPercent:number;oneWayTurnoverPercent:number;weights:{isin?:string;identity?:string;symbol:string;weightPercent:number}[]}[];notice:string};
type Correlation={historical_allocation?:HistoricalAllocation;cross_asset_allocation?:HistoricalAllocation;status:string;comparable_pairs?:number;attempted_pairs?:number;high_positive_pair_count?:number;pairs?:{first_symbol:string;second_symbol:string;first_isin:string;second_isin:string;correlation:number;observations:number;first_date:string;last_date:string;high_positive_correlation:boolean}[];notice:string};
type OpportunityContext={status:string;held_excluded_count:number;ready_sections:string[];blocked_sections:string[];notice:string;
 equities:{isin:string;symbol:string;exchange:string;horizon:string;as_of:string;sector:string|null;sector_weight_percent:number|null;context:string;identity_status:string;adjustment_status:string;blockers:string[]}[];
 funds:{scheme_code:string;name:string;category:string;as_of:string;cagr_3y_percent:number;drawdown_3y_percent:number;context:string;identity_status:string}[]};
type LevelRisk={look_through_status?:string;benchmark_status:string;concentration_status:string;sector_status:string;attention:{kind:string;label:string;value:number;threshold:number;unit:string;evidenceThrough:string}[];notice:string};
type JournalLots={status:string;reconciled_count:number;holdings:{symbol:string;assetType:string;status:string;recordedQuantity:number|null;journalQuantity:number|null;journalOpenCost:number|null;recordedCost:number|null;openLots:{acquired:string;quantity:number;unitPrice:number;calendarDaysHeld:number}[]}[];notice:string};
type Review={journal_lot_reconciliation?:JournalLots;portfolio_level_risk?:LevelRisk;ownership_changed_count?:number;ownership_attention_count?:number;ownership_monitor_notice?:string;fund_thesis_changed_count?:number;fund_thesis_attention_count?:number;fund_monitor_notice?:string;thesis_changed_count?:number;thesis_monitor_notice?:string;benchmark_risk_estimate?:BenchmarkRisk;opportunity_context?:OpportunityContext;diversification?:Diversification;equity_correlation?:Correlation;thesis_review_count?:number;generated_at:string;holding_count:number;attention_count:number;data_gap_count:number;holdings:HoldingReview[];notice:string};
const pct=(value:number|null)=>value==null?"—":(value>0?"+":"")+value.toFixed(2)+"%";
const statuses={REVIEW_REQUIRED:"Needs review",MONITOR:"Monitor",EVIDENCE_GAP:"Data needed"};

function ExposureList({title,rows}:{title:string;rows:Exposure[]}){
 return <div><h4>{title}</h4>{rows.length?<ul>{rows.map(r=><li key={r.label}>{r.label.replace(/_/g," ")}: <strong>{r.weight_percent.toFixed(2)}%</strong></li>)}</ul>:<p className="muted tiny">No recorded positive value in this group.</p>}</div>;
}
function CostSensitivityDigest({report}:{report:CostSensitivity}){
 const money=(v:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",minimumFractionDigits:0,maximumFractionDigits:2}).format(v);
 const [rate,setRate]=useState(50);
 return <details className="thesis-digest"><summary>One-time transaction cost sensitivity</summary>
  {report.status==="ILLUSTRATIVE_COST_SENSITIVITY"?<>
   <label>Assumed charge per purchase and sale <select aria-label="Assumed transaction cost rate" value={rate} onChange={e=>setRate(Number(e.target.value))}>
    {report.basis_points_per_side.map(bps=><option key={bps} value={bps}>{bps} bps ({(bps/100).toFixed(2)}%) per side</option>)}
   </select></label>
   <div className="tablewrap"><table><thead><tr><th>Scenario</th><th>Purchases / sales</th><th>Gross turnover</th><th>Estimated one-time cost</th><th>Cost / recorded value</th><th>Additional cash incl. cost</th></tr></thead><tbody>
    {report.scenarios.map(s=>{const e=s.estimates.find(x=>x.basisPointsPerSide===rate);return <tr key={s.label}><td>{s.label.replace(/_/g," ").toLowerCase()}</td><td>{money(s.purchaseNotional)} / {money(s.saleNotional)}</td><td>{money(s.grossNotional)}</td><td>{e?money(e.hypotheticalCost):"Unavailable"}</td><td>{e?e.costPercentOfRecordedValue.toFixed(4)+"%":"Unavailable"}</td><td>{e?money(e.additionalCashIncludingCost):"Unavailable"}</td></tr>})}
   </tbody></table></div>
   <p>Additional cash includes hypothetical costs on top of the pre-cost contribution or redistribution, rather than silently reducing the target amounts.</p>
  </>:<p>Turnover evidence is insufficient for cost estimates.</p>}
  <p className="muted tiny">{report.notice}</p>
 </details>;
}
function AllocationResearchDigest({report}:{report:AllocationResearch}){
 const money=(v:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",minimumFractionDigits:0,maximumFractionDigits:2}).format(v);
 return <section className="thesis-digest" aria-label="Automatic allocation research">
  <h4>Automatic allocation research</h4>
  {report.status==="HYPOTHETICAL_SCENARIOS_AVAILABLE"?<>
   <p>Largest identity: {report.current_largest_percent?.toFixed(2)}% · Top three: {report.current_top_three_percent?.toFixed(2)}%. Illustrative review limits: {report.single_identity_review_threshold_percent}% and {report.top_three_review_threshold_percent}%.</p>
   <p>Compare adding capital without selling versus redistributing part of the existing portfolio. Both are mathematical scenarios, not recommendations.</p>
   <div className="tablewrap"><table><thead><tr><th>Hypothetical distinct new identities</th><th>Additional capital (no sales)</th><th>Equal amount per new identity</th><th>Fixed-capital redistribution (before costs)</th><th>Projected largest / top three</th></tr></thead><tbody>
    {report.scenarios.map(s=><tr key={s.hypotheticalNewIdentities}><td>{s.hypotheticalNewIdentities}</td><td>{money(s.additionalCapital)}</td><td>{money(s.equalNewInvestmentAmount)}</td><td>{money(s.hypotheticalRedistributedCapital)} ({s.redistributedPercent.toFixed(2)}%)</td><td>{s.projectedLargestPercent.toFixed(2)}% / {s.projectedTopThreePercent.toFixed(2)}%</td></tr>)}
   </tbody></table></div>
   {report.cost_sensitivity&&<CostSensitivityDigest report={report.cost_sensitivity}/>}
  </>:report.status==="WITHIN_ILLUSTRATIVE_CONCENTRATION_LIMITS"?<p>Current exact-identity weights are within the illustrative concentration limits. This does not establish suitability or low risk.</p>:<p>Allocation scenarios withheld until all recorded valuations are recent and positive exposures have exact identities.</p>}
  <p className="muted tiny">{report.notice}</p>
 </section>;
}
function ExposureStressDigest({report}:{report:ExposureStress}){
 const money=(v:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",minimumFractionDigits:0,maximumFractionDigits:2}).format(v);
 return <section className="thesis-digest" aria-label="Automatic portfolio stress research">
  <h4>Automatic portfolio stress research</h4>
  {report.scenarios.length?<>
   <p>Recorded portfolio value: <strong>{money(report.recorded_value??0)}</strong>. Each scenario is independent; impacts must not be added together.</p>
   <div className="tablewrap"><table><thead><tr><th>Scenario</th><th>Assumed exposure shocks</th><th>Portfolio impact</th><th>Stressed value</th></tr></thead><tbody>
    {report.scenarios.map(s=><tr key={s.kind}><td>{s.title}</td><td>{s.shocks.map((shock,i)=><div key={shock.exposure+":"+i}>{shock.label}: {shock.assumedChangePercent}% on {money(shock.recordedExposure)}</div>)}</td><td>{money(s.changeAmount)} ({s.changePercent.toFixed(2)}%)</td><td>{money(s.stressedValue)}</td></tr>)}
   </tbody></table></div>
  </>:<p>Stress scenarios withheld until all recorded valuations are recent and the portfolio has positive supported asset values.</p>}
  {report.withheld.includes("LARGEST_IDENTITY_REQUIRES_COMPLETE_EXACT_IDENTITIES")&&<p className="muted tiny">Largest investment scenario requires complete exact investment identities.</p>}
  {report.withheld.includes("SECTOR_SHOCK_REQUIRES_COMPLETE_DIRECT_EQUITY_CLASSIFICATION")&&<p className="muted tiny">Largest sector scenario requires complete direct-equity sector classification.</p>}
  <p className="muted tiny">{report.notice}</p>
 </section>;
}
function LookThroughDigest({report}:{report:LookThrough}){
 const money=(v:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",minimumFractionDigits:0,maximumFractionDigits:2}).format(v);
 if(report.status==="NO_POSITIVE_FUND_HOLDINGS")return null;
 return <section className="thesis-digest" aria-label="Combined equity exposure and fund overlap">
  <h4>Combined equity exposure and fund overlap</h4>
  {report.status==="DATED_PARTIAL_EQUITY_EXPOSURE_ESTIMATE"?<>
   <p>Fund disclosure date: {report.portfolio_date} · {report.matched_scheme_count} matched schemes covering {report.matched_fund_value_percent?.toFixed(2)}% of recorded fund value.</p>
   {!!report.risk_observation_count&&<p><strong>{report.risk_observation_count} hidden concentration or high overlap review observations.</strong> See portfolio-level risk monitoring for the dated flags.</p>}
   <p>Mapped listed-equity estimate: <strong>{report.mapped_portfolio_percent?.toFixed(2)}%</strong> of recorded portfolio value · unmodeled capital {money(report.unmodeled_value??0)}.</p>
   <details open><summary>Largest combined equity exposures ({report.mapped_equity_count} mapped, up to 20 shown)</summary>
   {report.exposures.length?<div className="tablewrap"><table><thead><tr><th>Equity ISIN</th><th>Direct</th><th>Via funds</th><th>Combined estimate</th><th>Portfolio weight</th><th>Contributing schemes</th></tr></thead><tbody>
    {report.exposures.map(e=><tr key={e.isin}><td>{e.isin}</td><td>{money(e.directValue)}</td><td>{money(e.indirectValue)}</td><td>{money(e.estimatedValue)}</td><td>{e.portfolioPercent.toFixed(2)}%</td><td>{e.contributingSchemes}</td></tr>)}
   </tbody></table></div>:<p>No exact listed-equity exposures mapped.</p>}</details>
   {report.sector_status&&<details open><summary>Combined sector exposure ({report.sector_count??0} classified sectors)</summary>
    <p>Classified share of full portfolio: {report.sector_classified_portfolio_percent?.toFixed(2)}% · mapped equity without sector classification: {money(report.sector_unclassified_mapped_value??0)}.</p>
    {!!report.sector_review_count&&<p><strong>{report.sector_review_count} sectors exceed the illustrative 40% portfolio review threshold.</strong></p>}
    {report.sector_exposures?.length?<div className="tablewrap"><table><thead><tr><th>Sector</th><th>Direct</th><th>Via funds</th><th>Combined estimate</th><th>Full portfolio weight</th></tr></thead><tbody>
    {report.sector_exposures.map(s=><tr key={s.sector}><td>{s.sector}{s.reviewConcentration?" · Review":""}</td><td>{money(s.directValue)}</td><td>{money(s.indirectValue)}</td><td>{money(s.estimatedValue)}</td><td>{s.portfolioPercent.toFixed(2)}%</td></tr>)}
    </tbody></table></div>:<p>No current exact sector classifications available.</p>}
    <p className="muted tiny">{report.sector_notice}</p>
   </details>}
   <details><summary>Same-date fund overlap ({report.overlap_pair_count} comparable pairs)</summary>
    {report.overlap_pairs.length?<div className="tablewrap"><table><thead><tr><th>Scheme codes</th><th>Shared equity weight</th><th>Exact coverage A / B</th><th>Common equities</th></tr></thead><tbody>
    {report.overlap_pairs.map(p=><tr key={p.schemeA+":"+p.schemeB}><td>{p.schemeA} / {p.schemeB}{p.sameUnderlyingFund?" · same underlying fund":""}</td><td>{p.sharedWeightPercent.toFixed(2)}%</td><td>{p.coverageA.toFixed(2)}% / {p.coverageB.toFixed(2)}%</td><td>{p.commonEquities}</td></tr>)}
    </tbody></table></div>:<p>Insufficient comparable fund composition. This does not establish zero overlap.</p>}</details>
  </>:<p>{report.status==="NO_MATCHED_FUND_COMPOSITION"?"Current exact-scheme fund composition unavailable.":"Look-through estimates require complete recent recorded values for supported holdings."}</p>}
  <p className="muted tiny">{report.notice}</p>
 </section>;
}
function HistoricalAllocationDigest({report,mixed=false}:{report:HistoricalAllocation;mixed?:boolean}){
 const labels:Record<string,string>={CURRENT_WEIGHTS:"Current weights",HALFWAY_TO_EQUAL:"Halfway to equal weights",EQUAL_WEIGHTS:"Equal weights"};
 const label=(kind:string)=>labels[kind]??kind.replace(/_/g," ").toLowerCase();
 if(mixed&&report.status==="NO_MIXED_POSITIVE_HOLDINGS")return null;
 const title=mixed?"Mixed stock and fund allocation alternatives":"Historical allocation alternatives";
 return <section className="thesis-digest" aria-label={title}>
  <h4>{title}</h4>
  {report.status==="HISTORICAL_COMPARISON_AVAILABLE"?<>
   <p>{mixed?`${report.equity_identity_count??0} equity identities and ${report.fund_identity_count??0} fund schemes`:"Direct equities only"} · {report.observations} matched return intervals · {report.first_date} to {report.last_date}.</p>
   <p>Lowest observed variability in this sample: <strong>{label(report.lowest_observed_variability??"")}</strong>. This is not a recommendation.</p>
   <div className="tablewrap"><table><thead><tr><th>Alternative</th><th>Mean per interval</th><th>Sample volatility per interval</th><th>Largest weight</th><th>One-way turnover</th></tr></thead><tbody>
    {report.alternatives.map(a=><tr key={a.kind}><td>{label(a.kind)}</td><td>{a.sampleMeanPercent.toFixed(2)}%</td><td>{a.sampleVolatilityPercent.toFixed(2)}%</td><td>{a.largestWeightPercent.toFixed(2)}%</td><td>{a.oneWayTurnoverPercent.toFixed(2)}%</td></tr>)}
   </tbody></table></div>
   {report.cost_sensitivity&&<CostSensitivityDigest report={report.cost_sensitivity}/>}
   {report.chronological_validation&&<details open><summary>Chronological allocation validation</summary>
    {report.chronological_validation.status==="CONDITIONAL_HOLDOUT_AVAILABLE"?<>
      <p>Earlier selection: {report.chronological_validation.selection_count} intervals ({report.chronological_validation.selection_from} to {report.chronological_validation.selection_through}). Later holdout: {report.chronological_validation.holdout_count} intervals ({report.chronological_validation.holdout_from} to {report.chronological_validation.holdout_through}).</p>
      <p>Earlier-period selection: <strong>{label(report.chronological_validation.selected_kind??"")}</strong> · {report.chronological_validation.comparison?.replace(/_/g," ").toLowerCase()}.</p>
      <div className="tablewrap"><table><thead><tr><th>Alternative</th><th>Earlier volatility per interval</th><th>Later volatility per interval</th><th>Later mean per interval</th></tr></thead><tbody>
       {report.chronological_validation.metrics.map(m=><tr key={m.kind}><td>{label(m.kind)}</td><td>{m.selectionVolatilityPercent.toFixed(2)}%</td><td>{m.holdoutVolatilityPercent.toFixed(2)}%</td><td>{m.holdoutMeanPercent.toFixed(2)}%</td></tr>)}
      </tbody></table></div>
      <p>Selected allocation minus current weights: {report.chronological_validation.holdout_volatility_difference_pp?.toFixed(2)} percentage points of later volatility per interval.</p>
    </>:<p>Separate validation requires at least 30 earlier and 15 later matched intervals, with valid statistics.</p>}
    <p className="muted tiny">{report.chronological_validation.notice}</p>
   </details>}
   <details><summary>{mixed?"Hypothetical weights across recorded stocks and funds":"Hypothetical weights within the direct-equity sleeve"}</summary>
    {report.alternatives.map(a=><div key={a.kind}><h5>{label(a.kind)}</h5><ul>{a.weights.map(w=><li key={w.identity??w.isin}>{w.symbol} · {w.weightPercent.toFixed(2)}%</li>)}</ul></div>)}
   </details>
   {mixed&&report.nav_sources&&<p className="muted tiny">NAV history sources: {Object.entries(report.nav_sources).map(([id,source])=>id+" · "+source).join("; ")}.</p>}
  </>:<p>{mixed?"Mixed-asset comparisons require complete recent valuations, exact Growth schemes and comparable single-source NAV and adjusted equity history across 2–12 investment identities.":report.status==="INSUFFICIENT_RECENT_EXACT_DIRECT_EQUITY_COVERAGE"?"Requires complete recent exact valuations for 2–12 direct-equity identities.":"Comparable adjusted return history is insufficient for a full direct-equity comparison."}</p>}
  <p className="muted tiny">{report.notice}</p>
 </section>;
}
function JournalLotsDigest({report}:{report:JournalLots}){
 const money=(v:number|null)=>v==null?"Unavailable":new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",minimumFractionDigits:0,maximumFractionDigits:2}).format(v);
 const labels:Record<string,string>={PROVISIONAL_JOURNAL_RECONCILED:"Provisionally reconciled",NO_RECORDED_TRADES:"No recorded trades",QUANTITY_MISMATCH:"Quantity mismatch",COST_BASIS_MISMATCH:"Cost basis mismatch",SALE_EXCEEDS_RECORDED_ACQUISITIONS:"Sale exceeds recorded acquisitions",AMBIGUOUS_SAME_DAY_TRADES:"Ambiguous same-day trades",AMBIGUOUS_SAME_DAY_ACQUISITIONS:"Ambiguous same-day acquisitions",INVALID_OR_UNRECONCILED_TRADE:"Invalid or unreconciled trade",DUPLICATE_SOURCE_REFERENCE:"Duplicate source reference",AMBIGUOUS_RECORDED_HOLDING:"Ambiguous recorded holding",OPEN_LOT_LIMIT_EXCEEDED:"Open lot limit exceeded"};
 return <section className="doctor-item" aria-label="Recorded acquisition history">
  <h3>Recorded acquisition history</h3>
  <p>{report.reconciled_count} of {report.holdings.length} displayed holdings provisionally reconciled. No tax liability is calculated.</p>
  {report.holdings.length?<div className="tablewrap"><table><thead><tr><th>Investment</th><th>Journal status</th><th>Recorded / reconstructed quantity</th><th>Recorded / reconstructed open cost</th></tr></thead><tbody>
   {report.holdings.map((h,i)=><tr key={h.assetType+":"+h.symbol+":"+i}><td>{h.symbol}</td><td>{labels[h.status]??h.status.replace(/_/g," ").toLowerCase()}</td><td>{h.recordedQuantity??"—"} / {h.journalQuantity??"—"}</td><td>{money(h.recordedCost)} / {money(h.journalOpenCost)}</td></tr>)}
  </tbody></table></div>:<p>{report.status==="JOURNAL_LIMIT_EXCEEDED"?"Recorded journal exceeds the supported reconstruction limit.":"No recorded acquisition analysis available."}</p>}
  {report.holdings.filter(h=>h.openLots.length>0).map((h,i)=><details key={h.assetType+":"+h.symbol+":"+i}><summary>{h.symbol} · {h.openLots.length} provisional open lots</summary><div className="tablewrap"><table><thead><tr><th>Recorded acquisition date</th><th>Remaining quantity</th><th>Recorded unit price</th><th>Calendar days held</th></tr></thead><tbody>{h.openLots.map((l,j)=><tr key={l.acquired+":"+j}><td>{l.acquired}</td><td>{l.quantity}</td><td>{money(l.unitPrice)}</td><td>{l.calendarDaysHeld}</td></tr>)}</tbody></table></div></details>)}
  <p className="muted tiny">{report.notice}</p>
 </section>;
}
function DiversificationDigest({report,correlation}:{report:Diversification;correlation?:Correlation}){
 const weight=(value:number|null)=>value==null?"Not available":value.toFixed(2)+"%";
 return <section className="doctor-item" aria-label="Automatic diversification review">
  <h3>Diversification &amp; concentration</h3>
  <p>{report.status==="NO_PRICED_VALUE"?"Recorded valuations unavailable.":report.status==="PARTIAL_COVERAGE"?"Partial classification or pricing coverage.":"Recorded positions classified; direct allocation excludes fund underlying exposures."}</p>
  <div className="doctor-stats"><div><span>Resolved investment identities</span><strong>{report.resolved_identity_count}</strong></div><div><span>Top three resolved weights</span><strong>{weight(report.top_three_resolved_weight_percent)}</strong></div><div><span>Unpriced positions</span><strong>{report.unpriced_count}</strong></div></div>
  {report.allocation_research&&<AllocationResearchDigest report={report.allocation_research}/>}
  {report.exposure_stress&&<ExposureStressDigest report={report.exposure_stress}/>}
  {report.look_through&&<LookThroughDigest report={report.look_through}/>}
  {report.review_prompts.length>0&&<><h4>Portfolio-level review prompts</h4><ul>{report.review_prompts.map(p=><li key={p}>{p}</li>)}</ul></>}
  <details><summary>Asset, sector and fund category exposures</summary>
   <ExposureList title="Asset allocation · priced portfolio" rows={report.asset_exposure}/>
   <p>Direct equity sector classification coverage: {weight(report.sector_coverage_percent)}</p>
   <ExposureList title="Sector exposure · direct equities only" rows={report.direct_equity_sector_exposure}/>
   <p>Fund category classification coverage: {weight(report.fund_category_coverage_percent)}</p>
   <ExposureList title="Fund categories · mutual funds only" rows={report.fund_category_exposure}/>
   <p>Unresolved priced identities: {report.unresolved_identity_count}</p>
  </details>
  {correlation?.historical_allocation&&<HistoricalAllocationDigest report={correlation.historical_allocation}/>}
  {correlation?.cross_asset_allocation&&<HistoricalAllocationDigest report={correlation.cross_asset_allocation} mixed/>}
  {correlation&&<details><summary>Historical equity correlation</summary>
   <p>{correlation.comparable_pairs??0}/{correlation.attempted_pairs??0} pairs comparable · {correlation.high_positive_pair_count??0} highly positively correlated</p>
   {correlation.pairs?.length?<div className="tablewrap"><table><thead><tr><th>Equity pair</th><th>Correlation</th><th>Matched intervals</th></tr></thead><tbody>{correlation.pairs.map(p=><tr key={p.first_isin+":"+p.second_isin}><td>{p.first_symbol} / {p.second_symbol}{p.high_positive_correlation?" · Review":""}</td><td>{p.correlation.toFixed(2)}</td><td>{p.observations} · {p.first_date} to {p.last_date}</td></tr>)}</tbody></table></div>:<p>Comparable adjusted return history unavailable.</p>}
   <p className="muted tiny">{correlation.notice}</p>
  </details>}
  <p className="muted tiny">{report.notice}</p>
 </section>;
}

function OpportunityDigest({report}:{report:OpportunityContext}){
 const [expanded,setExpanded]=useState(false);
 const label=(value:string)=>value.replace(/_/g," ").toLowerCase();
 return <section className="doctor-item" aria-label="Portfolio opportunity research">
  <h3>Research beyond your recorded holdings</h3>
  <p className="muted">Existing technical and fund historical watches, compared locally with your portfolio. Not buy recommendations.</p>
  <p>{report.equities.length} equity watches · {report.funds.length} fund historical watches · {report.held_excluded_count} exact held identities excluded</p>
  {report.status!=="WATCH_CONTEXT_AVAILABLE"&&<p>{report.status==="NO_NEW_EXACT_IDENTITY_WATCHES"?"No additional exact-identity watches in the current sample.":report.status==="DISABLED"?"Automatic research is disabled.":"Current public watch evidence is unavailable or insufficient."}</p>}
  {report.blocked_sections.length>0&&<p className="muted tiny">Unavailable or stale sections: {report.blocked_sections.map(label).join(", ")}.</p>}
  {report.equities.length>0&&<><h4>Equity technical watches</h4><ul>{report.equities.slice(0,expanded?undefined:5).map(item=><li key={item.isin}><strong>{item.symbol} · {item.exchange}</strong> — {label(item.horizon)} · {item.as_of}. {item.sector||"Sector unknown"} · {label(item.context)}{item.sector_weight_percent!==null?` (${item.sector_weight_percent.toFixed(2)}% of priced direct equities)`:""}. {item.identity_status==="UNRESOLVED_HOLDINGS_EXIST"?"Some held identities are unresolved. ":""}{item.adjustment_status==="RAW_UNADJUSTED"?"Raw prices may be distorted by corporate actions. ":""}<small className="muted">Unverified: {item.blockers.map(label).join(", ")||"full investment thesis"}.</small></li>)}</ul></>}
  {report.funds.length>0&&<><h4>Mutual fund historical watches</h4><ul>{report.funds.slice(0,expanded?undefined:5).map(item=><li key={item.scheme_code}><strong>{item.name}</strong> · {label(item.category)} · {item.as_of}. 3-year CAGR {pct(item.cagr_3y_percent)} · historical drawdown {pct(item.drawdown_3y_percent)}. {label(item.context)}. {item.identity_status==="UNRESOLVED_HOLDINGS_EXIST"?"Some held identities are unresolved.":""}</li>)}</ul></>}
  {(report.equities.length>5||report.funds.length>5)&&<button type="button" className="secondary" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?"Show fewer watches":"Show all watches"}</button>}
  <p className="muted tiny">{report.notice}</p>
 </section>;
}

function HeldFundEvidence({evidence}:{evidence:FundThesisEvidence}){
 const d=evidence.disclosure,p=evidence.portfolio,u=p?.underlying_research;
 return <div><h4>{d.scheme_name} · {d.plan}</h4>
  <dl><div><dt>Reported TER</dt><dd>{d.ter_percent==null?"Unavailable":d.ter_percent.toFixed(2)+"%"} {d.ter_date||""}</dd></div>
  <div><dt>Reported Riskometer</dt><dd>{d.riskometer?.replace(/_/g," ")||"Unavailable"}</dd></div>
  <div><dt>Reported benchmark name</dt><dd>{d.benchmark||"Unavailable"}</dd></div>
  <div><dt>AUM (all plans)</dt><dd>{d.aum_cr_all_plans==null?"Unavailable":"₹"+d.aum_cr_all_plans.toFixed(2)+" cr"} {d.aum_date||""}</dd></div>
  <div><dt>Reported managers</dt><dd>{d.fund_managers||"Unavailable"}</dd></div>
  <div><dt>Reported exit load</dt><dd>{d.exit_load||"Unavailable"}</dd></div></dl>
  {d.document_date&&<p className="muted tiny">Document date: {d.document_date}</p>}
  {!!d.conflicts?.length&&<p>Conflicting disclosures: {d.conflicts.join(", ")}</p>}
  <p className="muted tiny">Source: {d.source}. Secondary reported data, not independently verified.</p>
  {p?<><h4>Reported composition · {p.portfolio_date}</h4><p>Exact listed equity weight: {p.exact_listed_equity_weight_percent.toFixed(2)}% · Top ten: {p.top_10_exact_equity_weight_percent.toFixed(2)}%</p>
   {!!p.top_holdings?.length&&<ul>{p.top_holdings.map(h=><li key={h.isin}>{h.name} · {h.weight_percent.toFixed(2)}%</li>)}</ul>}
   {u&&<p>Annual statement evidence: {u.annual_statement_weight_percent==null?"Unavailable":u.annual_statement_weight_percent.toFixed(2)+"%"} · Underlying deterioration observations: {u.deterioration_review_weight_percent==null?"Unavailable":u.deterioration_review_weight_percent.toFixed(2)+"%"}</p>}
   <p className="muted tiny">{u?.notice} {p.notice}</p></>:<p>Current reported holdings composition unavailable.</p>}
  <p className="muted tiny">{evidence.notice}</p></div>;
}

function ThesisDigest({summary}:{summary:ThesisSummary}){
 return <div className="thesis-digest">
  <h4>Investment research summary</h4>
  <p className="muted tiny">{summary.status==="REVIEW_EVIDENCE"?"Evidence warrants review":"Insufficient evidence for an investment verdict"}</p>
  {summary.risks.length>0&&<><strong>Recorded risks</strong><ul>{summary.risks.map((f,i)=><li key={i}>{f.statement} <small className="muted">({f.source})</small></li>)}</ul></>}
  {summary.review_prompts.length>0&&<><strong>What to investigate</strong><ul>{summary.review_prompts.map((f,i)=><li key={i}>{f.statement} <small className="muted">({f.source})</small></li>)}</ul></>}
  {summary.observations.length>0&&<><strong>Other measured observations</strong><ul>{summary.observations.map((f,i)=><li key={i}>{f.statement} <small className="muted">({f.source})</small></li>)}</ul></>}
  <details><summary>Unverified or missing evidence ({summary.gaps.length})</summary><ul>{summary.gaps.map((gap,i)=><li key={i}>{gap}</li>)}</ul></details>
  <p className="muted tiny">{summary.notice}</p>
 </div>;
}

const priority=(item:HoldingReview)=>item.status==="REVIEW_REQUIRED"||item.ownership_changes?.some(change=>change.attention==="REVIEW")||item.fund_thesis_changes?.some(change=>change.attention==="REVIEW")||item.thesis_changes?.some(change=>change.current_direction==="NEGATIVE"||change.current_direction==="DECLINING")?3:item.thesis_summary?.status==="REVIEW_EVIDENCE"?2:item.status==="EVIDENCE_GAP"?1:0;
function reviewLabel(item:HoldingReview){return priority(item)>=2?"Needs review":statuses[item.status];}
function firstFinding(item:HoldingReview){return item.ownership_changes?.some(change=>change.attention==="REVIEW")?"Reported quarterly ownership declined; verify filings and share counts.":item.fund_thesis_changes?.some(change=>change.attention==="REVIEW")?"Reported fund disclosure changed; review the dated evidence.":item.thesis_changes?.find(change=>change.current_direction==="NEGATIVE"||change.current_direction==="DECLINING")? "Newly observed financial deterioration; open the dated thesis evidence.":item.thesis_summary?.risks[0]?.statement||item.thesis_summary?.review_prompts[0]?.statement||item.findings[0]||item.missing_evidence[0]||"Further evidence is needed.";}
export default function PortfolioDoctor({revision,onSettings,compact=false,onOpenPortfolio}:{revision:number;onSettings:()=>void;compact?:boolean;onOpenPortfolio?:()=>void}){
 const [review,setReview]=useState<Review|null>(null);
 const [error,setError]=useState(false);
 const [expanded,setExpanded]=useState(false);
 useEffect(()=>visiblePolling(async signal=>{
  try{
   const response=await fetch("/api/v1/portfolio/review",{cache:"no-store",signal});
   if(!response.ok)throw Error();
   const body:Review=await response.json();if(!Array.isArray(body.holdings))throw Error();
   if(!signal.aborted){setReview(body);setError(false);}
  }catch{if(!signal.aborted){setReview(null);setError(true);}}
 },60000),[revision]);
 const ordered=[...(review?.holdings||[])].sort((a,b)=>priority(b)-priority(a)||a.symbol.localeCompare(b.symbol));
 const attention=ordered.filter(item=>priority(item)>=2);
 if(compact)return <section className="panel glass portfolio-doctor doctor-compact" aria-label="Portfolio attention summary">
  <div className="sectionhead"><div><small className="section-kicker">YOUR PORTFOLIO</small><h2>Portfolio attention</h2></div>{onOpenPortfolio&&<button type="button" className="secondary" onClick={onOpenPortfolio}>Open full review</button>}</div>
  {error?<p role="alert">Portfolio review unavailable. <button type="button" className="secondary" onClick={onSettings}>Check connections</button></p>:!review?<p role="status">Loading portfolio review…</p>:!review.holding_count?<p>No holdings recorded yet. Add investments in My Portfolio.</p>:<>
   <div className="doctor-stats"><div><span>Holdings reviewed</span><strong>{review.holding_count}</strong></div><div><span>Holdings needing review</span><strong>{attention.length}</strong></div><div><span>Core data gaps</span><strong>{review.data_gap_count}</strong></div></div>
   {attention.length?<ul className="doctor-compact-findings">{attention.slice(0,3).map(item=><li key={item.id}><strong>{item.symbol}</strong><span>{firstFinding(item)}</span></li>)}</ul>:<p>No review flags in the available observations. Missing evidence is not a clean bill of health.</p>}
   {!!review.portfolio_level_risk?.attention.length&&<p><strong>Portfolio-level review:</strong> {review.portfolio_level_risk.attention.length} benchmark, concentration or fund overlap observations. Open full review for evidence.</p>}
   {attention.length>3&&<p className="muted tiny">{attention.length-3} more holdings need review in My Portfolio.</p>}
   <p className="muted tiny">Reviewed {new Date(review.generated_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST · Research only.</p>
  </>}
 </section>;
 return <section className="panel glass portfolio-doctor" aria-label="Automatic portfolio review">
  <div className="sectionhead"><div><small className="section-kicker">AUTOMATIC PORTFOLIO REVIEW</small><h2>What needs your attention?</h2><p className="muted">ATLAS reviews your saved holdings and available historical evidence without a manual scan.</p></div><span className="tag">LOCAL RESEARCH</span></div>
  {error?<div role="alert" className="notice warning-notice">Portfolio review unavailable. <button type="button" className="secondary" onClick={onSettings}>Check data connections</button></div>:!review?<p role="status">Loading portfolio review…</p>:!review.holding_count?<p>No holdings yet. Add or synchronize your investments to begin automatic review.</p>:<>
    <div className="doctor-stats"><div><span>Holdings reviewed</span><strong>{review.holding_count}</strong></div><div><span>Need attention</span><strong>{review.attention_count}</strong></div><div><span>Core data gaps</span><strong>{review.data_gap_count}</strong></div></div>
    {review.ownership_changed_count!=null&&<p className="muted">Held equities with recently observed ownership changes: <strong>{review.ownership_changed_count}</strong> · {review.ownership_attention_count??0} need review. {review.ownership_monitor_notice}</p>}
    {review.fund_thesis_changed_count!=null&&<p className="muted">Held funds with recent disclosure changes: <strong>{review.fund_thesis_changed_count}</strong> · {review.fund_thesis_attention_count??0} need review. {review.fund_monitor_notice}</p>}
    {review.thesis_changed_count!=null&&<p className="muted">Holdings with recent dated financial direction changes: <strong>{review.thesis_changed_count}</strong>. {review.thesis_monitor_notice}</p>}
    {review.thesis_review_count!=null&&<p className="muted">Holdings with research review prompts: <strong>{review.thesis_review_count}</strong> (includes recorded risk flags).</p>}
    <div className="doctor-list">{ordered.slice(0,expanded?review.holdings.length:5).map(item=><article key={item.id} className="doctor-item">
      <header><div><strong>{item.symbol}</strong><small>{item.asset_type==="MUTUAL_FUND"?"Mutual fund":item.exchange||"Equity"}</small></div><span className={priority(item)>=2?"doctor-warning":"doctor-neutral"}>{reviewLabel(item)}</span></header>
      {!!item.ownership_changes?.length&&<div className="thesis-digest"><h4>Recently observed quarterly ownership changes</h4><ul>{item.ownership_changes.map(change=><li key={change.category}>{change.category.replace(/_/g," ")}: {change.previousPercent.toFixed(2)}% ({change.previousDate}) → {change.currentPercent.toFixed(2)}% ({change.currentDate}) · {change.changePp.toFixed(2)} pp. <small className="muted">{change.attention==="REVIEW"?"Review required. ":"Observation only. "}Reported ownership, not proof of trades.</small></li>)}</ul></div>}
      {item.ownership_monitor_status==="SAME_QUARTER_REVISION_UNVERIFIED"&&<p className="muted tiny">A same-quarter ownership revision needs verification; no new change alert.</p>}
      {!!item.fund_thesis_changes?.length&&<div className="thesis-digest"><h4>Recently observed fund disclosure changes</h4><ul>{item.fund_thesis_changes.map(change=><li key={change.metric}>{change.metric.replace(/_/g," ")}: {change.previousValue}{change.metric==="TER"?"%":""} ({change.previousDate}) → {change.currentValue}{change.metric==="TER"?"%":""} ({change.currentDate}). <small className="muted">{change.attention==="REVIEW"?"Review required. ":"Observation only. "}Secondary reported evidence; verify official disclosure.</small></li>)}</ul></div>}
      {item.fund_monitor_status==="NO_CURRENT_DATED_DISCLOSURES"&&<p className="muted tiny">No current comparable dated fund disclosures for change monitoring.</p>}
      {!!item.thesis_changes?.length&&<div className="thesis-digest"><h4>Recently observed financial direction changes</h4><ul>{item.thesis_changes.map(change=><li key={change.metric}>{change.metric.replace(/_/g," ")}: {change.previous_period} ({change.previous_direction.toLowerCase()}) → {change.current_period} ({change.current_direction.toLowerCase()}). <small className="muted">Observed {new Date(change.observed_at).toLocaleDateString("en-IN",{timeZone:"Asia/Kolkata"})} · reported evidence, not a forecast.</small></li>)}</ul></div>}
      {item.thesis_monitor_status==="NO_CURRENT_DATED_TRENDS"&&item.asset_type==="EQUITY"&&<p className="muted tiny">No current comparable annual trends for change monitoring.</p>}
      {item.thesis_summary?<ThesisDigest summary={item.thesis_summary}/>:item.findings.length?<ul>{item.findings.map(f=><li key={f}>{f}</li>)}</ul>:<p>{item.status==="EVIDENCE_GAP"?"More reliable data is needed.":"No threshold breach in the available observations; not a complete investment assessment."}</p>}
      <details><summary>Evidence and limitations</summary><dl><div><dt>Recorded weight</dt><dd>{pct(item.weight_percent)}</dd></div><div><dt>Recorded return</dt><dd>{pct(item.recorded_return_percent)}</dd></div><div><dt>20-observation change</dt><dd>{pct(item.change_20_observations_percent)}</dd></div><div><dt>Recent peak change</dt><dd>{pct(item.recent_peak_change_percent)}</dd></div></dl><p>History: {item.history_count} observations · {item.evidence_date||"No verified observation date"}</p><ul>{item.missing_evidence.map(m=><li key={m}>{m}</li>)}</ul></details>
      {item.asset_type==="EQUITY"&&<details><summary>Company thesis &amp; local AI review</summary>
       <CompanyEvidenceCard evidence={item.thesis_evidence?.company_evidence??undefined} status={item.thesis_evidence?"ENABLED":undefined}/>
       <AutomaticCompanyNews evidence={item.thesis_evidence?.news_evidence??undefined} status={item.thesis_evidence?"ENABLED":undefined}/>
       {item.thesis_evidence?.ai_review?<><h4>Local AI · {item.thesis_evidence.ai_review.provider}</h4><ul>{item.thesis_evidence.ai_review.findings.map((f,i)=><li key={i}>{f.statement} <small>[{f.evidence_ids.join(", ")}]</small></li>)}</ul><p className="muted tiny">{item.thesis_evidence.ai_review.notice}</p></>:<p className="muted tiny">Local AI evidence pending or local model not configured. No external fallback.</p>}
      </details>}
      {item.asset_type==="MUTUAL_FUND"&&<details><summary>Fund disclosures and portfolio quality</summary>{item.fund_thesis_evidence?<HeldFundEvidence evidence={item.fund_thesis_evidence}/>:<p>Current exact-scheme secondary disclosures unavailable.</p>}</details>}
      {item.asset_type==="MUTUAL_FUND"&&<details><summary>Exact scheme historical evidence</summary>{item.fund_history_evidence?<><p>{item.fund_history_evidence.scheme_name} · NAV ₹{item.fund_history_evidence.nav.toFixed(2)} · {item.fund_history_evidence.nav_date}</p><dl><div><dt>3-year CAGR</dt><dd>{pct(item.fund_history_evidence.cagr_3y_percent)}</dd></div><div><dt>Observed drawdown</dt><dd>{pct(item.fund_history_evidence.drawdown_3y_percent)}</dd></div><div><dt>Weekly volatility proxy</dt><dd>{pct(item.fund_history_evidence.weekly_volatility_percent??null)}</dd></div></dl><p className="muted tiny">Sources: {item.fund_history_evidence.sources.join(" · ")}. {item.fund_history_evidence.notice}</p></>:<p>Exact-scheme history insufficient or unavailable.</p>}</details>}
    </article>)}</div>
    {review.holdings.length>5&&<button type="button" className="secondary" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?"Show fewer holdings":"Show all holdings"}</button>}
    {review.portfolio_level_risk&&<section className="doctor-item" aria-label="Automatic portfolio-level risk"><h3>Portfolio-level risk monitoring</h3>
     <p className="muted tiny">Benchmark: {review.portfolio_level_risk.benchmark_status.replace(/_/g," ").toLowerCase()} · Concentration: {review.portfolio_level_risk.concentration_status.replace(/_/g," ").toLowerCase()}.</p>
     {review.portfolio_level_risk.attention.length?<ul>{review.portfolio_level_risk.attention.map((a,i)=><li key={a.kind+":"+i}>{a.label}: <strong>{a.value.toFixed(2)} {a.unit==="PP"?"pp":"%"}</strong> · review threshold {a.threshold}{a.unit==="PP"?" pp":"%"} · {a.evidenceThrough}</li>)}</ul>:<p>No supported portfolio-level review observations. Missing evidence is not a clean bill of health.</p>}
     <p className="muted tiny">{review.portfolio_level_risk.notice}</p>
    </section>}
    {review.benchmark_risk_estimate&&<PortfolioBenchmarkRisk report={review.benchmark_risk_estimate} compact/>}
    {review.diversification&&<DiversificationDigest report={review.diversification} correlation={review.equity_correlation}/>}
    {review.journal_lot_reconciliation&&<JournalLotsDigest report={review.journal_lot_reconciliation}/>}
    {review.opportunity_context&&<OpportunityDigest report={review.opportunity_context}/>}
    <p className="muted tiny">Reviewed {new Date(review.generated_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST. {review.notice}</p>
  </>}
 </section>;
}
