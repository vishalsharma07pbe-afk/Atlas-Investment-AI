import React, {useEffect, useState} from "react";
import {createRoot} from "react-dom/client";
import "./style.css";
import ResearchHome from "./ResearchHome";
import {AuthGate,type AuthIdentity} from "./AuthGate";
import StockExplorer from "./StockExplorer";
import PortfolioStress from "./PortfolioStress";
import PortfolioAllocation from "./PortfolioAllocation";
import GoalPlanner from "./GoalPlanner";
import GoalComparison from "./GoalComparison";
import ResearchJournal from "./ResearchJournal";
import FeeImpact from "./FeeImpact";
import PortfolioConcentration from "./PortfolioConcentration";
import PortfolioPerformanceHistory from "./PortfolioPerformanceHistory";
import PersonalAlerts from "./PersonalAlerts";
import MutualFundHoldings from "./MutualFundHoldings";
import MarketIntelligence from "./MarketIntelligence";
import BrokerResearch from "./BrokerResearch";
import ResearchOutcomes from "./ResearchOutcomes";
import ResearchSourceAudit from "./ResearchSourceAudit";
import InstitutionalFlows from "./InstitutionalFlows";
import FlowLedger from "./FlowLedger";
import NewsEvidence from "./NewsEvidence";
import NewsLedger from "./NewsLedger";
import ProviderQuality from "./ProviderQuality";
import ProviderBatchPreflight from "./ProviderBatchPreflight";
import UpstoxAuthorization from "./UpstoxAuthorization";
import MarketReadiness from "./MarketReadiness";
import DataReadiness from "./DataReadiness";
import MultiProviderHub from "./MultiProviderHub";
import FeedHealth from "./FeedHealth";
import ReliabilityIncidents from "./ReliabilityIncidents";
import IngestionQualityGate from "./IngestionQualityGate";
import EntitlementRegistry from "./EntitlementRegistry";
import ProviderReconciliation from "./ProviderReconciliation";
import NotificationCenter from "./NotificationCenter";
import HoldingEditor,{type HoldingDraft} from "./HoldingEditor";
import MarketIndexStrip from "./MarketIndexStrip";
import PortfolioIntelligence from "./PortfolioIntelligence";
import EquityResearchDashboard from "./EquityResearchDashboard";
import P2ResearchWorkspace from "./P2ResearchWorkspace";
import OnboardingGuide from "./OnboardingGuide";

type Holding = {id:number;symbol:string;asset_type:string;quantity:number;average_cost:number;last_price:number|null;invested:number;market_value:number|null;unrealized_pnl:number|null;price_as_of:string|null};
type Analysis = {holdingCount:number;invested:number;pricedMarketValue:number;pricedCostBasis:number;pricedUnrealizedPnl:number;unpricedHoldings:number;valuationComplete:boolean;riskFlags:string[]};
type Theme = "system" | "dark" | "light";
type Appearance = {theme:Theme;opacity:number;blur:number;border:boolean};
type Coverage = {exchange:string;instruments:number;candle_count:number;first_date:string|null;latest_date:string|null};
type HealthSource = {source_code:string;display_name:string;access_mode:string;license_scope:string;instruments:number;instruments_with_candles:number;latest_candle:string|null};
type HealthRun = {id:string;job_name:string;status:string;artifact_name:string;started_at:string;records_seen:number;records_written:number;failure_count:number;error_message:string|null};
type HealthIssue = {id:number;severity:string;event_type:string;observed_at:string;exchange:string|null;symbol:string|null;details:Record<string,unknown>};
type DataHealth = {generatedAt:string;providerMode:string;liveMarketDataConnected:boolean;instrumentCount:number;candleCount:number;unresolvedIssueCount:number;coverage:Coverage[];sources:HealthSource[];recentRuns:HealthRun[];issues:HealthIssue[]};
type FeedState = {transport_connected?:boolean;selected_instruments?:number;automatic_selection?:{status?:string;resolved_count?:number;missing_symbols?:string[]}};

