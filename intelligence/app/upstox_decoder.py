"""Bounded Upstox MarketDataFeedV3 protobuf LTPC decoder.

Field numbers follow Upstox's published MarketDataFeedV3.proto. Supports
LTPC in direct Feed, MarketFullFeed and IndexFullFeed. Rejects unknown
wire types, malformed varints, mismatched keys and stale trade timestamps.
This is intentionally narrower than the complete upstream schema.
"""
import struct
from .upstox_stream import StreamPolicy, normalize_tick

MAX_FRAME=1_048_576
MAX_FIELDS=20_000

class DecodeError(ValueError):
    pass

def _varint(data:bytes,pos:int)->tuple[int,int]:
    value=0
    for shift in range(0,70,7):
        if pos>=len(data):raise DecodeError("Truncated protobuf varint")
        byte=data[pos];pos+=1
        if shift==63 and byte>1:raise DecodeError("Protobuf varint overflow")
        value|=(byte&127)<<shift
        if byte<128:return value,pos
    raise DecodeError("Protobuf varint overflow")

def _fields(data:bytes):
    if len(data)>MAX_FRAME:raise DecodeError("Frame too large")
    pos=0;count=0
    while pos<len(data):
        count+=1
        if count>MAX_FIELDS:raise DecodeError("Too many protobuf fields")
        tag,pos=_varint(data,pos)
        number,wire=tag>>3,tag&7
        if number==0:raise DecodeError("Invalid protobuf field number")
        if wire==0:
            value,pos=_varint(data,pos)
        elif wire==1:
            if pos+8>len(data):raise DecodeError("Truncated fixed64")
            value=data[pos:pos+8];pos+=8
        elif wire==2:
            size,pos=_varint(data,pos)
            if size>MAX_FRAME or pos+size>len(data):raise DecodeError("Truncated length-delimited field")
            value=data[pos:pos+size];pos+=size
        elif wire==5:
            if pos+4>len(data):raise DecodeError("Truncated fixed32")
            value=data[pos:pos+4];pos+=4
        else:raise DecodeError("Unsupported protobuf wire type")
        yield number,wire,value

def _nested(data:bytes,number:int):
    return [value for n,w,value in _fields(data) if n==number and w==2]

def _ltpc(data:bytes)->dict:
    result={}
    for n,w,value in _fields(data):
        if n==1 and w==1:result["ltp"]=struct.unpack("<d",value)[0]
        elif n==2 and w==0:result["ltt"]=value
        elif n==3 and w==0:result["ltq"]=value
        elif n==4 and w==1:result["cp"]=struct.unpack("<d",value)[0]
    return result

def decode_quotes(frame:bytes,subscribed_keys:set[str],policy:StreamPolicy|None=None,
                  now_ms:int|None=None)->dict:
    if not isinstance(frame,bytes):raise DecodeError("Binary protobuf frame required")
    if not subscribed_keys:raise DecodeError("Subscriptions required")
    policy=policy or StreamPolicy()
    fields=list(_fields(frame))
    message_type=next((v for n,w,v in fields if n==1 and w==0),None)
    if message_type not in (0,1,2):raise DecodeError("Unknown feed response type")
    if message_type==2:return {"message_type":"MARKET_INFO","quotes":[],"rejected":[]}
    if message_type==0:return {"message_type":"INITIAL_FEED","quotes":[],"rejected":[]}
    quotes=[];rejected=[]
    for n,w,entry in fields:
        if n!=2 or w!=2:continue
        keys=_nested(entry,1)
        feeds=_nested(entry,2)
        if len(keys)!=1 or len(feeds)!=1:
            rejected.append("INVALID_FEED_MAP_ENTRY");continue
        try:key=keys[0].decode("utf-8")
        except UnicodeDecodeError:
            rejected.append("INVALID_INSTRUMENT_KEY");continue
        if key not in subscribed_keys:
            rejected.append("UNSUBSCRIBED_INSTRUMENT");continue
        feed=feeds[0]
        ltpcs=_nested(feed,1)
        if not ltpcs:
            for full in _nested(feed,2):
                for ff in _nested(full,1)+_nested(full,2):
                    ltpcs.extend(_nested(ff,1))
        if not ltpcs:
            for first in _nested(feed,3):
                ltpcs.extend(_nested(first,1))
        if len(ltpcs)!=1:
            rejected.append("LTPC_UNAVAILABLE");continue
        try:
            quote=normalize_tick(key,_ltpc(ltpcs[0]),policy,now_ms=now_ms)
            quotes.append(quote)
        except (ValueError,OverflowError,OSError):
            rejected.append("INVALID_OR_STALE_TRADE")
    return {"message_type":"LIVE_FEED","quotes":quotes,"rejected":rejected}
