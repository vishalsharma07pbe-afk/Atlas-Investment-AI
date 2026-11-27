import {useState} from "react";
import PortfolioVisuals from "./PortfolioVisuals";
import MutualFundNavResearch from "./MutualFundNavResearch";
import MutualFundSchemeSearch from "./MutualFundSchemeSearch";
import MutualFundSnapshotReview from "./MutualFundSnapshotReview";
import AmfiNavImport from "./AmfiNavImport";
import MutualFundHistoryImport from "./MutualFundHistoryImport";
import type {SharedNavHistory} from "./MutualFundHistoryImport";
import MutualFundComparison from "./MutualFundComparison";
import MutualFundReconciliation from "./MutualFundReconciliation";
import NavRefreshPreflight from "./NavRefreshPreflight";
import MutualFundPlanning from "./MutualFundPlanning";
import MutualFundGoals from "./MutualFundGoals";
import MutualFundRisk from "./MutualFundRisk";
import MutualFundHistoricalRisk from "./MutualFundHistoricalRisk";
import NavCatalog from "./NavCatalog";
import MutualFundResearchDashboard from "./MutualFundResearchDashboard";
import SavedSipPlans from "./SavedSipPlans";

export type FundHolding = {
  id:number;symbol:string;asset_type:string;quantity:number;average_cost:number;
  last_price:number|null;invested:number;market_value:number|null;unrealized_pnl:number|null;price_as_of:string|null;
};

const fmt=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);

