"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.
"""

import json
import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TextPart,
    TransportProtocol,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    svg_favicon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="8" fill="#13161f"/>
<circle cx="16" cy="16" r="6" fill="#3b82f6"/>
</svg>"""
    return Response(content=svg_favicon, media_type="image/svg+xml")


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        card = AgentCard(**resp.json())
        card.url = A2A_BASE
        _card = card
    return _card


def _extract_parts(parts: list) -> list[dict]:
    out: list[dict] = []
    for p in parts:
        root = getattr(p, "root", p)
        text_val = getattr(root, "text", None) if not isinstance(root, dict) else root.get("text")
        if text_val:
            if "<a2ui-json>" in text_val or "<a2a_datapart_json>" in text_val:
                clean = (
                    text_val.replace("<a2ui-json>", "")
                    .replace("</a2ui-json>", "")
                    .replace("<a2a_datapart_json>", "")
                    .replace("</a2a_datapart_json>", "")
                    .strip()
                )
                try:
                    data = json.loads(clean)
                    out.append({"kind": "a2ui", "data": data})
                    continue
                except Exception:
                    pass
            out.append({"kind": "text", "text": text_val})
            continue

        data_val = getattr(root, "data", None) if not isinstance(root, dict) else root.get("data")
        meta = (getattr(root, "metadata", None) if not isinstance(root, dict) else root.get("metadata")) or {}
        mime = meta.get("mimeType") if isinstance(meta, dict) else None

        if data_val is not None:
            if mime == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": data_val})
            elif isinstance(data_val, (dict, list)):
                out.append({"kind": "a2ui", "data": data_val})
            elif isinstance(data_val, str) and ("<a2a_datapart_json>" in data_val or "<a2ui-json>" in data_val):
                clean = (
                    data_val.replace("<a2ui-json>", "")
                    .replace("</a2ui-json>", "")
                    .replace("<a2a_datapart_json>", "")
                    .replace("</a2a_datapart_json>", "")
                    .strip()
                )
                try:
                    data = json.loads(clean)
                    out.append({"kind": "a2ui", "data": data})
                except Exception:
                    out.append({"kind": "text", "text": data_val})
            elif isinstance(data_val, str):
                out.append({"kind": "text", "text": data_val})
            continue

        file_obj = getattr(root, "file", None) if not isinstance(root, dict) else root.get("file")
        if file_obj:
            uri = getattr(file_obj, "uri", None) if not isinstance(file_obj, dict) else file_obj.get("uri")
            if uri:
                out.append({"kind": "text", "text": uri})
    return out


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
            context_id=_contexts.get(user_id),
        )

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(msg):
            task, update = event if isinstance(event, tuple) else (event, None)
            if task is not None:
                last_task = task
                if getattr(task, "context_id", None):
                    _contexts[user_id] = task.context_id
            if isinstance(update, TaskArtifactUpdateEvent):
                got_artifact_update = True
                parts.extend(_extract_parts(getattr(getattr(update, "artifact", None), "parts", [])))

        if not got_artifact_update and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                parts.extend(_extract_parts(getattr(artifact, "parts", [])))

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


@app.get("/api/tickets")
async def get_tickets():
    try:
        from google.cloud import firestore
        db = firestore.Client(project="qwiklabs-gcp-03-2f074985a624")
        docs = db.collection("tickets").stream()
        out = []
        for d in docs:
            data = d.to_dict()
            data["ticket_id"] = d.id
            out.append(data)
        return JSONResponse({"tickets": out})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
# Serve the chat UI (keep this mount last so /chat wins).
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
