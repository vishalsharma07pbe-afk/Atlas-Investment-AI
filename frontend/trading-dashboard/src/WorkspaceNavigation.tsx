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
export default function WorkspaceNavigation({page,onNavigate,account,onLogout,onHelp}:{page:number;onNavigate:(id:number)=>void;account?:string;onLogout?:()=>void;onHelp?:()=>void}){
 const [expanded,setExpanded]=useState(false);
 function select(id:number){onNavigate(id);setExpanded(false);}
 return <aside className="sidebar glass workspace-sidebar">
  <div className="brand"><span className="brandicon" aria-hidden="true">◆</span><div><strong>ATLAS</strong><small>INVESTMENT INTELLIGENCE</small></div></div>
  <button type="button" className="workspace-menu-toggle" aria-expanded={expanded} aria-controls="atlas-workspace-nav" onClick={()=>setExpanded(v=>!v)}><span>{pages[page]?.title||pages[0].title}</span><span aria-hidden="true">{expanded?"−":"☰"}</span></button>
  <div className={"workspace-nav-groups"+(expanded?" is-expanded":"")} id="atlas-workspace-nav">
   {groups.map(group=><div key={group.label} className="workspace-nav-group"><div className="navlabel">{group.label}</div><nav aria-label={group.label}>{group.ids.map(id=><button type="button" key={id} aria-current={page===id?"page":undefined} className={page===id?"active":""} onClick={()=>select(id)}><span className="navdot" aria-hidden="true"><NavIcon id={id}/></span><span>{pages[id].title}</span><span className="navarrow" aria-hidden="true">›</span></button>)}</nav></div>)}
  </div>
  {account&&<div className="terminal-sidebar-account"><span className="terminal-account-avatar" aria-hidden="true">{account.slice(0,1).toUpperCase()}</span><div><strong title={account}>{account.split("@")[0]}</strong><small>Private account</small></div></div>}
  {onLogout&&<div className="terminal-sidebar-actions"><button type="button" onClick={onHelp}>Help</button><button type="button" onClick={onLogout}>Logout</button></div>}
  <div className="sidebottom"><span className="statusdot"/> PRIVATE · LOCAL MODE<br/><small>Research only · No order execution</small></div>
 </aside>;
}

function NavIcon({id}:{id:number}){
 const paths:Record<number,string>={0:"M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",9:"M3 6h18v14H3z M8 6V3h8v3 M3 12h18 M10 12v2h4v-2",1:"M3 20h18 M5 17V9 M12 17V4 M19 17v-5",2:"m13 2-9 12h7l-1 8 10-13h-7z",3:"M3 17l6-6 4 4 8-10 M15 5h6v6",4:"M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v5l4 2",5:"M3 20h18 M6 16l4-5 4 3 6-9 M16 5h4v4",10:"M3 12h4l3-7 4 14 3-7h4",7:"M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6",8:"M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z",6:"M4 7h16 M4 17h16 M8 4v6 M16 14v6"};
 return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round"><path d={paths[id]||paths[0]}/></svg>;
}
