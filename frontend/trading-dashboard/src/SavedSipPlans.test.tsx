/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import SavedSipPlans from "./SavedSipPlans";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

describe("SavedSipPlans",()=>{
 it("searches the fund catalog and persists a selected SIP",async()=>{
  const fetcher=vi.spyOn(globalThis,"fetch").mockImplementation(async(input,init)=>{
   const url=String(input);
   if(url.includes("mutual-funds/search"))return new Response(JSON.stringify([{scheme_code:12345,scheme_name:"HDFC Balanced Advantage Fund",nav:510.2,nav_date:"2026-11-23"}]),{status:200,headers:{"Content-Type":"application/json"}});
   if(url.endsWith("/sip-plans")&&init?.method==="POST")return new Response(JSON.stringify({saved:true,id:"plan-1"}),{status:200,headers:{"Content-Type":"application/json"}});
   if(url.endsWith("/sip-plans"))return new Response(JSON.stringify([]),{status:200,headers:{"Content-Type":"application/json"}});
   return new Response("",{status:404});
  });
  render(<SavedSipPlans/>);
  fireEvent.change(screen.getByPlaceholderText(/Start typing HDFC/),{target:{value:"HDFC"}});
  fireEvent.click(await screen.findByRole("button",{name:/HDFC Balanced Advantage Fund/}));
  fireEvent.click(screen.getByRole("button",{name:"Save SIP"}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([,init])=>init?.method==="POST")).toBe(true));
  const request=fetcher.mock.calls.find(([,init])=>init?.method==="POST");
  expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({schemeCode:12345,monthlyAmount:5000,active:true});
  expect(await screen.findByText(/SIP plan saved/)).toBeTruthy();
 });
});
