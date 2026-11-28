import React,{useEffect,useMemo,useRef,useState} from "react";

export type HoldingDraft={symbol:string;assetType:string;quantity:number;averageCost:number;lastPrice:number|null;notes?:string|null};
export type SipDraft={schemeCode:number;schemeName:string;monthlyAmount:number;startDate:string;nextInstallmentDate:string};
type Instrument={instrument_key:string;exchange_code:string;isin:string|null;trading_symbol:string;instrument_type:string|null;display_name?:string|null};
type Fund={scheme_code:number;scheme_name:string;nav:number|null;nav_date:string|null};
type Quote={status?:string;price?:string;ltp?:number;as_of:string;source:string;live?:boolean;notice?:string};
const money=(value:number|null)=>value===null?"—":new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(value);
const today=()=>new Date().toISOString().slice(0,10);

export type ExistingFund={symbol:string;quantity:number;average_cost:number};
export default function HoldingEditor({busy,onSave,onSaveSip,fundOnly=false,initialFund,existingFunds=[]}:{busy:boolean;onSave:(draft:HoldingDraft)=>Promise<void>;onSaveSip?:(draft:SipDraft)=>Promise<void>;fundOnly?:boolean;initialFund?:ExistingFund|null;existingFunds?:ExistingFund[]}){
 const [assetType,setAssetType]=useState(fundOnly?"MUTUAL_FUND":"EQUITY"),[investmentMode,setInvestmentMode]=useState<"ONE_TIME"|"SIP">("ONE_TIME");
 const [symbol,setSymbol]=useState(initialFund?.symbol??""),[quantity,setQuantity]=useState(initialFund?String(initialFund.quantity):""),[averageCost,setAverageCost]=useState(initialFund?String(initialFund.average_cost):""),[lastPrice,setLastPrice]=useState("");
 const [sipAmount,setSipAmount]=useState("5000"),[sipDate,setSipDate]=useState(today());
 const [selected,setSelected]=useState<Instrument|null>(null),[selectedFund,setSelectedFund]=useState<Fund|null>(null);
 const [suggestions,setSuggestions]=useState<Instrument[]>([]),[fundSuggestions,setFundSuggestions]=useState<Fund[]>([]);
 const [searching,setSearching]=useState(false),[quote,setQuote]=useState<Quote|null>(null),[notice,setNotice]=useState("");
 const sequence=useRef(0);

 useEffect(()=>{
   const current=++sequence.current;
   const term=symbol.trim();
   const chosen=assetType==="EQUITY"?selected?.trading_symbol===term.toUpperCase():selectedFund?.scheme_name===term;
   if(!term||chosen||(assetType==="MUTUAL_FUND"&&term.length<2)){setSuggestions([]);setFundSuggestions([]);setSearching(false);return;}
   setSearching(true);
   const timer=window.setTimeout(async()=>{
     try{
       const url=assetType==="EQUITY"?"/api/v1/instruments/search?q=":"/api/v1/mutual-funds/search?q=";
       const response=await fetch(url+encodeURIComponent(term));if(!response.ok)throw Error("Search unavailable");
       const rows=await response.json();
       if(current===sequence.current){setSuggestions(assetType==="EQUITY"?rows.slice(0,10):[]);setFundSuggestions(assetType==="MUTUAL_FUND"?rows.slice(0,10):[]);setNotice("");}
     }catch{if(current===sequence.current){setSuggestions([]);setFundSuggestions([]);setNotice(assetType==="EQUITY"?"Stock suggestions are temporarily unavailable.":"Fund suggestions are temporarily unavailable.");}}
     finally{if(current===sequence.current)setSearching(false);}
   },180);
   return()=>{window.clearTimeout(timer);sequence.current++;};
 },[assetType,symbol,selected?.trading_symbol,selectedFund?.scheme_name]);

 async function loadQuote(item:Instrument){
   setNotice("Loading latest provider price…");setQuote(null);setLastPrice("");
   try{const params=new URLSearchParams({instrumentKey:item.instrument_key});const response=await fetch("/api/v1/instruments/quote?"+params);const body=await response.json();if(!response.ok)throw Error(body.detail||body.message||"Quote unavailable");const price=body.ltp??body.price;if(price==null)throw Error("Provider returned no price");setQuote(body);setLastPrice(String(price));setNotice("Latest authorized Upstox quote loaded.");}
   catch(e){const raw=e instanceof Error?e.message:"";const friendly=raw.includes("PROVIDER_ACCESS_REJECTED")?"Upstox rejected the access token. Connect today’s token in Market & Data Health.":raw.includes("PROVIDER_RATE_LIMITED")?"Upstox rate limit reached. Wait briefly and refresh the price.":raw.includes("PROVIDER_REQUEST_FAILED")?"Upstox could not be reached. Check the internet connection and try again.":raw||"Current price unavailable. You can still save the holding.";setNotice(friendly);}
 }
 function chooseStock(item:Instrument){setSelected(item);setSelectedFund(null);setSymbol(item.trading_symbol);setSuggestions([]);void loadQuote(item);}
 function chooseFund(item:Fund){sequence.current++;const existing=existingFunds.find(f=>f.symbol===String(item.scheme_code));if(existing){setQuantity(String(existing.quantity));setAverageCost(String(existing.average_cost));}setSelectedFund(item);setSelected(null);setSymbol(item.scheme_name);setFundSuggestions([]);setQuote(null);setLastPrice(item.nav==null?"":String(item.nav));setNotice(item.nav==null?"This fund has no published NAV yet.":`Latest stored NAV loaded${item.nav_date?` for ${item.nav_date}`:" (date unavailable)"}.`);}
 function changeSymbol(value:string){sequence.current++;setSuggestions([]);setFundSuggestions([]);setSymbol(assetType==="EQUITY"?value.toUpperCase():value);setSelected(null);setSelectedFund(null);setQuote(null);setLastPrice("");}
 function reset(){sequence.current++;setSymbol("");setQuantity("");setAverageCost("");setLastPrice("");setSelected(null);setSelectedFund(null);setQuote(null);setSuggestions([]);setFundSuggestions([]);}
 const preview=useMemo(()=>{const q=Number(quantity),cost=Number(averageCost),price=Number(lastPrice);const validQ=Number.isFinite(q)&&q>0,validCost=Number.isFinite(cost)&&cost>=0,validPrice=lastPrice!==""&&Number.isFinite(price)&&price>0;const invested=validQ&&validCost?q*cost:null;const value=validQ&&validPrice?q*price:null;return{invested,value,pnl:invested!==null&&value!==null?value-invested:null};},[quantity,averageCost,lastPrice]);
 async function submit(event:React.FormEvent){
   event.preventDefault();setNotice("");
   if(assetType==="EQUITY"&&!selected){setNotice("Choose a stock from the suggestions so ATLAS maps the correct NSE/BSE instrument.");return;}
   if(assetType==="MUTUAL_FUND"&&!selectedFund){setNotice("Choose a mutual fund from the suggestions so ATLAS can fill its NAV automatically.");return;}
   try{
     if(assetType==="MUTUAL_FUND"&&investmentMode==="SIP"){
       if(!onSaveSip||!selectedFund)return;
       await onSaveSip({schemeCode:selectedFund.scheme_code,schemeName:selectedFund.scheme_name,monthlyAmount:Number(sipAmount),startDate:sipDate,nextInstallmentDate:sipDate});
     }else await onSave({symbol:assetType==="MUTUAL_FUND"?String(selectedFund!.scheme_code):symbol.trim(),assetType,quantity:Number(quantity),averageCost:Number(averageCost),lastPrice:lastPrice===""?null:Number(lastPrice),notes:selectedFund?.scheme_name||null});
     reset();
   }catch{setNotice("This investment could not be saved. Your entries were kept so you can retry.");}
 }
 const open=suggestions.length>0||fundSuggestions.length>0,isSip=assetType==="MUTUAL_FUND"&&investmentMode==="SIP";
 return <form onSubmit={submit} className={`holding-editor${open?" suggestions-open":""}`}>
  {open&&<button type="button" className="holding-suggestion-scrim" aria-label={assetType==="EQUITY"?"Close stock suggestions":"Close fund suggestions"} onMouseDown={event=>{event.preventDefault();setSuggestions([]);setFundSuggestions([]);}}/>}
  <div className="holding-fields">
   <label className="holding-symbol-field"><span>{assetType==="EQUITY"?"Stock":"Mutual fund"}</span><input aria-label="Symbol" autoComplete="off" placeholder={assetType==="EQUITY"?"Type R, Reliance, TCS…":"Type HDFC, index, flexi cap…"} required maxLength={100} value={symbol} onChange={e=>changeSymbol(e.target.value)} onKeyDown={event=>{if(event.key==="Escape"){setSuggestions([]);setFundSuggestions([]);}}}/>{searching&&<small>Finding matching {assetType==="EQUITY"?"stocks":"funds"}…</small>}
    {suggestions.length>0&&<div className="holding-suggestions" role="listbox">{suggestions.map(item=><button type="button" role="option" aria-selected="false" key={item.instrument_key} onClick={()=>chooseStock(item)}><strong>{item.trading_symbol}</strong><span>{item.exchange_code} · {item.instrument_type||"Equity"}</span><small>{item.display_name||item.isin||item.instrument_key}</small></button>)}</div>}
    {fundSuggestions.length>0&&<div className="holding-suggestions" role="listbox">{fundSuggestions.map(item=><button type="button" role="option" aria-selected="false" key={item.scheme_code} onClick={()=>chooseFund(item)}><strong>{item.scheme_name}</strong><span>Scheme {item.scheme_code}</span><small>{item.nav==null?"NAV unavailable":`NAV ${money(Number(item.nav))}${item.nav_date?` · ${item.nav_date}`:""}`}</small></button>)}</div>}
   </label>
   {!fundOnly&&<label><span>Investment type</span><select aria-label="Asset type" value={assetType} onChange={e=>{setAssetType(e.target.value);setInvestmentMode("ONE_TIME");reset();}}><option value="EQUITY">Stock</option><option value="MUTUAL_FUND">Mutual fund</option></select></label>}
   {assetType==="MUTUAL_FUND"&&!fundOnly&&onSaveSip&&<label className="holding-mode"><span>How do you invest?</span><select aria-label="Mutual fund investment mode" value={investmentMode} onChange={e=>setInvestmentMode(e.target.value as "ONE_TIME"|"SIP")}><option value="ONE_TIME">One-time / lump sum</option><option value="SIP">SIP every month</option></select></label>}
   {isSip?<>
    <label><span>Monthly SIP amount</span><input aria-label="Monthly SIP amount" type="number" min="1" step="1" required value={sipAmount} onChange={e=>setSipAmount(e.target.value)}/></label>
    <label><span>Next SIP date</span><input aria-label="Next SIP date" type="date" required value={sipDate} onChange={e=>setSipDate(e.target.value)}/></label>
    <div className="holding-price holding-nav-readout"><span>Latest NAV (automatic)</span><strong>{lastPrice?money(Number(lastPrice)):"Choose a fund"}</strong></div>
   </>:<>
    <label><span>{assetType==="EQUITY"?"Quantity":"Units held"}</span><input aria-label="Quantity" type="number" min="0.000001" step="any" required placeholder="e.g. 60" value={quantity} onChange={e=>setQuantity(e.target.value)}/></label>
    <label><span>{assetType==="EQUITY"?"Average buy price":"Average buy NAV"}</span><input aria-label="Average cost" type="number" min="0" step="any" required placeholder="₹ per share / unit" value={averageCost} onChange={e=>setAverageCost(e.target.value)}/></label>
    <label className="holding-price"><span>{assetType==="EQUITY"?"Current price (automatic)":"Latest NAV (automatic)"}</span><input aria-label="Last price" type="number" min="0" step="any" placeholder={assetType==="EQUITY"?(selected?"Price unavailable":"Select a stock first"):"Select a fund first"} value={lastPrice} readOnly/>{selected&&<button className="quote-refresh" type="button" onClick={()=>void loadQuote(selected)}>Refresh price</button>}</label>
   </>}
  </div>
  {fundOnly&&selectedFund&&existingFunds.some(f=>f.symbol===String(selectedFund.scheme_code))&&<p className="holding-notice">Existing holding selected. Save the total units currently owned and weighted average buy NAV; this replaces the saved position, not adds another purchase.</p>}
  {fundOnly&&<p className="muted tiny">Record units already allotted, including completed SIP installments. Saving a holding does not place an order or create a future SIP.</p>}
  {notice&&<p className="holding-notice" role="status">{notice}</p>}
  {quote&&<p className="holding-quote-meta">{quote.source} · Latest authorized quote · {new Date(quote.as_of).toLocaleString("en-IN")}</p>}
  {!isSip&&<div className="holding-preview" aria-label="Automatic holding calculations"><div><span>Invested amount</span><strong>{money(preview.invested)}</strong></div><div><span>Current value</span><strong>{money(preview.value)}</strong></div><div><span>Gain / loss</span><strong className={(preview.pnl||0)>=0?"positive":"negative"}>{money(preview.pnl)}</strong></div></div>}
  {isSip&&<p className="sip-safety-note">This saves your SIP schedule in ATLAS. It does not debit your bank or place an order.</p>}
  <button className="primary holding-save" disabled={busy||!symbol.trim()||(isSip?(!sipAmount||!selectedFund):(!quantity||!averageCost))}>{busy?"Saving…":isSip?"Save SIP":"Save holding"} <span>→</span></button>
 </form>;
}
