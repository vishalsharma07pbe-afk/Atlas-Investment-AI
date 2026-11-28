import {useState} from "react";
import PortfolioVisuals from "./PortfolioVisuals";
import HoldingEditor,{type HoldingDraft,type ExistingFund} from "./HoldingEditor";
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
  last_price:number|null;invested:number;market_value:number|null;unrealized_pnl:number|null;price_as_of:string|null;notes?:string|null;valuation_status?:string;
};

const fmt=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);

export default function MutualFundHoldings({holdings,busy=false,onSave,onRemove,onRefresh}:{holdings:FundHolding[];busy?:boolean;onSave?:(draft:HoldingDraft)=>Promise<void>;onRemove?:(id:number)=>Promise<void>;onRefresh?:()=>Promise<{updated:number;total:number}>}){
  const [view,setView]=useState<"research"|"overview"|"find"|"compare"|"plan"|"risk"|"more">("research");
  const [editorOpen,setEditorOpen]=useState(false);
  const [editing,setEditing]=useState<ExistingFund|null>(null);
  const [editorKey,setEditorKey]=useState(0);
  const [message,setMessage]=useState("");
  const [refreshing,setRefreshing]=useState(false);
  function openEditor(fund:ExistingFund|null=null){setView("overview");setEditing(fund);setEditorKey(k=>k+1);setEditorOpen(true);setMessage("");}
  async function saveFund(draft:HoldingDraft){if(!onSave)throw Error("Holding save unavailable");await onSave(draft);setEditorOpen(false);setEditing(null);setMessage("Fund holding saved. Your portfolio reflects the saved units and available dated NAV.");}
  async function refresh(){if(!onRefresh)return;setRefreshing(true);setMessage("");try{const result=await onRefresh();setMessage(result.total===0?"No fund holdings to refresh.":`Refreshed ${result.updated} of ${result.total} saved fund valuations from dated NAV records. Check the observation dates below.`);}catch{setMessage("NAV refresh unavailable. Existing saved values were retained.");}finally{setRefreshing(false);}}
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
  const aged=priced.filter(f=>f.valuation_status?f.valuation_status!=="RECENT_RECORDED":!f.price_as_of).length;
  const fundName=(f:FundHolding)=>f.notes||f.symbol;
  const navDate=(f:FundHolding)=>f.price_as_of?new Date(f.price_as_of).toLocaleDateString("en-IN",{timeZone:"Asia/Kolkata"}):"Date unavailable";
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
      <div className="mf-hero-value"><span>Current saved value</span><strong>{priced.length?fmt(pricedValue):"—"}</strong><small>{!funds.length?"No saved holdings":unpriced||aged?`${unpriced} unpriced · ${aged} aged or undated`:"All saved funds have recorded NAVs"}</small></div>
    </section>
    {onSave&&<div className="mf-card glass"><div className="mf-card-head"><div><small className="section-kicker">MY INVESTMENTS</small><h2>Manage mutual fund holdings</h2><p className="muted tiny">Add existing units, update a position or track your monthly SIP plans.</p></div><button type="button" className="primary" disabled={busy} onClick={()=>openEditor()}>+ Add mutual fund holding</button></div><div className="terminal-holdings-toolbar"><button type="button" className="secondary" onClick={()=>setView("overview")}>My holdings ({funds.length})</button><button type="button" className="secondary" onClick={()=>setView("plan")}>Manage SIP plans</button>{onRefresh&&<button type="button" className="secondary" disabled={refreshing||busy} onClick={()=>void refresh()}>{refreshing?"Refreshing…":"Refresh saved NAVs"}</button>}</div>{message&&<p role="status">{message}</p>}</div>}

    <nav className="mf-nav" aria-label="Mutual fund tasks">{views.map(item=><button key={item.id} type="button" aria-current={view===item.id?"page":undefined} className={view===item.id?"active":""} onClick={()=>setView(item.id)}><i>{item.icon}</i><span><strong>{item.label}</strong><small>{item.hint}</small></span></button>)}<button type="button" aria-current={view==="more"?"page":undefined} className={view==="more"?"active":""} onClick={()=>setView("more")}><i>•••</i><span><strong>More tools</strong><small>Imports and data checks</small></span></button></nav>

    {view==="research"&&<div className="mf-task-pane active"><MutualFundResearchDashboard onExplore={()=>setView("find")}/></div>}
    {view==="overview"&&<div className="mf-task-pane active">
      {editorOpen&&onSave&&<section className="mf-card glass" aria-label="Add or edit mutual fund holding"><div className="mf-card-head"><div><small className="section-kicker">EXISTING INVESTMENT</small><h2>{editing?"Update fund holding":"Add fund holding"}</h2><p>Search the exact scheme and plan, then enter total units and average purchase NAV.</p></div><button type="button" className="secondary" onClick={()=>{setEditorOpen(false);setEditing(null);}}>Cancel</button></div><HoldingEditor key={editorKey} busy={busy} fundOnly initialFund={editing} existingFunds={funds} onSave={saveFund}/></section>}
      <div className="mf-stats">
        <article><span>Amount invested</span><strong>{fmt(invested)}</strong><small>What you originally paid</small></article>
        <article><span>Current value</span><strong>{priced.length?fmt(pricedValue):"—"}</strong><small>{aged?`${aged} aged or undated · recorded total`:"Using your saved NAVs"}</small></article>
        <article><span>Gain / loss</span><strong className={(gain||0)>=0?"positive":"negative"}>{gain===null?"—":fmt(gain)}</strong><small>{gainPct===null?"Add NAVs to calculate":`${gainPct>=0?"+":""}${gainPct.toFixed(2)}% overall`}</small></article>
        <article><span>Funds owned</span><strong>{funds.length}</strong><small>{unpriced?`${unpriced} needs attention`:aged?`${aged} needs date review`:"Valuation complete"}</small></article>
      </div>
      <PortfolioVisuals holdings={funds}/>
      {unpriced>0&&<div role="status" className="mf-attention"><span>!</span><div><strong>Some values are missing</strong><p>Published NAV is missing for {unpriced} fund position{unpriced===1?"":"s"}. Refresh saved NAVs after the daily AMFI collection, or check the exact scheme code.</p></div></div>}
      <section className="mf-card glass">
        <div className="mf-card-head"><div><small className="section-kicker">YOUR INVESTMENTS</small><h2>Your fund holdings</h2></div><span>Saved NAVs · not live</span></div>
        <div className="mf-holding-list">{funds.map(f=>{const performance=f.last_price===null||Number(f.average_cost)===0?null:100*(Number(f.last_price)/Number(f.average_cost)-1);return <article key={f.id}><div className="mf-fund-name"><i>{f.symbol.slice(0,2)}</i><div><strong>{fundName(f)}</strong><small>{f.quantity} units{f.notes?` · Scheme ${f.symbol}`:""}</small><small>{f.last_price===null?"NAV unavailable":`NAV ${navDate(f)}${f.valuation_status&&f.valuation_status!=="RECENT_RECORDED"?" · "+f.valuation_status.toLowerCase().replace(/_/g," "):""}`}</small></div></div><div><span>Invested</span><strong>{fmt(Number(f.invested))}</strong></div><div><span>Current value</span><strong>{f.market_value===null?"—":fmt(Number(f.market_value))}</strong></div><div><span>Gain / loss</span><strong className={(performance||0)>=0?"positive":"negative"}>{performance===null?"NAV needed":`${performance>=0?"+":""}${performance.toFixed(2)}%`}</strong>{onSave&&<button type="button" className="secondary" disabled={busy} onClick={()=>openEditor(f)}>Edit holding</button>}{onRemove&&<button type="button" className="danger" disabled={busy} onClick={()=>void onRemove(f.id)}>Delete</button>}</div></article>})}{!funds.length&&<div className="mf-empty"><strong>No mutual fund holdings saved</strong><p>Record your existing units using the add holding button above.</p>{onSave&&<button type="button" className="primary" disabled={busy} onClick={()=>openEditor()}>Add your first fund</button>}</div>}</div>
        <details className="mf-table-details"><summary>View detailed numbers</summary><div className="tablewrap"><table><thead><tr><th>FUND</th><th>UNITS</th><th>AVG. BUY NAV</th><th>CURRENT NAV</th><th>INVESTED</th><th>CURRENT VALUE</th><th>GAIN / LOSS</th></tr></thead><tbody>{funds.map(f=><tr key={f.id}><td className="symbol">{fundName(f)}{f.notes&&<small>Scheme {f.symbol}</small>}</td><td>{f.quantity}</td><td>{fmt(Number(f.average_cost))}</td><td>{f.last_price===null?"—":fmt(Number(f.last_price))}</td><td>{fmt(Number(f.invested))}</td><td>{f.market_value===null?"—":fmt(Number(f.market_value))}</td><td>{f.unrealized_pnl===null?"—":fmt(Number(f.unrealized_pnl))}</td></tr>)}{!funds.length&&<tr><td colSpan={7} className="empty">No mutual fund holdings saved. Use Add mutual fund holding.</td></tr>}</tbody></table></div></details>
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
