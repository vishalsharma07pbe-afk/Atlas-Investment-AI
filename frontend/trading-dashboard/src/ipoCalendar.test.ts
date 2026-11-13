import {describe,expect,it} from "vitest";
import {indiaDateToday,upcomingIpoEvents} from "./ipoCalendar";
const alert=(id:string,category:string,event_date:string|null,published_at="2026-11-13T00:00:00Z")=>({id,category,event_date,published_at});
describe("IPO calendar",()=>{
  it("includes today's events and day 30, sorted by event date",()=>{
    const events=[alert("late","IPO_ALLOTMENT","2026-12-13"),alert("other","MARKET_EVENT","2026-11-15"),
      alert("past","IPO_UPCOMING","2026-11-12"),alert("early","IPO_UPCOMING","2026-11-13"),
      alert("future","IPO_UPCOMING","2026-12-14")];
    expect(upcomingIpoEvents(events,"2026-11-13").map(x=>x.id)).toEqual(["early","late"]);
  });
  it("rejects malformed dates and undated alerts",()=>{
    const events=[alert("invalid","IPO_UPCOMING","2026-02-30"),alert("none","IPO_UPCOMING",null),
      alert("valid","IPO_SUBSCRIPTION","2026-02-28")];
    expect(upcomingIpoEvents(events,"2026-02-01").map(x=>x.id)).toEqual(["valid"]);
  });
  it("uses Indian date even across UTC midnight",()=>{
    expect(indiaDateToday(new Date("2026-11-13T20:00:00Z"))).toBe("2026-11-14");
  });
});
