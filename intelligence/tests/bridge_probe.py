"""CI-only ASGI wrapper: captures only sanitized bridge request JSON in a temp file."""
import os
from pathlib import Path
from app.main import app as real_app

async def app(scope, receive, send):
    if scope["type"]!="http" or scope.get("path")!="/api/v1/ai/analyze/TCS":
        await real_app(scope,receive,send)
        return
    messages=[]
    async def tap():
        message=await receive()
        if message["type"]=="http.request":
            messages.append(message.get("body",b""))
        return message
    await real_app(scope,tap,send)
    if messages:
        Path(os.environ["ATLAS_BRIDGE_CAPTURE_FILE"]).write_bytes(b"".join(messages))
