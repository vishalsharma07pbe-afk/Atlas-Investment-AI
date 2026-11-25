import {useMemo} from "react";

type Holding={id:number;symbol:string;asset_type:string;quantity:number;average_cost:number;last_price:number|null;invested:number;market_value:number|null;unrealized_pnl:number|null;price_as_of:string|null;valuation_status?:string};
type Analysis={holdingCount:number;invested:number;pricedMarketValue:number;pricedCostBasis?:number;pricedUnrealizedPnl:number;unpricedHoldings:number;valuationComplete:boolean;recentRecordedHoldings?:number;stalePriceHoldings?:number;undatedPriceHoldings?:number;futureDatedPriceHoldings?:number;recordedReturnPercent?:number|null;valuationFreshnessStatus?:string;valuationFreshnessNotice?:string;riskFlags:string[]};

const money=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(value);
const percent=(value:number)=>`${value>=0?"+":""}${value.toFixed(1)}%`;

export default function PortfolioIntelligence({holdings,analysis}:{holdings:Holding[];analysis:Analysis|null}){
 const summary=useMemo(()=>{
  if(!analysis)return null;
  const priced=holdings.filter(item=>item.market_value!==null);
  const marketValue=Number(analysis.pricedMarketValue)||0;
  const pricedCost=analysis.pricedCostBasis!==undefined?Number(analysis.pricedCostBasis):priced.reduce((sum,item)=>sum+Number(item.invested||0),0);
  const rows=priced.map(item=>{
   const value=Number(item.market_value)||0,pnl=Number(item.unrealized_pnl)||0;
   return{...item,value,pnl,weight:marketValue>0?value/marketValue*100:0,returnPct:Number(item.invested)>0?pnl/Number(item.invested)*100:null};
  }).sort((a,b)=>b.value-a.value);
  return{priced,rows,pricedCost,returnPct:analysis.recordedReturnPercent!==undefined?analysis.recordedReturnPercent:pricedCost>0?Number(analysis.pricedUnrealizedPnl)/pricedCost*100:null,largest:rows[0]||null};
 },[holdings,analysis]);

 if(!analysis||!summary)return <section id="portfolio-overview" className="panel glass portfolio-intelligence"><p>Loading portfolio intelligence…</p></section>;
 if(analysis.holdingCount===0)return <section id="portfolio-overview" className="panel glass portfolio-intelligence"><div className="sectionhead"><div><small className="section-kicker">PORTFOLIO INTELLIGENCE</small><h2>Portfolio snapshot</h2></div><span className="tag">RULE-BASED</span></div><div className="portfolio-empty"><strong>Add your first holding</strong><p>Allocation, performance and concentration checks will appear here automatically.</p></div></section>;

 return <section id="portfolio-overview" className="panel glass portfolio-intelligence" aria-label="Portfolio intelligence">
  <div className="sectionhead"><div><small className="section-kicker">PORTFOLIO INTELLIGENCE</small><h2>Portfolio snapshot</h2></div><span className={`tag ${analysis.valuationComplete&&analysis.valuationFreshnessStatus!=="INCOMPLETE_OR_AGED"?"tag-ready":"tag-warning"}`}>{analysis.valuationFreshnessStatus==="INCOMPLETE_OR_AGED"?"VALUATION GAPS":analysis.valuationComplete?"RECORDED PRICES COMPLETE":"PRICE GAPS"}</span></div>
  <div className="portfolio-health-grid">
   <article><span>Invested capital</span><strong>{money(Number(analysis.invested))}</strong><small>Cost basis of all positions</small></article>
   <article><span>Valued portfolio</span><strong>{summary.priced.length?money(Number(analysis.pricedMarketValue)):"—"}</strong><small>Positions with a recorded price</small></article>
   <article><span>Price coverage</span><strong>{summary.priced.length}/{analysis.holdingCount}</strong><small>{analysis.valuationComplete?"All positions valued":`${analysis.unpricedHoldings} need a price`}</small></article>
   <article><span>Recorded return</span><strong className={summary.returnPct===null?"":summary.returnPct>=0?"positive":"negative"}>{summary.returnPct===null?"Unavailable":percent(summary.returnPct)}</strong><small>{summary.priced.length?money(Number(analysis.pricedUnrealizedPnl))+" unrealised P&L":"No recorded valuation"}</small></article>
   <article><span>Largest position</span><strong>{summary.largest?.symbol||"—"}</strong><small>{summary.largest?`${summary.largest.weight.toFixed(1)}% of priced value`:"No priced position"}</small></article>
   <article><span>Concentration</span><strong>{!summary.largest||!analysis.valuationComplete?"INCOMPLETE":summary.largest.weight>25?"HIGH":"WITHIN BASIC LIMIT"}</strong><small>Basic limit: 25% per position</small></article>
  </div>

  {analysis.recentRecordedHoldings!==undefined&&<div className="portfolio-data-gap" role="status"><strong>Valuation age: {analysis.recentRecordedHoldings}/{analysis.holdingCount} recent recorded</strong><p>{analysis.stalePriceHoldings??0} stale · {analysis.undatedPriceHoldings??0} undated · {analysis.futureDatedPriceHoldings??0} future-dated · {analysis.unpricedHoldings} unpriced.</p><p>{analysis.valuationFreshnessNotice}</p></div>}
  <div className="portfolio-intelligence-body">
   <div className="portfolio-allocation"><h3>Allocation &amp; performance</h3>{summary.rows.map(row=><div className="portfolio-position" key={row.id}>
    <div><strong>{row.symbol}</strong><span>{row.asset_type==="MUTUAL_FUND"?"Mutual fund":"Stock"} · {row.weight.toFixed(1)}%{row.valuation_status&&" · "+row.valuation_status.toLowerCase().replace(/_/g," ")}</span></div>
    <div className="allocation-track" aria-label={`${row.symbol} allocation ${row.weight.toFixed(1)} percent`}><i style={{width:`${Math.min(100,row.weight)}%`}}/></div>
    <div><strong>{money(row.value)}</strong><span className={row.pnl>=0?"positive":"negative"}>{row.returnPct===null?"Return unavailable":percent(row.returnPct)} · {money(row.pnl)}</span></div>
   </div>)}{analysis.unpricedHoldings>0&&<p className="portfolio-data-gap">{analysis.unpricedHoldings} unpriced position(s) are excluded from allocation and return calculations.</p>}</div>
   <div className="portfolio-review"><h3>Needs your review</h3>{analysis.riskFlags.length?<ul className="flags compact-flags">{analysis.riskFlags.map((flag,index)=><li key={index}><span>!</span><div>{flag}<small>{flag.includes("exceeds 25%")?"Check whether this position size matches your own risk limit.":flag.includes("no recorded")?"Refresh or add a verified price to complete valuation.":"Review this portfolio condition before relying on the summary."}</small></div></li>)}</ul>:<div className="portfolio-clear"><strong>No basic risk flags</strong><p>No concentration or pricing issue was detected by the current rule set.</p></div>}</div>
  </div>
  <p className="muted tiny portfolio-method">Calculated from your saved quantities, costs and recorded prices. This is a portfolio measurement, not a buy/sell recommendation.</p>
 </section>;
}
