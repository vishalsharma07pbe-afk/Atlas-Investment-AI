import {useEffect,useState} from "react";
import FundHistoricalWatch from "./FundHistoricalWatch";

type Category="LARGE_CAP"|"MID_CAP"|"SMALL_CAP"|"FLEXI_CAP"|"INDEX";
type Pick={rank:number;score:number;atlas_research_rating:string;evidence_confidence:string;qualification_reason:string;key_risk:string;suitability:{status:string;flags:string[]};fund:{identifier:string;name:string;category:string;plan:string;nav:string|null;nav_date:string|null;returns_1y:number|null;returns_3y:number|null;returns_5y:number|null;riskometer:string|null;riskometer_date:string|null;benchmark:string|null}};
type Result={generated_at:string;methodology_version:string;category:Category;filters:{horizon_months:number;risk_tolerance:string};coverage:{name_matched_schemes:number;exact_direct_growth_schemes:number;official_category_verified:number;dated_nav_history_eligible:number;explicit_amfi_history_candidates?:number;portfolio_disclosures_eligible:number};top_performers:Pick[];growth_outlook:Pick[];suitability:{status:string;flags:string[]};blockers:string[];market_overview:{segment:string;status:string;benchmark:string|null;period:string|null;last_available_date:string|null;evidence:string[];blocker:string}[];recommendation_status:string;notice:string;snapshot_hash:string};

const categories:[Category,string][]=[["LARGE_CAP","Large Cap"],["MID_CAP","Mid Cap"],["SMALL_CAP","Small Cap"],["FLEXI_CAP","Flexi Cap"],["INDEX","Index Funds"]];
const words=(value:string)=>value.replace(/_/g," ").toLowerCase().replace(/^./,c=>c.toUpperCase());

function PickList({title,subtitle,items}:{title:string;subtitle:string;items:Pick[]}){
  return <section className="mf-ranking-list"><header><div><h3>{title}</h3><p>{subtitle}</p></div><span>{items.length}/5 qualified</span></header>
    {items.length?<div className="mf-picks">{items.map(item=><article key={item.fund.identifier}><b>#{item.rank}</b><div><h4>{item.fund.name}</h4><p>{item.fund.plan} · {item.fund.benchmark??item.fund.category}</p></div><dl><div><dt>ATLAS rating</dt><dd>{item.atlas_research_rating}</dd></div><div><dt>Confidence</dt><dd>{item.evidence_confidence}</dd></div><div><dt>1Y / 3Y / 5Y</dt><dd>{[item.fund.returns_1y,item.fund.returns_3y,item.fund.returns_5y].map(x=>x===null?"—":x.toFixed(2)+"%").join(" / ")}</dd></div></dl><p><strong>Why:</strong> {item.qualification_reason}<br/><strong>Risk:</strong> {item.key_risk}</p></article>)}</div>
    :<div className="mf-ranking-empty"><strong>No fund currently qualifies</strong><p>ATLAS found discovery candidates, but none has enough verified evidence for this list. This is safer than ranking incomplete records.</p></div>}
  </section>;
}

export default function MutualFundResearchDashboard({onExplore}:{onExplore:()=>void}){
  const [category,setCategory]=useState<Category>("LARGE_CAP");
  const [horizon,setHorizon]=useState(60);
  const [risk,setRisk]=useState("MODERATE");
  const [data,setData]=useState<Result|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();let active=true,pending=false;setLoading(true);setError("");setData(null);
    function load(){if(pending)return;pending=true;fetch(`/intelligence/api/v1/intelligence/mutual-funds/recommendations?category=${category}&horizon_months=${horizon}&risk_tolerance=${risk}`,{signal:controller.signal,cache:"no-store"})
      .then(r=>{if(!r.ok)throw Error("Research snapshot unavailable");return r.json()}).then(result=>{if(active){setData(result);setError("");}})
      .catch(e=>{if(active&&e.name!=="AbortError"){setError(e.message);setData(null)}}).finally(()=>{pending=false;if(active)setLoading(false)});}
    load();const timer=window.setInterval(load,60000);
    return()=>{active=false;controller.abort();window.clearInterval(timer);};},[category,horizon,risk]);
  return <section className="mf-research-dashboard">
    <header className="mf-research-hero"><div><small className="section-kicker">VERIFIED FUND RESEARCH</small><h2>Research picks, only when evidence qualifies</h2><p>Historical strength and forward growth use separate gates. Strong recent returns alone cannot enter Growth Outlook.</p></div><button className="secondary" type="button" onClick={onExplore}>Explore all funds</button></header>
    <div className="mf-category-tabs" role="tablist" aria-label="Mutual fund categories">{categories.map(([id,label])=><button key={id} type="button" role="tab" aria-selected={category===id} onClick={()=>setCategory(id)}>{label}</button>)}</div>
    <FundHistoricalWatch category={category}/>
    <div className="mf-research-filters"><label>Investment horizon<select value={horizon} onChange={e=>setHorizon(Number(e.target.value))}><option value={36}>3 years — near-term goal</option><option value={60}>5 years</option><option value={84}>7 years</option><option value={120}>10 years</option></select></label><label>Risk tolerance<select value={risk} onChange={e=>setRisk(e.target.value)}><option value="LOW">Low</option><option value="MODERATE">Moderate</option><option value="HIGH">High</option></select></label></div>
    {loading&&<div className="mf-research-state" role="status">Checking category evidence…</div>}
    {error&&<div className="mf-attention" role="alert"><span>!</span><div><strong>Research unavailable</strong><p>{error}</p></div></div>}
    {!loading&&data&&!error&&data.category===category&&<>
      {data.suitability.flags.length>0&&<div className="mf-horizon-warning"><strong>{horizon===36?"A 36-month goal needs capital protection":"Suitability warning"}</strong><p>{data.suitability.flags.map(words).join(" · ")}. Volatile equity funds can be unsuitable for money required on this date even when their long-term record is strong.</p></div>}
      <div className="mf-market-overview"><header><h3>Market context</h3><p>Trend, fund performance and forward outlook remain separate evidence.</p></header><div>{data.market_overview.map(item=><article key={item.segment}><span>{words(item.segment)}</span><strong>{words(item.status)}</strong><small>{item.benchmark??"Benchmark feed not connected"}</small></article>)}</div></div>
      <div className="mf-coverage-strip"><div><span>Name-matched universe</span><strong>{data.coverage.name_matched_schemes}</strong></div><div><span>Direct Growth candidates</span><strong>{data.coverage.exact_direct_growth_schemes}</strong></div><div><span>AMFI history eligible (sample)</span><strong>{data.coverage.dated_nav_history_eligible}</strong></div>{data.coverage.explicit_amfi_history_candidates!==undefined&&<div><span>Explicit AMFI Direct Growth evidence (sample)</span><strong>{data.coverage.explicit_amfi_history_candidates}</strong></div>}<div><span>Forward evidence eligible</span><strong>{data.coverage.portfolio_disclosures_eligible}</strong></div></div>
      <div className="mf-ranking-grid"><PickList title="Top Performers" subtitle="Consistency, benchmark-relative returns and downside risk." items={data.top_performers}/><PickList title="Growth Outlook" subtitle="Current holdings, earnings, valuation, concentration and risks." items={data.growth_outlook}/></div>
      <details className="mf-research-method"><summary>Why are recommendations unavailable?</summary><p>{data.notice}</p><div>{data.blockers.map(b=><span key={b}>{words(b)}</span>)}</div><small>Methodology {data.methodology_version} · Snapshot {data.snapshot_hash.slice(0,12)}</small></details>
    </>}
  </section>;
}
