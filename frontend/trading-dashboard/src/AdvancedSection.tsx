import {useState,type ReactNode} from "react";

/** Mount expensive diagnostic and manual forms only when explicitly opened.
 * After the first open retain their state while collapsed on the current page.
 */
export default function AdvancedSection({title,description,children}:{title:string;description:string;children:ReactNode}){
 const [loaded,setLoaded]=useState(false);
 return <details className="advanced-tools glass workspace-disclosure" onToggle={event=>{if(event.currentTarget.open)setLoaded(true);}}>
  <summary><span><strong>{title}</strong><small>{description}</small></span><b aria-hidden="true">⌄</b></summary>
  {loaded&&<div className="advanced-tools-content">{children}</div>}
 </details>;
}
