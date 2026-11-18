import React,{useCallback,useEffect,useState} from "react";

export type AuthIdentity={id:string;email:string;role:string};
type AuthState="checking"|"signed-out"|"signed-in";

function savedTheme(){
  try{const value=JSON.parse(localStorage.getItem("atlas:appearance")||"null")?.theme;return ["system","dark","light"].includes(value)?value:"system";}catch{return "system";}
}

export function AuthGate({children}:{children:(session:{identity:AuthIdentity;logout:()=>Promise<void>})=>React.ReactNode}){
  const [state,setState]=useState<AuthState>("checking");
  const [identity,setIdentity]=useState<AuthIdentity|null>(null);
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [pending,setPending]=useState(false);
  const [error,setError]=useState("");
  const verify=useCallback(async()=>{
    try{
      const response=await fetch("/api/v1/auth/me",{cache:"no-store",credentials:"same-origin"});
      if(!response.ok)throw Error("SIGNED_OUT");
      setIdentity(await response.json());setState("signed-in");setError("");return true;
    }catch{setIdentity(null);setState("signed-out");return false;}
  },[]);
  useEffect(()=>{void verify();const timer=window.setInterval(()=>{if(document.visibilityState==="visible")void verify();},60_000);return()=>window.clearInterval(timer);},[verify]);
  async function login(event:React.FormEvent){
    event.preventDefault();if(pending)return;setPending(true);setError("");
    try{
      const response=await fetch("/api/v1/auth/login",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:email.trim(),password})});
      if(response.status===401)throw Error("Email or password is incorrect.");
      if(response.status===429)throw Error("Too many attempts. Wait one minute and try again.");
      if(!response.ok)throw Error("Sign in is unavailable. Check that the local backend is running.");
      if(!await verify())throw Error("The session could not be verified.");
      setPassword("");
    }catch(reason){setError(reason instanceof Error?reason.message:"Sign in failed.");setState("signed-out");}
    finally{setPending(false);}
  }
  async function logout(){
    try{await fetch("/api/v1/auth/logout",{method:"POST",credentials:"same-origin"});}finally{setIdentity(null);setState("signed-out");setEmail("");setPassword("");}
  }
  if(state==="signed-in"&&identity)return <>{children({identity,logout})}</>;
  const theme=savedTheme();
  return <div className="dashboard auth-gate" data-theme={theme} style={{"--panel-alpha":"0.78","--panel-blur":"24px","--panel-border-color":"var(--glass-border)"} as React.CSSProperties}>
    <div className="canvas" aria-hidden="true"><i/><i/><i/><i/></div>
    <main className="auth-page">
      <section className="auth-card glass" aria-label={state==="checking"?"Checking account session":"ATLAS sign in"}>
        <div className="auth-brand"><span className="brandicon">◆</span><div><strong>ATLAS</strong><small>INVESTMENT INTELLIGENCE</small></div></div>
        {state==="checking"?<div className="auth-checking" role="status"><span/><h1>Checking your session</h1><p>Securing your private research workspace…</p></div>:
        <form onSubmit={login} className="auth-login-form">
          <div className="auth-copy"><small>PRIVATE · LOCAL ACCOUNT</small><h1>Welcome back</h1><p>Sign in to open your dashboard, portfolio and research tools.</p></div>
          <label htmlFor="login-email"><span>Email address</span><input id="login-email" aria-label="Account email" type="email" autoComplete="username" placeholder="you@example.com" value={email} onChange={event=>setEmail(event.target.value)} required autoFocus/></label>
          <label htmlFor="login-password"><span>Password</span><input id="login-password" aria-label="Account password" type="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={event=>setPassword(event.target.value)} minLength={12} required/></label>
          {error&&<div className="auth-error" role="alert">{error}</div>}
          <button className="primary auth-login-button" disabled={pending}>{pending?"Signing in…":"Open dashboard"}<span>→</span></button>
          <p className="auth-security-note"><span>●</span> Secure local session · stays signed in for up to 7 days</p>
        </form>}
      </section>
    </main>
  </div>;
}
