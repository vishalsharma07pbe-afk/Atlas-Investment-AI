import {useEffect,useRef,useState} from "react";
import type {EliteTarget} from "./SteadyMomentumCard";
import BacktestPanel from "./BacktestPanel";
import RiskQualification from "./RiskQualification";
import ResearchAlerts from "./ResearchAlerts";
import ExchangePicker from "./ExchangePicker";
import EquityResearchDashboard from "./EquityResearchDashboard";
import {CandlestickSeries,HistogramSeries,LineSeries,createChart,createSeriesMarkers,ColorType} from "lightweight-charts";

type Instrument={id:number;exchange:string;symbol:string;series:string|null;isin:string|null;security_name:string|null;listing_status:string;source:string;source_revision:string|null};
type Candle={trade_date:string;open:number;high:number;low:number;close:number;volume:number;adjustment_status:string;source_code:string;received_at:string};
type Pattern={pattern_type:string;detection_timestamp:string;explanation:string;confirmation_status:string;invalidation_conditions:string};
type Technical={instrument:Instrument;status:string;as_of?:string;candle_count?:number;candles:Candle[];indicators:Record<string,{time:string;value:number}[]>;latest_indicators?:Record<string,number|null>;levels?:{support:number[];resistance:number[]};patterns:Pattern[];missing_data?:string[];notice?:string};
type Summary={research:null|{trend:string;momentum:string;volatility_annualized:number|null;relative_volume:number|null;support_resistance:{support:number[];resistance:number[]};patterns:Pattern[];bullish_evidence:string[];bearish_evidence:string[];risk_observations:string[];missing_data:string[];source_freshness:{latest_verified_date:string;is_live:boolean}};notice:string};

