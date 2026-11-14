"""CI-only ASGI wrapper that buffers then replays the exact HTTP request body."""
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
            break
        chunks.append(message.get("body",b""))
        if not message.get("more_body",False):
            break
    body=b"".join(chunks)
    Path(os.environ["ATLAS_BRIDGE_CAPTURE_FILE"]).write_bytes(body)
    delivered=False
    async def replay():
        nonlocal delivered
        if not delivered:
            delivered=True
            return {"type":"http.request","body":body,"more_body":False}
        return {"type":"http.disconnect"}
    await real_app(scope,replay,send)
