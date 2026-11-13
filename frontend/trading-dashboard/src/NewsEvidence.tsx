import React,{useState} from "react";

type Event={headline:string;source_name:string;source_url:string;published_at:string;geography:string;event_type:string;sentiment:string;freshness:string;age_hours:number};
type Result={events:Event[];event_count:number;fresh_count:number;notice:string};

export default function NewsEvidence(){
  const [headline,setHeadline]=useState("");
  const [source,setSource]=useState("");
  const [url,setUrl]=useState("");
  const [published,setPublished]=useState("");
  const [geography,setGeography]=useState("GLOBAL");
  const [eventType,setEventType]=useState("MACRO");
  const [sentiment,setSentiment]=useState("UNKNOWN");
  const [result,setResult]=useState<Result|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(false);
  async function analyze(e:React.FormEvent){
    e.preventDefault();setError("");setResult(null);setLoading(true);
    try{
      const timestamp=new Date(published);
      if(!Number.isFinite(timestamp.getTime()))throw Error("Enter a valid publication time.");
      const response=await fetch("/intelligence/api/v1/intelligence/news/analyze",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({events:[{
          headline,source_name:source,source_url:url,published_at:timestamp.toISOString(),
          geography,event_type:eventType,sentiment,sentiment_method:"USER_LABELLED"
        }],max_age_hours:72})
      });
      if(!response.ok)throw Error("News evidence rejected or service unavailable ("+response.status+").");
      setResult(await response.json());
    }catch(err){setError(String(err));}finally{setLoading(false);}
  }
  return <section className="panel glass">
    <div className="sectionhead"><div><small className="section-kicker">GLOBAL NEWS RESEARCH</small><h2>News event evidence</h2></div><span className="tag">USER-SUPPLIED</span></div>
    <p className="muted tiny">Enter an article and your own event and sentiment labels. ATLAS checks its age against a 72-hour window; it does not retrieve, verify or classify news automatically.</p>
    <form className="form" onSubmit={analyze}>
      <input aria-label="News headline" placeholder="Headline" minLength={8} maxLength={300} required value={headline} onChange={e=>setHeadline(e.target.value)}/>
      <input aria-label="Publisher" placeholder="Publisher" required minLength={3} value={source} onChange={e=>setSource(e.target.value)}/>
      <input aria-label="Article URL" type="url" placeholder="https://publisher.example/article" required value={url} onChange={e=>setUrl(e.target.value)}/>
      <label className="muted tiny">Publication date and time <input aria-label="Publication date and time" type="datetime-local" required value={published} onChange={e=>setPublished(e.target.value)}/></label>
      <select aria-label="News geography" value={geography} onChange={e=>setGeography(e.target.value)}>{["GLOBAL","INDIA","US","EUROPE","ASIA_OTHER","OTHER"].map(v=><option key={v}>{v}</option>)}</select>
      <select aria-label="News event type" value={eventType} onChange={e=>setEventType(e.target.value)}>{["MACRO","EARNINGS","REGULATORY","MERGER","MANAGEMENT","PRODUCT","MARKET_STRUCTURE","OTHER"].map(v=><option key={v}>{v}</option>)}</select>
      <select aria-label="User sentiment label" value={sentiment} onChange={e=>setSentiment(e.target.value)}>{["UNKNOWN","POSITIVE","NEGATIVE","MIXED","NEUTRAL"].map(v=><option key={v}>{v}</option>)}</select>
      <button className="primary" disabled={loading}>{loading?"Analyzing…":"Check news evidence"}</button>
    </form>
    {error&&<p role="alert" className="error">{error}</p>}
    {result&&<><p role="status" className="muted tiny">{result.notice} Fresh: {result.fresh_count}/{result.event_count}.</p><div className="tablewrap"><table><thead><tr><th>HEADLINE</th><th>PUBLISHER</th><th>DATE</th><th>EVENT</th><th>SENTIMENT</th><th>FRESHNESS</th></tr></thead><tbody>
      {result.events.map((item,i)=><tr key={i}><td><a href={item.source_url} target="_blank" rel="noopener noreferrer">{item.headline}</a></td><td>{item.source_name}</td><td>{item.published_at}</td><td>{item.event_type}</td><td>{item.sentiment}</td><td>{item.freshness}</td></tr>)}
    </tbody></table></div></>}
  </section>;
}