const priceFormat=new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",minimumFractionDigits:2,maximumFractionDigits:2});
const price=(n:number|null|undefined)=>n==null||!Number.isFinite(Number(n))?"—":priceFormat.format(Number(n));
const periods=[{label:"1M",sessions:21},{label:"3M",sessions:63},{label:"6M",sessions:126},{label:"1Y",sessions:252},{label:"All",sessions:0}] as const;
type ChartMode="candles"|"line";
export function dailyPriceChange(candles:Candle[]){
 const latest=candles[candles.length-1],prior=candles[candles.length-2];
 if(!latest||!prior||latest.adjustment_status!==prior.adjustment_status||latest.source_code!==prior.source_code||latest.trade_date<=prior.trade_date||latest.close==null||prior.close==null||!Number.isFinite(Number(latest.close))||!Number.isFinite(Number(prior.close))||Number(prior.close)<=0)return null;
 const amount=Number(latest.close)-Number(prior.close);return {amount,percent:amount/Number(prior.close)*100};
}
function MarketChart({data,toggles,mode,sessions,volumeVisible,expanded}:{data:Technical;toggles:Set<string>;mode:ChartMode;sessions:number;volumeVisible:boolean;expanded:boolean}){
 const ref=useRef<HTMLDivElement>(null);
 const [hovered,setHovered]=useState<Candle|null>(null);
 const [failed,setFailed]=useState(false);
 useEffect(()=>{
  const host=ref.current;if(!host||!data.candles.length)return;
  setFailed(false);setHovered(null);
  let chart:ReturnType<typeof createChart>|undefined;let observer:MutationObserver|undefined;let media:MediaQueryList|undefined;let applyTheme:(()=>void)|undefined;
  try{
   const themeOptions=()=>{const styles=getComputedStyle(host);const ink=styles.getPropertyValue("--ink-soft").trim()||"#b9c4dc";const grid=styles.getPropertyValue("--row-line").trim()||"rgba(130,150,200,.12)";return {layout:{background:{type:ColorType.Solid as const,color:"transparent"},textColor:ink},grid:{vertLines:{color:grid},horzLines:{color:grid}},timeScale:{borderColor:grid},rightPriceScale:{borderColor:grid}};};
   // Use a stable BCP 47 locale rather than inheriting a host/browser locale
   // that may contain unsupported POSIX modifiers in Chromium or on Linux.
   chart=createChart(host,{autoSize:true,...themeOptions(),localization:{locale:"en-IN",dateFormat:"dd MMM yyyy"},crosshair:{mode:0}});
   applyTheme=()=>chart?.applyOptions(themeOptions());
   const dashboard=host.closest(".dashboard");if(dashboard&&typeof MutationObserver!=="undefined"){observer=new MutationObserver(applyTheme);observer.observe(dashboard,{attributes:true,attributeFilter:["data-theme"]});}
   if(typeof matchMedia==="function"){media=matchMedia("(prefers-color-scheme: light)");media.addEventListener?.("change",applyTheme);}
   if(mode==="candles"){
    const candles=chart.addSeries(CandlestickSeries,{upColor:"#2caa86",downColor:"#d66580",wickUpColor:"#2caa86",wickDownColor:"#d66580",borderVisible:false});
    candles.setData(data.candles.map(x=>({time:x.trade_date as any,open:Number(x.open),high:Number(x.high),low:Number(x.low),close:Number(x.close)})));
    if(data.patterns?.length)createSeriesMarkers(candles,data.patterns.slice(-30).map(p=>({time:p.detection_timestamp as any,position:p.pattern_type.includes("BEAR")||p.pattern_type.includes("TOP")||p.pattern_type==="SHOOTING_STAR"?"aboveBar":"belowBar",color:p.confirmation_status==="CONFIRMED"?"#f2b760":"#8d7bff",shape:p.confirmation_status==="CONFIRMED"?"arrowDown":"circle",text:p.pattern_type.replace(/_/g," ").slice(0,14)})) as any);
   }else{
    const line=chart.addSeries(LineSeries,{color:"#2caa86",lineWidth:2,priceLineVisible:false});line.setData(data.candles.map(x=>({time:x.trade_date as any,value:Number(x.close)})));
   }
   if(volumeVisible){const volume=chart.addSeries(HistogramSeries,{priceFormat:{type:"volume"},priceScaleId:"volume",lastValueVisible:false,priceLineVisible:false});
    volume.priceScale().applyOptions({scaleMargins:{top:.8,bottom:0}});volume.setData(data.candles.map(x=>({time:x.trade_date as any,value:Number(x.volume),color:Number(x.close)>=Number(x.open)?"rgba(44,170,134,.45)":"rgba(214,101,128,.45)"})));}
   const colors:Record<string,string>={sma_20:"#478bdc",sma_50:"#a58be8",sma_200:"#ce9a46",ema_20:"#d66db2"};
   Object.keys(colors).forEach(key=>{if(toggles.has(key)&&data.indicators?.[key]){const line=chart!.addSeries(LineSeries,{color:colors[key],lineWidth:2,priceLineVisible:false,lastValueVisible:false,title:key.toUpperCase().replace("_"," ")});line.setData(data.indicators[key].map(x=>({time:x.time as any,value:x.value})));}});
   const byDate=new Map(data.candles.map(c=>[c.trade_date,c]));
   chart.subscribeCrosshairMove(event=>{const t=event.time;const day=typeof t==="string"?t:typeof t==="object"?`${t.year}-${String(t.month).padStart(2,"0")}-${String(t.day).padStart(2,"0")}`:null;setHovered(day?byDate.get(day)??null:null);});
   chart.timeScale().fitContent();
   if(sessions>0&&data.candles.length>sessions)chart.timeScale().setVisibleRange({from:data.candles[data.candles.length-sessions].trade_date as any,to:data.candles[data.candles.length-1].trade_date as any});
  }catch{setFailed(true);}
  return()=>{observer?.disconnect();if(media&&applyTheme)media.removeEventListener?.("change",applyTheme);chart?.remove();};
 },[data,toggles,mode,sessions,volumeVisible]);
 const candle=hovered??data.candles[data.candles.length-1];
 return <><div className="terminal-ohlc" aria-label="Daily candle values"><span>{candle.trade_date}</span>{([["O",candle.open],["H",candle.high],["L",candle.low],["C",candle.close]] as const).map(([label,value])=><span key={label}><small>{label}</small> {price(value)}</span>)}<span><small>Vol</small> {candle.volume==null?"—":Number(candle.volume).toLocaleString("en-IN")}</span></div><div className={"market-chart terminal-stock-canvas"+(expanded?" is-expanded":"")} ref={ref} aria-label="Interactive daily price chart"/>{failed&&<p role="status" className="notice">Chart rendering is unavailable. The recorded price and candle values remain visible.</p>}</>;
}

