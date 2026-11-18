import React,{useEffect,useMemo,useRef,useState} from "react";

export type HoldingDraft={symbol:string;assetType:string;quantity:number;averageCost:number;lastPrice:number|null};
type Instrument={instrument_key:string;exchange_code:string;isin:string|null;trading_symbol:string;instrument_type:string|null;display_name?:string|null};
type Quote={status:string;price:string;as_of:string;source:string;live:boolean;notice:string};
const money=(value:number|null)=>value===null?"—":new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);

export default function HoldingEditor({busy,onSave}:{busy:boolean;onSave:(draft:HoldingDraft)=>Promise<void>}){
 const [assetType,setAssetType]=useState("EQUITY");
 const [symbol,setSymbol]=useState("");
 const [quantity,setQuantity]=useState("");
 const [averageCost,setAverageCost]=useState("");
 const [lastPrice,setLastPrice]=useState("");
 const [selected,setSelected]=useState<Instrument|null>(null);
 const [suggestions,setSuggestions]=useState<Instrument[]>([]);
 const [searching,setSearching]=useState(false);
 const [quote,setQuote]=useState<Quote|null>(null);
 const [notice,setNotice]=useState("");
 const sequence=useRef(0);

 useEffect(()=>{
   if(assetType!=="EQUITY"||!symbol.trim()||selected?.trading_symbol===symbol.trim().toUpperCase()){
     setSuggestions([]);setSearching(false);return;
   }
   const current=++sequence.current;setSearching(true);
   const timer=window.setTimeout(async()=>{
     try{const response=await fetch("/api/v1/instruments/search?q="+encodeURIComponent(symbol.trim()));if(!response.ok)throw Error("Stock search unavailable");const rows:Instrument[]=await response.json();if(current===sequence.current){setSuggestions(rows.slice(0,10));setNotice("");}}
     catch{if(current===sequence.current){setSuggestions([]);setNotice("Stock suggestions are temporarily unavailable.");}}
     finally{if(current===sequence.current)setSearching(false);}
   },180);
   return()=>window.clearTimeout(timer);
 },[assetType,symbol,selected?.trading_symbol]);

 async function loadQuote(item:Instrument){
   setNotice("Loading latest provider price…");setQuote(null);setLastPrice("");
   try{const params=new URLSearchParams({symbol:item.trading_symbol,instrument_key:item.instrument_key});const response=await fetch("/intelligence/api/v1/intelligence/providers/upstox/quote?"+params);const body=await response.json();if(!response.ok)throw Error(body.detail||"Quote unavailable");setQuote(body);setLastPrice(String(body.price));setNotice(body.live?"Fresh Upstox quote loaded.":"Latest quote loaded; check its timestamp.");}
   catch(e){const raw=e instanceof Error?e.message:"";const friendly=raw.includes("PROVIDER_ACCESS_REJECTED")?"Upstox rejected the access token. Generate today's token, update .env, then restart the intelligence service.":raw.includes("PROVIDER_RATE_LIMITED")?"Upstox rate limit reached. Wait briefly and refresh the price.":raw.includes("PROVIDER_REQUEST_FAILED")?"Upstox could not be reached. Check the internet connection and try again.":raw||"Current price unavailable. You can still save the holding.";setNotice(friendly);}
 }
 function choose(item:Instrument){setSelected(item);setSymbol(item.trading_symbol);setSuggestions([]);void loadQuote(item);}
 function changeSymbol(value:string){setSymbol(value.toUpperCase());setSelected(null);setQuote(null);setLastPrice("");}
 const preview=useMemo(()=>{const q=Number(quantity),cost=Number(averageCost),price=Number(lastPrice);const validQ=Number.isFinite(q)&&q>0,validCost=Number.isFinite(cost)&&cost>=0,validPrice=lastPrice!==""&&Number.isFinite(price)&&price>0;const invested=validQ&&validCost?q*cost:null;const value=validQ&&validPrice?q*price:null;return{invested,value,pnl:invested!==null&&value!==null?value-invested:null};},[quantity,averageCost,lastPrice]);
 async function submit(event:React.FormEvent){event.preventDefault();setNotice("");if(assetType==="EQUITY"&&!selected){setNotice("Choose a stock from the suggestions so ATLAS can map the correct NSE/BSE instrument.");return;}try{await onSave({symbol:symbol.trim(),assetType,quantity:Number(quantity),averageCost:Number(averageCost),lastPrice:lastPrice===""?null:Number(lastPrice)});setSymbol("");setQuantity("");setAverageCost("");setLastPrice("");setSelected(null);setQuote(null);setSuggestions([]);}catch{setNotice("The holding could not be saved. Your entries were kept so you can retry.");}}
 return <form onSubmit={submit} className={`holding-editor${suggestions.length?" suggestions-open":""}`}>
  {suggestions.length>0&&<button type="button" className="holding-suggestion-scrim" aria-label="Close stock suggestions" onMouseDown={event=>{event.preventDefault();setSuggestions([]);}}/>}
  <div className="holding-fields">
   <label className="holding-symbol-field"><span>Stock or fund</span><input aria-label="Symbol" autoComplete="off" placeholder={assetType==="EQUITY"?"Type R, Reliance, TCS…":"Fund scheme code"} required maxLength={50} value={symbol} onChange={e=>changeSymbol(e.target.value)} onKeyDown={event=>{if(event.key==="Escape")setSuggestions([]);}}/>{searching&&<small>Finding matching stocks…</small>}
    {suggestions.length>0&&<div className="holding-suggestions" role="listbox">{suggestions.map(item=><button type="button" role="option" aria-selected="false" key={item.instrument_key} onClick={()=>choose(item)}><strong>{item.trading_symbol}</strong><span>{item.exchange_code} · {item.instrument_type||"Equity"}</span><small>{item.display_name||item.isin||item.instrument_key}</small></button>)}</div>}
   </label>
   <label><span>Investment type</span><select aria-label="Asset type" value={assetType} onChange={e=>{setAssetType(e.target.value);setSelected(null);setSuggestions([]);setQuote(null);setLastPrice("");}}><option value="EQUITY">Stock</option><option value="MUTUAL_FUND">Mutual fund</option></select></label>
   <label><span>Quantity</span><input aria-label="Quantity" type="number" min="0.000001" step="any" required placeholder="e.g. 60" value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
   <label><span>Average buy price</span><input aria-label="Average cost" type="number" min="0" step="any" required placeholder="₹ per share / unit" value={averageCost} onChange={e=>setAverageCost(e.target.value)}/></label>
   <label className="holding-price"><span>{assetType==="EQUITY"?"Current price (automatic)":"Latest NAV (optional)"}</span><input aria-label="Last price" type="number" min="0" step="any" placeholder={assetType==="EQUITY"?(selected?"Price unavailable":"Select a stock first"):"₹ per unit"} value={lastPrice} readOnly={assetType==="EQUITY"} onChange={e=>setLastPrice(e.target.value)}/>{selected&&<button className="quote-refresh" type="button" onClick={()=>void loadQuote(selected)}>Refresh price</button>}</label>
  </div>
  {notice&&<p className="holding-notice" role="status">{notice}</p>}
  {quote&&<p className="holding-quote-meta">{quote.source} · {quote.live?"Fresh quote":"Latest quote"} · {new Date(quote.as_of).toLocaleString("en-IN")}</p>}
  <div className="holding-preview" aria-label="Automatic holding calculations"><div><span>Invested amount</span><strong>{money(preview.invested)}</strong></div><div><span>Current value</span><strong>{money(preview.value)}</strong></div><div><span>Gain / loss</span><strong className={(preview.pnl||0)>=0?"positive":"negative"}>{money(preview.pnl)}</strong></div></div>
  <button className="primary holding-save" disabled={busy||!symbol.trim()||!quantity||!averageCost}>{busy?"Saving…":"Save holding"} <span>→</span></button>
 </form>;
}
