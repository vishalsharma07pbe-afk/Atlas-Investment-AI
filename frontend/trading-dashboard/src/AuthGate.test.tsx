/** @vitest-environment jsdom */
import {afterEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import {AuthGate} from "./AuthGate";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});

describe("application authentication gate",()=>{
 it("shows login before dashboard, verifies the session, and logs out",async()=>{
  let signedIn=false;
  vi.stubGlobal("fetch",vi.fn(async (url:string,init?:RequestInit)=>{
   if(url.endsWith("/auth/me"))return {ok:signedIn,status:signedIn?200:401,json:async()=>({id:"u1",email:"owner@example.test",role:"USER"})};
   if(url.endsWith("/auth/login")&&init?.method==="POST"){signedIn=true;return {ok:true,status:200,json:async()=>({expires_in:900})};}
   if(url.endsWith("/auth/logout")){signedIn=false;return {ok:true,status:200,json:async()=>({logged_out:true})};}
   return {ok:false,status:404,json:async()=>({})};
  }));
  render(<AuthGate>{({identity,logout})=><div><h1>Private dashboard</h1><span>{identity.email}</span><button onClick={()=>void logout()}>Logout</button></div>}</AuthGate>);
  expect(await screen.findByRole("button",{name:/Open dashboard/i})).toBeTruthy();
  expect(screen.queryByText("Private dashboard")).toBeNull();
  fireEvent.change(screen.getByLabelText("Account email"),{target:{value:"owner@example.test"}});
  fireEvent.change(screen.getByLabelText("Account password"),{target:{value:"strong-password-123"}});
  fireEvent.click(screen.getByRole("button",{name:/Open dashboard/i}));
  expect(await screen.findByText("Private dashboard")).toBeTruthy();
  expect(screen.getByText("owner@example.test")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Logout"}));
  await waitFor(()=>expect(screen.getByRole("button",{name:/Open dashboard/i})).toBeTruthy());
  expect(screen.queryByText("Private dashboard")).toBeNull();
 });
});
