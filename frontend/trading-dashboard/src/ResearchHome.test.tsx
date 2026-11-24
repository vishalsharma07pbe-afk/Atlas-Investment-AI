/** @vitest-environment jsdom */
import {afterEach,beforeEach,describe,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import ResearchHome from "./ResearchHome";

const json=(data:unknown,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
const holdings=[{id:1,symbol:"TCS",asset_type:"EQUITY",quantity:2,average_cost:100,last_price:120,invested:200,market_value:240,unrealized_pnl:40},{id:2,symbol:"INFY",asset_type:"EQUITY",quantity:1,average_cost:100,last_price:null,invested:100,market_value:null,unrealized_pnl:null}];

describe("research home",()=>{
 beforeEach(()=>vi.stubGlobal("fetch",vi.fn(async(url:string)=>{
  if(url.includes("screener/daily"))return json({eligible_count:1,universe_size:2,top_gainers:[{id:1,symbol:"TCS",exchange:"NSE",as_of:"2026-11-14",close:120,change_1d_percent:2,momentum_20d_percent:5,relative_volume_20:1.2,rsi_14:60}],momentum_leaders:[],notice:"Research only"});
  if(url.includes("/technical/1/summary"))return json({status:"READY",research:{trend:"UPTREND",momentum:"POSITIVE",relative_volume:1.2,bullish_evidence:["Close is above SMA 50."],bearish_evidence:[],risk_observations:[],missing_data:[],source_freshness:{latest_verified_date:"2026-11-14",is_live:false}},notice:"Research only"});
  if(url.includes("/ai/analyze/"))return json({providers:[{provider:"GEMINI",status:"VALID",verdict:{action:"HOLD",confidence_pct:60,holding_horizon:"SWING",pros:["Trend"],cons:["Risk"]}}],consensus:{majority_action:null,agreement_pct:100,conflict:false,valid_verdict_count:1},notice:"Opinions only"});
  return json([]);
 })));
 afterEach(()=>{cleanup();vi.unstubAllGlobals();});
 it("opens the single portfolio snapshot instead of rendering a duplicate",()=>{const review=vi.fn();render(<ResearchHome holdings={holdings} onReviewHoldings={review} onOpenExplorer={()=>{}} onOpenDataHealth={()=>{}}/>);fireEvent.click(screen.getByRole("tab",{name:/Review holdings/}));expect(review).toHaveBeenCalledOnce();expect(screen.queryByText("Your holdings at a glance")).toBeNull();});
 it("discovers validated candidates automatically and sends them to AI review",async()=>{render(<ResearchHome holdings={holdings} onReviewHoldings={()=>{}} onOpenExplorer={()=>{}} onOpenDataHealth={()=>{}}/>);fireEvent.click(screen.getByRole("tab",{name:/Find opportunities/}));expect(await screen.findByText("Analyze with AI →")).toBeTruthy();fireEvent.click(screen.getByText("Analyze with AI →"));fireEvent.click(screen.getByRole("button",{name:"Run all available models"}));await waitFor(()=>expect(screen.getByText("GEMINI")).toBeTruthy());});
 it("explains when automatically loaded daily history is not sufficient",async()=>{(fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(json({eligible_count:0,universe_size:20,top_gainers:[],momentum_leaders:[],skipped:{NO_HISTORY:20},notice:"Research only"}));render(<ResearchHome holdings={holdings} onReviewHoldings={()=>{}} onOpenExplorer={()=>{}} onOpenDataHealth={()=>{}}/>);fireEvent.click(screen.getByRole("tab",{name:/Find opportunities/}));expect(await screen.findByText("No eligible daily history yet")).toBeTruthy();expect(screen.getByText("no history: 20")).toBeTruthy();expect(screen.getByRole("button",{name:"Open Data Health"})).toBeTruthy();});
});
