import SectorPriceView,{type SectorPriceEvidence} from "./SectorPriceView";
import {useEffect,useState} from "react";
import PledgeEvidenceView,{type PledgeEvidence} from "./PledgeEvidenceView";
import FinancialFilingView,{type FilingEvidence} from "./FinancialFilingView";
import CompanyEvidenceCard,{type CompanyEvidence} from "./CompanyEvidenceCard";
type Report={sector_price_context?:SectorPriceEvidence[];independent_financial_evidence?:FilingEvidence|null;independent_pledge_evidence?:PledgeEvidence|null;isin:string;status:string;observations:{id:number;exchange:string;symbol:string;horizon:string;as_of:string;close:number|null;qualification_status:string}[];observed_venues:string[];review_findings:string[];company_evidence:CompanyEvidence|null;venue_observations?:{exchange:string;id:number;as_of:string|null;close:number|null;security_state:string;turnover_proxy_cr:number|null}[];news_evidence?:{source_exchange:string;retrieved_at:string;articles:{id:string;headline:string;url:string;published_at:string;topics:string[]}[];notice:string}|null;ai_review:{reviews:{provider:string;role?:string;findings:{statement:string;evidence_ids:string[]}[]}[];reviewed_at:string;notice:string}|null;notice:string};
const words=(s:string)=>s.toLowerCase().replace(/_/g," ");
export default function UnifiedCompanyReport({isin}:{isin:string}){
 const [report,setReport]=useState<Report|null>(null),[status,setStatus]=useState("Loading current company research…");
 useEffect(()=>{const controller=new AbortController();let active=true;
 setReport(null);setStatus("Loading current company research…");
 async function load(){try{
 const response=await fetch("/intelligence/api/v1/intelligence/research/overview",{cache:"no-store",signal:controller.signal});
 if(!response.ok)throw Error();
 const snapshot=await response.json();const item=snapshot.company_reports?.items?.[isin];
 if(!active)return;
 if(!snapshot.enabled||!item||item.isin!==isin||!Array.isArray(item.observations)){setStatus("No current unified company research in the saved shortlist.");return;}
 setReport(item);setStatus("");
 }catch{if(active)setStatus("Unified company research unavailable.");}}
 void load();return()=>{active=false;controller.abort();};
 },[isin]);
 if(!report)return <p className="muted tiny" role="status">{status}</p>;
 if(report.isin!==isin)return null;
 return <section aria-label="Unified company research"><div className="sectionhead"><div><small className="section-kicker">ONE COMPANY · EXCHANGE-AWARE</small><h3>{report.isin} · {report.observed_venues.join(" + ")}</h3></div><span className="tag">RESEARCH ONLY</span></div>
 <div className="tablewrap"><table><thead><tr><th>Horizon</th><th>Venue</th><th>Observation date</th><th>Close</th><th>Assessment</th></tr></thead><tbody>{report.observations.map(r=><tr key={r.horizon+":"+r.exchange+":"+r.id+":"+r.as_of}><td>{words(r.horizon)}</td><td>{r.exchange}</td><td>{r.as_of}</td><td>{r.close==null?"—":"₹"+r.close.toFixed(2)}</td><td>{words(r.qualification_status)}</td></tr>)}</tbody></table></div>
 {report.review_findings.length>0&&<details><summary>Company review findings</summary><ul>{report.review_findings.map(f=><li key={f}>{words(f)}</li>)}</ul></details>}
 {!!report.venue_observations?.length&&<details><summary>All sampled venue observations</summary>{report.venue_observations.map(v=><p key={v.exchange+":"+v.id}>{v.exchange} · {v.as_of??"No validated close"} · {words(v.security_state)}{v.turnover_proxy_cr!=null?" · ₹"+v.turnover_proxy_cr.toFixed(2)+" cr historical turnover proxy":""}</p>)}</details>}
 {report.sector_price_context?.map(r=><SectorPriceView key={r.exchange+":"+r.id+":"+r.as_of} report={r}/>)}
 {report.independent_financial_evidence&&<FinancialFilingView report={report.independent_financial_evidence}/>}
 {report.independent_pledge_evidence&&<PledgeEvidenceView report={report.independent_pledge_evidence}/>}
 <CompanyEvidenceCard evidence={report.company_evidence??undefined} status={report.company_evidence?"ENABLED":"UNAVAILABLE"}/>
 {report.news_evidence&&<details><summary>Shared company headlines · {report.news_evidence.source_exchange} source</summary>{report.news_evidence.articles.map(a=><p key={a.id}><a href={a.url} target="_blank" rel="noreferrer">{a.headline}</a><small> · {a.published_at}</small></p>)}<p className="muted tiny">{report.news_evidence.notice}</p></details>}
 {report.ai_review?.reviews.length?<details><summary>Shared company AI evidence review · {report.ai_review.reviews.length} providers</summary>{report.ai_review.reviews.map(r=><div key={r.provider}><strong>{r.provider}</strong><ul>{r.findings.map((f,i)=><li key={i}>{f.statement}</li>)}</ul></div>)}<p className="muted tiny">{report.ai_review.notice}</p></details>:<p className="muted tiny">Shared company AI review pending or unavailable.</p>}
 <p className="muted tiny">{report.notice}</p></section>;
}
