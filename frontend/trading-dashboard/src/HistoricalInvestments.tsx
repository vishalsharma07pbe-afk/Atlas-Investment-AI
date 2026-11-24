import {FormEvent,useCallback,useEffect,useRef,useState} from "react";

type Instrument={instrument_key:string;exchange_code:string;trading_symbol:string;display_name?:string|null};
type Fund={scheme_code:number;scheme_name:string};
type HistoryRow={id:string;symbol:string;display_name:string|null;asset_type:string;quantity:number;average_cost:number;exit_price:number;opened_on:string|null;closed_on:string;invested:number;exit_value:number;realized_pnl:number};
type ActiveHolding={unrealized_pnl:number|null;one_day_change:number|null};
const money=(value:number)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:2}).format(Number(value));
const today=()=>new Date().toISOString().slice(0,10);

export default function HistoricalInvestments({activeHoldings=[]}:{activeHoldings?:ActiveHolding[]}){
 const [rows,setRows]=useState<HistoryRow[]>([]),[assetType,setAssetType]=useState("EQUITY"),[query,setQuery]=useState("");
 const [selected,setSelected]=useState<{symbol:string;name:string}|null>(null),[matches,setMatches]=useState<Array<Instrument|Fund>>([]);
 const [quantity,setQuantity]=useState(""),[buyPrice,setBuyPrice]=useState(""),[sellPrice,setSellPrice]=useState("");
 const [openedOn,setOpenedOn]=useState(""),[closedOn,setClosedOn]=useState(today()),[busy,setBusy]=useState(false),[message,setMessage]=useState("");
 const requestId=useRef(0);
 const load=useCallback(async()=>{const response=await fetch("/api/v1/portfolio/history",{cache:"no-store"});if(!response.ok)throw Error("Past investments are unavailable");setRows(await response.json());},[]);
 useEffect(()=>{void load().catch(error=>setMessage(error.message));},[load]);
 useEffect(()=>{
   const term=query.trim();if(term.length<(assetType==="EQUITY"?1:2)||selected?.name===term){setMatches([]);return;}
   const id=++requestId.current;const timer=window.setTimeout(async()=>{try{const url=assetType==="EQUITY"?"/api/v1/instruments/search?q=":"/api/v1/mutual-funds/search?q=";const response=await fetch(url+encodeURIComponent(term));if(!response.ok)throw Error();const data=await response.json();if(id===requestId.current)setMatches(data.slice(0,8));}catch{if(id===requestId.current)setMatches([]);}},180);
   return()=>window.clearTimeout(timer);
 },[assetType,query,selected?.name]);
 function choose(item:Instrument|Fund){
   const fund="scheme_code" in item;const symbol=fund?String(item.scheme_code):item.trading_symbol;const name=fund?item.scheme_name:(item.display_name||item.trading_symbol);
   setSelected({symbol,name});setQuery(name);setMatches([]);
 }
 async function save(event:FormEvent){
   event.preventDefault();if(!selected){setMessage("Choose an investment from the suggestions first.");return;}
   setBusy(true);setMessage("");
   try{const response=await fetch("/api/v1/portfolio/history",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol:selected.symbol,displayName:selected.name,assetType,quantity:Number(quantity),averageCost:Number(buyPrice),exitPrice:Number(sellPrice),openedOn:openedOn||null,closedOn})});if(!response.ok)throw Error((await response.json().catch(()=>null))?.message||"Past investment could not be saved");setQuery("");setSelected(null);setQuantity("");setBuyPrice("");setSellPrice("");setOpenedOn("");setMessage("Past investment saved separately from your active holdings.");await load();}
   catch(error){setMessage(error instanceof Error?error.message:"Past investment could not be saved");}finally{setBusy(false);}
 }
 async function remove(row:HistoryRow){if(!confirm(`Delete the history record for ${row.display_name||row.symbol}?`))return;const response=await fetch(`/api/v1/portfolio/history/${row.id}`,{method:"DELETE"});if(response.ok)await load();}
 const total=rows.reduce((sum,row)=>sum+Number(row.realized_pnl),0);
 const currentPnl=activeHoldings.reduce((sum,row)=>sum+Number(row.unrealized_pnl||0),0);
 const dayChange=activeHoldings.reduce((sum,row)=>sum+Number(row.one_day_change||0),0);
 const overallPnl=total+currentPnl;
 return <section className="panel glass historical-investments" aria-label="Past investments">
  <div className="sectionhead"><div><small className="section-kicker">SEPARATE HISTORY</small><h2>Past investments (closed)</h2><p>Stocks and funds you have completely sold. These records never change your active holdings.</p></div></div>
  <div className="profit-summary" aria-label="Overall profit and loss summary">
   <div><small>CURRENT P&amp;L</small><strong className={currentPnl>=0?"positive":"negative"}>{money(currentPnl)}</strong><span>Unrealised active holdings</span></div>
   <div><small>ONE-DAY CHANGE</small><strong className={dayChange>=0?"positive":"negative"}>{money(dayChange)}</strong><span>Where previous close exists</span></div>
   <div><small>HISTORY P&amp;L</small><strong className={total>=0?"positive":"negative"}>{money(total)}</strong><span>Realised closed investments</span></div>
   <div><small>OVERALL P&amp;L</small><strong className={overallPnl>=0?"positive":"negative"}>{money(overallPnl)}</strong><span>Current plus realised</span></div>
  </div>
  <details><summary>Add an older closed investment</summary><form className="history-investment-form" onSubmit={save}>
   <label><span>Type</span><select value={assetType} onChange={event=>{setAssetType(event.target.value);setQuery("");setSelected(null);setMatches([]);}}><option value="EQUITY">Stock</option><option value="MUTUAL_FUND">Mutual fund</option></select></label>
   <label className="history-search"><span>{assetType==="EQUITY"?"Company or symbol":"Fund name or code"}</span><input value={query} onChange={event=>{setQuery(event.target.value);setSelected(null);}} placeholder={assetType==="EQUITY"?"Reliance, TCS…":"HDFC, index fund…"} autoComplete="off" required/>{matches.length>0&&<div className="history-suggestions">{matches.map(item=>{const fund="scheme_code" in item;const key=fund?item.scheme_code:item.instrument_key;return <button key={key} type="button" onClick={()=>choose(item)}><strong>{fund?item.scheme_name:item.trading_symbol}</strong><small>{fund?`Scheme ${item.scheme_code}`:`${item.exchange_code} · ${item.display_name||"Listed stock"}`}</small></button>})}</div>}</label>
   <label><span>Quantity / units</span><input type="number" min="0.000001" step="any" value={quantity} onChange={event=>setQuantity(event.target.value)} required/></label>
   <label><span>Average buy price</span><input type="number" min="0" step="any" value={buyPrice} onChange={event=>setBuyPrice(event.target.value)} required/></label>
   <label><span>Average sell price</span><input type="number" min="0" step="any" value={sellPrice} onChange={event=>setSellPrice(event.target.value)} required/></label>
   <label><span>Purchase date (optional)</span><input type="date" max={closedOn} value={openedOn} onChange={event=>setOpenedOn(event.target.value)}/></label>
   <label><span>Sold / closed date</span><input type="date" max={today()} value={closedOn} onChange={event=>setClosedOn(event.target.value)} required/></label>
   <button className="primary" disabled={busy||!selected}>{busy?"Saving…":"Save to history"}</button>
  </form></details>
  {message&&<p className="holding-notice" role="status">{message}</p>}
  <div className="tablewrap"><table><thead><tr><th>INVESTMENT</th><th>TYPE</th><th>CLOSED</th><th>INVESTED</th><th>EXIT VALUE</th><th>REALISED P&amp;L</th><th/></tr></thead><tbody>
   {rows.map(row=><tr key={row.id}><td className="symbol">{row.display_name||row.symbol}<small>{row.quantity} units · {row.symbol}</small></td><td><span className="asset-pill">{row.asset_type==="EQUITY"?"STOCK":"MUTUAL FUND"}</span></td><td>{new Date(row.closed_on+"T00:00:00").toLocaleDateString("en-IN")}</td><td>{money(row.invested)}</td><td>{money(row.exit_value)}</td><td className={Number(row.realized_pnl)>=0?"positive":"negative"}>{money(row.realized_pnl)}</td><td><button className="danger" onClick={()=>void remove(row)}>Delete</button></td></tr>)}
   {!rows.length&&<tr><td colSpan={7} className="empty">No closed investments saved. Your current holdings remain separate above.</td></tr>}
  </tbody></table></div>
 </section>;
}
