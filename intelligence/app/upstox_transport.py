"""Read-only Upstox V3 WebSocket transport.

This is an opt-in, server-side binary frame transport, not a verified live quote
pipeline. Protobuf decoding/persistence are deliberately separate.
"""
import asyncio
import json
import random
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable
from .upstox_authorization import AuthorizationError, authorize_feed
from .upstox_stream import StreamPolicy,subscription_request

@dataclass(frozen=True)
class TransportPolicy:
    max_retries: int = 5
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    connect_timeout_seconds: float = 15.0
    max_frame_bytes: int = 1_048_576

class TransportUnavailable(RuntimeError):
    pass

def _safe_failure_code(exc: Exception) -> str:
    """Classify failures without returning provider URLs, tokens, or messages."""
    if isinstance(exc, AuthorizationError):
        return exc.code
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "FEED_CONNECTION_TIMEOUT"
    if isinstance(exc, TransportUnavailable):
        return "FEED_TRANSPORT_UNAVAILABLE"
    # Keep this list based on public exception class names so importing the
    # optional WebSocket package is not required just to expose diagnostics.
    if exc.__class__.__name__ in {"InvalidStatus", "InvalidStatusCode"}:
        return "FEED_HANDSHAKE_REJECTED"
    if exc.__class__.__name__ in {"ConnectionClosed", "ConnectionClosedError", "ConnectionClosedOK"}:
        return "FEED_CONNECTION_CLOSED"
    if isinstance(exc, OSError):
        return "FEED_NETWORK_UNAVAILABLE"
    return "FEED_CONNECTION_FAILED"

async def receive_session(
    token: str,
    instrument_keys: list[str],
    on_binary_frame: Callable[[bytes], Awaitable[None]],
    *,
    policy: TransportPolicy = TransportPolicy(),
    connect=None,
    authorize=authorize_feed,
    on_connection_change=None,
) -> int:
    """Authorize, subscribe, and forward bounded binary frames for trusted decoding.

    Caller must provide a verified decoder; this function never interprets bytes
    as prices. Do not log the signed URI, bearer token or raw frames.
    """
    if not callable(on_binary_frame):
        raise ValueError("Binary frame handler required")
    payload=subscription_request(instrument_keys,StreamPolicy(),str(uuid.uuid4()))
    uri=await asyncio.to_thread(authorize,token)
    if connect is None:
        try:
            from websockets.asyncio.client import connect as ws_connect
        except ImportError as exc:
            raise TransportUnavailable("WebSocket dependency unavailable") from None
        connect=ws_connect
    count=0
    try:
        async with connect(uri,open_timeout=policy.connect_timeout_seconds,
                           max_size=policy.max_frame_bytes,ping_interval=20,ping_timeout=20) as ws:
            await ws.send(json.dumps(payload).encode("utf-8"))
            if on_connection_change is not None:
                await on_connection_change(True)
            async for frame in ws:
                if not isinstance(frame,bytes):
                    continue
                if len(frame)>policy.max_frame_bytes:
                    raise TransportUnavailable("Provider frame exceeds configured limit")
                await on_binary_frame(frame)
                count+=1
        return count
    finally:
        if on_connection_change is not None:
            await on_connection_change(False)

async def reconnecting_stream(
    token: str,
    instrument_keys: list[str],
    on_binary_frame: Callable[[bytes],Awaitable[None]],
    *,
    stop: asyncio.Event,
    policy: TransportPolicy = TransportPolicy(),
    session=receive_session,
    sleep=asyncio.sleep,
    on_connection_change=None,
) -> dict:
    """Bounded retries; a fresh authorization URI is requested on each session."""
    if policy.max_retries<0 or policy.base_delay_seconds<=0 or policy.max_delay_seconds<=0:
        raise ValueError("Invalid retry policy")
    attempts=0
    sessions=0
    last_failure=None
    while not stop.is_set():
        try:
            if on_connection_change is None:
                await session(token,instrument_keys,on_binary_frame,policy=policy)
            else:
                await session(token,instrument_keys,on_binary_frame,policy=policy,
                              on_connection_change=on_connection_change)
            sessions+=1
            if stop.is_set():break
            attempts+=1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_failure=_safe_failure_code(exc)
            attempts+=1
        finally:
            if on_connection_change is not None:
                await on_connection_change(False)
        if last_failure=="FEED_CREDENTIAL_REJECTED":
            return {"status":"DISCONNECTED","sessions":sessions,"retries":max(0,attempts-1),
                    "reason":"CREDENTIAL_REJECTED","last_failure":last_failure}
        if attempts>policy.max_retries:
            return {"status":"DISCONNECTED","sessions":sessions,"retries":attempts-1,
                    "reason":"RETRY_BUDGET_EXHAUSTED","last_failure":last_failure}
        delay=min(policy.max_delay_seconds,policy.base_delay_seconds*(2**(attempts-1)))
        # Small jitter avoids synchronized reconnect storms.
        await sleep(delay*(0.8+random.random()*0.2))
    return {"status":"STOPPED","sessions":sessions,"retries":attempts}
