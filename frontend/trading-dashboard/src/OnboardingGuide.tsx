import {useEffect,useState} from "react";

const STORAGE_KEY="atlas:onboarding-complete:v1";
const steps=[
 {title:"Add what you own",body:"Start in Research Home. Search by company or symbol, enter quantity and average cost, then verify the dated price before saving.",tab:0},
 {title:"Check the evidence",body:"Use Market & Data Health to confirm provider status, freshness and quality issues before relying on any research output.",tab:6},
 {title:"Research, do not trade blindly",body:"The P2 Research Lab explains cited evidence, tests historical signals and keeps uncertainty visible. It never places an order.",tab:8},
];

export default function OnboardingGuide({onNavigate}:{onNavigate:(tab:number)=>void}){
 const [open,setOpen]=useState(()=>{try{return localStorage.getItem(STORAGE_KEY)!=="true";}catch{return true;}});
 const [step,setStep]=useState(0);
 useEffect(()=>{const show=()=>{setStep(0);setOpen(true);};window.addEventListener("atlas:open-onboarding",show);return()=>window.removeEventListener("atlas:open-onboarding",show);},[]);
 if(!open)return null;
 const current=steps[step];
 function finish(){try{localStorage.setItem(STORAGE_KEY,"true");}catch{/* A blocked store must not block the app. */}setOpen(false);}
 return <section className="onboarding glass" aria-labelledby="onboarding-title">
  <div className="onboarding-progress" aria-label={`Onboarding step ${step+1} of ${steps.length}`}>{steps.map((_,index)=><i key={index} className={index<=step?"active":""}/>)}</div>
  <div><small>GET STARTED · {step+1} OF {steps.length}</small><h2 id="onboarding-title">{current.title}</h2><p>{current.body}</p></div>
  <div className="onboarding-actions"><button type="button" className="secondary" onClick={()=>{onNavigate(current.tab);document.getElementById("main-content")?.focus();}}>Open this area</button>{step>0&&<button type="button" className="secondary" onClick={()=>setStep(step-1)}>Back</button>}{step<steps.length-1?<button type="button" className="primary" onClick={()=>setStep(step+1)}>Next</button>:<button type="button" className="primary" onClick={finish}>Finish setup</button>}<button type="button" className="onboarding-dismiss" onClick={finish}>Dismiss</button></div>
 </section>;
}