const API = "/api/v1/portfolio";
const categories = ["Research Home", "Mutual Funds", "Intraday", "Swing Trading", "Short-Term Equity", "Long-Term Stocks"];
const tabIcons = ["▦", "◈", "ϟ", "↗", "◷", "◇"];
const TAB_STORAGE_KEY = "atlas:selected-tab";
const APPEARANCE_STORAGE_KEY = "atlas:appearance";
const DEFAULT_APPEARANCE:Appearance = {theme:"system", opacity:72, blur:20, border:true};
const fmt = (n:number|null|undefined) => n == null ? "—" : new Intl.NumberFormat("en-IN", {style:"currency", currency:"INR", maximumFractionDigits:2}).format(Number(n));
const clamp = (value:unknown, min:number, max:number, fallback:number) => { const n = Number(value); return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback; };

const getSavedTab = () => {
  try { const saved = Number(localStorage.getItem(TAB_STORAGE_KEY)); return Number.isInteger(saved) && saved >= 0 && saved <= 8 ? saved : 0; }
  catch { return 0; }
};

const getSavedAppearance = ():Appearance => {
  try {
    const saved = JSON.parse(localStorage.getItem(APPEARANCE_STORAGE_KEY) || "null");
    const theme:Theme = ["system", "dark", "light"].includes(saved?.theme) ? saved.theme : DEFAULT_APPEARANCE.theme;
    return {theme, opacity:clamp(saved?.opacity, 0, 100, 72), blur:clamp(saved?.blur, 0, 40, 20), border:typeof saved?.border === "boolean" ? saved.border : true};
  } catch { return DEFAULT_APPEARANCE; }
};

export function AppearanceControls({value, onChange, open, onOpenChange}:{value:Appearance;onChange:(next:Appearance)=>void;open:boolean;onOpenChange:(open:boolean)=>void}) {
  const update = <K extends keyof Appearance>(key:K, next:Appearance[K]) => onChange({...value, [key]:next});
  useEffect(()=>{const close=()=>onOpenChange(false);window.addEventListener("atlas:close-appearance",close);return()=>window.removeEventListener("atlas:close-appearance",close);},[onOpenChange]);
  useEffect(()=>{if(!open)return;const close=(event:KeyboardEvent)=>{if(event.key==="Escape")onOpenChange(false);};window.addEventListener("keydown",close);return()=>window.removeEventListener("keydown",close);},[open,onOpenChange]);
  const toggle=()=>{const next=!open;if(next)window.dispatchEvent(new Event("atlas:close-notifications"));onOpenChange(next);};
  return <div className="appearance-shell">
    <button className="appearance-trigger" type="button" aria-label="Open appearance settings" aria-expanded={open} onClick={toggle}><span className="appearance-spark">✦</span><span>Appearance</span></button>
    {open && <><button className="appearance-scrim" type="button" aria-label="Close appearance settings" onClick={() => onOpenChange(false)}/><section className="appearance-panel" role="dialog" aria-modal="true" aria-label="Appearance settings">
      <div className="appearance-title"><div><small>DISPLAY</small><strong>Liquid Glass</strong></div><button type="button" aria-label="Close appearance settings" onClick={() => onOpenChange(false)}>×</button></div>
      <div className="setting-group"><label>Theme</label><div className="theme-picker" role="group" aria-label="Theme">
        {(["system", "dark", "light"] as Theme[]).map(theme => <button type="button" key={theme} className={value.theme === theme ? "selected" : ""} aria-pressed={value.theme === theme} onClick={() => update("theme", theme)}>{theme === "system" ? "◐" : theme === "dark" ? "☾" : "☀"}<span>{theme === "system" ? "Auto" : theme}</span></button>)}
      </div><p className="theme-help">Auto follows your Mac or browser light/dark appearance.</p></div>
      <div className="setting-group"><div className="setting-label"><label htmlFor="panel-opacity">Panel opacity</label><output>{value.opacity}%</output></div><input id="panel-opacity" type="range" min="0" max="100" value={value.opacity} onChange={event => update("opacity", Number(event.target.value))}/><p>{value.opacity === 0 ? "Perfectly clear · blur disabled" : value.opacity === 100 ? "Fully solid surface" : "Background alpha only"}</p></div>
      <div className="setting-group"><div className="setting-label"><label htmlFor="panel-blur">Backdrop blur</label><output>{value.blur}px</output></div><input id="panel-blur" type="range" min="0" max="40" value={value.blur} onChange={event => update("blur", Number(event.target.value))}/><p>{value.opacity === 0 && value.blur > 0 ? `Set opacity above 0% to see blur · saved at ${value.blur}px` : value.opacity === 100 ? "Hidden by the fully solid panel" : "Softens the texture visible through each panel"}</p></div>
      <label className="border-toggle"><span><strong>Subtle border</strong><small>Independent of opacity</small></span><input type="checkbox" checked={value.border} onChange={event => update("border", event.target.checked)}/><i aria-hidden="true"/></label>
    </section></>}
  </div>;
}

