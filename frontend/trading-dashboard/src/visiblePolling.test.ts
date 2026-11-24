/** @vitest-environment jsdom */
import {afterEach,expect,it,vi} from "vitest";
import {visiblePolling} from "./visiblePolling";

afterEach(()=>{vi.useRealTimers();vi.restoreAllMocks();});
it("pauses hidden polling, resumes immediately, and never overlaps",async()=>{
 vi.useFakeTimers();
 let state:DocumentVisibilityState="visible";
 vi.spyOn(document,"visibilityState","get").mockImplementation(()=>state);
 let resolve:()=>void=()=>{};
 let signal:AbortSignal|undefined;
 const load=vi.fn((next:AbortSignal)=>{signal=next;return new Promise<void>(done=>{resolve=done;});});
 const stop=visiblePolling(load,1000);
 try{
  expect(load).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(3000);
  expect(load).toHaveBeenCalledTimes(1);
  resolve();await Promise.resolve();
  state="hidden";document.dispatchEvent(new Event("visibilitychange"));
  await vi.advanceTimersByTimeAsync(3000);
  expect(load).toHaveBeenCalledTimes(1);
  state="visible";document.dispatchEvent(new Event("visibilitychange"));
  expect(load).toHaveBeenCalledTimes(2);
  stop();expect(signal?.aborted).toBe(true);
  resolve();await vi.advanceTimersByTimeAsync(3000);
  expect(load).toHaveBeenCalledTimes(2);
 }finally{stop();}
});
