import React,{useState} from "react";
type Details={missing_scheme_codes:string[];unexpected_scheme_codes:string[];duplicate_scheme_codes:string[];future_scheme_codes:string[];stale_scheme_codes:string[];matched_as_of_dates:string[];expected_count:number;received_count:number};
type Result={status:"BLOCKED"|"READY_FOR_MANUAL_REVIEW";blockers:string[];details:Details;source:{verification:string};stored:boolean;refresh_executed:boolean;notice:string};
export default function NavRefreshPreflight(){
 const [source,setSource]=useState("");const [authorized,setAuthorized]=useState(false);
 const [expected,setExpected]=useState("");const [records,setRecords]=useState("[]");
 const [result,setResult]=useState<Result|null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 async function validate(){
  setLoading(true);setError("");setResult(null);
  try{
   const codes=expected.split(/[\s,]+/).map(s=>s.trim()).filter(Boolean);
   if(!codes.length||codes.some(s=>!/^\d{1,12}$/.test(s)))throw Error("Enter numeric scheme codes separated by commas or whitespace.");
   const parsed=JSON.parse(records);
   if(!Array.isArray(parsed))throw Error("NAV records must be a JSON array.");
   const response=await fetch("/intelligence/api/v1/intelligence/mutual-funds/nav-refresh-preflight",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({source_name:source,source_authorized:authorized,expected_scheme_codes:codes,records:parsed})
   });
   if(!response.ok)throw Error("Preflight input rejected. Check source, scheme codes and NAV records.");
   setResult(await response.json());
  }catch(e){setError(e instanceof Error?e.message:"Validation unavailable");}
  finally{setLoading(false);}
 }
 return <section className="panel glass" aria-label="NAV refresh batch preflight">
  <div className="sectionhead"><div><small className="section-kicker">NAV REFRESH · PREFLIGHT ONLY</small><h2>Validate a NAV batch</h2></div><span className="tag">READ ONLY</span></div>
  <p className="muted tiny">Validate a caller-supplied NAV batch before manual review. No data is fetched, stored or applied to holdings.</p>
  <label htmlFor="preflight-source">Source name</label><input id="preflight-source" value={source} onChange={e=>setSource(e.target.value)} placeholder="Authorized local NAV export"/>
  <label htmlFor="preflight-expected">Expected scheme codes</label><textarea id="preflight-expected" rows={2} style={{width:"100%"}} value={expected} onChange={e=>setExpected(e.target.value)} placeholder="12345, 67890"/>
  <label htmlFor="preflight-records">NAV records JSON</label><textarea id="preflight-records" rows={5} style={{width:"100%"}} value={records} onChange={e=>setRecords(e.target.value)} placeholder={'[{"scheme_code":"12345","nav":"10.5","as_of":"2026-11-13"}]'}/>
  <label style={{display:"block",margin:"12px 0"}}><input type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/> I confirm I am authorized to use these supplied NAV records.</label>
  <button className="secondary" disabled={loading} onClick={validate}>{loading?"Checking…":"Validate batch"}</button>
  {error&&<p role="alert">{error}</p>}
  {result&&<div role="status">
   <h3>{result.status==="BLOCKED"?"Blocked — review issues":"Ready for manual review only"}</h3>
   <p>{result.details.received_count} supplied records · {result.details.expected_count} expected schemes</p>
   {result.blockers.length>0&&<ul>{result.blockers.map(code=><li key={code}>{code.replace(/_/g," ")}</li>)}</ul>}
   <p className="muted tiny">Missing: {result.details.missing_scheme_codes.join(", ")||"none"} · Unexpected: {result.details.unexpected_scheme_codes.join(", ")||"none"} · Duplicate: {result.details.duplicate_scheme_codes.join(", ")||"none"}</p>
   <p className="muted tiny">Future dates: {result.details.future_scheme_codes.join(", ")||"none"} · Stale dates: {result.details.stale_scheme_codes.join(", ")||"none"} · Valuation dates: {result.details.matched_as_of_dates.join(", ")||"none"}</p>
   <p className="muted tiny">{result.notice}</p>
  </div>}
 </section>;
}
