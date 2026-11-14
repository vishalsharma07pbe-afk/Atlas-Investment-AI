"""CI-only ASGI tap; forward each original receive message unchanged."""
import os
from pathlib import Path
from app.main import app as real_app

async def app(scope, receive, send):
    if scope["type"]!="http" or scope.get("path")!="/api/v1/ai/analyze/TCS":
        await real_app(scope,receive,send)
        return
    captured=bytearray()
    async def tapped_receive():
        message=await receive()
        if message["type"]=="http.request":
            captured.extend(message.get("body",b""))
            if not message.get("more_body",False):
                Path(os.environ["ATLAS_BRIDGE_CAPTURE_FILE"]).write_bytes(captured)
        return message
    await real_app(scope,tapped_receive,send)
