import {useId} from "react";
export const finite=(v:unknown):v is number=>typeof v==="number"&&Number.isFinite(v);
export const fmt=(v:unknown,digits=2)=>finite(v)?v.toLocaleString("en-IN",{maximumFractionDigits:digits}):"—";
export const signed=(v:unknown)=>finite(v)?(v>0?"+":"")+v.toFixed(2)+"%":"—";
export function CoverageMeter({label,value,total}:{label:string;value:number;total:number}){
 if(!finite(value)||!finite(total)||total<=0||value<0||value>total)return null;
 const percent=value/total*100;
 return <div className="research-meter"><div><span>{label}</span><strong>{value.toLocaleString("en-IN")} / {total.toLocaleString("en-IN")}</strong></div><div className="research-meter-track" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={total} aria-valuenow={value}><i style={{width:percent+"%"}}/></div><small>{percent.toFixed(0)}% coverage</small></div>;
}
export function ObservationChart({title,points,unit="",neutral=false}:{title:string;points:{date:string;value:number|null}[];unit?:string;neutral?:boolean}){
 const id=useId();
 const unique=[...new Map(points.filter(p=>p.date&&finite(p.value)).map(p=>[p.date,p])).values()].sort((a,b)=>a.date.localeCompare(b.date)).slice(-30);
 if(unique.length<2)return null;
 const values=unique.map(p=>p.value!);
 const min=Math.min(0,...values),max=Math.max(0,...values),span=max-min||1;
 const y=(v:number)=>10+(max-v)/span*94;
 const x=(i:number)=>18+i*264/(unique.length-1);
 const path=values.map((v,i)=>(i===0?"M":"L")+x(i)+" "+y(v)).join(" ");
 const latest=values[values.length-1],baseline=y(0);
 return <figure className="research-observation-chart" aria-label={title}><figcaption>{title}</figcaption><div className="research-chart-readout"><strong>{fmt(latest)}{unit}</strong><small>{unique[unique.length-1].date}</small></div><svg viewBox="0 0 300 116" role="img" aria-label={title+" trend, observed dates only"}><defs><linearGradient id={id} x1="0" x2="0" y1="0" y2="1"><stop stopColor="var(--accent)" stopOpacity=".22"/><stop offset="1" stopColor="var(--accent)" stopOpacity=".02"/></linearGradient></defs>{[10,41,72,104].map(v=><line key={v} x1="18" x2="282" y1={v} y2={v} stroke="var(--row-line)" strokeDasharray="3 4"/>)}<line x1="18" x2="282" y1={baseline} y2={baseline} stroke="currentColor" opacity=".28"/><path d={path+" L282 "+baseline+" L18 "+baseline+" Z"} fill={"url(#"+id+")"}/><path d={path} stroke="var(--accent)" fill="none" strokeWidth="2.3" strokeLinejoin="round" vectorEffect="non-scaling-stroke"/>{values.map((v,i)=><circle key={unique[i].date} cx={x(i)} cy={y(v)} r={2.5} fill={neutral?"var(--accent)":v<0?"var(--danger)":"var(--terminal-positive)"}><title>{unique[i].date}: {fmt(v)}{unit}</title></circle>)}</svg><div className="research-chart-axis"><span>{unique[0].date}</span><span>{unique[unique.length-1].date}</span></div><small>Reported observations · not interpolated sessions</small></figure>;
}
