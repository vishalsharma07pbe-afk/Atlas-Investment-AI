"""CI-only ASGI request recorder. Buffer the complete body, replay it to FastAPI."""
import asyncio
import os
from pathlib import Path
from app.main import app as real_app

async def app(scope, receive, send):
    if scope["type"]!="http" or scope.get("path")!="/api/v1/ai/analyze/TCS":
        await real_app(scope,receive,send)
        return
    chunks=[]
    while True:
        message=await receive()
        if message["type"]!="http.request":
            continue
        chunks.append(message.get("body",b""))
        if not message.get("more_body",False):
            break
    body=b"".join(chunks)
    Path(os.environ["ATLAS_BRIDGE_CAPTURE_FILE"]).write_bytes(body)
    print("bridge_captured_request_bytes="+str(len(body)),flush=True)
    first=True
    finished=asyncio.Event()
    async def replay():
        nonlocal first
        if first:
            first=False
            return {"type":"http.request","body":body,"more_body":False}
        await finished.wait()
        return {"type":"http.disconnect"}
    try:
        await real_app(scope,replay,send)
    finally:
        finished.set()
