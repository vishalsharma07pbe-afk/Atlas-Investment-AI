type Point={period:string;value:number};
type Metric={name:string;history:Point[]};
type Ratio={name:string;company_value:number;sector_value:number|null;unit:string};
type Section<T>={status:string;data:T|null;source:{provider:string;endpoint:string|null;retrieved_at:string}|null};
export type CompanyEvidence={isin:string;retrieved_at:string;available_sections:number;total_sections:number;notice:string;sections:{
 profile:Section<{sector?:string;industry?:string;company_name?:string}>;
 ratios:Section<Ratio[]>;
 income_statement:Section<{units:string|null;rows:Metric[]}>;
 cash_flow:Section<{units:string|null;rows:Metric[]}>;
 balance_sheet:Section<{units:string|null;rows:{period:string;total_asset:number|null;total_liability:number|null}[]}>;
 shareholding:Section<Metric[]>;
 corporate_actions:Section<{name:string;date:string|null}[]>;
 competitors:Section<{name:string;sector:string|null}[]>;
}};
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
 <h4>Company vs sector ratios</h4>
 {s.ratios.data?.length?<div className="tablewrap"><table><thead><tr><th>Ratio</th><th>Company</th><th>Sector</th></tr></thead><tbody>{s.ratios.data.map((r,i)=><tr key={i}><td>{r.name}</td><td>{fmt(r.company_value)}{r.unit==="PERCENT"?"%":""}</td><td>{fmt(r.sector_value)}{r.sector_value!==null&&r.unit==="PERCENT"?"%":""}</td></tr>)}</tbody></table></div>:<p>Ratio evidence unavailable.</p>}
 {(["income_statement","cash_flow"] as const).map(key=><details key={key}><summary>{key==="income_statement"?"Income statement":"Cash flow"}</summary>{s[key].data?<><p className="muted tiny">Provider units: {s[key].data!.units||"Not supplied"}</p><Metrics rows={s[key].data!.rows}/></>:<p>Evidence unavailable.</p>}</details>)}
 <details><summary>Balance sheet</summary>{s.balance_sheet.data?<><p>Provider units: {s.balance_sheet.data.units||"Not supplied"}</p><div className="tablewrap"><table><thead><tr><th>Period</th><th>Assets</th><th>Liabilities</th></tr></thead><tbody>{s.balance_sheet.data.rows.map((r,i)=><tr key={i}><td>{r.period}</td><td>{fmt(r.total_asset)}</td><td>{fmt(r.total_liability)}</td></tr>)}</tbody></table></div></>:<p>Evidence unavailable.</p>}</details>
 <details><summary>Shareholding</summary>{s.shareholding.data?<Metrics rows={s.shareholding.data}/>:<p>Evidence unavailable.</p>}</details>
 <details><summary>Corporate actions and peers</summary><h4>Actions</h4>{s.corporate_actions.data?.length?<ul>{s.corporate_actions.data.map((r,i)=><li key={i}>{r.name} · {r.date||"Date not supplied"}</li>)}</ul>:<p>No usable action evidence.</p>}<h4>Peers</h4>{s.competitors.data?.length?<ul>{s.competitors.data.map((r,i)=><li key={i}>{r.name} · {r.sector||"Sector not supplied"}</li>)}</ul>:<p>No usable peer evidence.</p>}</details>
 <p className="muted tiny">{evidence.notice} No fair-value estimate or investment verdict.</p>
 </details>;
}