export function App({identity={id:"preview",email:"Local preview",role:"USER"},onLogout=async()=>{}}:{identity?:AuthIdentity;onLogout?:()=>Promise<void>}) {
  const [tab, setTab] = useState(getSavedTab);
  const [appearance, setAppearance] = useState(getSavedAppearance);
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [analysis, setAnalysis] = useState<Analysis|null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<DataHealth|null>(null);
  const [portfolioRevision, setPortfolioRevision] = useState(0);
  const [feedState,setFeedState] = useState<FeedState|null>(null);

  async function load() {
    try {
      const [h, a] = await Promise.all([fetch(API + "/holdings"), fetch(API + "/analysis")]);
      if (!h.ok || !a.ok) throw Error("Portfolio API is unavailable. Start the local backend.");
      setHoldings(await h.json()); setAnalysis(await a.json()); setPortfolioRevision(v => v + 1); setError("");
    } catch (e) { setError(String(e)); }
  }

  async function loadHealth() {
    try { const response=await fetch("/api/v1/data-health/summary"); if(!response.ok) throw Error("Data Health API is unavailable."); setHealth(await response.json()); setError(""); }
    catch(e){ setError(String(e)); }
  }

  async function refreshFeedState(){
    try{const response=await fetch("/intelligence/api/v1/intelligence/providers/upstox/quote-status");if(response.ok)setFeedState(await response.json());}
    catch{/* Background feed status must not interrupt portfolio use. */}
  }

  async function reconcileFeed(){
    try{await fetch("/intelligence/api/v1/intelligence/providers/upstox/subscriptions/reconcile",{method:"POST"});await refreshFeedState();}
    catch{/* The ten-second background reconciler remains the fallback. */}
  }

  useEffect(() => { load(); }, []);
  useEffect(()=>{void refreshFeedState();const timer=window.setInterval(()=>void refreshFeedState(),10000);return()=>window.clearInterval(timer);},[]);
  useEffect(() => { if(tab === 6) loadHealth(); }, [tab]);
  useEffect(() => { try { localStorage.setItem(TAB_STORAGE_KEY, String(tab)); } catch { /* Storage may be blocked. */ } }, [tab]);
  useEffect(() => { try { localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(appearance)); } catch { /* Storage may be blocked. */ } }, [appearance]);

  async function save(item:{symbol:string;assetType:string;quantity:number;averageCost:number;lastPrice:number|null}) {
    const response = await fetch(API + "/holdings", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(item)});
    if (!response.ok) throw Error((await response.text()).slice(0, 250));
  }

  async function submitHolding(draft:HoldingDraft) {
    setLoading(true);
    try { await save(draft); await load();await reconcileFeed(); }
    catch (e) { setError(String(e)); throw e; } finally { setLoading(false); }
  }

  async function remove(id:number) {
    if (!confirm("Delete this holding?")) return;
    try { const response = await fetch(API + "/holdings/" + id, {method:"DELETE"}); if (!response.ok) throw Error("Delete failed"); await load();await reconcileFeed(); }
    catch (e) { setError(String(e)); }
  }

  async function importCsv(file:File) {
    setLoading(true);
    try {
      const text = await file.text();
      const lines = text.replace(/^\uFEFF/, "").trim().split(/\r?\n/);
      const header = lines.shift()?.split(",").map(s => s.trim().toLowerCase()) || [];
      const required = ["symbol", "asset_type", "quantity", "average_cost", "last_price"];
      if (required.some(key => !header.includes(key))) throw Error("CSV headers must be: " + required.join(","));
      let count = 0;
      for (const line of lines) {
        if (!line.trim()) continue;
        const parts = line.split(",").map(value => value.trim());
        if (parts.length !== header.length) throw Error("CSV must not contain embedded commas. Use simple symbol/number fields.");
        const obj = Object.fromEntries(header.map((key, index) => [key, parts[index]]));
        const quantity = Number(obj.quantity), cost = Number(obj.average_cost), price = obj.last_price === "" ? null : Number(obj.last_price);
        if (!obj.symbol || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(cost) || cost < 0 || (price !== null && (!Number.isFinite(price) || price < 0))) throw Error("Invalid row: " + line);
        await save({symbol:obj.symbol, assetType:obj.asset_type, quantity, averageCost:cost, lastPrice:price}); count++;
      }
      await load();await reconcileFeed(); alert(`Imported ${count} holdings. Existing matching symbols were updated.`);
    } catch (e) { setError(String(e)); } finally { setLoading(false); }
  }

  async function importMarketData(type:string,file:File){
    setLoading(true);
    try { const body=new FormData(); body.append("file",file); const response=await fetch(`/api/v1/data-import/${type}`,{method:"POST",body}); const result=await response.json(); if(!response.ok) throw Error(result.error || "Import rejected"); await loadHealth(); alert(`${result.status}: ${result.recordsWritten} record(s) written. ${result.message}`); }
    catch(e){setError(String(e));}finally{setLoading(false);}
  }

  const style = {"--panel-alpha":(appearance.opacity / 100).toFixed(2), "--panel-blur":`${appearance.opacity === 0 ? 0 : appearance.blur}px`, "--panel-border-color":appearance.border ? "var(--glass-border)" : "transparent"} as React.CSSProperties;
  const activeTitle = tab===6?"Market & Data Health":tab===7?"Stock Explorer":tab===8?"P2 Research Lab":categories[tab];

  return <div className="dashboard" data-theme={appearance.theme} data-panel-clear={appearance.opacity === 0 ? "true" : undefined} data-blur-zero={appearance.opacity === 0 || appearance.blur === 0 ? "true" : undefined} data-appearance-open={appearanceOpen ? "true" : undefined} style={style}>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <div className="canvas" aria-hidden="true"><i/><i/><i/><i/></div>
    <div className="layout">
      <aside className="sidebar glass">
        <div className="brand"><span className="brandicon">◆</span><div><strong>ATLAS</strong><small>INVESTMENT INTELLIGENCE</small></div></div>
        <div className="navlabel">WORKSPACE</div>
        <nav aria-label="Workspace">{categories.map((category, index) => <button type="button" key={category} aria-current={tab === index ? "page" : undefined} className={tab === index ? "active" : ""} onClick={() => setTab(index)}><span className="navdot" aria-hidden="true">{tabIcons[index]}</span><span>{category}</span><span className="navarrow" aria-hidden="true">›</span></button>)}</nav>
        <div className="navlabel">INTELLIGENCE</div>
        <nav aria-label="Intelligence"><button type="button" onClick={() => setTab(8)} aria-current={tab === 8 ? "page" : undefined} className={tab === 8 ? "active" : ""}><span className="navdot" aria-hidden="true">✦</span><span>P2 Research Lab</span><span className="navarrow" aria-hidden="true">›</span></button><button type="button" onClick={() => setTab(7)} aria-current={tab === 7 ? "page" : undefined} className={tab === 7 ? "active" : ""}><span className="navdot" aria-hidden="true">⌁</span><span>Stock Explorer</span><span className="navarrow" aria-hidden="true">›</span></button><button type="button" onClick={() => setTab(6)} aria-current={tab === 6 ? "page" : undefined} className={tab === 6 ? "active" : ""}><span className="navdot" aria-hidden="true">◉</span><span>Market &amp; Data Health</span><span className="navarrow" aria-hidden="true">›</span></button></nav>
        <div className="sidebottom"><span className="statusdot"/> PRIVATE · LOCAL MODE<br/><small>Research only · No order execution</small></div>
      </aside>

      <main className="content" id="main-content" tabIndex={-1}>
        <header><div><div className="eyebrow"><span/> YOUR PRIVATE RESEARCH TERMINAL</div><h1>{activeTitle}</h1><p>{tab === 0 ? "Your holdings, performance and portfolio risk — all stored locally." : "Strict research gates. No invented prices or recommendations."}</p></div><div className="header-actions"><button type="button" className="help-trigger" onClick={()=>window.dispatchEvent(new Event("atlas:open-onboarding"))}>Help</button><NotificationCenter/><div className={`headerbadge ${feedState?.transport_connected?"feed-live":""}`} role="status" aria-live="polite" title={feedState?.automatic_selection?.missing_symbols?.length?`Unresolved: ${feedState.automatic_selection.missing_symbols.join(", ")}`:undefined}><span/> {feedState?.transport_connected?`LIVE · ${feedState.selected_instruments||0} STOCKS`:feedState?.automatic_selection?.status==="IDLE_NO_EQUITY_HOLDINGS"?"FEED READY · ADD A STOCK":feedState?.automatic_selection?.status==="STARTING"?"MARKET FEED CONNECTING":"MARKET FEED NOT CONNECTED"}</div><div className="account-chip"><span>{identity.email.slice(0,1).toUpperCase()}</span><div><small>SIGNED IN</small><strong>{identity.email}</strong></div><button type="button" onClick={()=>void onLogout()}>Logout</button></div><AppearanceControls value={appearance} onChange={setAppearance} open={appearanceOpen} onOpenChange={setAppearanceOpen}/></div></header>
        <MarketIndexStrip/>
        <OnboardingGuide onNavigate={setTab}/>
        {loading&&<div className="global-loading" role="status" aria-live="polite"><span/>Saving your changes…</div>}
        {error && <div className="error glass" role="alert">{error} <button type="button" onClick={() => tab === 6 ? loadHealth() : load()}>Retry</button></div>}

        {tab === 0 ? <>
          <ResearchHome holdings={holdings} onReviewHoldings={()=>document.getElementById("portfolio-overview")?.scrollIntoView({behavior:"smooth",block:"start"})} onOpenExplorer={()=>setTab(7)} onOpenDataHealth={()=>setTab(6)}/>
          <div className="two">
            <PortfolioIntelligence holdings={holdings} analysis={analysis}/>
            <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">POSITION MANAGER</small><h2>Add or update holding</h2></div><span className="tag">AUTO PRICE</span></div><HoldingEditor busy={loading} onSave={submitHolding}/></section>
          </div>
          <details className="advanced-tools glass"><summary><span><strong>Advanced portfolio tools</strong><small>Stress tests, allocation, goals, journal, fees and concentration</small></span><b>Open tools</b></summary><div className="advanced-tools-content">
            <PortfolioStress revision={portfolioRevision}/>
            <PortfolioAllocation revision={portfolioRevision}/>
            <GoalPlanner/>
            <GoalComparison/>
            <ResearchJournal/>
            <FeeImpact/>
            <PortfolioConcentration revision={portfolioRevision}/>
            <PortfolioPerformanceHistory revision={portfolioRevision}/>
            <PersonalAlerts/>
          </div></details>
          <section className="panel glass holdings-panel"><div className="sectionhead"><div><small className="section-kicker">POSITION RECORDS</small><h2>Positions</h2></div><label className="upload">Import CSV <input type="file" accept=".csv,text/csv" hidden disabled={loading} onChange={e => { const file = e.target.files?.[0]; if (file) importCsv(file); e.target.value = ""; }}/></label></div><p className="muted tiny">This table is your editable position record. CSV format: symbol,asset_type,quantity,average_cost,last_price. Imports update matching positions; they do not add transactions.</p><div className="tablewrap"><table><thead><tr><th>SYMBOL</th><th>TYPE</th><th>QTY</th><th>AVG COST</th><th>LAST PRICE*</th><th>INVESTED</th><th>VALUE*</th><th>P&amp;L*</th><th/></tr></thead><tbody>
            {holdings.map(holding => <tr key={holding.id}><td className="symbol">{holding.symbol}</td><td><span className="asset-pill">{holding.asset_type}</span></td><td>{holding.quantity}</td><td>{fmt(holding.average_cost)}</td><td>{fmt(holding.last_price)}</td><td>{fmt(holding.invested)}</td><td>{fmt(holding.market_value)}</td><td className={(holding.unrealized_pnl || 0) >= 0 ? "positive" : "negative"}>{fmt(holding.unrealized_pnl)}</td><td><button className="danger" onClick={() => remove(holding.id)}>Delete</button></td></tr>)}
            {!holdings.length && <tr><td colSpan={9} className="empty">No holdings yet. Add your first position above or import a CSV.</td></tr>}
          </tbody></table></div></section>
        </> : tab === 1 ? <MutualFundHoldings holdings={holdings}/> : tab === 5 ? <EquityResearchDashboard/> : (tab === 2 || tab === 3 || tab === 4) ? <><MarketIntelligence/><BrokerResearch/><ResearchOutcomes/><ResearchSourceAudit/></> : tab === 8 ? <P2ResearchWorkspace/> : tab === 7 ? <StockExplorer/> : tab === 6 ? <>
          <DataReadiness/><MultiProviderHub/>
          <FeedHealth/>
          <ReliabilityIncidents/>
          <IngestionQualityGate/>
          <EntitlementRegistry/>
          <MarketReadiness/>
          <UpstoxAuthorization/>
          <ProviderQuality/>
          <ProviderBatchPreflight/>
          <ProviderReconciliation/>
          <div className="stats">
            <div className="stat glass"><small>INSTRUMENTS</small><strong>{health?.instrumentCount ?? "—"}</strong><span>NSE/BSE registry records</span><b aria-hidden="true">◇</b></div>
            <div className="stat glass"><small>DAILY CANDLES</small><strong>{health?.candleCount ?? "—"}</strong><span>Validated 1d OHLCV records</span><b aria-hidden="true">▥</b></div>
            <div className="stat glass"><small>OPEN QUALITY EVENTS</small><strong className={(health?.unresolvedIssueCount || 0)>0?"negative":"positive"}>{health?.unresolvedIssueCount ?? "—"}</strong><span>Review before research use</span><b aria-hidden="true">!</b></div>
            <div className="stat glass"><small>PROVIDER MODE</small><strong>MANUAL</strong><span>Lawfully sourced CSV only</span><b aria-hidden="true">⇧</b></div>
          </div>
          <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">CONTROLLED INGESTION</small><h2>Import validated source files</h2></div><span className="tag">NO SCRAPING</span></div>
            <p className="muted tiny">Import in order: instruments, market sessions, corporate actions, then daily candles. Files are accepted atomically, hashed for idempotency, and must match the templates in <code>data/templates</code>. You are responsible for having lawful rights to each source file.</p>
            <div className="import-grid">{[["instruments","Instrument registry"],["market-sessions","Market sessions"],["corporate-actions","Corporate actions"],["daily-candles","Daily OHLCV"]].map(([type,label])=><label className="upload" key={type}>{label}<input type="file" accept=".csv,text/csv" hidden disabled={loading} onChange={e=>{const file=e.target.files?.[0];if(file)importMarketData(type,file);e.target.value="";}}/></label>)}</div>
            <div className="notice warning-notice">Daily candles must explicitly declare RAW_UNADJUSTED or ADJUSTED. ATLAS never silently assumes corporate-action adjustment.</div>
          </section>
          <InstitutionalFlows/>
          <FlowLedger/>
          <NewsEvidence/><NewsLedger/>
          <div className="two health-two">
            <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">EXCHANGE COVERAGE</small><h2>Registry &amp; date coverage</h2></div></div><div className="tablewrap"><table><thead><tr><th>EXCHANGE</th><th>INSTRUMENTS</th><th>CANDLES</th><th>FIRST DATE</th><th>LATEST DATE</th></tr></thead><tbody>{health?.coverage.map(row=><tr key={row.exchange}><td className="symbol">{row.exchange}</td><td>{row.instruments}</td><td>{row.candle_count}</td><td>{row.first_date || "—"}</td><td>{row.latest_date || "—"}</td></tr>)}</tbody></table></div></section>
            <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">PROVENANCE</small><h2>Enabled data sources</h2></div></div><div className="tablewrap"><table><thead><tr><th>SOURCE</th><th>ACCESS</th><th>LICENSE SCOPE</th><th>LATEST CANDLE</th></tr></thead><tbody>{health?.sources.map(row=><tr key={row.source_code}><td><span className="asset-pill">{row.source_code}</span></td><td>{row.access_mode}</td><td>{row.license_scope}</td><td>{row.latest_candle ? new Date(row.latest_candle).toLocaleDateString("en-IN") : "—"}</td></tr>)}</tbody></table></div></section>
          </div>
          <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">AUDIT TRAIL</small><h2>Recent ingestion runs</h2></div><button className="secondary" onClick={loadHealth}>Refresh</button></div><div className="tablewrap"><table><thead><tr><th>STARTED</th><th>JOB</th><th>FILE</th><th>STATUS</th><th>SEEN</th><th>WRITTEN</th><th>ERROR</th></tr></thead><tbody>{health?.recentRuns.map(row=><tr key={row.id}><td>{new Date(row.started_at).toLocaleString("en-IN")}</td><td>{row.job_name}</td><td>{row.artifact_name}</td><td><span className={`status-pill status-${row.status.toLowerCase()}`}>{row.status}</span></td><td>{row.records_seen}</td><td>{row.records_written}</td><td className="failure-cell">{row.error_message || "—"}</td></tr>)}{!health?.recentRuns.length&&<tr><td colSpan={7} className="empty">No ingestion has run. No market data is claimed.</td></tr>}</tbody></table></div></section>
          <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">DATA QUALITY</small><h2>Unresolved quality events</h2></div></div><div className="tablewrap"><table><thead><tr><th>OBSERVED</th><th>SEVERITY</th><th>EVENT</th><th>INSTRUMENT</th><th>DETAILS</th></tr></thead><tbody>{health?.issues.map(row=><tr key={row.id}><td>{new Date(row.observed_at).toLocaleString("en-IN")}</td><td><span className={`severity severity-${row.severity.toLowerCase()}`}>{row.severity}</span></td><td>{row.event_type.replace(/_/g," ")}</td><td>{row.exchange&&row.symbol?`${row.exchange}:${row.symbol}`:"—"}</td><td className="details-cell">{JSON.stringify(row.details)}</td></tr>)}{!health?.issues.length&&<tr><td colSpan={5} className="empty">No unresolved quality events.</td></tr>}</tbody></table></div></section>
        </> : <>
          <div className="stats placeholder-stats"><div className="stat glass"><small>DATA STATUS</small><strong>OFFLINE</strong><span>Provider not configured</span><b aria-hidden="true">◌</b></div><div className="stat glass"><small>QUALIFIED SIGNALS</small><strong>0</strong><span>Strict gates enabled</span><b aria-hidden="true">⌁</b></div><div className="stat glass"><small>RECOMMENDATION ENGINE</small><strong>PAUSED</strong><span>No verified input data</span><b aria-hidden="true">Ⅱ</b></div></div>
          <section className="panel glass emptyfeature"><div className="featureicon">◎</div><small className="section-kicker">RESEARCH MODULE</small><h2>{tab === 6 ? "Data sources & intelligence services" : categories[tab]}</h2><p>{tab === 1 ? "Mutual fund NAV, benchmark, expense ratio, drawdown and overlap analysis will appear after verified fund data is connected." : tab === 2 ? "Intraday opportunities require fresh market quotes, liquidity checks, trap detection and validated risk gates." : tab === 3 ? "Swing setups require historical candles, sector momentum, confirmation and stop-loss validation." : tab === 4 ? "Short-term ideas require verified earnings, valuation, catalysts and momentum." : tab === 5 ? "Long-term research requires company fundamentals, valuation history, governance and downside scenarios." : "The application is operating locally. Licensed market data, global news and institutional reports are not yet connected."}</p><div className="notice">No signals are shown until the data, strategy and risk checks pass. This is intentional.</div></section>
        </>}
        <footer>ATLAS · Local-first investment research · Not financial advice · No automated trading</footer>
      </main>
    </div>
  </div>;
}

const root=document.getElementById("root");
if(root)createRoot(root).render(<React.StrictMode><AuthGate>{session=><App identity={session.identity} onLogout={session.logout}/>}</AuthGate></React.StrictMode>);
