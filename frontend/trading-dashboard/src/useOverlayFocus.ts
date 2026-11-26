import {useEffect,useRef,type RefObject} from "react";

// Keep the two existing mutually exclusive header overlays keyboard usable.
// The callback ref avoids restarting focus management on ordinary data renders.
export function useOverlayFocus(open:boolean,onClose:()=>void):{
 triggerRef:RefObject<HTMLButtonElement|null>;panelRef:RefObject<HTMLElement|null>
}{
 const triggerRef=useRef<HTMLButtonElement>(null);
 const panelRef=useRef<HTMLElement>(null);
 const closeRef=useRef(onClose);
 useEffect(()=>{closeRef.current=onClose;},[onClose]);
 useEffect(()=>{
  if(!open)return;
  const panel=panelRef.current;
  const trigger=triggerRef.current;
  if(!panel)return;
  const focusable=()=>Array.from(panel.querySelectorAll<HTMLElement>(
   'button:not([disabled]),a[href],input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]:not([tabindex="-1"])'
  )).filter(el=>el.tabIndex>=0&&!el.closest('[hidden],[inert]')&&
    !Array.from(panel.querySelectorAll("details:not([open])")).some(d=>d.contains(el)&&d.querySelector("summary")!==el));
  const first=()=>focusable()[0]||panel;
  first().focus({preventScroll:true});
  const onKey=(event:KeyboardEvent)=>{
   if(event.key==="Escape"){event.preventDefault();closeRef.current();return;}
   if(event.key!=="Tab")return;
   const items=focusable(),active=document.activeElement;
   if(!items.length){event.preventDefault();panel.focus();return;}
   if(!panel.contains(active)||active===panel||!items.includes(active as HTMLElement)){
    event.preventDefault();(event.shiftKey?items[items.length-1]:items[0]).focus();return;
   }
   if(event.shiftKey&&active===items[0]){event.preventDefault();items[items.length-1].focus();}
   else if(!event.shiftKey&&active===items[items.length-1]){event.preventDefault();items[0].focus();}
  };
  document.addEventListener("keydown",onKey);
  return ()=>{
   document.removeEventListener("keydown",onKey);
   // Do not steal focus when another overlay already received it.
   if(trigger?.isConnected&&(panel.contains(document.activeElement)||document.activeElement===document.body)){
    trigger.focus({preventScroll:true});
   }
  };
 },[open]);
 return {triggerRef,panelRef};
}
