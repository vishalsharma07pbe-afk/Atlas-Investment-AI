import {useCallback,useEffect,useRef,useState} from "react";

type IndexQuote={label:string;price:number;change:number;change_percent:number;as_of:string;freshness:"LIVE"|"DELAYED"};
type IndexResponse={status:"AVAILABLE"|"UNAVAILABLE";source:string;reason?:string;items:IndexQuote[];notice:string};

const number=new Intl.NumberFormat("en-IN",{maximumFractionDigits:2,minimumFractionDigits:2});
const reasonText=(reason?:string)=>reason==="PROVIDER_ACCESS_REJECTED"?"Upstox authorization expired":reason==="PROVIDER_RATE_LIMITED"?"Provider rate limit reached":reason==="PROVIDER_NOT_CONFIGURED"?"Index provider not configured":"Index quotes unavailable";

export default function MarketIndexStrip(){
 const [data,setData]=useState<IndexResponse|null>(null);
 const [loading,setLoading]=useState(true);
 const [streamState,setStreamState]=useState<"CONNECTING"|"LIVE"|"RECONNECTING"|"UNAVAILABLE">("CONNECTING");
 const request=useRef<AbortController|null>(null);const rail=useRef<HTMLDivElement|null>(null);
 const slide=(direction:number)=>{const el=rail.current;if(!el)return;const first=el.querySelector("article");el.scrollBy({left:direction*((first?.getBoundingClientRect().width??el.clientWidth)+8),behavior:"smooth"});};
 const streamRevision=useRef(0);
 const load=useCallback(async()=>{
  request.current?.abort();
  const controller=new AbortController();request.current=controller;
  const revision=streamRevision.current;
  setLoading(true);
  try{
   const response=await fetch("/intelligence/api/v1/intelligence/market/indices",{signal:controller.signal});
   if(!response.ok)throw Error("Index service unavailable");
   const next:IndexResponse=await response.json();
   if(!Array.isArray(next.items))throw Error("Invalid index response");
   if(controller.signal.aborted||revision!==streamRevision.current)return;
   setData(previous=>{
    // Keep the latest stream snapshot if a manual HTTP refresh returns older
    // observations or loses provider access. Never downgrade newer prices.
    if(previous?.source==="UPSTOX_V3_STREAM"&&previous.items.length){
     const old=new Map(previous.items.map(item=>[item.label,Date.parse(item.as_of)]));
     if(next.status!=="AVAILABLE"||next.items.some(item=>old.has(item.label)&&Date.parse(item.as_of)<=old.get(item.label)!))return previous;
    }
    return next;
   });
  }catch{
   if(!controller.signal.aborted&&revision===streamRevision.current)setData(previous=>previous?.items.length?previous:{status:"UNAVAILABLE",source:"UPSTOX",reason:"REQUEST_FAILED",items:[],notice:"Index service unavailable."});
  }finally{if(!controller.signal.aborted&&request.current===controller)setLoading(false);}
 },[]);
 useEffect(()=>{
  void load();
  if(typeof EventSource==="undefined"){setStreamState("UNAVAILABLE");return()=>request.current?.abort();}
  const source=new EventSource("/api/v1/live/market-indices");
  const receive=(event:Event)=>{try{
   const next=JSON.parse((event as MessageEvent<string>).data) as IndexResponse;
   if(!Array.isArray(next.items))throw Error("Invalid index stream");
   streamRevision.current++;
   if(next.status==="AVAILABLE"&&next.items.length){setData(next);setStreamState("LIVE");}
   else{setData(previous=>previous?.items.length?previous:next);setStreamState("RECONNECTING");}
   setLoading(false);
  }catch{streamRevision.current++;setStreamState("RECONNECTING");}};

  source.addEventListener("quote",receive);
  source.onopen=()=>setStreamState("CONNECTING");
  source.onerror=()=>{streamRevision.current++;setStreamState("RECONNECTING");};
  return()=>{request.current?.abort();source.removeEventListener("quote",receive);source.close();};
 },[load]);
 const streamedLive=streamState==="LIVE"&&data?.source==="UPSTOX_V3_STREAM"&&data.status==="AVAILABLE";
 const displayFreshness=(item:IndexQuote)=>data?.source==="UPSTOX_V3_STREAM"&&!streamedLive?"LAST OBSERVED":item.freshness==="LIVE"&&!streamedLive?"RECENT SNAPSHOT":item.freshness;
 return <section className={`market-strip glass${data?.status==="UNAVAILABLE"?" unavailable":""}`} aria-label="Market indices">
  <div className="market-strip-label" role="status" aria-label={streamedLive?"Market quotes live":loading||data?.status==="AVAILABLE"||streamState==="RECONNECTING"?"Market quotes delayed or connecting":"Market quotes unavailable"} title={streamedLive?"Live market quotes":loading||data?.status==="AVAILABLE"||streamState==="RECONNECTING"?"Delayed or connecting":"Unavailable"}><span className={streamedLive?"live-dot":loading||data?.status==="AVAILABLE"||streamState==="RECONNECTING"?"market-dot-wait":"market-dot-off"}/><strong>MARKETS</strong></div>
  {data?.items.length?<><button className="market-slide" type="button" aria-label="Previous market index" onClick={()=>slide(-1)}>‹</button><div ref={rail} className="market-strip-quotes" tabIndex={0} aria-label="Scrollable market indices">{data.items.map(item=><article key={item.label} title={`${displayFreshness(item)} · ${new Date(item.as_of).toLocaleString("en-IN")}`}><span>{item.label}</span><strong>{number.format(item.price)}</strong><small className={item.change>=0?"positive":"negative"}>{item.change>=0?"+":""}{number.format(item.change)} ({item.change_percent>=0?"+":""}{item.change_percent.toFixed(2)}%)</small><i>{displayFreshness(item)}</i></article>)}</div><button className="market-slide" type="button" aria-label="Next market index" onClick={()=>slide(1)}>›</button></>:<div className="market-strip-empty"><strong>{loading?"Retrieving verified index snapshots…":reasonText(data?.reason)}</strong><span>{data?.reason==="PROVIDER_ACCESS_REJECTED"?"Check the configured Analytics Token and market-data permissions in Settings.":"ATLAS will never substitute fabricated index values."}</span></div>}
  <button type="button" onClick={()=>void load()} disabled={loading} aria-label="Refresh market indices">↻</button>
 </section>;
}
