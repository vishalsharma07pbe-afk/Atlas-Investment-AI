import {FormEvent,useCallback,useEffect,useState} from "react";

type Performance={
  transaction_count:number;
  snapshot_count:number;
  xirr_percent:number|null;
  xirr_status:string;
  maximum_drawdown_percent:number|null;
  drawdown_status:string;
  methodology:string;
};

const empty:Performance={transaction_count:0,snapshot_count:0,xirr_percent:null,xirr_status:"UNAVAILABLE",maximum_drawdown_percent:null,drawdown_status:"UNAVAILABLE",methodology:""};
const percent=(value:number|null)=>value==null?"Not enough history":`${value.toFixed(2)}%`;

export default function PortfolioPerformanceHistory({revision=0}:{revision?:number}){
  const [performance,setPerformance]=useState<Performance>(empty);
  const [type,setType]=useState("DEPOSIT");
  const [amount,setAmount]=useState("");
  const [date,setDate]=useState(()=>new Date().toISOString().slice(0,10));
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const load=useCallback(async()=>{
    try{
      const response=await fetch("/api/v1/portfolio/history/performance",{cache:"no-store"});
      if(response.ok)setPerformance(await response.json());
    }catch{/* Keep an explicit unavailable state while offline. */}
  },[]);
  useEffect(()=>{void load();},[load,revision]);
  const snapshot=async()=>{
    setBusy(true);setMessage("");
    try{
      const response=await fetch("/api/v1/portfolio/history/snapshots/current",{method:"POST"});
      if(!response.ok)throw new Error("Could not record valuation");
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
    <p className="muted tiny">Record dated valuations and external cash flows to calculate money-weighted return. Buying or selling a holding is not treated as money entering or leaving the portfolio.</p>
    <div className="portfolio-history-metrics">
      <div><small>XIRR</small><strong>{percent(performance.xirr_percent)}</strong><span>{performance.transaction_count} cash-flow records</span></div>
      <div><small>MAX DRAWDOWN</small><strong>{percent(performance.maximum_drawdown_percent)}</strong><span>{performance.snapshot_count} dated valuations</span></div>
    </div>
    <form className="portfolio-cashflow-form" onSubmit={event=>void saveFlow(event)}>
      <label>Cash-flow type<select value={type} onChange={event=>setType(event.target.value)}><option value="DEPOSIT">Money added</option><option value="WITHDRAWAL">Money withdrawn</option><option value="DIVIDEND">Dividend received</option><option value="FEE">Fee paid</option></select></label>
      <label>Date<input type="date" max={new Date().toISOString().slice(0,10)} value={date} onChange={event=>setDate(event.target.value)} required/></label>
      <label>Amount (₹)<input type="number" min="0.01" step="0.01" value={amount} onChange={event=>setAmount(event.target.value)} required/></label>
      <button type="submit" disabled={busy||!amount}>Save cash flow</button>
    </form>
    {message&&<p className="muted tiny" role="status">{message}</p>}
    <p className="muted tiny">{performance.methodology||"XIRR and drawdown remain unavailable until enough dated, user-owned records exist."}</p>
  </section>;
}
