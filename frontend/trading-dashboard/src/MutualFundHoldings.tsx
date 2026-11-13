import React,{useState} from "react";
import MutualFundNavResearch from "./MutualFundNavResearch";
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

export type FundHolding = {
  id:number;symbol:string;asset_type:string;quantity:number;average_cost:number;
  last_price:number|null;invested:number;market_value:number|null;unrealized_pnl:number|null;price_as_of:string|null;
};

const fmt=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);

export default function MutualFundHoldings({holdings}:{holdings:FundHolding[]}){
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
  return <div>
    <div className="stats">
      <div className="stat glass"><small>FUND POSITIONS</small><strong>{funds.length}</strong><span>Saved mutual fund holdings</span></div>
      <div className="stat glass"><small>TOTAL INVESTED</small><strong>{fmt(invested)}</strong><span>Cost basis of all funds</span></div>
      <div className="stat glass"><small>RECORDED VALUE</small><strong>{priced.length?fmt(pricedValue):"—"}</strong><span>Only funds with entered NAV</span></div>
      <div className="stat glass"><small>UNREALISED P&amp;L</small><strong>{priced.length?fmt(pricedValue-pricedCost):"—"}</strong><span>Priced fund positions only</span></div>
    </div>
    <section className="panel glass">
      <div className="sectionhead"><div><small className="section-kicker">MUTUAL FUND WORKSPACE</small><h2>Your fund holdings</h2></div><span className="tag">MANUAL NAV</span></div>
      <p className="muted tiny">These figures use the holdings and prices you entered, not verified or live NAV data. Update holdings in My Portfolio.</p>
      {unpriced>0&&<p role="status" className="notice">Incomplete valuation: {unpriced} fund position(s) have no recorded NAV. Totals for recorded value and P&amp;L exclude them.</p>}
      <div className="tablewrap"><table><thead><tr><th>FUND</th><th>UNITS</th><th>AVERAGE COST</th><th>RECORDED NAV</th><th>INVESTED</th><th>RECORDED VALUE</th><th>P&amp;L</th></tr></thead><tbody>
        {funds.map(f=><tr key={f.id}><td className="symbol">{f.symbol}</td><td>{f.quantity}</td><td>{fmt(Number(f.average_cost))}</td><td>{f.last_price===null?"—":fmt(Number(f.last_price))}</td><td>{fmt(Number(f.invested))}</td><td>{f.market_value===null?"—":fmt(Number(f.market_value))}</td><td>{f.unrealized_pnl===null?"—":fmt(Number(f.unrealized_pnl))}</td></tr>)}
        {!funds.length&&<tr><td colSpan={7} className="empty">No mutual fund holdings saved. Add one from My Portfolio.</td></tr>}
      </tbody></table></div>
      <p className="muted tiny">Benchmark returns, expense ratios, fund overlap and forward NAV predictions are unavailable until verified fund reference and historical data are connected. No estimates are fabricated.</p>
    </section>
    <AmfiNavImport/>
    <MutualFundHistoryImport onValidated={acceptHistory}/>
    <MutualFundComparison validatedHistories={validatedHistories} onRemoveValidated={code=>setValidatedHistories(previous=>previous.filter(item=>item.schemeCode!==code))}/>
    <MutualFundPlanning holdings={holdings}/>
    <MutualFundGoals/>
    <MutualFundRisk holdings={holdings}/>
    <MutualFundHistoricalRisk validatedHistory={validatedHistory}/>
    <MutualFundReconciliation holdings={holdings}/>
    <NavRefreshPreflight/>
    <MutualFundNavResearch/>
  </div>;
}
