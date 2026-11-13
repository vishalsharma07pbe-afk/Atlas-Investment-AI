import React, {useEffect, useState} from "react";

type Scenario = {
  name:string;
  assumed_uniform_price_change_percent:string;
  stressed_value_of_priced_holdings:string;
  change_from_recorded_value:string;
  unrealized_pnl_vs_priced_cost:string;
};
type StressResponse = {
  status:string;
  price_source:string;
  recorded_value_priced_holdings:string;
  unpriced_holdings:{id:number;symbol:string}[];
  scenarios:Scenario[];
  notice:string;
};

const currency=(value:string)=>new Intl.NumberFormat("en-IN",{
  style:"currency",currency:"INR",maximumFractionDigits:2
}).format(Number(value));

export default function PortfolioStress({revision}:{revision:number}){
  const [result,setResult]=useState<StressResponse|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setLoading(true);
    setError("");
    fetch("/intelligence/api/v1/intelligence/portfolio/stress-scenarios",{signal:controller.signal})
      .then(async response=>{
        if(!response.ok)throw new Error("Stress analysis is unavailable.");
        return response.json() as Promise<StressResponse>;
      })
      .then(data=>{if(!controller.signal.aborted)setResult(data);})
      .catch(err=>{if(!controller.signal.aborted){setResult(null);setError(String(err));}})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[revision,retry]);

  return <section className="panel glass" aria-label="Portfolio stress scenarios">
    <div className="sectionhead"><div><small className="section-kicker">PORTFOLIO RISK LAB</small><h2>Illustrative stress scenarios</h2></div><span className="tag">NOT A FORECAST</span></div>
    <p className="muted tiny">Uniform hypothetical shocks to holdings with manually recorded prices. No live prices or probabilities are implied.</p>
    {loading?<p role="status">Loading scenario analysis…</p>:error?
      <div role="alert"><p>{error}</p><button className="secondary" onClick={()=>setRetry(value=>value+1)}>Retry</button></div>:
      result?<>
        <p>Recorded value of priced holdings: <strong>{currency(result.recorded_value_priced_holdings)}</strong></p>
        {result.unpriced_holdings.length>0&&<p role="status" className="muted">Partial coverage: {result.unpriced_holdings.length} holding(s) have no recorded price and are excluded from these calculations.</p>}
        <div className="tablewrap"><table><thead><tr><th>SCENARIO</th><th>ASSUMED MOVE</th><th>STRESSED VALUE</th><th>CHANGE</th></tr></thead><tbody>
          {result.scenarios.map(s=><tr key={s.name}><td>{s.name.replace(/_/g," ")}</td><td>{s.assumed_uniform_price_change_percent}%</td><td>{currency(s.stressed_value_of_priced_holdings)}</td><td>{currency(s.change_from_recorded_value)}</td></tr>)}
        </tbody></table></div>
        <p className="muted tiny">{result.notice}</p>
      </>:null}
  </section>;
}
