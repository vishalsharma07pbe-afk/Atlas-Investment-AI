/** @vitest-environment jsdom */
import React from "react";
import {describe,it,expect,vi,afterEach} from "vitest";
import {render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react";
import ProviderBatchPreflight,{containsCredentialFields} from "./ProviderBatchPreflight";

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
describe("provider preflight credential protection",()=>{
 it("rejects nested and array credential keys",()=>{
  expect(containsCredentialFields({candles:[{metadata:{api_key:"secret"}}]})).toBe(true);
  expect(containsCredentialFields({authorization:"Bearer secret"})).toBe(true);
  expect(containsCredentialFields({candles:[{instrument_key:"NSE_EQ|123"}]})).toBe(false);
 });
 it("does not transmit a batch containing a token",async()=>{
  const fetchMock=vi.fn();vi.stubGlobal("fetch",fetchMock);
  render(<ProviderBatchPreflight/>);
  fireEvent.change(screen.getByLabelText("Provider batch JSON"),{target:{value:JSON.stringify({provider:"UPSTOX",credentials:{access_token:"sensitive"}})}});
  fireEvent.click(screen.getByRole("button",{name:"Run dry-run preflight"}));
  expect(await screen.findByRole("alert")).toHaveProperty("textContent",expect.stringContaining("Credential fields detected"));
  expect(fetchMock).not.toHaveBeenCalled();
 });
 it("sends a credential-free batch and requires blocked dry-run response",async()=>{
  const fetchMock=vi.fn().mockResolvedValue({ok:true,json:async()=>({status:"BLOCKED",ingestion_authorized:false,dry_run:true,blockers:["NO_VERIFIED_ADAPTER"],records_examined:1,instruments_examined:1,latest_trade_date:"2026-11-13",notice:"Dry run"})});
  vi.stubGlobal("fetch",fetchMock);
  render(<ProviderBatchPreflight/>);
  fireEvent.click(screen.getByRole("button",{name:"Run dry-run preflight"}));
  await waitFor(()=>expect(fetchMock).toHaveBeenCalledTimes(1));
  expect(await screen.findByRole("status")).toHaveProperty("textContent",expect.stringContaining("BLOCKED"));
 });
});
