import {useCallback,useEffect,useState} from "react";

type IndexQuote={label:string;price:number;change:number;change_percent:number;as_of:string;freshness:"LIVE"|"DELAYED"};
type IndexResponse={status:"AVAILABLE"|"UNAVAILABLE";source:string;reason?:string;items:IndexQuote[];notice:string};

const number=new Intl.NumberFormat("en-IN",{maximumFractionDigits:2,minimumFractionDigits:2});
const reasonText=(reason?:string)=>reason==="PROVIDER_ACCESS_REJECTED"?"Upstox authorization expired":reason==="PROVIDER_RATE_LIMITED"?"Provider rate limit reached":reason==="PROVIDER_NOT_CONFIGURED"?"Index provider not configured":"Index quotes unavailable";

export default function MarketIndexStrip(){
 const [data,setData]=useState<IndexResponse|null>(null);
 const [loading,setLoading]=useState(true);
 const [streamState,setStreamState]=useState<"CONNECTING"|"LIVE"|"RECONNECTING"|"UNAVAILABLE">("CONNECTING");
 const load=useCallback(async()=>{
  try{const response=await fetch("/intelligence/api/v1/intelligence/market/indices");if(!response.ok)throw Error("Index service unavailable");setData(await response.json());}
  catch{setData({status:"UNAVAILABLE",source:"UPSTOX",reason:"REQUEST_FAILED",items:[],notice:"Index service unavailable."});}
  finally{setLoading(false);}
 },[]);
 useEffect(()=>{
  void load();
  if(typeof EventSource==="undefined"){setStreamState("UNAVAILABLE");return;}
  const source=new EventSource("/api/v1/live/market-indices");
  const receive=(event:Event)=>{try{const next=JSON.parse((event as MessageEvent<string>).data) as IndexResponse;if(next.status==="AVAILABLE"){setData(next);setStreamState("LIVE");}else{setData(previous=>previous||next);setStreamState("RECONNECTING");}setLoading(false);}catch{setStreamState("RECONNECTING");}};
  source.addEventListener("quote",receive);
  source.onopen=()=>setStreamState("CONNECTING");
  source.onerror=()=>setStreamState("RECONNECTING");
  return()=>{source.removeEventListener("quote",receive);source.close();};
 },[load]);
 return <section className={`market-strip glass${data?.status==="UNAVAILABLE"?" unavailable":""}`} aria-label="Market indices">
  <div className="market-strip-label"><span className={streamState==="LIVE"&&data?.status==="AVAILABLE"?"live-dot":""}/><strong>MARKETS</strong><small>{loading?"Loading…":streamState==="LIVE"&&data?.status==="AVAILABLE"?`${data.source} · live push`:streamState==="RECONNECTING"?"Stream reconnecting…":`${data?.source||"Provider"} · unavailable`}</small></div>
  {data?.items.length?<div className="market-strip-quotes">{data.items.map(item=><article key={item.label} title={`${item.freshness} · ${new Date(item.as_of).toLocaleString("en-IN")}`}><span>{item.label}</span><strong>{number.format(item.price)}</strong><small className={item.change>=0?"positive":"negative"}>{item.change>=0?"+":""}{number.format(item.change)} ({item.change_percent>=0?"+":""}{item.change_percent.toFixed(2)}%)</small><i>{item.freshness}</i></article>)}</div>:<div className="market-strip-empty"><strong>{loading?"Retrieving verified index snapshots…":reasonText(data?.reason)}</strong><span>{data?.reason==="PROVIDER_ACCESS_REJECTED"?"Daily Upstox sign-in is required before automatic stock and index prices can resume.":"ATLAS will never substitute fabricated index values."}</span></div>}
  <button type="button" onClick={()=>void load()} disabled={loading} aria-label="Refresh market indices">↻</button>
 </section>;
}