export default function StockExplorer({initialTarget}:{initialTarget?:EliteTarget}={}){
  const [query,setQuery]=useState(initialTarget?.symbol??"");const [exchange,setExchange]=useState(initialTarget?.exchange??"");
  const pendingTarget=useRef(initialTarget);const [results,setResults]=useState<Instrument[]>([]);const [selected,setSelected]=useState<Instrument|null>(null);
  const [technical,setTechnical]=useState<Technical|null>(null);const [summary,setSummary]=useState<Summary|null>(null);const [loading,setLoading]=useState(false);const [error,setError]=useState("");
  const [toggles,setToggles]=useState(new Set(["sma_20","sma_50","ema_20"]));
  const [liveQuote,setLiveQuote]=useState<{status:string;quote:{last_traded_price:number;traded_at:string;age_ms:number}|null;reason:string|null}|null>(null);
  const [providerResolution,setProviderResolution]=useState<{subscription_ready:boolean;instrument_key:string|null;blocker:string|null}|null>(null);
  const searchSeq=useRef(0);const detailSeq=useRef(0);
  const [detailLoading,setDetailLoading]=useState(false);const [detailError,setDetailError]=useState("");
  const [mode,setMode]=useState<ChartMode>("candles");const [sessions,setSessions]=useState<number>(126);const [volumeVisible,setVolumeVisible]=useState(true);const [expanded,setExpanded]=useState(false);const [companyOpen,setCompanyOpen]=useState(false);
  async function search(){
    const sequence=++searchSeq.current;
    if(!query.trim()){setResults([]);setError("");return;}
    setLoading(true);
    try{
      const params=new URLSearchParams({q:query.trim(),limit:"50"});
      if(exchange)params.set("exchange",exchange);
      const response=await fetch("/api/v1/instruments?"+params);
      if(!response.ok)throw Error("Instrument search failed");
      const items:Instrument[]=await response.json();
      if(sequence===searchSeq.current){setResults(items);setError("");const target=pendingTarget.current;if(target){pendingTarget.current=undefined;const match=items.find(x=>x.id===target.id&&x.isin===target.isin&&x.exchange===target.exchange&&x.symbol===target.symbol);if(match)void choose(match);else setError("Selected research instrument could not be verified. Choose a matching registry record.");}}
    }catch(e){if(sequence===searchSeq.current){setResults([]);setError(String(e));}}
    finally{if(sequence===searchSeq.current)setLoading(false);}
  }
  useEffect(()=>{
    searchSeq.current++;
    if(!query.trim()){setResults([]);setError("");setLoading(false);return;}
    const handle=setTimeout(()=>{void search();},350);
    return()=>clearTimeout(handle);
  },[query,exchange]);
  async function choose(item:Instrument){
   const request=++detailSeq.current;setSelected(item);setTechnical(null);setSummary(null);setLiveQuote(null);setProviderResolution(null);setDetailLoading(true);setDetailError("");setCompanyOpen(false);setExpanded(false);
   try{
    const [t,s]=await Promise.all([fetch(`/intelligence/api/v1/intelligence/technical/${item.id}`),fetch(`/intelligence/api/v1/intelligence/technical/${item.id}/summary`)]);
    if(!t.ok||!s.ok)throw Error("Technical research API is unavailable");
    const [nextTechnical,nextSummary]=await Promise.all([t.json(),s.json()]);
    if(request!==detailSeq.current)return;
    if(nextTechnical.instrument?.id!==item.id)throw Error("Instrument response did not match selected stock");
    setTechnical(nextTechnical);setSummary(nextSummary);
    try{const resolution=await fetch(`/intelligence/api/v1/intelligence/providers/upstox/resolve?instrument_id=${item.id}`);if(resolution.ok){const mapping=await resolution.json();if(request===detailSeq.current)setProviderResolution(mapping);}}catch{/* provider mapping is optional research metadata */}
   }catch(e){if(request===detailSeq.current){setDetailError(String(e));setTechnical(null);setSummary(null);}}
   finally{if(request===detailSeq.current)setDetailLoading(false);}
  }
  useEffect(()=>{
    if(!selected||!providerResolution?.subscription_ready)return;
    let cancelled=false;let streamRevision=0;
    const refresh=async()=>{const revision=streamRevision;try{const response=await fetch(`/intelligence/api/v1/intelligence/providers/upstox/quotes/${selected.id}`);if(response.ok){const quote=await response.json();if(!cancelled&&revision===streamRevision)setLiveQuote(quote);}}catch{if(!cancelled&&revision===streamRevision)setLiveQuote({status:"UNAVAILABLE",quote:null,reason:"QUOTE_API_UNAVAILABLE"});}};
    void refresh();
    if(typeof EventSource==="undefined")return()=>{cancelled=true;};
    const source=new EventSource(`/api/v1/live/instruments/${selected.id}`);
    const receive=(event:Event)=>{streamRevision++;try{if(!cancelled)setLiveQuote(JSON.parse((event as MessageEvent<string>).data));}catch{if(!cancelled)setLiveQuote({status:"UNAVAILABLE",quote:null,reason:"INVALID_STREAM_EVENT"});}};
    source.addEventListener("quote",receive);
    source.onerror=()=>{streamRevision++;if(!cancelled)setLiveQuote(previous=>({status:previous?.quote?"LAST_OBSERVED":"UNAVAILABLE",quote:previous?.quote??null,reason:"LIVE_STREAM_RECONNECTING"}));};
    return()=>{cancelled=true;source.removeEventListener("quote",receive);source.close();};
  },[selected?.id,providerResolution?.subscription_ready]);
  function toggle(key:string){const next=new Set(toggles);next.has(key)?next.delete(key):next.add(key);setToggles(next);}
  const latest=technical?.candles?.[technical.candles.length-1];const change=technical?dailyPriceChange(technical.candles):null;
  return <div className="explorer terminal-stock-explorer">
    <section className="panel glass explorer-search"><div className="sectionhead"><div><small className="section-kicker">VALIDATED DAILY DATA</small><h2>Stock Explorer</h2></div><span className="tag">RESEARCH ONLY</span></div><div className="searchbar exchange-searchbar"><ExchangePicker value={exchange} onChange={v=>{pendingTarget.current=undefined;setExchange(v);}}/><input aria-label="Instrument search" value={query} onChange={e=>{pendingTarget.current=undefined;setQuery(e.target.value);}} onKeyDown={e=>e.key==="Enter"&&search()} placeholder="Type stock name, ticker or ISIN — searches automatically"/><button className="primary" onClick={search} disabled={loading}>Search</button></div>
      {loading&&<p className="muted tiny" role="status">Loading validated market records…</p>}{error&&<div className="error">{error}</div>}<div className="instrument-results">{results.map(x=><button key={x.id} onClick={()=>choose(x)} className={selected?.id===x.id?"selected":""}><strong>{x.exchange}:{x.symbol}</strong><span>{x.security_name||x.isin||"Name unavailable"}</span><small>{x.listing_status} · {x.source}</small></button>)}{!results.length&&!loading&&<p className="muted tiny">The production registry is empty until a lawfully sourced instrument file is imported.</p>}</div></section>
    {selected&&<section className="panel glass terminal-stock-header" aria-label="Selected stock overview">
      <div className="terminal-stock-identity"><small className="section-kicker">{selected.exchange} · {selected.series||"Listed equity"}</small><h2>{selected.symbol}</h2><p>{selected.security_name||selected.isin||"Company name unavailable"}</p></div>
      <div className="terminal-stock-price"><span>Latest verified daily close</span><strong>{price(latest?.close)}</strong>{change&&<span className={change.amount>=0?"positive":"negative"}>{change.amount>=0?"+":""}{price(change.amount)} ({change.percent>=0?"+":""}{change.percent.toFixed(2)}%) vs previous recorded close</span>}<small>{latest?latest.trade_date+" · "+latest.source_code:"Awaiting daily evidence"}</small></div>
      <div className="terminal-stock-quote"><span>{liveQuote?.status==="LIVE"?"Live provider quote":liveQuote?.quote?"Last observed provider quote":"Live quote"}</span><strong>{price(liveQuote?.quote?.last_traded_price)}</strong><small>{liveQuote?.quote?.traded_at||liveQuote?.reason?.replace(/_/g," ")||"Not available yet"}</small><small>{providerResolution?.subscription_ready?"Provider instrument resolved":providerResolution?.blocker?.replace(/_/g," ")||"Provider mapping pending"}</small></div>
    </section>}
    {!selected?<section className="panel glass emptyfeature compact-empty"><div className="featureicon">⌁</div><h2>Select a validated instrument</h2><p>Charts and calculations appear only when registry and daily candle records exist. No demonstration prices are shown in production.</p></section>:
      detailLoading&&!technical?<section className="panel glass terminal-chart-empty" role="status"><strong>Loading {selected.symbol} research…</strong><p>Retrieving validated daily records.</p></section>:
      detailError?<section className="panel glass" role="alert"><strong>{detailError}</strong><button className="secondary" onClick={()=>void choose(selected)}>Retry stock research</button></section>:
      technical?.candles?.length?<><section className="panel glass chart-panel terminal-stock-chart" aria-label="Stock price and volume chart">
       <div className="sectionhead"><div><small className="section-kicker">VERIFIED DAILY HISTORY</small><h2>Price &amp; volume</h2><p className="muted tiny">{technical.candles.length} completed candles · {technical.as_of||latest?.trade_date} · Not live</p></div><button className="secondary" type="button" aria-pressed={expanded} onClick={()=>setExpanded(v=>!v)}>{expanded?"Reduce chart":"Expand chart"}</button></div>
       <div className="terminal-chart-toolbar"><div role="group" aria-label="Chart period">{periods.map(p=><button key={p.label} type="button" aria-pressed={sessions===p.sessions} className={sessions===p.sessions?"on":""} onClick={()=>setSessions(p.sessions)}>{p.label}</button>)}</div><div role="group" aria-label="Chart type"><button type="button" aria-pressed={mode==="candles"} className={mode==="candles"?"on":""} onClick={()=>setMode("candles")}>Candles</button><button type="button" aria-pressed={mode==="line"} className={mode==="line"?"on":""} onClick={()=>setMode("line")}>Line</button><button type="button" aria-pressed={volumeVisible} className={volumeVisible?"on":""} onClick={()=>setVolumeVisible(v=>!v)}>Volume</button></div></div>
       <div className="indicator-toggles" role="group" aria-label="Moving averages">{["sma_20","sma_50","sma_200","ema_20"].map(x=><button key={x} type="button" aria-pressed={toggles.has(x)} className={toggles.has(x)?"on":""} disabled={!technical.indicators?.[x]?.length} onClick={()=>toggle(x)}>{x.toUpperCase().replace("_"," ")}</button>)}</div>
       <MarketChart data={technical} toggles={toggles} mode={mode} sessions={sessions} volumeVisible={volumeVisible} expanded={expanded}/><div className="chart-attribution">Periods use approximate trading-session counts, limited to available history. Charts by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView Lightweight Charts™</a></div></section>
      <div className="terminal-stock-actions"><details className="terminal-stock-tool"><summary>Research alerts</summary><ResearchAlerts key={"alerts-"+selected.id} instrumentId={selected.id}/></details><details className="terminal-stock-tool"><summary>Risk qualification</summary><RiskQualification key={"risk-"+selected.id} instrumentId={selected.id}/></details><details className="terminal-stock-tool"><summary>Strategy backtest</summary><BacktestPanel key={selected.id} instrumentId={selected.id}/></details></div>
      <div className="two"><section className="panel glass research-panel"><small className="section-kicker">TECHNICAL OBSERVATIONS</small><h2>Research summary</h2>{summary?.research&&<><div className="research-grid"><div><span>Trend</span><strong>{summary.research.trend}</strong></div><div><span>Momentum</span><strong>{summary.research.momentum}</strong></div><div><span>RSI 14</span><strong>{technical.latest_indicators?.rsi_14?.toFixed(2)||"—"}</strong></div><div><span>ADX 14</span><strong>{technical.latest_indicators?.adx_14?.toFixed(2)||"—"}</strong></div></div><Evidence title="Bullish evidence" items={summary.research.bullish_evidence}/><Evidence title="Bearish evidence" items={summary.research.bearish_evidence}/><Evidence title="Risk & missing data" items={[...summary.research.risk_observations,...summary.research.missing_data]}/></>}</section>
      <section className="panel glass"><small className="section-kicker">EXPLAINABLE DETECTIONS</small><h2>Patterns & levels</h2><div className="levels"><div><span>Support</span><strong>{technical.levels?.support.join(", ")||"—"}</strong></div><div><span>Resistance</span><strong>{technical.levels?.resistance.join(", ")||"—"}</strong></div></div><div className="pattern-list">{technical.patterns.slice(-8).reverse().map((p,i)=><article key={i}><div><strong>{p.pattern_type.replace(/_/g," ")}</strong><span className={p.confirmation_status==="CONFIRMED"?"positive":"muted"}>{p.confirmation_status}</span></div><small>{p.detection_timestamp}</small><p>{p.explanation}</p><p className="muted tiny">Invalidation: {p.invalidation_conditions}</p></article>)}{!technical.patterns.length&&<p>No rule-based pattern detected in available history.</p>}</div></section></div></>:
      <section className="panel glass emptyfeature compact-empty"><div className="featureicon">∅</div><h2>No validated candles</h2><p>This instrument has no eligible completed daily candles. Import market sessions and lawful OHLCV records through Data Health.</p></section>}
    {selected&&<section className="panel glass terminal-company-link"><div className="sectionhead"><div><small className="section-kicker">COMPANY INTELLIGENCE</small><h2>Fundamentals &amp; company news</h2><p className="muted tiny">Authorized provider evidence, financial statements and institutional context.</p></div><button type="button" className="secondary" aria-expanded={companyOpen} onClick={()=>setCompanyOpen(v=>!v)}>{companyOpen?"Hide company research":"Open company research"}</button></div>{companyOpen&&<EquityResearchDashboard key={selected.id} initialQuery={selected.symbol}/>}</section>}
  </div>;
}
function Evidence({title,items}:{title:string;items:string[]}){return <div className="evidence"><strong>{title}</strong>{items.length?<ul>{items.map((x,i)=><li key={i}>{x.replace(/_/g," ")}</li>)}</ul>:<p className="muted tiny">No supported observation.</p>}</div>}
