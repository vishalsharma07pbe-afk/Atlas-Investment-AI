import {useState} from "react";
import type {FundHolding} from "./MutualFundHoldings";
type RiskResult={status:string;total_positions:number;priced_positions:number;unpriced_positions:number;
 largest_weight_pct:string|null;top_three_weight_pct:string|null;hhi:string|null;effective_holdings:string|null;
 weights:{holding_id:number;label:string;recorded_value:string;weight_pct:string}[];
 diagnostics:{code:string;severity:string;message:string}[];unavailable_metrics:string[];notice:string};
export default function MutualFundRisk({holdings}:{holdings:FundHolding[]}){
 const [result,setResult]=useState<RiskResult|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false);
 const funds=holdings.filter(h=>h.asset_type==="MUTUAL_FUND");
 async function inspect(){
  setLoading(true);setError("");setResult(null);
  try{
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/portfolio-risk",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({positions:funds.map(h=>({holding_id:h.id,label:h.symbol,recorded_value:h.market_value}))})
   });
   if(!response.ok)throw Error("Unable to calculate fund concentration from recorded holdings.");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Risk analysis unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="Mutual fund concentration analysis">
  <div className="sectionhead"><div><small className="section-kicker">FUND ALLOCATION · READ ONLY</small><h2>Concentration &amp; diversification diagnostics</h2></div><span className="tag">RECORDED VALUES</span></div>
  <p className="muted tiny">Measure fund-position concentration using saved recorded values. Underlying holdings overlap and market risk cannot be calculated without verified data.</p>
  <button className="secondary" disabled={loading||funds.length===0} onClick={inspect}>{loading?"Analyzing…":"Analyze fund concentration"}</button>
  {!funds.length&&<p className="muted tiny">Add mutual fund holdings to My Portfolio to analyze concentration.</p>}
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   {result.diagnostics.map(d=><p className="notice" key={d.code}>{d.severity}: {d.message}</p>)}
   <div className="stats">
    <div className="stat glass"><small>LARGEST FUND WEIGHT</small><strong>{result.largest_weight_pct===null?"—":result.largest_weight_pct+"%"}</strong></div>
    <div className="stat glass"><small>TOP 3 FUND WEIGHT</small><strong>{result.top_three_weight_pct===null?"—":result.top_three_weight_pct+"%"}</strong></div>
    <div className="stat glass"><small>CONCENTRATION HHI</small><strong>{result.hhi??"—"}</strong></div>
    <div className="stat glass"><small>EFFECTIVE FUND POSITIONS</small><strong>{result.effective_holdings??"—"}</strong></div>
   </div>
   <p>{result.priced_positions} priced / {result.total_positions} total fund positions</p>
   <div className="tablewrap"><table><thead><tr><th>Fund</th><th>Recorded value (₹)</th><th>Weight (%)</th></tr></thead><tbody>
    {result.weights.map(row=><tr key={row.holding_id}><td>{row.label}</td><td>{row.recorded_value}</td><td>{row.weight_pct}</td></tr>)}
    {!result.weights.length&&<tr><td colSpan={3}>No positive recorded fund values.</td></tr>}
   </tbody></table></div>
   <p className="muted tiny">Unavailable without verified data: {result.unavailable_metrics.join(", ").replace(/_/g," ")}.</p>
   <p className="muted tiny">{result.notice}</p>
  </div>}
 </section>;
}
