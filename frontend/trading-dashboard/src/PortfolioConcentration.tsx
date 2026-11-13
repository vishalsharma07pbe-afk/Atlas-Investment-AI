import React,{useState} from "react";
type Key="max_single_holding_percent"|"max_equity_percent"|"max_mutual_fund_percent"|"max_top_three_percent";
type Breach={type:string;label:string;actual_percent:string;limit_percent:string};
type Holding={id:number;symbol:string;asset_type:string;recorded_value:string;weight_percent:string};
type Exposure={asset_type:string;recorded_value:string;weight_percent:string;limit_percent:string};
type Report={status:string;recorded_value:string;holdings:Holding[];exposures:Exposure[];breaches:Breach[];unpriced_holdings:{id:number;symbol:string}[];top_three_percent?:string;notice:string};
const labels:{key:Key;label:string;min:number}[]=[
  {key:"max_single_holding_percent",label:"Max individual holding (%)",min:1},
  {key:"max_equity_percent",label:"Max equity exposure (%)",min:0},
  {key:"max_mutual_fund_percent",label:"Max mutual fund exposure (%)",min:0},
  {key:"max_top_three_percent",label:"Max top-three holdings (%)",min:1}];
const initial:Record<Key,string>={max_single_holding_percent:"25",max_equity_percent:"80",max_mutual_fund_percent:"80",max_top_three_percent:"60"};
const inr=(n:string)=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(Number(n));
export default function PortfolioConcentration({revision}:{revision:number}){
  const [limits,setLimits]=useState(initial);
  const [report,setReport]=useState<Report|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [lastRevision,setLastRevision]=useState(revision);
  if(lastRevision!==revision){setLastRevision(revision);setReport(null);}
  async function inspect(e:React.FormEvent){
    e.preventDefault();setError("");setReport(null);
    if(labels.some(l=>limits[l.key].trim()===""||!Number.isFinite(Number(limits[l.key]))||
       Number(limits[l.key])<l.min||Number(limits[l.key])>100)){
      setError("Enter valid percentage thresholds from 0 to 100.");return;
    }
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/portfolio/concentration",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(limits)});
      if(!response.ok)throw Error("Concentration analysis unavailable");
      setReport(await response.json() as Report);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass" aria-label="Portfolio concentration risk limits">
    <div className="sectionhead"><div><small className="section-kicker">RISK LIMITS LAB</small><h2>Portfolio concentration & limits</h2></div><span className="tag">RECORDED PRICES ONLY</span></div>
    <p className="muted tiny">Inspect concentration against your thresholds. Unpriced holdings are excluded; mutual fund underlying exposures are not available.</p>
    <form onSubmit={inspect}>
      {labels.map(l=><label key={l.key}>{l.label}<input type="number" aria-label={l.label} required min={l.min} max="100" step="0.01" value={limits[l.key]} onChange={e=>setLimits(old=>({...old,[l.key]:e.target.value}))}/></label>)}
      <button className="primary" type="submit" disabled={loading}>{loading?"Checking…":"Check concentration"}</button>
    </form>
    {error&&<p role="alert">{error}</p>}
    {report&&<div aria-label="Concentration results">
      <p><strong>{report.status}</strong> · Priced recorded value: {inr(report.recorded_value)} · Threshold breaches: <strong>{report.breaches.length}</strong></p>
      {report.unpriced_holdings.length>0&&<p role="status">Missing recorded prices: {report.unpriced_holdings.map(h=>h.symbol).join(", ")}. Results cover priced holdings only.</p>}
      {report.breaches.length>0&&<div><h3>Threshold breaches</h3><ul>{report.breaches.map((b,i)=><li key={i}>{b.label}: {b.actual_percent}% exceeds your {b.limit_percent}% limit</li>)}</ul></div>}
      <div className="tablewrap"><table><thead><tr><th>HOLDING</th><th>ASSET TYPE</th><th>RECORDED VALUE</th><th>WEIGHT</th></tr></thead><tbody>
        {report.holdings.map(h=><tr key={h.id}><td>{h.symbol}</td><td>{h.asset_type}</td><td>{inr(h.recorded_value)}</td><td>{h.weight_percent}%</td></tr>)}
      </tbody></table></div>
      <p>Top three holdings: {report.top_three_percent??"N/A"}%</p>
      <p className="muted tiny">{report.notice}</p>
    </div>}
  </section>;
}
