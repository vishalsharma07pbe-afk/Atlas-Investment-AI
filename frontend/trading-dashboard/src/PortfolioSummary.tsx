type Analysis={holdingCount:number;invested:number;pricedMarketValue:number;pricedUnrealizedPnl:number;unpricedHoldings:number;valuationComplete:boolean;recentRecordedHoldings?:number;stalePriceHoldings?:number;undatedPriceHoldings?:number;futureDatedPriceHoldings?:number;valuationFreshnessNotice?:string};
const fmt=(n:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(n);
export default function PortfolioSummary({analysis,onOpen,holdings=[],feedConnected=false}:{analysis:Analysis|null;onOpen:()=>void;holdings?:{asset_type:string;price_as_of:string|null;one_day_change:number|null}[];feedConnected?:boolean}){
 const equities=holdings.filter(h=>h.asset_type==="EQUITY"),fresh=equities.filter(h=>h.price_as_of!==null&&Date.now()-Date.parse(h.price_as_of)>=0&&Date.now()-Date.parse(h.price_as_of)<=20000).length;
 const daily=holdings.filter(h=>h.one_day_change!==null);const dayChange=daily.reduce((total,h)=>total+Number(h.one_day_change),0);
 return <section className="panel glass overview-portfolio" aria-label="Portfolio summary">
  <div className="sectionhead"><div><small className="section-kicker">YOUR INVESTMENTS</small><h2>Portfolio at a glance</h2><p className="muted tiny">{feedConnected?"Market feed connected · values refresh automatically when fresh quotes arrive.":"Last recorded values · fresh market connection not verified."}</p></div><button type="button" className="secondary" onClick={onOpen}>Open portfolio</button></div>
  {!analysis?<p role="status">Portfolio summary not available yet.</p>:analysis.holdingCount===0?<p>No investments recorded. Open My Portfolio to add or synchronize holdings.</p>:<div className="overview-metrics">
   <article><span>Invested</span><strong>{fmt(analysis.invested)}</strong></article>
   <article><span>Recorded value</span><strong>{analysis.holdingCount===analysis.unpricedHoldings?"—":fmt(analysis.pricedMarketValue)}</strong><small>{feedConnected&&equities.length>0?`${fresh}/${equities.length} stocks priced in the last 20s`:analysis.recentRecordedHoldings!==undefined?`${analysis.recentRecordedHoldings}/${analysis.holdingCount} recent recorded`:analysis.valuationComplete?"All holdings priced":analysis.unpricedHoldings+" unpriced"}</small></article>
   <article><span>Unrealized P&amp;L</span><strong className={analysis.pricedUnrealizedPnl>=0?"positive":"negative"}>{analysis.holdingCount===analysis.unpricedHoldings?"—":fmt(analysis.pricedUnrealizedPnl)}</strong><small>Priced holdings only</small></article>
   <article><span>Day change · priced subset</span><strong className={dayChange>=0?"positive":"negative"}>{daily.length?fmt(dayChange):"—"}</strong><small>{daily.length}/{analysis.holdingCount} with previous close / NAV · {analysis.holdingCount} holdings</small></article>
  </div>}
  {!!analysis&&analysis.holdingCount>0&&analysis.recentRecordedHoldings!==undefined&&analysis.recentRecordedHoldings<analysis.holdingCount&&<p className="muted tiny" role="status">Some valuations are missing, aged or undated. Recorded totals may not reflect current market value.</p>}
 </section>;
}
