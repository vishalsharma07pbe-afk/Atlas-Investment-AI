type Point={period:string;value:number};
type Metric={name:string;history:Point[]};
type Ratio={name:string;company_value:number;sector_value:number|null;unit:string;sector_unit?:string};
type Section<T>={status:string;data:T|null;source:{provider:string;endpoint:string|null;retrieved_at:string}|null};
type FinancialTrend={metric:string;unit:string;previous_year:number;latest_year:number;previous_value:number;latest_value:number;change_percent:number|null;direction:string;latest_period_may_be_stale:boolean};
type FinancialTrends={status:string;items:FinancialTrend[];missing_metrics:string[];notice:string};
type DerivedMetric={metric:string;previous_year:number;latest_year:number;previous_value:number;latest_value:number;change:number;unit:string};
type SectorComparison={metric:string;company:number;sector:number;unit:string;difference:number;premium_discount_percent:number|null;position:string};
type FundamentalQuality={status:string;strengths:string[];warnings:string[];derived_metrics:DerivedMetric[];sector_comparisons:SectorComparison[];valuation:{status:string;fair_value:null;scenario_status:string};gaps:string[];notice:string};
export type CompanyEvidence={fundamental_quality?:FundamentalQuality;financial_trends?:FinancialTrends;isin:string;retrieved_at:string;available_sections:number;total_sections:number;notice:string;sections:{
 profile:Section<{sector?:string;industry?:string;company_name?:string}>;
 ratios:Section<Ratio[]>;
 income_statement:Section<{units:string|null;rows:Metric[]}>;
 cash_flow:Section<{units:string|null;rows:Metric[]}>;
 balance_sheet:Section<{units:string|null;rows:{period:string;total_asset:number|null;total_liability:number|null}[]}>;
 shareholding:Section<Metric[]>;
 corporate_actions:Section<{name:string;date:string|null}[]>;
 competitors:Section<{name:string;sector:string|null}[]>;
}};
const words=(v:string)=>v.replace(/_/g," ").toLowerCase();
const fmt=(n:number|null)=>n==null?"—":new Intl.NumberFormat("en-IN",{maximumFractionDigits:2}).format(n);
function Metrics({rows}:{rows:Metric[]}){
 return <div className="tablewrap"><table><thead><tr><th>Metric</th><th>Reported periods and values</th></tr></thead><tbody>{rows.map((r,i)=><tr key={i}><td>{r.name.replace(/_/g," ")}</td><td>{r.history.map(p=>p.period+": "+fmt(p.value)).join(" · ")}</td></tr>)}</tbody></table></div>;
}
export default function CompanyEvidenceCard({evidence,status}:{evidence?:CompanyEvidence;status?:string}){
 if(!evidence)return <p className="muted tiny">{status==="ENABLED"?"Automatic company evidence pending or unavailable.":"Automatic company research requires authorized provider access."}</p>;
 const s=evidence.sections;
 return <details className="company-evidence"><summary>Company fundamentals &amp; valuation evidence ({evidence.available_sections}/{evidence.total_sections})</summary>
 <p className="muted tiny">ISIN {evidence.isin} · Retrieved {new Date(evidence.retrieved_at).toLocaleString("en-IN",{timeZone:"Asia/Kolkata"})} IST · Upstox</p>
 {s.profile.data&&<p>{[s.profile.data.company_name,s.profile.data.sector,s.profile.data.industry].filter(Boolean).join(" · ")}</p>}
 {evidence.fundamental_quality&&<section aria-label="Fundamental research assessment">
 <h4>Fundamental research assessment</h4>
 <p><strong>{evidence.fundamental_quality.status==="REVIEW_REQUIRED"?"Reported deterioration requires review":evidence.fundamental_quality.status==="PARTIAL_EVIDENCE"?"Partial business evidence":"Comparable business evidence unavailable"}</strong></p>
 {evidence.fundamental_quality.warnings.length>0&&<ul>{evidence.fundamental_quality.warnings.map(w=><li key={w}>{words(w)}</li>)}</ul>}
 {evidence.fundamental_quality.strengths.length>0&&<><p>Reported improvements:</p><ul>{evidence.fundamental_quality.strengths.map(w=><li key={w}>{words(w)}</li>)}</ul></>}
 {evidence.fundamental_quality.derived_metrics.length>0&&<div className="tablewrap"><table><thead><tr><th>Matched annual metric</th><th>Prior FY</th><th>Latest FY</th><th>Change</th></tr></thead><tbody>{evidence.fundamental_quality.derived_metrics.map(m=><tr key={m.metric}><td>{words(m.metric)}</td><td>FY{m.previous_year}: {fmt(m.previous_value)}{m.unit==="PERCENT"?"%":"x"}</td><td>FY{m.latest_year}: {fmt(m.latest_value)}{m.unit==="PERCENT"?"%":"x"}</td><td>{fmt(m.change)} {m.unit==="PERCENT"?"pp":"x"}</td></tr>)}</tbody></table></div>}
 <h4>Sector-relative valuation and quality</h4>
 {evidence.fundamental_quality.sector_comparisons.length>0?<div className="tablewrap"><table><thead><tr><th>Metric</th><th>Company</th><th>Sector</th><th>Comparison</th></tr></thead><tbody>{evidence.fundamental_quality.sector_comparisons.map(m=><tr key={m.metric}><td>{m.metric==="PE"?"Price / earnings":m.metric==="PB"?"Price / book":words(m.metric)}</td><td>{fmt(m.company)}{m.unit==="PERCENT"?"%":"x"}</td><td>{fmt(m.sector)}{m.unit==="PERCENT"?"%":"x"}</td><td>{m.premium_discount_percent===null?words(m.position):m.premium_discount_percent===0?"At sector multiple":fmt(Math.abs(m.premium_discount_percent))+"% "+(m.premium_discount_percent>0?"premium":"discount")}</td></tr>)}</tbody></table></div>:<p>Comparable sector ratios unavailable.</p>}
 <p>Fair value and valuation scenarios withheld: dated inputs required.</p>
 <details><summary>Outstanding fundamental evidence</summary><ul>{evidence.fundamental_quality.gaps.map(g=><li key={g}>{words(g)}</li>)}</ul></details>
 <p className="muted tiny">{evidence.fundamental_quality.notice}</p>
 </section>}
 <h4>Annual financial trends</h4>
 {evidence.financial_trends?.items.length?<div className="tablewrap"><table><thead><tr><th>Metric</th><th>Prior year</th><th>Latest year</th><th>Annual change</th></tr></thead><tbody>{evidence.financial_trends.items.map(t=><tr key={t.metric}><td>{t.metric.replace(/_/g," ").toLowerCase()}<small> · {t.unit}</small></td><td>FY{t.previous_year}: {fmt(t.previous_value)}</td><td>FY{t.latest_year}: {fmt(t.latest_value)}{t.latest_period_may_be_stale?" (older period)":""}</td><td>{t.change_percent===null?"Not comparable":fmt(t.change_percent)+"%"} · {t.direction.toLowerCase()}</td></tr>)}</tbody></table></div>:<p>Comparable annual statement trends unavailable.</p>}
 {evidence.financial_trends&&<p className="muted tiny">{evidence.financial_trends.missing_metrics.length?("Missing comparisons: "+evidence.financial_trends.missing_metrics.map(m=>m.replace(/_/g," ").toLowerCase()).join(", ")+". "):""}{evidence.financial_trends.notice}</p>}
 <h4>Company vs sector ratios</h4>
 {s.ratios.data?.length?<div className="tablewrap"><table><thead><tr><th>Ratio</th><th>Company</th><th>Sector</th></tr></thead><tbody>{s.ratios.data.map((r,i)=><tr key={i}><td>{r.name}</td><td>{fmt(r.company_value)}{r.unit==="PERCENT"?"%":""}</td><td>{fmt(r.sector_value)}{r.sector_value!==null&&(r.sector_unit??r.unit)==="PERCENT"?"%":""}</td></tr>)}</tbody></table></div>:<p>Ratio evidence unavailable.</p>}
 {(["income_statement","cash_flow"] as const).map(key=><details key={key}><summary>{key==="income_statement"?"Income statement":"Cash flow"}</summary>{s[key].data?<><p className="muted tiny">Provider units: {s[key].data!.units||"Not supplied"}</p><Metrics rows={s[key].data!.rows}/></>:<p>Evidence unavailable.</p>}</details>)}
 <details><summary>Balance sheet</summary>{s.balance_sheet.data?<><p>Provider units: {s.balance_sheet.data.units||"Not supplied"}</p><div className="tablewrap"><table><thead><tr><th>Period</th><th>Assets</th><th>Liabilities</th></tr></thead><tbody>{s.balance_sheet.data.rows.map((r,i)=><tr key={i}><td>{r.period}</td><td>{fmt(r.total_asset)}</td><td>{fmt(r.total_liability)}</td></tr>)}</tbody></table></div></>:<p>Evidence unavailable.</p>}</details>
 <details><summary>Shareholding</summary>{s.shareholding.data?<Metrics rows={s.shareholding.data}/>:<p>Evidence unavailable.</p>}</details>
 <details><summary>Corporate actions and peers</summary><h4>Actions</h4>{s.corporate_actions.data?.length?<ul>{s.corporate_actions.data.map((r,i)=><li key={i}>{r.name} · {r.date||"Date not supplied"}</li>)}</ul>:<p>No usable action evidence.</p>}<h4>Peers</h4>{s.competitors.data?.length?<ul>{s.competitors.data.map((r,i)=><li key={i}>{r.name} · {r.sector||"Sector not supplied"}</li>)}</ul>:<p>No usable peer evidence.</p>}</details>
 <p className="muted tiny">{evidence.notice} No fair-value estimate or investment verdict.</p>
 </details>;
}
