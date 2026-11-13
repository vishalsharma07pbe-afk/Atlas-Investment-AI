"""Deterministic daily technical calculations. No forecasting or trade advice."""
from dataclasses import dataclass
from math import log, sqrt
from statistics import pstdev

@dataclass(frozen=True)
class Candle:
    date:str; open:float; high:float; low:float; close:float; volume:int; adjustment_status:str="RAW_UNADJUSTED"; revision:int=1

def sma(v,n): return [None if i+1<n else sum(v[i-n+1:i+1])/n for i in range(len(v))]
def ema(v,n):
    out=[None]*len(v)
    if len(v)<n:return out
    out[n-1]=sum(v[:n])/n;k=2/(n+1)
    for i in range(n,len(v)):out[i]=v[i]*k+out[i-1]*(1-k)
    return out
def wilder(v,n):
    out=[None]*len(v)
    if len(v)<n:return out
    out[n-1]=sum(v[:n])/n
    for i in range(n,len(v)):out[i]=(out[i-1]*(n-1)+v[i])/n
    return out
def rsi(v,n=14):
    if len(v)<2:return [None]*len(v)
    gains=[0]+[max(v[i]-v[i-1],0) for i in range(1,len(v))]; losses=[0]+[max(v[i-1]-v[i],0) for i in range(1,len(v))]
    ag=wilder(gains[1:],n);al=wilder(losses[1:],n);out=[None]
    for g,l in zip(ag,al): out.append(None if g is None else (100 if l==0 else 100-100/(1+g/l)))
    return out
def true_ranges(c): return [c[0].high-c[0].low]+[max(x.high-x.low,abs(x.high-c[i-1].close),abs(x.low-c[i-1].close)) for i,x in enumerate(c[1:],1)] if c else []
def atr(c,n=14): return wilder(true_ranges(c),n)
def adx(c,n=14):
    if not c:return []
    tr=true_ranges(c);plus=[0];minus=[0]
    for i in range(1,len(c)):
        up=c[i].high-c[i-1].high;down=c[i-1].low-c[i].low;plus.append(up if up>down and up>0 else 0);minus.append(down if down>up and down>0 else 0)
    at=wilder(tr,n);ap=wilder(plus,n);am=wilder(minus,n);dx=[]
    for t,p,m in zip(at,ap,am):
        if t in (None,0):dx.append(None);continue
        pdi=100*p/t;mdi=100*m/t;dx.append(0 if pdi+mdi==0 else 100*abs(pdi-mdi)/(pdi+mdi))
    values=[x for x in dx if x is not None];smooth=wilder(values,n);out=[None]*len(dx);offset=next((i for i,x in enumerate(dx) if x is not None),len(dx))
    for j,x in enumerate(smooth):out[offset+j]=x
    return out
def compute(c):
    closes=[x.close for x in c];vol=[x.volume for x in c];result={}
    for n in (20,50,100,200):result[f"sma_{n}"]=sma(closes,n)
    for n in (9,20,50,200):result[f"ema_{n}"]=ema(closes,n)
    result["rsi_14"]=rsi(closes);result["atr_14"]=atr(c);result["adx_14"]=adx(c)
    e12,e26=ema(closes,12),ema(closes,26);macd=[None if a is None or b is None else a-b for a,b in zip(e12,e26)]
    valid=[x for x in macd if x is not None];signal_valid=ema(valid,9);signal=[None]*len(c);start=next((i for i,x in enumerate(macd) if x is not None),len(c))
    for j,x in enumerate(signal_valid):signal[start+j]=x
    result["macd"]=macd;result["macd_signal"]=signal;result["macd_histogram"]=[None if a is None or b is None else a-b for a,b in zip(macd,signal)]
    mid=sma(closes,20);result["bollinger_mid_20"]=mid;result["bollinger_upper_20"]=[None if i<19 else mid[i]+2*pstdev(closes[i-19:i+1]) for i in range(len(c))];result["bollinger_lower_20"]=[None if i<19 else mid[i]-2*pstdev(closes[i-19:i+1]) for i in range(len(c))]
    result["relative_volume_20"]=[None if i<20 or sum(vol[i-20:i])==0 else vol[i]/(sum(vol[i-20:i])/20) for i in range(len(c))]
    obv=[0]
    for i in range(1,len(c)):obv.append(obv[-1]+(vol[i] if closes[i]>closes[i-1] else -vol[i] if closes[i]<closes[i-1] else 0))
    result["obv"]=obv
    result["momentum_1d"]=[None]+[closes[i]/closes[i-1]-1 for i in range(1,len(c))]
    result["momentum_20d"]=[None if i<20 else closes[i]/closes[i-20]-1 for i in range(len(c))]
    returns=[None]+[log(closes[i]/closes[i-1]) for i in range(1,len(c))]
    result["historical_volatility_20"]=[None if i<20 else pstdev(returns[i-19:i+1])*sqrt(252) for i in range(len(c))]
    result["vwap"]= [None]*len(c)
    return result

def levels(c,window=60):
    recent=c[-window:];supports=[];resistances=[]
    for i in range(2,len(recent)-2):
        if recent[i].low==min(x.low for x in recent[i-2:i+3]):supports.append(recent[i].low)
        if recent[i].high==max(x.high for x in recent[i-2:i+3]):resistances.append(recent[i].high)
    def unique(values):
        out=[]
        for x in values:
            if not any(abs(x-y)/max(y,1e-9)<.015 for y in out):out.append(x)
        return out[-3:]
    return {"support":unique(supports),"resistance":unique(resistances)}
