import {useEffect,useRef,useState} from "react";
import BacktestPanel from "./BacktestPanel";
import RiskQualification from "./RiskQualification";
import ResearchAlerts from "./ResearchAlerts";
import ExchangePicker from "./ExchangePicker";
import {CandlestickSeries,HistogramSeries,LineSeries,createChart,createSeriesMarkers,ColorType} from "lightweight-charts";

type Instrument={id:number;exchange:string;symbol:string;series:string|null;isin:string|null;security_name:string|null;listing_status:string;source:string;source_revision:string|null};
type Candle={trade_date:string;open:number;high:number;low:number;close:number;volume:number;adjustment_status:string;source_code:string;received_at:string};
type Pattern={pattern_type:string;detection_timestamp:string;explanation:string;confirmation_status:string;invalidation_conditions:string};
type Technical={instrument:Instrument;status:string;as_of?:string;candle_count?:number;candles:Candle[];indicators:Record<string,{time:string;value:number}[]>;latest_indicators?:Record<string,number|null>;levels?:{support:number[];resistance:number[]};patterns:Pattern[];missing_data?:string[];notice?:string};
type Summary={research:null|{trend:string;momentum:string;volatility_annualized:number|null;relative_volume:number|null;support_resistance:{support:number[];resistance:number[]};patterns:Pattern[];bullish_evidence:string[];bearish_evidence:string[];risk_observations:string[];missing_data:string[];source_freshness:{latest_verified_date:string;is_live:boolean}};notice:string};

function MarketChart({data,toggles}:{data:Technical;toggles:Set<string>}){
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!ref.current||!data.candles.length)return;
    const styles=getComputedStyle(ref.current);const ink=styles.getPropertyValue("--ink-soft").trim()||"#b9c4dc";const grid="rgba(130,150,200,.12)";
    const chart=createChart(ref.current,{height:520,autoSize:true,layout:{background:{type:ColorType.Solid,color:"transparent"},textColor:ink},grid:{vertLines:{color:grid},horzLines:{color:grid}},timeScale:{borderColor:grid},rightPriceScale:{borderColor:grid}});
    const candles=chart.addSeries(CandlestickSeries,{upColor:"#42ddb0",downColor:"#f0667e",wickUpColor:"#42ddb0",wickDownColor:"#f0667e",borderVisible:false});
    candles.setData(data.candles.map(x=>({time:x.trade_date as any,open:Number(x.open),high:Number(x.high),low:Number(x.low),close:Number(x.close)})));
    const volume=chart.addSeries(HistogramSeries,{priceFormat:{type:"volume"},priceScaleId:"volume",lastValueVisible:false,priceLineVisible:false});
    volume.priceScale().applyOptions({scaleMargins:{top:.78,bottom:0}});volume.setData(data.candles.map(x=>({time:x.trade_date as any,value:Number(x.volume),color:Number(x.close)>=Number(x.open)?"rgba(66,221,176,.42)":"rgba(240,102,126,.42)"})));
    const colors:Record<string,string>={sma_20:"#4bd7ff",sma_50:"#8d7bff",sma_200:"#f2b760",ema_20:"#ff63c6"};
    Object.keys(colors).forEach(key=>{if(toggles.has(key)&&data.indicators?.[key]){const line=chart.addSeries(LineSeries,{color:colors[key],lineWidth:2,priceLineVisible:false,lastValueVisible:false,title:key.toUpperCase().replace("_"," ")});line.setData(data.indicators[key].map(x=>({time:x.time as any,value:x.value})));}});
    if(data.patterns?.length)createSeriesMarkers(candles,data.patterns.slice(-30).map(p=>({time:p.detection_timestamp as any,position:p.pattern_type.includes("BEAR")||p.pattern_type.includes("TOP")||p.pattern_type==="SHOOTING_STAR"?"aboveBar":"belowBar",color:p.confirmation_status==="CONFIRMED"?"#f2b760":"#8d7bff",shape:p.confirmation_status==="CONFIRMED"?"arrowDown":"circle",text:p.pattern_type.replace(/_/g," ").slice(0,14)})) as any);
    chart.timeScale().fitContent();return()=>chart.remove();
  },[data,toggles]);
  return <div className="market-chart" ref={ref}/>;
}

