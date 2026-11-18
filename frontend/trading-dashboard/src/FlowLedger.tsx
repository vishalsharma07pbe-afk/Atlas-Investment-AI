import {useEffect,useState} from "react";

type Row={trade_date:string;market:string;participant:string;buy_crore_inr:string;sell_crore_inr:string;net_crore_inr:string;source_name:string;source_url:string|null;verification:string;freshness:string;age_days:number};
type Ledger={records:Row[];total:number;notice:string;live_feed_connected:boolean};
const API="/intelligence/api/v1/intelligence/institutional-flows/ledger";
const HEADER="trade_date,market,participant,buy_crore_inr,sell_crore_inr,source_name";

export default function FlowLedger(){
  const [csv,setCsv]=useState("");
  const [ledger,setLedger]=useState<Ledger|null>(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const [version,setVersion]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    fetch(API+"?limit=100",{signal:controller.signal}).then(r=>{if(!r.ok)throw Error("Flow ledger unavailable");return r.json()})
      .then(setLedger).catch(e=>{if(e.name!=="AbortError")setMessage("Could not load flow ledger")});
    return ()=>controller.abort();
  },[version]);
  async function save(){
    setMessage("");
    try{
      const lines=csv.trim().split(/\r?\n/).filter(Boolean);
      if(lines.length<2||lines.length>121||lines[0].trim()!==HEADER)throw Error("Use the exact six-column header and 1–120 rows.");
      const fields=HEADER.split(",");
      const records=lines.slice(1).map(line=>{
        const values=line.split(",").map(s=>s.trim());
        if(values.length!==6)throw Error("Rows must have exactly six comma-free fields.");
        return Object.fromEntries(fields.map((f,i)=>[f,values[i]]));
      });
      setBusy(true);
      const response=await fetch(API,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({records})});
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"Import rejected");
      setMessage("Saved "+data.inserted+" new records; "+data.unchanged+" unchanged.");
      setVersion(v=>v+1);
    }catch(e){setMessage(e instanceof Error?e.message:"Import failed")}
    finally{setBusy(false)}
  }
  return <section className="panel glass" aria-label="Institutional flow evidence ledger">
    <div className="sectionhead"><div><small className="section-kicker">INSTITUTIONAL EVIDENCE</small><h2>Persistent FII / DII evidence ledger</h2></div><span className="tag">NOT LIVE</span></div>
    <p>Save source-attributed flow figures locally. Conflicting values for the same date, market and participant are rejected; records are never silently replaced. Freshness is based on calendar days, not exchange trading days.</p>
    <label className="field field-full">Flow CSV<textarea className="editor" aria-label="Flow ledger CSV" rows={5} value={csv} onChange={e=>setCsv(e.target.value)} placeholder={HEADER+"\n2026-11-12,NSE,FII,100,120,Example source"}/></label>
    <button className="primary" disabled={busy} onClick={()=>void save()}>{busy?"Saving…":"Save evidence"}</button>
    {message&&<p role="status">{message}</p>}
    <p>{ledger?.total??"—"} saved records. No automatic licensed feed or independent verification.</p>
    <div className="tablewrap"><table><thead><tr><th>Date</th><th>Market</th><th>Participant</th><th>Net ₹ crore</th><th>Age</th><th>Source</th></tr></thead><tbody>
      {ledger?.records.map(r=><tr key={r.trade_date+"-"+r.market+"-"+r.participant}><td>{r.trade_date}</td><td>{r.market}</td><td>{r.participant}</td><td>{r.net_crore_inr}</td><td>{r.age_days} days ({r.freshness})</td><td>{r.source_name}</td></tr>)}
      {!ledger?.records.length&&<tr><td colSpan={6}>No saved institutional flow evidence yet.</td></tr>}
    </tbody></table></div>
  </section>;
}
