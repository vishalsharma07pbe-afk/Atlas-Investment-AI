import {useState} from "react";

type Backtest={status:string;as_of?:string;candle_count?:number;required_candles?:number;observed_candles?:number;strategy_total_return_percent?:number;buy_hold_return_percent?:number;max_drawdown_percent?:number;closed_trade_count?:number;open_position_at_end?:boolean;notice?:string;trades?:{entry_date:string;exit_date:string;return_percent:number}[]};

export default function BacktestPanel({instrumentId}:{instrumentId:number}){
  const [fast,setFast]=useState(10),[slow,setSlow]=useState(30);
  const [result,setResult]=useState<Backtest|null>(null);
  const [loading,setLoading]=useState(false),[error,setError]=useState("");
  async function run(){
    setResult(null);setError("");
    if(fast>=slow){setError("Fast SMA must be smaller than slow SMA.");return;}
    setLoading(true);
    try{
      const params=new URLSearchParams({fast:String(fast),slow:String(slow)});
      const response=await fetch(`/intelligence/api/v1/intelligence/backtest/${instrumentId}?${params}`);
      if(!response.ok)throw Error("Backtest unavailable or invalid daily candles.");
      setResult(await response.json());
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">HISTORICAL SIMULATION</small><h2>Daily SMA strategy backtest</h2></div><span className="tag">NOT PREDICTIVE</span></div>
    <p className="muted tiny">Long-only SMA crossover, next-day open fills. Assumes 10 bps fees + 5 bps slippage per transaction. Uses stored daily candles only, never live trading.</p>
    <div className="searchbar">
      <label>Fast SMA <input aria-label="Fast SMA" type="number" min={2} max={199} value={fast} onChange={e=>setFast(Number(e.target.value))}/></label>
      <label>Slow SMA <input aria-label="Slow SMA" type="number" min={3} max={200} value={slow} onChange={e=>setSlow(Number(e.target.value))}/></label>
      <button className="primary" disabled={loading} onClick={run}>{loading?"Simulating…":"Run backtest"}</button>
    </div>
    {error&&<p role="alert" className="error">{error}</p>}
    {result?.status==="INSUFFICIENT_HISTORY"&&<p role="status">Insufficient data: need {result.required_candles} candles, found {result.observed_candles}.</p>}
    {result?.status==="HISTORICAL_SIMULATION_ONLY"&&<>
      <div className="stats">
        <div className="stat glass"><small>STRATEGY RETURN</small><strong>{result.strategy_total_return_percent}%</strong></div>
        <div className="stat glass"><small>BUY &amp; HOLD</small><strong>{result.buy_hold_return_percent}%</strong></div>
        <div className="stat glass"><small>MAX DRAWDOWN</small><strong>{result.max_drawdown_percent}%</strong></div>
        <div className="stat glass"><small>CLOSED TRADES</small><strong>{result.closed_trade_count}</strong></div>
      </div>
      <p className="muted tiny">Through {result.as_of} · {result.candle_count} daily candles · Open position at end: {result.open_position_at_end?"Yes":"No"}.</p>
      <div className="tablewrap"><table><thead><tr><th>ENTRY</th><th>EXIT</th><th>RETURN</th></tr></thead><tbody>
        {result.trades?.map((t,i)=><tr key={i}><td>{t.entry_date}</td><td>{t.exit_date}</td><td>{t.return_percent}%</td></tr>)}
        {!result.trades?.length&&<tr><td colSpan={3} className="empty">No completed trades in the selected period.</td></tr>}
      </tbody></table></div>
      <p className="muted tiny">{result.notice}</p>
    </>}
  </section>;
}
