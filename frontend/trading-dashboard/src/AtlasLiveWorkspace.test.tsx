/** @vitest-environment jsdom */
import React from "react";
import {beforeEach,afterEach,describe,it,expect,vi} from "vitest";
import {render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react";
import {AtlasLiveWorkspace} from "./AtlasLiveWorkspace";
const json=(data:unknown,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
describe("P0 authenticated UI verification",()=>{
 beforeEach(()=>{sessionStorage.clear();vi.stubGlobal("fetch",vi.fn(async (url:string,options?:RequestInit)=>{
  if(url.endsWith("/auth/login"))return json({access_token:"test.jwt",expires_in:900});
  if(url.endsWith("/auth/me"))return json({email:"owner@example.test"});
  if(url.endsWith("/system/freshness"))return json({instruments:[{alert_id:1}],mutualFunds:[{stale:true}]});
  if(url.includes("/instruments/search"))return json([{trading_symbol:"RELIANCE",isin:"INE002A01018"}]);
  if(url.includes("/mutual-funds/search"))return json([{scheme_name:"Example Fund",scheme_code:123}]);
  if(url.endsWith("/ai/providers/health"))return json({healthy:true});
  if(url.includes("/ai/analyze/"))return json({recommendation:"HOLD"});
  if(url.endsWith("/portfolio/sync/upstox"))return json({synced:1});
  if(url.endsWith("/auth/logout"))return json({logged_out:true});
  return json({});
 }));});
 afterEach(()=>{cleanup();vi.unstubAllGlobals();});
 async function signIn(){
  render(<AtlasLiveWorkspace/>);
  fireEvent.change(screen.getByLabelText("Account email"),{target:{value:"owner@example.test"}});
  fireEvent.change(screen.getByLabelText("Account password"),{target:{value:"strong-password-123"}});
  fireEvent.click(screen.getByRole("button",{name:"Sign in"}));
  await screen.findByText(/Signed in: owner@example.test/);
 }
 it("signs in, renders stale-feed banner and searches both asset classes",async()=>{
  await signIn();
  expect(await screen.findByRole("alert")).toHaveProperty("textContent",expect.stringContaining("stale"));
  fireEvent.change(screen.getByLabelText("Research search"),{target:{value:"RELIANCE"}});
  fireEvent.click(screen.getByRole("button",{name:"Search stocks"}));
  expect(await screen.findByText("RELIANCE")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Mutual Fund Explorer"}));
  fireEvent.change(screen.getByLabelText("Research search"),{target:{value:"Example"}});
  fireEvent.click(screen.getByRole("button",{name:"Search mutual funds"}));
  expect(await screen.findByText("Example Fund")).toBeTruthy();
 });
 it("displays AI report and logs out",async()=>{
  await signIn();
  fireEvent.click(screen.getByRole("button",{name:"AI Committee"}));
  fireEvent.change(screen.getByLabelText("Research search"),{target:{value:"RELIANCE"}});
  fireEvent.click(screen.getByRole("button",{name:"Analyze with AI committee"}));
  await waitFor(()=>expect(screen.getByLabelText("AI committee report").textContent).toContain("HOLD"));
  fireEvent.click(screen.getByRole("button",{name:"Logout"}));
  expect(await screen.findByRole("button",{name:"Sign in"})).toBeTruthy();
 });
});
