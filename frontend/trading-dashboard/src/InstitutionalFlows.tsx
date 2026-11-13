import React,{useState} from "react";

type Row={trade_date:string;market:string;participant:string;net_crore_inr:string;direction:string;source_name:string;verification:string};
type Result={records:Row[];notice:string;independent_verification:boolean};

export default function InstitutionalFlows(){
  const [csv,setCsv]=useState("");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function analyze(){
    setError("");setResult(null);
    const lines=csv.trim().split(/\r?\n/).filter(Boolean);
    if(lines.length<2||lines.length>121){setError("Provide a header and 1–120 data rows.");return;}
    const expected="trade_date,market,participant,buy_crore_inr,sell_crore_inr,source_name";
    if(lines[0].trim()!==expected){setError("Header must be: "+expected);return;}
    const records=lines.slice(1).map(line=>{
      const cells=line.split(",").map(s=>s.trim());
      if(cells.length!==6)throw new Error("Each row must have exactly six fields (no embedded commas).");
      return Object.fromEntries(expected.split(",").map((key,i)=>[key,cells[i]]));
    });
    setLoading(true);
    try{
      const response=await fetch("/intelligence/api/v1/intelligence/institutional-flows/analyze",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({records})
      });
      if(!response.ok)throw new Error("Invalid flow records or service unavailable ("+response.status+").");
      setResult(await response.json());
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">INSTITUTIONAL FLOW RESEARCH</small><h2>FII / FPI / DII / Retail flows</h2></div><span className="tag">USER-SUPPLIED</span></div>
    <p className="muted tiny">Paste source-attributed CSV data to calculate net buying or selling in ₹ crore. No live exchange feed is connected. Never combine overlapping exchange and India-combined figures.</p>
    <textarea aria-label="Institutional flow CSV" rows={6} value={csv} onChange={e=>setCsv(e.target.value)}
      placeholder={"trade_date,market,participant,buy_crore_inr,sell_crore_inr,source_name\n2026-11-12,NSE,FII,100,120,Example source"}/>
    <div><button className="primary" disabled={loading} onClick={async()=>{
      try{await analyze();}catch(e){setError(String(e));}
    }}>{loading?"Analyzing…":"Analyze flow evidence"}</button></div>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<><p role="status" className="muted tiny">{result.notice}</p><div className="tablewrap"><table><thead><tr><th>DATE</th><th>MARKET</th><th>PARTICIPANT</th><th>NET ₹ CR</th><th>DIRECTION</th><th>SOURCE</th></tr></thead><tbody>{result.records.map((r,i)=><tr key={i}><td>{r.trade_date}</td><td>{r.market}</td><td>{r.participant}</td><td>{r.net_crore_inr}</td><td>{r.direction}</td><td>{r.source_name}</td></tr>)}</tbody></table></div></>}
  </section>;
}
