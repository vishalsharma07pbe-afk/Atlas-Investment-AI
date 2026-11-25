import {FormEvent,useCallback,useEffect,useState} from "react";

type Performance={
  transaction_count:number;
  snapshot_count:number;
  xirr_percent:number|null;
  xirr_status:string;
  maximum_drawdown_percent:number|null;
  drawdown_status:string;
  methodology:string;
  external_cash_flow_count?:number;
  external_flows_after_valuation?:number;
  incomplete_snapshot_count?:number;
  future_snapshot_count?:number;
  valuation_through?:string|null;
  automatic_snapshot_count?:number;
  latest_capture_source?:string|null;
  latest_oldest_price_at?:string|null;
  latest_newest_price_at?:string|null;
};

const empty:Performance={transaction_count:0,snapshot_count:0,xirr_percent:null,xirr_status:"UNAVAILABLE",maximum_drawdown_percent:null,drawdown_status:"UNAVAILABLE",methodology:""};
const percent=(value:number|null)=>value==null?"Unavailable":`${value.toFixed(2)}%`;
const istToday=()=>new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Kolkata",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const statusText=(status:string)=>({UNAVAILABLE_INCOMPLETE_TERMINAL_VALUATION:"Latest valuation is incomplete.",UNAVAILABLE_AMBIGUOUS_OR_UNSUPPORTED_CASH_FLOWS:"Cash-flow sequence does not support a unique return within the calculation range.",UNAVAILABLE_EXTERNAL_FLOWS_REQUIRE_FLOW_ADJUSTED_HISTORY:"External flows require flow-adjusted history.",UNAVAILABLE_INCOMPLETE_VALUATION_HISTORY:"Historical valuations contain gaps.",UNAVAILABLE_INVALID_VALUATION_HISTORY:"Valuation history is invalid."} as Record<string,string>)[status]??"More dated evidence is needed.";

export default function PortfolioPerformanceHistory({revision=0}:{revision?:number}){
  const [performance,setPerformance]=useState<Performance>(empty);
  const [unavailable,setUnavailable]=useState(false);
  const [type,setType]=useState("DEPOSIT");
  const [amount,setAmount]=useState("");
  const [date,setDate]=useState(()=>istToday());
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const load=useCallback(async()=>{
    try{
      const response=await fetch("/api/v1/portfolio/history/performance",{cache:"no-store"});
      if(!response.ok)throw new Error("Performance unavailable");
      setPerformance(await response.json());setUnavailable(false);
    }catch{setPerformance(empty);setUnavailable(true);}
  },[]);
  useEffect(()=>{void load();const timer=window.setInterval(()=>{if(document.visibilityState==="visible")void load();},60_000);return()=>window.clearInterval(timer);},[load,revision]);
  const snapshot=async()=>{
    setBusy(true);setMessage("");
    try{
      const response=await fetch("/api/v1/portfolio/history/snapshots/current",{method:"POST"});
      if(!response.ok)throw new Error("Could not record valuation");
      const result=await response.json();
      if(result.recorded===false)throw new Error("Valuation not recorded: prices are missing, aged or undated. Refresh holdings first.");
      setMessage("Today's valuation was recorded.");await load();
    }catch(error){setMessage(error instanceof Error?error.message:"Could not record valuation");}
    finally{setBusy(false);}
  };
  const saveFlow=async(event:FormEvent)=>{
    event.preventDefault();setBusy(true);setMessage("");
    try{
      const response=await fetch("/api/v1/portfolio/history/transactions",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol:"PORTFOLIO",assetType:"CASH",transactionType:type,transactionDate:date,cashAmount:Number(amount),sourceCode:"MANUAL"})});
      if(!response.ok)throw new Error("Could not save cash flow");
      setAmount("");setMessage("Cash flow saved.");await load();
    }catch(error){setMessage(error instanceof Error?error.message:"Could not save cash flow");}
    finally{setBusy(false);}
  };
  return <section className="portfolio-history" aria-labelledby="portfolio-history-title">
    <div className="sectionhead"><div><small className="section-kicker">PERFORMANCE HISTORY</small><h2 id="portfolio-history-title">Returns &amp; drawdown</h2></div><button type="button" className="secondary" disabled={busy} onClick={()=>void snapshot()}>Record today&apos;s value</button></div>
    <p className="muted tiny">Record dated valuations and external cash flows to calculate money-weighted return. Buying or selling a holding is not treated as money entering or leaving the portfolio. Record dividends and fees here only when cash crosses the portfolio boundary; do not double count internal cash movements.</p>
    {unavailable&&<p role="alert">Performance data is unavailable. Previously calculated figures have been cleared.</p>}
    <div className="portfolio-history-metrics">
      <div><small>XIRR</small><strong>{percent(performance.xirr_percent)}</strong><span>{performance.external_cash_flow_count??performance.transaction_count} cash-flow records</span>{performance.xirr_percent==null&&<span>{statusText(performance.xirr_status)}</span>}</div>
      <div><small>MAX DRAWDOWN</small><strong>{percent(performance.maximum_drawdown_percent)}</strong><span>{performance.snapshot_count} dated valuations</span>{performance.maximum_drawdown_percent==null&&<span>{statusText(performance.drawdown_status)}</span>}</div>
    </div>
    {performance.valuation_through&&<p className="muted tiny">Performance through {performance.valuation_through} · {performance.external_flows_after_valuation??0} later external flows excluded · {performance.incomplete_snapshot_count??0} incomplete historical valuations · {performance.future_snapshot_count??0} future valuations excluded.</p>}
    {performance.automatic_snapshot_count!==undefined&&<div className="muted tiny"><p>Automatic evening valuation records: {performance.automatic_snapshot_count}. Automatic capture runs while the local backend is enabled and has sufficient recorded prices; missing days are not reconstructed.</p>{performance.latest_capture_source&&<p>Latest capture: {performance.latest_capture_source==="AUTO_RECORDED"?"Automatic":performance.latest_capture_source==="MANUAL_RECORDED"?"Manual":"Legacy recorded"}{performance.latest_oldest_price_at&&performance.latest_newest_price_at?` · Price observations: ${performance.latest_oldest_price_at} to ${performance.latest_newest_price_at}`:" · Price observation timestamps unavailable"}. Recorded values are not certified market closes.</p>}</div>}
    <form className="portfolio-cashflow-form" onSubmit={event=>void saveFlow(event)}>
      <label>Cash-flow type<select value={type} onChange={event=>setType(event.target.value)}><option value="DEPOSIT">Money added</option><option value="WITHDRAWAL">Money withdrawn</option><option value="DIVIDEND">Dividend paid out to you</option><option value="FEE">Fee paid from outside portfolio</option></select></label>
      <label>Date<input type="date" max={istToday()} value={date} onChange={event=>setDate(event.target.value)} required/></label>
      <label>Amount (₹)<input type="number" min="0.01" step="0.01" value={amount} onChange={event=>setAmount(event.target.value)} required/></label>
      <button type="submit" disabled={busy||!amount}>Save cash flow</button>
    </form>
    {message&&<p className="muted tiny" role="status">{message}</p>}
    <p className="muted tiny">{performance.methodology||"XIRR and drawdown remain unavailable until enough dated, user-owned records exist."}</p>
  </section>;
}
