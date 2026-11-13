/** Date-only IPO event calendar derived from already opened notification details. */
export type CalendarAlert={id:string;category:string;event_date:string|null;published_at:string};
const IPO_CATEGORIES=new Set(["IPO_UPCOMING","IPO_SUBSCRIPTION","IPO_ALLOTMENT"]);
export function upcomingIpoEvents<T extends CalendarAlert>(alerts:T[],today:string,days=30):T[]{
  const start=Date.parse(today+"T00:00:00Z");
  if(!Number.isFinite(start)||days<1||days>365)throw Error("Invalid calendar range");
  const end=start+days*86400000;
  return alerts.filter(a=>{
    if(!IPO_CATEGORIES.has(a.category)||!a.event_date||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(a.event_date))return false;
    const time=Date.parse(a.event_date+"T00:00:00Z");
    return Number.isFinite(time)&&new Date(time).toISOString().slice(0,10)===a.event_date&&time>=start&&time<=end;
  }).sort((a,b)=>a.event_date!.localeCompare(b.event_date!)||b.published_at.localeCompare(a.published_at));
}
export function indiaDateToday(now=new Date()):string{
  return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Kolkata",year:"numeric",month:"2-digit",day:"2-digit"}).format(now);
}
