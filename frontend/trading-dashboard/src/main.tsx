import React, {useEffect, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import "./style.css";
import "./research-accessibility.css";
import {useOverlayFocus} from "./useOverlayFocus";
import ResearchHome from "./ResearchHome";
import WorkspaceNavigation,{pages,validPage} from "./WorkspaceNavigation";
import AdvancedSection from "./AdvancedSection";
import PortfolioSummary from "./PortfolioSummary";
import AutonomousOverview from "./AutonomousOverview";
import {AuthGate,type AuthIdentity} from "./AuthGate";
import StockExplorer from "./StockExplorer";
import type {EliteTarget} from "./SteadyMomentumCard";
import PortfolioStress from "./PortfolioStress";
import PortfolioAllocation from "./PortfolioAllocation";
import GoalPlanner from "./GoalPlanner";
import GoalMonitor from "./GoalMonitor";
import GoalComparison from "./GoalComparison";
import ResearchJournal from "./ResearchJournal";
import FeeImpact from "./FeeImpact";
import PortfolioConcentration from "./PortfolioConcentration";
import PortfolioPerformanceHistory from "./PortfolioPerformanceHistory";
import PersonalAlerts from "./PersonalAlerts";
import MutualFundHoldings from "./MutualFundHoldings";
import MarketIntelligence from "./MarketIntelligence";
import HorizonResearch,{type Horizon,type WatchReportTarget} from "./HorizonResearch";
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
import HoldingEditor,{type HoldingDraft,type SipDraft} from "./HoldingEditor";
import MarketIndexStrip from "./MarketIndexStrip";
import PortfolioIntelligence from "./PortfolioIntelligence";
import PortfolioDoctor from "./PortfolioDoctor";
import EquityResearchDashboard from "./EquityResearchDashboard";
import P2ResearchWorkspace from "./P2ResearchWorkspace";
import OnboardingGuide from "./OnboardingGuide";
import UpstoxVaultCard from "./UpstoxVaultCard";
import HistoricalInvestments from "./HistoricalInvestments";
import PortfolioVisuals from "./PortfolioVisuals";
import "./terminal.css";

type Holding = {id:number;symbol:string;asset_type:string;quantity:number;average_cost:number;last_price:number|null;previous_close:number|null;invested:number;market_value:number|null;unrealized_pnl:number|null;one_day_change:number|null;price_as_of:string|null;valuation_status?:string;notes:string|null};
type Analysis = {holdingCount:number;invested:number;pricedMarketValue:number;pricedCostBasis:number;pricedUnrealizedPnl:number;unpricedHoldings:number;valuationComplete:boolean;recentRecordedHoldings?:number;stalePriceHoldings?:number;undatedPriceHoldings?:number;futureDatedPriceHoldings?:number;recordedReturnPercent?:number|null;valuationFreshnessStatus?:string;valuationFreshnessNotice?:string;riskFlags:string[]};
type Theme = "system" | "dark" | "light";
type Appearance = {theme:Theme;opacity:number;blur:number;border:boolean};
type Coverage = {exchange:string;instruments:number;candle_count:number;first_date:string|null;latest_date:string|null};
type HealthSource = {source_code:string;display_name:string;access_mode:string;license_scope:string;instruments:number;instruments_with_candles:number;latest_candle:string|null};
type HealthRun = {id:string;job_name:string;status:string;artifact_name:string;started_at:string;records_seen:number;records_written:number;failure_count:number;error_message:string|null};
type HealthIssue = {id:number;severity:string;event_type:string;observed_at:string;exchange:string|null;symbol:string|null;details:Record<string,unknown>};
type DataHealth = {generatedAt:string;providerMode:string;liveMarketDataConnected:boolean;instrumentCount:number;candleCount:number;unresolvedIssueCount:number;coverage:Coverage[];sources:HealthSource[];recentRuns:HealthRun[];issues:HealthIssue[]};
type FeedState = {transport_connected?:boolean;selected_instruments?:number;automatic_selection?:{status?:string;resolved_count?:number;missing_symbols?:string[]}};

const API = "/api/v1/portfolio";
const TAB_STORAGE_KEY = "atlas:selected-tab";
const APPEARANCE_STORAGE_KEY = "atlas:appearance";
const DEFAULT_APPEARANCE:Appearance = {theme:"system", opacity:72, blur:20, border:true};
const fmt = (n:number|null|undefined) => n == null ? "—" : new Intl.NumberFormat("en-IN", {style:"currency", currency:"INR", maximumFractionDigits:2}).format(Number(n));
const clamp = (value:unknown, min:number, max:number, fallback:number) => { const n = Number(value); return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback; };

const getSavedTab = () => {
  try { return validPage(localStorage.getItem(TAB_STORAGE_KEY)); }
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
  const {triggerRef,panelRef}=useOverlayFocus(open,()=>onOpenChange(false),false);
  const toggle=()=>{const next=!open;if(next)window.dispatchEvent(new Event("atlas:close-notifications"));onOpenChange(next);};
  return <div className="appearance-shell">
    <button ref={triggerRef} className="appearance-trigger" type="button" aria-label="Open appearance settings" aria-haspopup="dialog" aria-expanded={open} onClick={toggle}><span className="appearance-spark" aria-hidden="true">✦</span><span className="terminal-action-label">Appearance</span></button>
    {open && <><section ref={panelRef} tabIndex={-1} className="appearance-panel" role="dialog" aria-label="Appearance settings">
      <div className="appearance-title"><div><small>DISPLAY</small><strong>Liquid Glass</strong></div><button type="button" aria-label="Close appearance settings" onClick={() => onOpenChange(false)}>×</button></div>
      <div className="setting-group"><label>Theme</label><div className="theme-picker" role="group" aria-label="Theme">
        {(["system", "dark", "light"] as Theme[]).map(theme => <button type="button" key={theme} className={value.theme === theme ? "selected" : ""} aria-pressed={value.theme === theme} onClick={() => update("theme", theme)}>{theme === "system" ? "◐" : theme === "dark" ? "☾" : "☀"}<span>{theme === "system" ? "Auto" : theme}</span></button>)}
      </div><p className="theme-help">Auto follows your Mac or browser light/dark appearance.</p></div>
      <div className="setting-group"><div className="setting-label"><label htmlFor="panel-opacity">Panel opacity</label><output>{value.opacity}%</output></div><input id="panel-opacity" type="range" min="0" max="100" value={value.opacity} onChange={event => update("opacity", Number(event.target.value))}/><p>{value.opacity === 0 ? "Perfectly clear · blur disabled" : value.opacity === 100 ? "Fully solid surface" : "Background alpha only"}</p></div>
      <div className="setting-group"><div className="setting-label"><label htmlFor="panel-blur">Background &amp; backdrop blur</label><output>{value.blur}px</output></div><input id="panel-blur" type="range" min="0" max="40" value={value.blur} onChange={event => update("blur", Number(event.target.value))}/><p>{value.opacity===0?"Background blur stays active; clear panels remain transparent.":"Softens the background and translucent panels."}</p></div>
      <label className="border-toggle"><span><strong>Subtle border</strong><small>Independent of opacity</small></span><input type="checkbox" checked={value.border} onChange={event => update("border", event.target.checked)}/><i aria-hidden="true"/></label>
    </section></>}
  </div>;
}

export function App({identity={id:"preview",email:"Local preview",role:"USER"},onLogout=async()=>{}}:{identity?:AuthIdentity;onLogout?:()=>Promise<void>}) {
  const [tab, setTab] = useState(getSavedTab);
  const [reportTarget,setReportTarget]=useState<WatchReportTarget|undefined>(undefined);
  const [eliteTarget,setEliteTarget]=useState<EliteTarget|undefined>(undefined);
  const [appearance, setAppearance] = useState(getSavedAppearance);
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [holdingFilter,setHoldingFilter]=useState("ALL");const [holdingSearch,setHoldingSearch]=useState("");const [holdingSort,setHoldingSort]=useState("VALUE");
  const visibleHoldings=holdings.filter(h=>(holdingFilter==="ALL"||h.asset_type===holdingFilter)&&(!holdingSearch.trim()||(h.symbol+" "+(h.notes??"")).toLowerCase().includes(holdingSearch.trim().toLowerCase()))).sort((a,b)=>{if(holdingSort==="NAME")return a.symbol.localeCompare(b.symbol);const av=holdingSort==="PNL"?a.unrealized_pnl:a.market_value,bv=holdingSort==="PNL"?b.unrealized_pnl:b.market_value;return av==null?(bv==null?a.symbol.localeCompare(b.symbol):1):bv==null?-1:Number(bv)-Number(av)||a.symbol.localeCompare(b.symbol);});
  const [analysis, setAnalysis] = useState<Analysis|null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<DataHealth|null>(null);
  const [portfolioRevision, setPortfolioRevision] = useState(0);
  const [feedState,setFeedState] = useState<FeedState|null>(null);
  const [providerActionRequired,setProviderActionRequired]=useState(false);
  const initialRefreshStarted=useRef(false);
  const portfolioRequest=useRef(0);
  const portfolioPending=useRef(false);
  const portfolioFingerprint=useRef<string|null>(null);
  const feedPending=useRef(false);const livePending=useRef(false);const positionFingerprint=useRef<string|null>(null);

  async function load(background=false) {
    if(background&&portfolioPending.current)return;
    const request=++portfolioRequest.current;
    portfolioPending.current=true;
    try {
      const [h, a] = await Promise.all([fetch(API + "/holdings"), fetch(API + "/analysis")]);
      if (!h.ok || !a.ok) throw Error("Portfolio API is unavailable. Start the local backend.");
      const nextHoldings:Holding[]=await h.json(),nextAnalysis:Analysis=await a.json();
      if(request!==portfolioRequest.current)return;
      const fingerprint=JSON.stringify([nextHoldings,nextAnalysis]);
      if(fingerprint!==portfolioFingerprint.current){
        portfolioFingerprint.current=fingerprint;setHoldings(nextHoldings);setAnalysis(nextAnalysis);
        const positions=JSON.stringify(nextHoldings.map(h=>[h.id,h.symbol,h.asset_type,h.quantity,h.average_cost,h.notes]));
        if(positions!==positionFingerprint.current||!background){positionFingerprint.current=positions;setPortfolioRevision(v=>v+1);}
      }
      setError("");
    } catch (e) { if(request===portfolioRequest.current)setError(String(e)); }
    finally{if(request===portfolioRequest.current)portfolioPending.current=false;}
  }

  async function loadHealth() {
    try { const response=await fetch("/api/v1/data-health/summary"); if(!response.ok) throw Error("Data Health API is unavailable."); setHealth(await response.json()); setError(""); }
    catch(e){ setError(String(e)); }
  }

  async function refreshFeedState(){
    if(feedPending.current)return;feedPending.current=true;
    try{const response=await fetch("/intelligence/api/v1/intelligence/providers/upstox/quote-status");if(response.ok)setFeedState(await response.json());else setFeedState(null);}
    catch{setFeedState(null);/* Background feed status must not interrupt portfolio use. */}
    finally{feedPending.current=false;}
  }

  async function refreshPortfolioPrices(includeHistory=false){
    try{
      const response=await fetch(`${API}/refresh-prices?includeHistory=${includeHistory}`,{method:"POST"});
      if(!response.ok)return;
      const result=await response.json();
      const unavailable=Array.isArray(result.skipped)&&result.skipped.some((item:{reason?:string})=>/credential unavailable|REAUTHORIZATION_REQUIRED|ACCESS_REJECTED/.test(String(item.reason||"")));
      setProviderActionRequired(unavailable);
      if(Number(result.updated)>0||Number(result.history_synced)>0)await load();
    }catch{/* Automatic refresh is best-effort; saved data remains usable offline. */}
  }

  async function refreshFundPrices(){
    const response=await fetch(`${API}/refresh-prices?assetType=MUTUAL_FUND`,{method:"POST"});
    if(!response.ok)throw Error("Fund NAV refresh unavailable");
    const result=await response.json();
    if(!Number.isInteger(result.updated)||result.updated<0||!Number.isInteger(result.total)||result.total<result.updated)throw Error("Invalid NAV refresh result");
    await load();
    return {updated:result.updated,total:result.total};
  }

  async function refreshLiveValuations(){
    if(livePending.current||document.visibilityState!=="visible")return;livePending.current=true;
    try{const result=await fetch(API+"/refresh-live-prices",{method:"POST",cache:"no-store"});if(result.ok)await load(true);}
    catch{/* Existing recorded values remain labelled as recorded. */}finally{livePending.current=false;}
  }

  async function reconcileFeed(){
    try{await fetch("/intelligence/api/v1/intelligence/providers/upstox/subscriptions/reconcile",{method:"POST"});await refreshFeedState();}
    catch{/* The ten-second background reconciler remains the fallback. */}
  }

  useEffect(() => {
    if(!initialRefreshStarted.current){
      initialRefreshStarted.current=true;
      void (async()=>{await load();await refreshPortfolioPrices(true);})();
    }
    const poll=()=>{if(document.visibilityState==="visible")void load(true);};
    const timer=window.setInterval(poll,60_000);
    document.addEventListener("visibilitychange",poll);
    return()=>{window.clearInterval(timer);document.removeEventListener("visibilitychange",poll);};
  }, []);
  useEffect(()=>{if(!feedState?.transport_connected)return;void refreshLiveValuations();const timer=window.setInterval(()=>void refreshLiveValuations(),5000);return()=>window.clearInterval(timer);},[feedState?.transport_connected]);
  useEffect(()=>{const poll=()=>{if(document.visibilityState==="visible")void refreshFeedState();};poll();const timer=window.setInterval(poll,10000);document.addEventListener("visibilitychange",poll);return()=>{window.clearInterval(timer);document.removeEventListener("visibilitychange",poll);};},[]);
  useEffect(() => { if(tab === 6) loadHealth(); }, [tab]);
  useEffect(() => { try { localStorage.setItem(TAB_STORAGE_KEY, String(tab)); } catch { /* Storage may be blocked. */ } }, [tab]);
  useEffect(() => { try { localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(appearance)); } catch { /* Storage may be blocked. */ } }, [appearance]);

  async function save(item:{symbol:string;assetType:string;quantity:number;averageCost:number;lastPrice:number|null;notes?:string|null}) {
    const response = await fetch(API + "/holdings", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(item)});
    if (!response.ok) throw Error((await response.text()).slice(0, 250));
  }

  async function submitHolding(draft:HoldingDraft) {
    setLoading(true);
    try { await save(draft); await load();if(draft.assetType==="EQUITY"){await reconcileFeed();await refreshPortfolioPrices(true);} }
    catch (e) { setError(String(e)); throw e; } finally { setLoading(false); }
  }

  async function submitSip(draft:SipDraft){
    setLoading(true);
    try{
      const response=await fetch("/api/v1/research-workspace/sip-plans",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...draft,active:true})});
      if(!response.ok)throw Error((await response.json().catch(()=>null))?.message||"SIP could not be saved");
      setError("");setTab(1);
    }catch(error){setError(String(error));throw error;}finally{setLoading(false);}
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

  const style = {"--panel-alpha":(appearance.opacity / 100).toFixed(2), "--canvas-blur":`${appearance.blur}px`, "--panel-blur":`${appearance.opacity === 0 ? 0 : appearance.blur}px`, "--panel-border-color":appearance.border ? "var(--glass-border)" : "transparent"} as React.CSSProperties;
  const activePage = pages[tab] || pages[0];
  function navigate(id:number){setEliteTarget(undefined);setReportTarget(undefined);setTab(validPage(id));window.scrollTo({top:0,behavior:"auto"});}
  function navigateElite(target:EliteTarget){navigate(7);setEliteTarget(target);}
  function navigateHorizon(horizon:Exclude<Horizon,"INTRADAY">,target?:WatchReportTarget){
    navigate(horizon==="SWING"?3:horizon==="SHORT_TERM"?4:5);
    setReportTarget(target);
  }

  return <div className="dashboard" data-theme={appearance.theme} data-panel-clear={appearance.opacity === 0 ? "true" : undefined} data-blur-zero={appearance.opacity === 0 || appearance.blur === 0 ? "true" : undefined} data-appearance-open={appearanceOpen ? "true" : undefined} style={style}>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <div className="canvas" aria-hidden="true"><i/><i/><i/><i/></div><div className="canvas-texture" aria-hidden="true"/>
    <div className="layout">
      <WorkspaceNavigation page={tab} onNavigate={navigate} account={identity.email} onLogout={()=>void onLogout()} onHelp={()=>window.dispatchEvent(new Event("atlas:open-onboarding"))}/>

      <main className="content" id="main-content" tabIndex={-1}>
        <header className="terminal-page-header"><div><div className="eyebrow"><span/> YOUR PRIVATE RESEARCH TERMINAL</div><h1>{activePage.title}</h1><p>{activePage.description}</p></div><div className="header-actions terminal-utility"><button type="button" className="terminal-search secondary" onClick={()=>navigate(7)}><svg aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg><span>Stock search</span></button><NotificationCenter key={identity.id} includePersonal/><AppearanceControls value={appearance} onChange={setAppearance} open={appearanceOpen} onOpenChange={setAppearanceOpen}/></div></header>
        <MarketIndexStrip/>
        {providerActionRequired&&!feedState?.transport_connected&&holdings.some(h=>h.asset_type==="EQUITY")&&<div className="provider-action-banner" role="status"><div><strong>Market-data access needs attention</strong><span>Check the existing Analytics Token configuration and data permissions. Account synchronization is optional.</span></div><button className="secondary" onClick={()=>setTab(6)}>Review connection</button></div>}
        <OnboardingGuide onNavigate={navigate}/>
        {loading&&<div className="global-loading" role="status" aria-live="polite"><span/>Saving your changes…</div>}
        {error && <div className="error glass" role="alert">{error} <button type="button" onClick={() => tab === 6 ? loadHealth() : load()}>Retry</button></div>}

        {tab === 0 ? <>
          <div className="terminal-overview-grid"><PortfolioSummary analysis={analysis} holdings={holdings} feedConnected={feedState?.transport_connected===true} onOpen={()=>navigate(9)}/><PortfolioVisuals holdings={holdings}/></div>
          <PortfolioDoctor compact revision={portfolioRevision} onOpenPortfolio={()=>navigate(9)} onSettings={()=>navigate(6)}/>
          <AutonomousOverview onPortfolio={()=>navigate(9)} onFunds={()=>navigate(1)} onSettings={()=>navigate(6)} onHorizon={navigateHorizon} onOpenStock={navigateElite}><ResearchHome holdings={holdings} revision={portfolioRevision} onReviewHoldings={()=>navigate(9)} onOpenExplorer={()=>navigate(7)} onOpenDataHealth={()=>navigate(6)}/></AutonomousOverview>
        </> : tab === 9 ? <>
          <div className="terminal-overview-grid"><PortfolioSummary analysis={analysis} holdings={holdings} feedConnected={feedState?.transport_connected===true} onOpen={()=>document.getElementById("active-holdings")?.scrollIntoView({block:"start"})}/><PortfolioVisuals holdings={holdings}/></div>
          <section className="panel glass terminal-performance-panel"><PortfolioPerformanceHistory revision={portfolioRevision}/></section>
          <AdvancedSection title="Add or update an investment" description="Search a stock or fund, save a holding or set up an SIP"><HoldingEditor busy={loading} onSave={submitHolding} onSaveSip={submitSip}/></AdvancedSection>
          <AdvancedSection title="Advanced portfolio tools" description="Stress tests, allocation, goals, journal, fees and concentration">
            <PortfolioStress revision={portfolioRevision}/>
            <PortfolioAllocation revision={portfolioRevision}/>
            <GoalPlanner/>
            <GoalComparison/>
            <ResearchJournal/>
            <FeeImpact/>
            <PortfolioConcentration revision={portfolioRevision}/>
            <PersonalAlerts/>
          </AdvancedSection>
          <section id="active-holdings" className="panel glass holdings-panel"><div className="sectionhead"><div><small className="section-kicker">CURRENT INVESTMENTS</small><h2>Active holdings</h2></div><label className="upload">Import CSV <input type="file" accept=".csv,text/csv" hidden disabled={loading} onChange={e => { const file = e.target.files?.[0]; if (file) importCsv(file); e.target.value = ""; }}/></label></div><p className="muted tiny">Only investments you still own appear here. One-day change uses the previous provider close or previous published NAV when available.</p><div className="terminal-holdings-toolbar"><div role="group" aria-label="Holdings asset type">{[["ALL","All"],["EQUITY","Stocks"],["MUTUAL_FUND","Mutual funds"]].map(([id,label])=><button type="button" key={id} className={"secondary"+(holdingFilter===id?" selected":"")} aria-pressed={holdingFilter===id} onClick={()=>setHoldingFilter(id)}>{label}</button>)}</div><input aria-label="Search active holdings" placeholder="Search holdings" value={holdingSearch} onChange={e=>setHoldingSearch(e.target.value)}/><select aria-label="Sort holdings" value={holdingSort} onChange={e=>setHoldingSort(e.target.value)}><option value="VALUE">Value: high to low</option><option value="PNL">P&amp;L: high to low</option><option value="NAME">Name: A–Z</option></select></div><p className="muted tiny">{visibleHoldings.length} of {holdings.length} holdings shown</p><div className="tablewrap"><table><thead><tr><th>INVESTMENT</th><th>TYPE</th><th>QTY</th><th>AVG COST</th><th>CURRENT*</th><th>VALUE*</th><th>OVERALL P&amp;L*</th><th>1 DAY*</th><th/></tr></thead><tbody>
            {visibleHoldings.map(holding => <tr key={holding.id}><td className="symbol">{holding.asset_type==="MUTUAL_FUND"&&holding.notes?<>{holding.notes}<small>Scheme {holding.symbol}</small></>:holding.symbol}</td><td><span className="asset-pill">{holding.asset_type}</span></td><td>{holding.quantity}</td><td>{fmt(holding.average_cost)}</td><td>{fmt(holding.last_price)}{holding.valuation_status&&<small className="muted tiny" style={{display:"block"}}>{holding.valuation_status.toLowerCase().replace(/_/g," ")}</small>}</td><td>{fmt(holding.market_value)}</td><td className={(holding.unrealized_pnl || 0) >= 0 ? "positive" : "negative"}>{fmt(holding.unrealized_pnl)}</td><td className={(holding.one_day_change||0)>=0?"positive":"negative"}>{fmt(holding.one_day_change)}</td><td><button className="danger" onClick={() => remove(holding.id)}>Delete</button></td></tr>)}
            {!visibleHoldings.length && <tr><td colSpan={9} className="empty">{holdings.length?"No holdings match the selected filters.":"No active holdings yet. Open Add or update an investment above."}</td></tr>}
          </tbody></table></div></section>
          <PortfolioIntelligence holdings={holdings} analysis={analysis}/>
          <PortfolioDoctor revision={portfolioRevision} onSettings={()=>navigate(6)}/>
          <GoalMonitor/>
          <AdvancedSection title="Past investments" description="Review closed holdings and realized performance"><HistoricalInvestments activeHoldings={holdings}/></AdvancedSection>
        </> : tab === 1 ? <MutualFundHoldings holdings={holdings} busy={loading} onSave={submitHolding} onRemove={remove} onRefresh={refreshFundPrices}/> : (tab === 2 || tab === 3 || tab === 4 || tab === 5) ? <HorizonResearch key={tab} horizon={tab===2?"INTRADAY":tab===3?"SWING":tab===4?"SHORT_TERM":"LONG_TERM"} reportTarget={tab===2?undefined:reportTarget} onSettings={()=>navigate(6)}>{tab===5?<EquityResearchDashboard/>:<><MarketIntelligence/><BrokerResearch/><ResearchOutcomes/><ResearchSourceAudit/></>}</HorizonResearch> : tab === 8 ? <P2ResearchWorkspace/> : tab === 7 ? <StockExplorer initialTarget={eliteTarget}/> : tab === 10 ? <>
          <AutonomousOverview onPortfolio={()=>navigate(9)} onFunds={()=>navigate(1)} onSettings={()=>navigate(6)} onHorizon={navigateHorizon} onOpenStock={navigateElite}><MarketIntelligence/></AutonomousOverview>
          <AdvancedSection title="Company and institutional research" description="Company reports, news and institutional activity"><EquityResearchDashboard/><InstitutionalFlows/></AdvancedSection>
          <AdvancedSection title="Research evidence and history" description="Broker research, source audit, outcome review and evidence ledgers"><BrokerResearch/><ResearchOutcomes/><ResearchSourceAudit/><FlowLedger/><NewsEvidence/><NewsLedger/></AdvancedSection>
        </> : tab === 6 ? <>
          <UpstoxVaultCard onConnected={()=>refreshPortfolioPrices(true)}/>
          <section className="panel glass terminal-settings-summary" aria-label="Workspace settings summary"><div className="sectionhead"><div><small className="section-kicker">LOCAL WORKSPACE</small><h2>Connections &amp; system status</h2><p>Manage read-only authorization and investigate data availability without changing your holdings.</p></div></div><div className="terminal-research-metrics"><article><span>Registry instruments</span><strong>{health?.instrumentCount??"—"}</strong></article><article><span>Daily observations</span><strong>{health?.candleCount??"—"}</strong></article><article><span>Unresolved quality events</span><strong>{health?.unresolvedIssueCount??"—"}</strong></article><article><span>Provider mode</span><strong>{health?.providerMode?.replace(/_/g," ")||"—"}</strong></article></div></section>
          <DataReadiness/>
          <AdvancedSection title="Data and AI provider connections" description="Provider setup, authorization and capabilities"><MultiProviderHub/><UpstoxAuthorization/><EntitlementRegistry/><MarketReadiness/></AdvancedSection>
          <AdvancedSection title="Advanced system diagnostics" description="Feed health, ingestion, reliability, data quality and audit records">
          <FeedHealth/>
          <ReliabilityIncidents/>
          <IngestionQualityGate/>
          <ProviderQuality/>
          <ProviderBatchPreflight/>
          <ProviderReconciliation/>
          <div className="stats">
            <div className="stat glass"><small>INSTRUMENTS</small><strong>{health?.instrumentCount ?? "—"}</strong><span>NSE/BSE registry records</span><b aria-hidden="true">◇</b></div>
            <div className="stat glass"><small>DAILY CANDLES</small><strong>{health?.candleCount ?? "—"}</strong><span>Validated 1d OHLCV records</span><b aria-hidden="true">▥</b></div>
            <div className="stat glass"><small>OPEN QUALITY EVENTS</small><strong className={(health?.unresolvedIssueCount || 0)>0?"negative":"positive"}>{health?.unresolvedIssueCount ?? "—"}</strong><span>Review before research use</span><b aria-hidden="true">!</b></div>
            <div className="stat glass"><small>PROVIDER MODE</small><strong>{health?.providerMode?.replace(/_/g," ")||"—"}</strong><span>Reported by the backend</span><b aria-hidden="true">⇧</b></div>
          </div>
          <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">CONTROLLED INGESTION</small><h2>Import validated source files</h2></div><span className="tag">NO SCRAPING</span></div>
            <p className="muted tiny">Import in order: instruments, market sessions, corporate actions, then daily candles. Files are accepted atomically, hashed for idempotency, and must match the templates in <code>data/templates</code>. You are responsible for having lawful rights to each source file.</p>
            <div className="import-grid">{[["instruments","Instrument registry"],["market-sessions","Market sessions"],["corporate-actions","Corporate actions"],["daily-candles","Daily OHLCV"]].map(([type,label])=><label className="upload" key={type}>{label}<input type="file" accept=".csv,text/csv" hidden disabled={loading} onChange={e=>{const file=e.target.files?.[0];if(file)importMarketData(type,file);e.target.value="";}}/></label>)}</div>
            <div className="notice warning-notice">Daily candles must explicitly declare RAW_UNADJUSTED or ADJUSTED. ATLAS never silently assumes corporate-action adjustment.</div>
          </section>
          <div className="two health-two">
            <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">EXCHANGE COVERAGE</small><h2>Registry &amp; date coverage</h2></div></div><div className="tablewrap"><table><thead><tr><th>EXCHANGE</th><th>INSTRUMENTS</th><th>CANDLES</th><th>FIRST DATE</th><th>LATEST DATE</th></tr></thead><tbody>{health?.coverage.map(row=><tr key={row.exchange}><td className="symbol">{row.exchange}</td><td>{row.instruments}</td><td>{row.candle_count}</td><td>{row.first_date || "—"}</td><td>{row.latest_date || "—"}</td></tr>)}</tbody></table></div></section>
            <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">PROVENANCE</small><h2>Enabled data sources</h2></div></div><div className="tablewrap"><table><thead><tr><th>SOURCE</th><th>ACCESS</th><th>LICENSE SCOPE</th><th>LATEST CANDLE</th></tr></thead><tbody>{health?.sources.map(row=><tr key={row.source_code}><td><span className="asset-pill">{row.source_code}</span></td><td>{row.access_mode}</td><td>{row.license_scope}</td><td>{row.latest_candle ? new Date(row.latest_candle).toLocaleDateString("en-IN") : "—"}</td></tr>)}</tbody></table></div></section>
          </div>
          <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">AUDIT TRAIL</small><h2>Recent ingestion runs</h2></div><button className="secondary" onClick={loadHealth}>Refresh</button></div><div className="tablewrap"><table><thead><tr><th>STARTED</th><th>JOB</th><th>FILE</th><th>STATUS</th><th>SEEN</th><th>WRITTEN</th><th>ERROR</th></tr></thead><tbody>{health?.recentRuns.map(row=><tr key={row.id}><td>{new Date(row.started_at).toLocaleString("en-IN")}</td><td>{row.job_name}</td><td>{row.artifact_name}</td><td><span className={`status-pill status-${row.status.toLowerCase()}`}>{row.status}</span></td><td>{row.records_seen}</td><td>{row.records_written}</td><td className="failure-cell">{row.error_message || "—"}</td></tr>)}{!health?.recentRuns.length&&<tr><td colSpan={7} className="empty">No ingestion has run. No market data is claimed.</td></tr>}</tbody></table></div></section>
          <section className="panel glass"><div className="sectionhead"><div><small className="section-kicker">DATA QUALITY</small><h2>Unresolved quality events</h2></div></div><div className="tablewrap"><table><thead><tr><th>OBSERVED</th><th>SEVERITY</th><th>EVENT</th><th>INSTRUMENT</th><th>DETAILS</th></tr></thead><tbody>{health?.issues.map(row=><tr key={row.id}><td>{new Date(row.observed_at).toLocaleString("en-IN")}</td><td><span className={`severity severity-${row.severity.toLowerCase()}`}>{row.severity}</span></td><td>{row.event_type.replace(/_/g," ")}</td><td>{row.exchange&&row.symbol?`${row.exchange}:${row.symbol}`:"—"}</td><td className="details-cell">{JSON.stringify(row.details)}</td></tr>)}{!health?.issues.length&&<tr><td colSpan={5} className="empty">No unresolved quality events.</td></tr>}</tbody></table></div></section>
          </AdvancedSection>
        </> : null}
        <footer>ATLAS · Local-first investment research · Not financial advice · No automated trading</footer>
      </main>
    </div>
  </div>;
}

const root=document.getElementById("root");
if(root)createRoot(root).render(<React.StrictMode><AuthGate>{session=><App identity={session.identity} onLogout={session.logout}/>}</AuthGate></React.StrictMode>);