export default function MutualFundHoldings({holdings}:{holdings:FundHolding[]}){
  const [view,setView]=useState<"research"|"overview"|"find"|"compare"|"plan"|"risk"|"more">("research");
  const [validatedHistory,setValidatedHistory]=useState<SharedNavHistory|null>(null);
  const [validatedHistories,setValidatedHistories]=useState<SharedNavHistory[]>([]);
  function acceptHistory(history:SharedNavHistory|null,schemeCode?:string){
    setValidatedHistory(history);
    if(history)setValidatedHistories(previous=>[...previous.filter(item=>item.schemeCode!==history.schemeCode),history].slice(-5));
    else if(schemeCode)setValidatedHistories(previous=>previous.filter(item=>item.schemeCode!==schemeCode));
  }
  const funds=holdings.filter(h=>h.asset_type==="MUTUAL_FUND");
  const invested=funds.reduce((sum,h)=>sum+Number(h.invested),0);
  const priced=funds.filter(h=>h.last_price!==null && h.market_value!==null);
  const pricedValue=priced.reduce((sum,h)=>sum+Number(h.market_value),0);
  const pricedCost=priced.reduce((sum,h)=>sum+Number(h.invested),0);
  const unpriced=funds.length-priced.length;
  const gain=priced.length?pricedValue-pricedCost:null;
  const gainPct=gain===null||pricedCost===0?null:100*gain/pricedCost;
  const views=[
    {id:"research",icon:"✦",label:"Research picks",hint:"Qualified funds only"},
    {id:"overview",icon:"⌂",label:"Overview",hint:"Your funds in one place"},
    {id:"find",icon:"⌕",label:"Find a fund",hint:"Search by name or code"},
    {id:"compare",icon:"⇄",label:"Compare funds",hint:"Returns side by side"},
    {id:"plan",icon:"◎",label:"Plan a goal",hint:"SIP and target planning"},
    {id:"risk",icon:"◇",label:"Check risk",hint:"Diversification and falls"},
  ] as const;
  return <div className="mf-dashboard">
    <section className="mf-hero glass">
      <div><small className="section-kicker">MUTUAL FUNDS</small><h2>Invest with a clearer view</h2><p>See how your funds are doing, compare choices and plan your goals—all in plain language.</p></div>
      <div className="mf-hero-value"><span>Current saved value</span><strong>{priced.length?fmt(pricedValue):"—"}</strong><small>{unpriced?`${unpriced} fund${unpriced===1?"":"s"} need a current NAV`:"All saved funds have a NAV"}</small></div>
    </section>

    <nav className="mf-nav" aria-label="Mutual fund tasks">{views.map(item=><button key={item.id} type="button" aria-current={view===item.id?"page":undefined} className={view===item.id?"active":""} onClick={()=>setView(item.id)}><i>{item.icon}</i><span><strong>{item.label}</strong><small>{item.hint}</small></span></button>)}<button type="button" aria-current={view==="more"?"page":undefined} className={view==="more"?"active":""} onClick={()=>setView("more")}><i>•••</i><span><strong>More tools</strong><small>Imports and data checks</small></span></button></nav>

    {view==="research"&&<div className="mf-task-pane active"><MutualFundResearchDashboard onExplore={()=>setView("find")}/></div>}
    {view==="overview"&&<div className="mf-task-pane active">
      <div className="mf-stats">
        <article><span>Amount invested</span><strong>{fmt(invested)}</strong><small>What you originally paid</small></article>
        <article><span>Current value</span><strong>{priced.length?fmt(pricedValue):"—"}</strong><small>Using your saved NAVs</small></article>
        <article><span>Gain / loss</span><strong className={(gain||0)>=0?"positive":"negative"}>{gain===null?"—":fmt(gain)}</strong><small>{gainPct===null?"Add NAVs to calculate":`${gainPct>=0?"+":""}${gainPct.toFixed(2)}% overall`}</small></article>
        <article><span>Funds owned</span><strong>{funds.length}</strong><small>{unpriced?`${unpriced} needs attention`:"Valuation complete"}</small></article>
      </div>
      <PortfolioVisuals holdings={funds}/>
      {unpriced>0&&<div role="status" className="mf-attention"><span>!</span><div><strong>Some values are missing</strong><p>Add the latest NAV (price per unit) for {unpriced} fund position{unpriced===1?"":"s"} to see a complete portfolio value and gain/loss.</p></div></div>}
      <section className="mf-card glass">
        <div className="mf-card-head"><div><small className="section-kicker">YOUR INVESTMENTS</small><h2>Your fund holdings</h2></div><span>Saved NAVs · not live</span></div>
        <div className="mf-holding-list">{funds.map(f=>{const performance=f.last_price===null||Number(f.average_cost)===0?null:100*(Number(f.last_price)/Number(f.average_cost)-1);return <article key={f.id}><div className="mf-fund-name"><i>{f.symbol.slice(0,2)}</i><div><strong>{f.symbol}</strong><small>{f.quantity} units</small></div></div><div><span>Invested</span><strong>{fmt(Number(f.invested))}</strong></div><div><span>Current value</span><strong>{f.market_value===null?"—":fmt(Number(f.market_value))}</strong></div><div><span>Gain / loss</span><strong className={(performance||0)>=0?"positive":"negative"}>{performance===null?"NAV needed":`${performance>=0?"+":""}${performance.toFixed(2)}%`}</strong></div></article>})}{!funds.length&&<div className="mf-empty"><strong>No mutual fund holdings saved</strong><p>Add a mutual fund from Research Home using “Add or update holding”.</p></div>}</div>
        <details className="mf-table-details"><summary>View detailed numbers</summary><div className="tablewrap"><table><thead><tr><th>FUND</th><th>UNITS</th><th>AVG. BUY NAV</th><th>CURRENT NAV</th><th>INVESTED</th><th>CURRENT VALUE</th><th>GAIN / LOSS</th></tr></thead><tbody>{funds.map(f=><tr key={f.id}><td className="symbol">{f.symbol}</td><td>{f.quantity}</td><td>{fmt(Number(f.average_cost))}</td><td>{f.last_price===null?"—":fmt(Number(f.last_price))}</td><td>{fmt(Number(f.invested))}</td><td>{f.market_value===null?"—":fmt(Number(f.market_value))}</td><td>{f.unrealized_pnl===null?"—":fmt(Number(f.unrealized_pnl))}</td></tr>)}{!funds.length&&<tr><td colSpan={7} className="empty">No mutual fund holdings saved. Add one from Research Home.</td></tr>}</tbody></table></div></details>
        <p className="muted tiny">Benchmark returns, expense ratios, fund overlap and forward NAV predictions are unavailable until verified fund reference and historical data are connected. No estimates are fabricated.</p>
      </section>
    </div>}

    {view==="find"&&<div className="mf-task-pane active"><div className="mf-explainer"><strong>Find the exact fund you want</strong><p>Search using the fund name or scheme code. NAV means the price of one fund unit and is usually updated once per business day.</p></div><NavCatalog/></div>}
    {view==="compare"&&<div className="mf-task-pane active"><div className="mf-explainer"><strong>Compare funds fairly</strong><p>Add historical NAV files for two funds. ATLAS compares the same date range so you can review growth and falls without mixing periods.</p></div><MutualFundHistoryImport onValidated={acceptHistory}/><MutualFundComparison validatedHistories={validatedHistories} onRemoveValidated={code=>setValidatedHistories(previous=>previous.filter(item=>item.schemeCode!==code))}/></div>}
    {view==="plan"&&<div className="mf-task-pane active"><div className="mf-explainer"><strong>Save your SIPs, then plan the goal</strong><p>Keep your monthly fund plans in one place. The calculators below help with scenarios; their return rate is an assumption, not a forecast.</p></div><SavedSipPlans/><MutualFundGoals/><MutualFundPlanning holdings={holdings}/></div>}
    {view==="risk"&&<div className="mf-task-pane active"><div className="mf-explainer"><strong>Understand concentration and past falls</strong><p>Check whether too much money sits in one fund and, when history is available, see the largest past drop. Past performance does not predict future returns.</p></div><MutualFundRisk holdings={holdings}/><MutualFundHistoricalRisk validatedHistory={validatedHistory}/></div>}
    {view==="more"&&<div className="mf-task-pane active"><div className="mf-explainer"><strong>Advanced data tools</strong><p>Use these only when importing or checking source files. Your holdings are never changed without an explicit portfolio action.</p></div><MutualFundSchemeSearch/><AmfiNavImport/><MutualFundReconciliation holdings={holdings} validatedHistories={validatedHistories}/><MutualFundSnapshotReview holdings={holdings}/><NavRefreshPreflight/><MutualFundNavResearch/></div>}
  </div>;
}