export default function StockExplorer(){
  const [query,setQuery]=useState("");const [exchange,setExchange]=useState("");const [results,setResults]=useState<Instrument[]>([]);const [selected,setSelected]=useState<Instrument|null>(null);
  const [technical,setTechnical]=useState<Technical|null>(null);const [summary,setSummary]=useState<Summary|null>(null);const [loading,setLoading]=useState(false);const [error,setError]=useState("");
  const [toggles,setToggles]=useState(new Set(["sma_20","sma_50","ema_20"]));
  const [liveQuote,setLiveQuote]=useState<{status:string;quote:{last_traded_price:number;traded_at:string;age_ms:number}|null;reason:string|null}|null>(null);
  const [providerResolution,setProviderResolution]=useState<{subscription_ready:boolean;instrument_key:string|null;blocker:string|null}|null>(null);
  const searchSeq=useRef(0);
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
      if(sequence===searchSeq.current){setResults(items);setError("");}
    }catch(e){if(sequence===searchSeq.current){setResults([]);setError(String(e));}}
    finally{if(sequence===searchSeq.current)setLoading(false);}
  }
  useEffect(()=>{
    if(!query.trim()){searchSeq.current++;setResults([]);setError("");return;}
    const handle=setTimeout(()=>{void search();},350);
    return()=>clearTimeout(handle);
  },[query,exchange]);
  async function choose(item:Instrument){setSelected(item);setLiveQuote(null);setProviderResolution(null);setLoading(true);try{const [t,s]=await Promise.all([fetch(`/intelligence/api/v1/intelligence/technical/${item.id}`),fetch(`/intelligence/api/v1/intelligence/technical/${item.id}/summary`)]);if(!t.ok||!s.ok)throw Error("Technical research API is unavailable");setTechnical(await t.json());setSummary(await s.json());setError("");
    try{const resolution=await fetch(`/intelligence/api/v1/intelligence/providers/upstox/resolve?instrument_id=${item.id}`);if(resolution.ok)setProviderResolution(await resolution.json());}catch{/* provider mapping is optional research metadata */}}catch(e){setError(String(e));setTechnical(null);setSummary(null);}finally{setLoading(false);}}
  useEffect(()=>{
    if(!selected||!providerResolution?.subscription_ready)return;
    let cancelled=false;
    const refresh=async()=>{try{const response=await fetch(`/intelligence/api/v1/intelligence/providers/upstox/quotes/${selected.id}`);if(response.ok&&!cancelled)setLiveQuote(await response.json());}catch{if(!cancelled)setLiveQuote({status:"UNAVAILABLE",quote:null,reason:"QUOTE_API_UNAVAILABLE"});}};
    void refresh();const interval=setInterval(()=>void refresh(),5000);
    return()=>{cancelled=true;clearInterval(interval);};
  },[selected?.id,providerResolution?.subscription_ready]);
  function toggle(key:string){const next=new Set(toggles);next.has(key)?next.delete(key):next.add(key);setToggles(next);}
  return <div className="explorer">
    <section className="panel glass explorer-search"><div className="sectionhead"><div><small className="section-kicker">VALIDATED DAILY DATA</small><h2>Stock Explorer</h2></div><span className="tag">RESEARCH ONLY</span></div><div className="searchbar exchange-searchbar"><ExchangePicker value={exchange} onChange={setExchange}/><input aria-label="Instrument search" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==="Enter"&&search()} placeholder="Type stock name, ticker or ISIN — searches automatically"/><button className="primary" onClick={search} disabled={loading}>Search</button></div>
      {loading&&<p className="muted tiny" role="status">Loading validated market records…</p>}{error&&<div className="error">{error}</div>}<div className="instrument-results">{results.map(x=><button key={x.id} onClick={()=>choose(x)} className={selected?.id===x.id?"selected":""}><strong>{x.exchange}:{x.symbol}</strong><span>{x.security_name||x.isin||"Name unavailable"}</span><small>{x.listing_status} · {x.source}</small></button>)}{!results.length&&!loading&&<p className="muted tiny">The production registry is empty until a lawfully sourced instrument file is imported.</p>}</div></section>
    {selected&&liveQuote&&<section className="panel glass"><small className="section-kicker">UPSTOX QUOTE STATUS</small><h3>{liveQuote.status==="LIVE"&&liveQuote.quote?`₹${liveQuote.quote.last_traded_price.toFixed(2)}`:"Live quote unavailable"}</h3><p className="muted tiny">{liveQuote.status==="LIVE"&&liveQuote.quote?`Verified provider trade: ${liveQuote.quote.traded_at}`:liveQuote.reason?.replace(/_/g," ")}</p></section>}
    {selected&&providerResolution&&<section className="panel glass"><small className="section-kicker">UPSTOX INSTRUMENT DISCOVERY</small><h3>{providerResolution.subscription_ready?"Instrument key resolved":"Live subscription unavailable"}</h3><p className="muted tiny">{providerResolution.subscription_ready?`Provider key: ${providerResolution.instrument_key} · Not connected to live feed`:providerResolution.blocker?.replace(/_/g," ")}</p></section>}
    {!selected?<section className="panel glass emptyfeature compact-empty"><div className="featureicon">⌁</div><h2>Select a validated instrument</h2><p>Charts and calculations appear only when registry and daily candle records exist. No demonstration prices are shown in production.</p></section>:
      technical?.candles?.length?<><div className="explorer-heading"><div><small className="section-kicker">{selected.exchange} · DAILY</small><h2>{selected.symbol} <span>{selected.security_name}</span></h2></div><div className="freshness"><span>Latest verified</span><strong>{technical.as_of}</strong><small>Not live · {technical.candle_count} candles · {technical.candles[technical.candles.length-1]?.source_code}</small></div></div>
      <ResearchAlerts key={"alerts-"+selected.id} instrumentId={selected.id}/>
      <RiskQualification key={"risk-"+selected.id} instrumentId={selected.id}/>
      <BacktestPanel key={selected.id} instrumentId={selected.id}/>
      <section className="panel glass chart-panel"><div className="indicator-toggles">{["sma_20","sma_50","sma_200","ema_20"].map(x=><button key={x} className={toggles.has(x)?"on":""} onClick={()=>toggle(x)}>{x.toUpperCase().replace("_"," ")}</button>)}</div><MarketChart data={technical} toggles={toggles}/><div className="chart-attribution">Charts by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView Lightweight Charts™</a></div></section>
      <div className="two"><section className="panel glass research-panel"><small className="section-kicker">TECHNICAL OBSERVATIONS</small><h2>Research summary</h2>{summary?.research&&<><div className="research-grid"><div><span>Trend</span><strong>{summary.research.trend}</strong></div><div><span>Momentum</span><strong>{summary.research.momentum}</strong></div><div><span>RSI 14</span><strong>{technical.latest_indicators?.rsi_14?.toFixed(2)||"—"}</strong></div><div><span>ADX 14</span><strong>{technical.latest_indicators?.adx_14?.toFixed(2)||"—"}</strong></div></div><Evidence title="Bullish evidence" items={summary.research.bullish_evidence}/><Evidence title="Bearish evidence" items={summary.research.bearish_evidence}/><Evidence title="Risk & missing data" items={[...summary.research.risk_observations,...summary.research.missing_data]}/></>}</section>
      <section className="panel glass"><small className="section-kicker">EXPLAINABLE DETECTIONS</small><h2>Patterns & levels</h2><div className="levels"><div><span>Support</span><strong>{technical.levels?.support.join(", ")||"—"}</strong></div><div><span>Resistance</span><strong>{technical.levels?.resistance.join(", ")||"—"}</strong></div></div><div className="pattern-list">{technical.patterns.slice(-8).reverse().map((p,i)=><article key={i}><div><strong>{p.pattern_type.replace(/_/g," ")}</strong><span className={p.confirmation_status==="CONFIRMED"?"positive":"muted"}>{p.confirmation_status}</span></div><small>{p.detection_timestamp}</small><p>{p.explanation}</p><p className="muted tiny">Invalidation: {p.invalidation_conditions}</p></article>)}{!technical.patterns.length&&<p>No rule-based pattern detected in available history.</p>}</div></section></div></>:
      <section className="panel glass emptyfeature compact-empty"><div className="featureicon">∅</div><h2>No validated candles</h2><p>This instrument has no eligible completed daily candles. Import market sessions and lawful OHLCV records through Data Health.</p></section>}
  </div>;
}
function Evidence({title,items}:{title:string;items:string[]}){return <div className="evidence"><strong>{title}</strong>{items.length?<ul>{items.map((x,i)=><li key={i}>{x.replace(/_/g," ")}</li>)}</ul>:<p className="muted tiny">No supported observation.</p>}</div>}
