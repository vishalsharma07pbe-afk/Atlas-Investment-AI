// Export ATLAS research only. No TradingView account, credential or data access.
type ExportRow={id:number;isin:string;symbol:string;exchange:string;as_of:string;status:string;
  adjustment_status?:string;strict_fip_evidence?:{status:string;adjustment_status?:string;calendar_status?:string;as_of?:string};
  governance_review?:{findings:string[]};company_venue_context?:{review_findings:string[]}};
type ExportReport={status:string;matched_count:number;qualification_eligible:false;items:ExportRow[]};
export function buildTradingViewExport(report:ExportReport|undefined,today:string){
  if(!report||report.status!=="JOINT_SCREEN_MATCHES"||report.qualification_eligible!==false||
     !Number.isSafeInteger(report.matched_count)||report.matched_count<1||!Array.isArray(report.items)||
     report.items.length!==Math.min(report.matched_count,10)||!/^\d{4}-\d{2}-\d{2}$/.test(today))return null;
  const companies=new Set<string>(),symbols=new Set<string>();let session:string|undefined;
  const now=Date.parse(today+"T00:00:00Z");
  for(const row of report.items){
    if(!row||!Number.isSafeInteger(row.id)||row.id<1||!/^INE[A-Z0-9]{9}$/.test(row.isin)||
       !["NSE","BSE"].includes(row.exchange)||!/^[A-Z0-9][A-Z0-9&._-]{0,49}$/.test(row.symbol)||
       row.status!=="SCREEN_MATCH_ONLY"||row.adjustment_status!=="ADJUSTED"||
       row.strict_fip_evidence?.status!=="FIP_PRICE_MATCH"||
       row.strict_fip_evidence.adjustment_status!=="ADJUSTED"||
       row.strict_fip_evidence.calendar_status!=="STORED_SESSIONS_MATCHED"||
       row.strict_fip_evidence.as_of!==row.as_of||
       row.governance_review?.findings?.length||row.company_venue_context?.review_findings?.length||
       !/^\d{4}-\d{2}-\d{2}$/.test(row.as_of))return null;
    const age=(now-Date.parse(row.as_of+"T00:00:00Z"))/86400000;
    if(!Number.isFinite(age)||age<1||age>4||session&&session!==row.as_of)return null;
    session=row.as_of;
    const symbol=row.exchange+":"+row.symbol;
    if(companies.has(row.isin)||symbols.has(symbol))return null;
    companies.add(row.isin);symbols.add(symbol);
  }
  return {filename:"TV-Suggestion-"+today+".txt",text:[...symbols].join(","),count:symbols.size,session};
}
export function indiaDate(now=new Date()){
 return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Kolkata",year:"numeric",month:"2-digit",day:"2-digit"}).format(now);
}
