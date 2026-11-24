type RecordRow={trade_date:string;observed_at:string;buy_amount:string;sell_amount:string;net_amount:string};
type Participant={status:string;retrieved_at:string|null;endpoint:string;records:RecordRow[]};
export type InstitutionalActivity={status:string;market?:string;unit?:string;participants?:Record<"FII"|"DII",Participant>;paired_five_date_window?:{dates:string[];fii_net:string;dii_net:string}|null;blockers?:string[];notice?:string};
const format=(n:string)=>{const value=Number(n);return Number.isFinite(value)?new Intl.NumberFormat("en-IN",{maximumFractionDigits:2}).format(value):"—";};
const words=(s:string)=>s.toLowerCase().replace(/_/g," ");
export default function AutomaticInstitutionalActivity({data}:{data:InstitutionalActivity}){
 return <section className="panel glass" aria-label="Automatic institutional activity">
 <div className="sectionhead"><div><small className="section-kicker">INSTITUTIONAL INTELLIGENCE</small><h3>FII / DII market activity</h3><p className="muted tiny">NSE cash market aggregate · Upstox · provider-reported units</p></div><span className="tag">{words(data.status)}</span></div>
 {data.participants?<div className="horizon-cards">{(["FII","DII"] as const).map(kind=>{
 const section=data.participants![kind],latest=section.records[0];
 return <article className="horizon-card" key={kind}><h3>{kind}</h3>{latest?<><strong>{Number(latest.net_amount)>0?"Net buying":Number(latest.net_amount)<0?"Net selling":"Balanced"}: {format(latest.net_amount)}</strong><p className="muted tiny">Observed {latest.trade_date} · not a live tick</p><dl><div><dt>Gross buying</dt><dd>{format(latest.buy_amount)}</dd></div><div><dt>Gross selling</dt><dd>{format(latest.sell_amount)}</dd></div></dl><details><summary>Recent provider observations</summary><div className="tablewrap"><table><thead><tr><th>Date</th><th>Net amount</th></tr></thead><tbody>{section.records.map(r=><tr key={r.trade_date}><td>{r.trade_date}</td><td>{format(r.net_amount)}</td></tr>)}</tbody></table></div><p className="muted tiny">Source: {section.endpoint}</p></details></>:<p>No recent usable observation · {words(section.status)}</p>}</article>;
 })}</div>:<p>Automatic institutional data is not available.</p>}
 {data.paired_five_date_window&&<div className="overview-metrics"><article><span>FII net · five matched dates</span><strong>{format(data.paired_five_date_window.fii_net)}</strong></article><article><span>DII net · five matched dates</span><strong>{format(data.paired_five_date_window.dii_net)}</strong></article><article><span>Observed dates</span><small>{data.paired_five_date_window.dates.join(" · ")}</small></article></div>}
 <p className="muted tiny">{data.notice||"Authorized provider data is required. No inferred trades or units."}</p>
 {!!data.blockers?.length&&<details><summary>Institutional evidence still required</summary><p>{data.blockers.map(words).join(" · ")}</p></details>}
 </section>;
}
