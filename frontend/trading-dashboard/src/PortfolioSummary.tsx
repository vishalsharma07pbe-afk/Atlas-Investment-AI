type Analysis={holdingCount:number;invested:number;pricedMarketValue:number;pricedUnrealizedPnl:number;unpricedHoldings:number;valuationComplete:boolean;recentRecordedHoldings?:number;stalePriceHoldings?:number;undatedPriceHoldings?:number;futureDatedPriceHoldings?:number;valuationFreshnessNotice?:string};
const fmt=(n:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(n);
export default function PortfolioSummary({analysis,onOpen}:{analysis:Analysis|null;onOpen:()=>void}){
 return <section className="panel glass overview-portfolio" aria-label="Portfolio summary">
  <div className="sectionhead"><div><small className="section-kicker">YOUR INVESTMENTS</small><h2>Portfolio at a glance</h2><p className="muted tiny">Recorded values, not guaranteed live quotes.</p></div><button type="button" className="secondary" onClick={onOpen}>Open portfolio</button></div>
  {!analysis?<p role="status">Portfolio summary not available yet.</p>:analysis.holdingCount===0?<p>No investments recorded. Open My Portfolio to add or synchronize holdings.</p>:<div className="overview-metrics">
   <article><span>Invested</span><strong>{fmt(analysis.invested)}</strong></article>
   <article><span>Recorded value</span><strong>{analysis.holdingCount===analysis.unpricedHoldings?"—":fmt(analysis.pricedMarketValue)}</strong><small>{analysis.recentRecordedHoldings!==undefined?`${analysis.recentRecordedHoldings}/${analysis.holdingCount} recent recorded`:analysis.valuationComplete?"All holdings priced":analysis.unpricedHoldings+" unpriced"}</small></article>
   <article><span>Unrealized P&amp;L</span><strong className={analysis.pricedUnrealizedPnl>=0?"positive":"negative"}>{analysis.holdingCount===analysis.unpricedHoldings?"—":fmt(analysis.pricedUnrealizedPnl)}</strong><small>Priced holdings only</small></article>
   <article><span>Holdings</span><strong>{analysis.holdingCount}</strong></article>
  </div>}
  {!!analysis&&analysis.holdingCount>0&&analysis.recentRecordedHoldings!==undefined&&analysis.recentRecordedHoldings<analysis.holdingCount&&<p className="muted tiny" role="status">Some valuations are missing, aged or undated. Recorded totals may not reflect current market value.</p>}
 </section>;
}
