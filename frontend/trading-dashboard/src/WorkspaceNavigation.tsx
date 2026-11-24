import {useState} from "react";

// Keep previously persisted route IDs stable across the redesign.
export const pages:Record<number,{title:string;description:string;icon:string}>={
 0:{title:"Overview",description:"Your latest automatic research and portfolio attention items.",icon:"▦"},
 9:{title:"My Portfolio",description:"Review investments, recorded performance and risks in one place.",icon:"◫"},
 2:{title:"Intraday",description:"Current-session research, subject to live evidence and liquidity checks.",icon:"ϟ"},
 3:{title:"Swing Trading",description:"Automatically researched multi-session technical watch candidates.",icon:"↗"},
 4:{title:"Short-Term Equity",description:"Medium-term research with explicit evidence limitations.",icon:"◷"},
 5:{title:"Long-Term Investments",description:"Long-horizon research, business evidence and valuation.",icon:"◇"},
 1:{title:"Mutual Funds",description:"Category-wise historical research and verified fund qualification.",icon:"◈"},
 10:{title:"Market Intelligence",description:"Market observations, institutional evidence and news.",icon:"◎"},
 7:{title:"Stock Explorer",description:"Look up a company and inspect its available source evidence.",icon:"⌁"},
 8:{title:"AI Research",description:"Evidence-based research, strategy evaluation and planning.",icon:"✦"},
 6:{title:"Settings",description:"Manage data connections and review system diagnostics.",icon:"⚙"}
};
const groups=[{label:"Investments",ids:[0,9,1]},{label:"Opportunities",ids:[2,3,4,5]},{label:"Research & settings",ids:[10,7,8,6]}];
export function validPage(value:unknown):number {
 const id=Number(value);
 return Number.isInteger(id)&&Object.prototype.hasOwnProperty.call(pages,id)?id:0;
}
export default function WorkspaceNavigation({page,onNavigate}:{page:number;onNavigate:(id:number)=>void}){
 const [expanded,setExpanded]=useState(false);
 function select(id:number){onNavigate(id);setExpanded(false);}
 return <aside className="sidebar glass workspace-sidebar">
  <div className="brand"><span className="brandicon" aria-hidden="true">◆</span><div><strong>ATLAS</strong><small>INVESTMENT INTELLIGENCE</small></div></div>
  <button type="button" className="workspace-menu-toggle" aria-expanded={expanded} aria-controls="atlas-workspace-nav" onClick={()=>setExpanded(v=>!v)}><span>{pages[page]?.title||pages[0].title}</span><span aria-hidden="true">{expanded?"−":"☰"}</span></button>
  <div className={"workspace-nav-groups"+(expanded?" is-expanded":"")} id="atlas-workspace-nav">
   {groups.map(group=><div key={group.label} className="workspace-nav-group"><div className="navlabel">{group.label}</div><nav aria-label={group.label}>{group.ids.map(id=><button type="button" key={id} aria-current={page===id?"page":undefined} className={page===id?"active":""} onClick={()=>select(id)}><span className="navdot" aria-hidden="true">{pages[id].icon}</span><span>{pages[id].title}</span><span className="navarrow" aria-hidden="true">›</span></button>)}</nav></div>)}
  </div>
  <div className="sidebottom"><span className="statusdot"/> PRIVATE · LOCAL MODE<br/><small>Research only · No order execution</small></div>
 </aside>;
}
