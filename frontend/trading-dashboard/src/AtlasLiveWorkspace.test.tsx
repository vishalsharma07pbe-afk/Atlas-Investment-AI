/** @vitest-environment jsdom */
import {beforeEach,afterEach,describe,it,expect,vi} from "vitest";
import {render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react";
import {AtlasLiveWorkspace} from "./AtlasLiveWorkspace";
const json=(data:unknown,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
const identity={id:"user-1",email:"owner@example.test",role:"USER"};
describe("authenticated live workspace",()=>{
 beforeEach(()=>{vi.stubGlobal("fetch",vi.fn(async (url:string)=>{
  if(url.endsWith("/system/freshness"))return json({instruments:[{alert_id:1}],mutualFunds:[{stale:true}]});
  if(url.includes("/instruments/search"))return json([{trading_symbol:"RELIANCE",isin:"INE002A01018"}]);
  if(url.includes("/mutual-funds/search"))return json([{scheme_name:"Example Fund",scheme_code:123}]);
  if(url.endsWith("/ai/providers/health"))return json({healthy:true});
  if(url.includes("/ai/analyze/"))return json({recommendation:"HOLD"});
  return json({});
 }));});
 afterEach(()=>{cleanup();vi.unstubAllGlobals();});
 it("renders the verified identity, stale-feed banner and asset searches",async()=>{
  render(<AtlasLiveWorkspace identity={identity}/>);
  expect(screen.getByText("owner@example.test")).toBeTruthy();
  expect(await screen.findByRole("alert")).toHaveProperty("textContent",expect.stringContaining("stale"));
  fireEvent.change(screen.getByLabelText("Research search"),{target:{value:"RELIANCE"}});
  fireEvent.click(screen.getByRole("button",{name:"Search stocks"}));
  expect(await screen.findByText("RELIANCE")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab",{name:"Mutual Fund Explorer"}));
  fireEvent.change(screen.getByLabelText("Research search"),{target:{value:"Example"}});
  fireEvent.click(screen.getByRole("button",{name:"Search mutual funds"}));
  expect(await screen.findByText("Example Fund")).toBeTruthy();
 });
 it("displays an AI report without a second login form",async()=>{
  render(<AtlasLiveWorkspace identity={identity}/>);
  expect(screen.queryByLabelText("Account email")).toBeNull();
  fireEvent.click(screen.getByRole("tab",{name:"AI Committee"}));
  fireEvent.change(screen.getByLabelText("Research search"),{target:{value:"RELIANCE"}});
  fireEvent.click(screen.getByRole("button",{name:"Analyze with AI committee"}));
  await waitFor(()=>expect(screen.getByLabelText("AI committee report").textContent).toContain("HOLD"));
 });
});
