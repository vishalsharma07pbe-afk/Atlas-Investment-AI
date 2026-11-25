import PortfolioBenchmarkRisk,{type BenchmarkRisk} from "./PortfolioBenchmarkRisk";
import {FormEvent,useCallback,useEffect,useState} from "react";

type RollingWindow={days:number;status:string;from:string|null;through:string|null;returnPercent:number|null;drawdownPercent:number|null;benchmarkStatus:string;benchmarkReturnPercent:number|null;relativePercentagePoints:number|null};
type WeeklyRisk={status:string;weeklyObservations:number;annualizedVolatilityPercent:number|null;annualizedDownsideDeviationPercent:number|null;negativeWeekFrequencyPercent:number|null;from:string|null;through:string|null};
type Performance={
  benchmark_risk_estimate?:BenchmarkRisk;
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
  flow_adjusted_status?:string;
  flow_adjusted_return_percent?:number|null;
  flow_adjusted_drawdown_percent?:number|null;
  flow_adjusted_interval_count?:number;
  flow_adjusted_cash_flow_count?:number;
  flow_adjusted_max_interval_days?:number|null;
  flow_adjusted_from?:string|null;
  flow_adjusted_through?:string|null;
  flow_adjusted_methodology?:string;
  rolling_performance?:RollingWindow[];
  weekly_risk_estimate?:WeeklyRisk;
  benchmark_reference?:string;
  benchmark_eligible_observation_count?:number;
  benchmark_latest_eligible_date?:string|null;
  benchmark_history_status?:string;
  rolling_methodology?:string;
};

const empty:Performance={transaction_count:0,snapshot_count:0,xirr_percent:null,xirr_status:"UNAVAILABLE",maximum_drawdown_percent:null,drawdown_status:"UNAVAILABLE",methodology:""};
const percent=(value:number|null)=>value==null?"Unavailable":`${value.toFixed(2)}%`;
const adjustedStatus=(status:string)=>({UNAVAILABLE_REQUIRES_TWO_VALUATIONS:"At least two dated valuations are required.",UNAVAILABLE_INCOMPLETE_VALUATIONS:"Incomplete valuations prevent adjustment.",UNAVAILABLE_VALUATION_GAPS:"Valuation intervals exceed seven calendar days.",UNAVAILABLE_NONPOSITIVE_CAPITAL_BASE:"A positive investment base is required.",UNAVAILABLE_INCONSISTENT_CASH_FLOWS:"Recorded flows and valuations are inconsistent.",UNAVAILABLE_INVALID_VALUATION_ORDER:"Valuation dates are not strictly increasing.",UNAVAILABLE_NUMERIC_RANGE:"The calculated return exceeds the supported range."} as Record<string,string>)[status]??"Insufficient recorded evidence.";
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
    {performance.flow_adjusted_status&&<section aria-label="Cash-flow-adjusted performance">
      <h3>Cash-flow-adjusted performance estimate</h3>
      <div className="portfolio-history-metrics">
        <div><small>LINKED DIETZ RETURN</small><strong>{percent(performance.flow_adjusted_return_percent??null)}</strong><span>Non-annualized estimate, not exact TWR</span></div>
        <div><small>ADJUSTED DRAWDOWN</small><strong>{percent(performance.flow_adjusted_drawdown_percent??null)}</strong><span>Estimated wealth index at recorded dates</span></div>
      </div>
      {performance.flow_adjusted_status!=="AVAILABLE_ESTIMATE"&&<p className="muted tiny">{adjustedStatus(performance.flow_adjusted_status)}</p>}
      {performance.flow_adjusted_from&&<p className="muted tiny">{performance.flow_adjusted_from} to {performance.flow_adjusted_through} · {performance.flow_adjusted_interval_count??0} intervals · {performance.flow_adjusted_cash_flow_count??0} external flows · longest gap {performance.flow_adjusted_max_interval_days??"unknown"} days.</p>}
      <p className="muted tiny">{performance.flow_adjusted_methodology}</p>
    </section>}
    {performance.rolling_performance&&<section aria-label="Trailing portfolio performance">
      <h3>Trailing portfolio returns and benchmark reference</h3>
      <p className="muted tiny">{performance.benchmark_reference} · Price reference only, not total return or a personalized benchmark.</p>
      {performance.benchmark_history_status&&<p className="muted tiny">{performance.benchmark_history_status==="STORED_OBSERVATIONS_AVAILABLE"?`${performance.benchmark_eligible_observation_count??0} eligible stored index dates in the portfolio history window · latest ${performance.benchmark_latest_eligible_date??"unknown"}. Coverage does not guarantee matched benchmark endpoints.`:"No eligible index history for this portfolio window. Automatic collection requires authorized data access and a stored exchange calendar."}</p>}
      <div className="portfolio-history-metrics">
      {performance.rolling_performance.map(window=><div key={window.days}><small>{window.days} DAYS</small><strong>{percent(window.returnPercent)}</strong>
        <span>Adjusted drawdown: {percent(window.drawdownPercent)}</span>
        <span>{window.status==="AVAILABLE_ESTIMATE"?"Linked Dietz estimate":window.status==="UNAVAILABLE_EXACT_START_DATE"?"Exact starting valuation missing.":adjustedStatus(window.status)}</span>
        <span>Index price return: {percent(window.benchmarkReturnPercent)}</span>
        <span>Relative difference: {window.relativePercentagePoints==null?"Unavailable":window.relativePercentagePoints.toFixed(2)+" pp"}</span>
        {window.benchmarkStatus!=="AVAILABLE_PRICE_REFERENCE"&&<span>{window.benchmarkStatus==="UNAVAILABLE_BENCHMARK_QUALITY"?"Index evidence failed quality checks.":"Comparable dated index evidence unavailable."}</span>}
      </div>)}
      </div>
      {performance.weekly_risk_estimate&&<><h3>Historical weekly risk estimate</h3><div className="portfolio-history-metrics">
        <div><small>ANNUALIZED VOLATILITY</small><strong>{percent(performance.weekly_risk_estimate.annualizedVolatilityPercent)}</strong></div>
        <div><small>DOWNSIDE DEVIATION</small><strong>{percent(performance.weekly_risk_estimate.annualizedDownsideDeviationPercent)}</strong></div>
        <div><small>NEGATIVE WEEKS</small><strong>{percent(performance.weekly_risk_estimate.negativeWeekFrequencyPercent)}</strong></div>
      </div><p className="muted tiny">{performance.weekly_risk_estimate.weeklyObservations}/13 exact weekly intervals. {performance.weekly_risk_estimate.status==="AVAILABLE_ESTIMATE"?"Historical estimate, not a forecast.":"Insufficient contiguous weekly evidence."}</p></>}
      <p className="muted tiny">{performance.rolling_methodology}</p>
    </section>}
    {performance.benchmark_risk_estimate&&<PortfolioBenchmarkRisk report={performance.benchmark_risk_estimate}/>}
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
