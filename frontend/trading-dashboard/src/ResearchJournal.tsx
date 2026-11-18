import React,{useEffect,useState} from "react";
type Status="IDEA"|"RESEARCHING"|"MONITORING"|"CLOSED";
type Entry={id:string;symbol:string;thesis:string;evidence:string;risks:string;source_url:string;status:Status;updated_at:string};
type Form={symbol:string;thesis:string;evidence:string;risks:string;source_url:string;status:Status};
const API="/intelligence/api/v1/intelligence/journal";
const blank:Form={symbol:"",thesis:"",evidence:"",risks:"",source_url:"",status:"IDEA"};
const statuses:Status[]=["IDEA","RESEARCHING","MONITORING","CLOSED"];
export default function ResearchJournal(){
  const [entries,setEntries]=useState<Entry[]>([]);
  const [form,setForm]=useState<Form>(blank);
  const [editing,setEditing]=useState<string|null>(null);
  const [filter,setFilter]=useState("ALL");
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{const controller=new AbortController();
    fetch(API,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error("Journal unavailable");return r.json();})
      .then((d:{entries:Entry[]})=>{if(!controller.signal.aborted)setEntries(d.entries);})
      .catch(e=>{if(!controller.signal.aborted)setError(String(e));});
    return()=>controller.abort();
  },[refresh]);
  async function save(e:React.FormEvent){
    e.preventDefault();setError("");setLoading(true);
    try{
      const response=await fetch(editing?`${API}/${editing}`:API,{
        method:editing?"PUT":"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});
      if(!response.ok)throw Error("Could not save journal entry");
      setEditing(null);setForm(blank);setRefresh(v=>v+1);
    }catch(e){setError(String(e));}finally{setLoading(false);}
  }
  async function remove(id:string){
    if(!window.confirm("Delete this research journal entry?"))return;
    setError("");
    try{const response=await fetch(`${API}/${id}`,{method:"DELETE"});
      if(!response.ok)throw Error("Could not delete entry");
      setRefresh(v=>v+1);
    }catch(e){setError(String(e));}
  }
  return <section className="panel glass" aria-label="Investment research journal">
    <div className="sectionhead"><div><small className="section-kicker">RESEARCH WORKSPACE</small><h2>Investment research journal</h2></div><span className="tag">LOCAL NOTES</span></div>
    <p className="muted tiny">Track ideas, evidence and risks. Notes are your own research, not verified market facts or investment recommendations.</p>
    <form onSubmit={save} className="research-journal-form">
      <label>Symbol<input aria-label="Journal symbol" required maxLength={40} pattern="[A-Za-z0-9._&-]+" value={form.symbol} onChange={e=>setForm({...form,symbol:e.target.value.toUpperCase()})}/></label>
      <label>Research status<select aria-label="Journal status" value={form.status} onChange={e=>setForm({...form,status:e.target.value as Status})}>{statuses.map(s=><option key={s}>{s}</option>)}</select></label>
      <label className="journal-wide">Thesis<textarea aria-label="Journal thesis" required minLength={3} maxLength={2000} value={form.thesis} onChange={e=>setForm({...form,thesis:e.target.value})}/></label>
      <label>Evidence / source notes<textarea aria-label="Journal evidence" maxLength={3000} value={form.evidence} onChange={e=>setForm({...form,evidence:e.target.value})}/></label>
      <label>Risks<textarea aria-label="Journal risks" maxLength={2000} value={form.risks} onChange={e=>setForm({...form,risks:e.target.value})}/></label>
      <label className="journal-wide journal-source">Source reference (text)<input aria-label="Journal source" maxLength={500} value={form.source_url} onChange={e=>setForm({...form,source_url:e.target.value})}/></label>
      <div className="compact-form-actions"><button className="primary" type="submit" disabled={loading}>{loading?"Saving…":editing?"Update research note":"Save research note"}</button>
      {editing&&<button type="button" className="secondary" onClick={()=>{setEditing(null);setForm(blank);}}>Cancel edit</button>}</div>
    </form>
    {error&&<p role="alert">{error}</p>}
    <label className="journal-filter">Filter research notes<select aria-label="Filter journal status" value={filter} onChange={e=>setFilter(e.target.value)}><option>ALL</option>{statuses.map(s=><option key={s}>{s}</option>)}</select></label>
    <div className="tablewrap"><table><thead><tr><th>SYMBOL</th><th>THESIS / EVIDENCE / RISKS</th><th>STATUS</th><th>ACTIONS</th></tr></thead><tbody>
      {entries.filter(e=>filter==="ALL"||e.status===filter).map(entry=><tr key={entry.id}><td>{entry.symbol}</td>
        <td><strong>{entry.thesis}</strong><p>{entry.evidence}</p><p>{entry.risks}</p><small>{entry.source_url}</small></td><td>{entry.status}</td>
        <td><button type="button" className="secondary" onClick={()=>{setEditing(entry.id);setForm({symbol:entry.symbol,thesis:entry.thesis,evidence:entry.evidence,risks:entry.risks,source_url:entry.source_url,status:entry.status});}}>Edit</button>
        <button type="button" className="secondary" onClick={()=>remove(entry.id)}>Delete</button></td></tr>)}
    </tbody></table></div>
    <p className="muted tiny">Stored in a local journal file. Back up your notes; do not store credentials or private broker tokens.</p>
  </section>;
}
