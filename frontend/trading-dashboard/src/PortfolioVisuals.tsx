import {useMemo} from "react";

type Holding={asset_type:string;market_value:number|null;invested:number};
const palette=["#2caa86","#6489df","#a889d9","#dfaa59","#8293a9"];
const money=(n:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(n);
const label=(s:string)=>s==="EQUITY"?"Stocks":s==="MUTUAL_FUND"?"Mutual funds":s.toLowerCase().replace(/_/g," ");
export function recordedAllocation(holdings:Holding[]){
 const grouped=new Map<string,number>();
 let excluded=0,cost=0,pricedCount=0,costComplete=true;
 for(const h of holdings){
  const value=h.market_value;
  if(value==null||!Number.isFinite(Number(value))||Number(value)<0){excluded++;continue;}
  pricedCount++;
  grouped.set(h.asset_type,(grouped.get(h.asset_type)??0)+Number(value));
  if(h.invested==null||!Number.isFinite(Number(h.invested))||Number(h.invested)<0)costComplete=false;
  else cost+=Number(h.invested);
 }
 const total=[...grouped.values()].reduce((a,b)=>a+b,0);
 const slices=[...grouped.entries()].filter(([,value])=>value>0).sort((a,b)=>b[1]-a[1]).map(([type,value],i)=>({type,value,share:total>0?value/total:0,color:palette[i%palette.length]}));
 return {total,slices,excluded,pricedCount,cost:costComplete?cost:null};
}

export default function PortfolioVisuals({holdings}:{holdings:Holding[]}){
 const {total,slices,excluded,pricedCount,cost}=useMemo(()=>recordedAllocation(holdings),[holdings]);
 const max=Math.max(1,total,cost??0);
 const circumference=2*Math.PI*42;
 let offset=0;
 return <section className="panel glass terminal-portfolio-visuals" aria-label="Recorded portfolio charts">
  <div className="sectionhead"><div><small className="section-kicker">PORTFOLIO BREAKDOWN</small><h2>Allocation &amp; value</h2></div><span className="terminal-neutral-tag">Recorded</span></div>
  {!pricedCount?<div className="terminal-chart-empty"><svg viewBox="0 0 48 48" width="44" height="44" aria-hidden="true"><circle cx="24" cy="24" r="17" fill="none" stroke="currentColor" strokeWidth="5" strokeDasharray="5 5"/></svg><strong>No recorded valuations</strong><p>Charts appear automatically after holdings have recorded prices.</p></div>:<>
   <div className="terminal-allocation-content">
    {total>0?<svg className="terminal-donut" viewBox="0 0 120 120" role="img" aria-label="Asset allocation by recorded value"><circle cx="60" cy="60" r="42" fill="none" stroke="var(--row-line)" strokeWidth="14"/>{slices.map(s=>{const start=offset;const length=s.share*circumference;offset+=length;return <circle key={s.type} cx="60" cy="60" r="42" fill="none" stroke={s.color} strokeWidth="14" strokeDasharray={length+" "+Math.max(0,circumference-length)} strokeDashoffset={-start} transform="rotate(-90 60 60)"/>})}<text x="60" y="56" textAnchor="middle" className="terminal-donut-number">{slices.length}</text><text x="60" y="70" textAnchor="middle" className="terminal-donut-label">Asset types</text></svg>:<div className="terminal-chart-empty"><strong>Recorded value is zero</strong><small>Allocation percentages are unavailable.</small></div>}
    <div className="terminal-chart-legend">{slices.map(s=><div key={s.type}><i style={{background:s.color}}/><span>{label(s.type)}<small>{money(s.value)}</small></span><strong>{(s.share*100).toFixed(1)}%</strong></div>)}</div>
   </div>
   <div className="terminal-value-bars" aria-label="Priced holdings cost and value comparison">
    {[{name:"Priced cost",value:cost},{name:"Recorded value",value:total}].map((r,i)=><div key={r.name}><div><span>{r.name}</span><strong>{r.value==null?"Unavailable":money(r.value)}</strong></div><div className="terminal-value-track" aria-hidden="true">{r.value!==null&&<i style={{width:(r.value/max*100)+"%"}} className={i?"gain":"flat"}/>}</div></div>)}
   </div>
   <p className="muted tiny">{excluded?excluded+" position(s) without a usable recorded valuation excluded. ":""}Recorded prices may be aged. Not a historical return chart.</p>
  </>}
 </section>;
}
