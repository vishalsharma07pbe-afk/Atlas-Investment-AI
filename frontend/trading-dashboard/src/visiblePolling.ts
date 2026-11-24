/** Foreground-only, single-flight polling. Always stop/abort on disposal. */
export function visiblePolling(load:(signal:AbortSignal)=>Promise<void>,interval:number){
 const controller=new AbortController();
 let pending=false;
 async function run(){
  if(controller.signal.aborted||pending||document.visibilityState==="hidden")return;
  pending=true;
  try{await load(controller.signal);}catch{/* Each consumer owns its error state. */}
  finally{pending=false;}
 }
 const visibility=()=>{if(document.visibilityState==="visible")void run();};
 void run();
 const timer=window.setInterval(run,interval);
 document.addEventListener("visibilitychange",visibility);
 return ()=>{
  controller.abort();
  window.clearInterval(timer);
  document.removeEventListener("visibilitychange",visibility);
 };
}
