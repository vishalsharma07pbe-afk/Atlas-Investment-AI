import {useState} from "react";

export type ValuePoint={date:string;value:number|null};
const fmt=(n:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(n);
export function ValueHistory({points}:{points:ValuePoint[]}){
 const [period,setPeriod]=useState(90);
 const ordered=points.filter(p=>/^\d{4}-\d{2}-\d{2}$/.test(p.date)&&Number.isFinite(Date.parse(p.date))).sort((a,b)=>a.date.localeCompare(b.date));
 const last=ordered[ordered.length-1];const start=last?Date.parse(last.date)-(period-1)*86400000:0;
 const shown=ordered.filter(p=>period===0||Date.parse(p.date)>=start);
 const valid=shown.filter((p):p is {date:string;value:number}=>p.value!==null&&Number.isFinite(p.value)&&p.value>=0);
 const low=valid.length?Math.min(...valid.map(p=>p.value)):0,high=valid.length?Math.max(...valid.map(p=>p.value)):0;
 const spread=high-low||Math.max(1,high*.02),min=high===low?low-spread/2:low,max=high===low?high+spread/2:high;
 const first=shown[0],lastShown=shown[shown.length-1];const duration=first&&lastShown?Math.max(86400000,Date.parse(lastShown.date)-Date.parse(first.date)):86400000;
 const x=(date:string)=>12+(Date.parse(date)-Date.parse(first.date))/duration*476;
 const y=(v:number)=>12+(max-v)/(max-min)*128;
 const [hover,setHover]=useState<string|null>(null);
 const selected=valid.find(p=>p.date===hover)??valid[valid.length-1];
 return <section className="terminal-value-history" aria-label="Recorded valuation history"><div className="sectionhead"><div><h3>Portfolio value history</h3><p className="muted tiny">Recorded holdings-only value. Deposits, withdrawals and changes to holdings can affect the series. Not investment return.</p></div><div className="terminal-chart-toolbar"><div role="group" aria-label="Valuation history period">{[30,90,365,0].map(n=><button type="button" className={period===n?"on":""} aria-pressed={period===n} key={n} onClick={()=>{setPeriod(n);setHover(null)}}>{n===0?"All":n+"D"}</button>)}</div></div></div>
 {valid.length<2?<div className="terminal-chart-empty"><strong>{valid.length===1?"One complete valuation recorded":"No complete valuations in this period"}</strong><small>{valid.length===1?fmt(valid[0].value)+" · "+valid[0].date:"At least two complete dated valuations are needed for a history chart."}</small></div>:<><div className="terminal-history-readout"><strong>{fmt(selected.value)}</strong><span>{selected.date} · recorded value</span></div><svg viewBox="0 0 500 152" className="terminal-history-svg" role="img" aria-label="Dated recorded portfolio values">
 {[12,44,76,108,140].map(n=><line key={n} x1="12" x2="488" y1={n} y2={n} stroke="var(--row-line)" strokeDasharray="3 4"/>)}
 {shown.slice(1).map((p,i)=>{const prev=shown[i];return p.value!==null&&prev.value!==null&&Number.isFinite(p.value)&&Number.isFinite(prev.value)&&p.value>=0&&prev.value>=0&&Date.parse(p.date)-Date.parse(prev.date)<=7*86400000?<line key={p.date} x1={x(prev.date)} y1={y(prev.value)} x2={x(p.date)} y2={y(p.value)} stroke="var(--accent)" strokeWidth="2" vectorEffect="non-scaling-stroke"/>:null})}
 {valid.map(p=><circle key={p.date} cx={x(p.date)} cy={y(p.value)} r={selected.date===p.date?4:2} fill="var(--accent)" onMouseEnter={()=>setHover(p.date)}><title>{p.date}: {fmt(p.value)}</title></circle>)}</svg><div className="terminal-history-axis"><span>{first.date}</span><span>{lastShown.date}</span></div><details><summary>View recorded observations</summary><div className="tablewrap"><table><thead><tr><th>Date</th><th>Recorded value</th></tr></thead><tbody>{shown.map(p=><tr key={p.date}><td>{p.date}</td><td>{p.value===null?"Incomplete":fmt(p.value)}</td></tr>)}</tbody></table></div></details></>}
 <p className="muted tiny">Incomplete observations and intervals exceeding seven days are not connected. No missing history is reconstructed.</p></section>;
}
export function EvidenceBars({title,rows,unit="%",format,neutral=false}:{title:string;rows:{label:string;value:number|null|undefined}[];unit?:string;format?:(v:number)=>string;neutral?:boolean}){
 const values=rows.map(r=>r.value).filter((v):v is number=>typeof v==="number"&&Number.isFinite(v));const max=Math.max(1,...values.map(Math.abs));const negative=values.some(v=>v<0);
 return <figure className="terminal-evidence-bars" aria-label={title}><figcaption>{title}</figcaption>{rows.map((r,i)=>{const valid=typeof r.value==="number"&&Number.isFinite(r.value);const v=valid?r.value!:0;return <div className="terminal-evidence-row" key={i}><span>{r.label}</span><div className={"terminal-evidence-track"+(negative?" signed":"")} aria-hidden="true">{valid&&<i className={neutral?"neutral":v<0?"loss":"gain"} style={{width:Math.abs(v)/max*(negative?50:100)+"%",left:negative?(v<0?50-Math.abs(v)/max*50:50)+"%":"0"}}/>}</div><strong className={valid&&!neutral?v<0?"negative":v>0?"positive":"":""}>{valid?(format?format(v):v.toFixed(2)+unit):"—"}</strong></div>})}</figure>;
}

export function MarketTiles({title,items,period}:{title:string;items:{key:string;label:string;exchange:string;date:string;value:number|null}[];period:string}){
 const unique=[...new Map(items.map(i=>[i.key,i])).values()];
 return <section className="terminal-market-tiles" aria-label={title}><div className="sectionhead"><div><h3>{title}</h3><p className="muted tiny">Equal-sized tiles show observed changes, not market capitalization or a full-market heatmap.</p></div></div>{unique.length?<div className="terminal-tiles-grid">{unique.map(i=>{const valid=i.value!==null&&Number.isFinite(i.value);const value=valid?i.value!:0;return <article className={valid?value>0?"tile-up":value<0?"tile-down":"tile-flat":"tile-flat"} key={i.key}><span>{i.exchange}</span><strong>{i.label}</strong><b>{valid?(value>0?"+":"")+value.toFixed(2)+"%":"—"}</b><small>{period} · {i.date}</small></article>})}</div>:<p className="muted tiny">No usable observations in this sample.</p>}</section>;
}
