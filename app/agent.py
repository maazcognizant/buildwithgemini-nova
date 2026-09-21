# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import random
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.code_executors.code_execution_utils import CodeExecutionInput
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from app.a2ui_utils import a2ui_callback

# Hardcoded project ID string required for Firestore client on Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-2f074985a624"
RAG_CORPUS_NAME = "projects/1091400127157/locations/us-central1/ragCorpora/1691620629565931520"
REASONING_ENGINE_RESOURCE = "projects/1091400127157/locations/us-central1/reasoningEngines/2845610309719162880"

# Agent Engine Sandbox Code Executor setup
sandbox_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=REASONING_ENGINE_RESOURCE
)


def _get_firestore_client():
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_it_knowledge_base(query: str) -> str:
    """Search the official Nova Corp Internal IT Policy and Troubleshooting Knowledge Base.

    Args:
        query: Policy or technical question (e.g. incident SLA definitions, VPN drops on macOS, docking station screen flicker, new hire provisioning timeline, hardware refresh cycles).

    Returns:
        Relevant internal IT policy guidelines and step-by-step troubleshooting instructions.
    """
    import vertexai
    from vertexai.preview import rag

    try:
        vertexai.init(project=FIRESTORE_PROJECT_ID, location="us-central1")
        resp = rag.retrieval_query(
            text=query,
            rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS_NAME)],
            rag_retrieval_config=rag.RagRetrievalConfig(top_k=5),
        )
        contexts = getattr(resp.contexts, "contexts", [])
        passages = [c.text.strip() for c in contexts if getattr(c, "text", "").strip()]
        return "\n\n---\n\n".join(passages) or "No relevant IT policy passage found."
    except Exception as e:
        return f"Knowledge base retrieval failed: {e}"


async def generate_diagnostic_diagram(
    issue_description: str,
    tool_context: ToolContext = None,
) -> str:
    """Generate a visual IT troubleshooting diagram or connection infographic for an IT issue using gemini-3.1-flash-lite-image in the global region.

    Saves the generated image as a session artifact and uploads it to public Cloud Storage bucket nova-it-assets-qwiklabs-gcp-03-2f074985a624.

    Args:
        issue_description: Detailed description of the IT issue or hardware/network setup needing a diagram.

    Returns:
        JSON string containing the public HTTPS URL of the generated diagnostic diagram in Cloud Storage and confirmation details.
    """
    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    prompt = (
        f"A clear, highly detailed enterprise IT troubleshooting diagram and infographic for: {issue_description}. "
        "Illustrate step-by-step diagnostic flow, connection topology, and hardware setup in a modern tech aesthetic."
    )

    try:
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
        )
    except Exception as e:
        return f"Failed to generate diagram image: {e}"

    image_bytes = None
    mime_type = "image/jpeg"
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"
                break

    if not image_bytes:
        return "Error: Image model did not return image data for the diagram."

    ext = "png" if "png" in mime_type.lower() else "jpg"
    filename = f"diagnostic_diagram_{uuid.uuid4().hex[:8]}.{ext}"

    # 1. Save artifact for Playground Artifacts panel
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            await tool_context.save_artifact(
                filename=filename,
                artifact=types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            )
        except Exception as e:
            print(f"Warning: Failed to save artifact in session: {e}")

    # 2. Upload image bytes to public Cloud Storage bucket
    bucket_name = "nova-it-assets-qwiklabs-gcp-03-2f074985a624"
    try:
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(bucket_name)
        blob_name = f"diagrams/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
    except Exception as e:
        return f"Failed to upload diagram image to Cloud Storage: {e}"

    return json.dumps(
        {
            "message": "Diagnostic diagram generated and uploaded successfully.",
            "artifact_filename": filename,
            "public_url": public_url,
        },
        indent=2,
    )


def calculate_sla_risk(
    priority: str,
    created_at: str,
    tool_context: ToolContext = None,
) -> str:
    """Calculate SLA deadline, time remaining, and breach-risk percentage for an IT support ticket using secure Python code execution in an Agent Engine Sandbox.

    Args:
        priority: Incident priority level ('P1' = Critical 1h, 'P2' = High 4h, 'P3' = Standard 24h, 'P4' = Low 72h).
        created_at: Creation timestamp string of the ticket in ISO format (e.g. '2026-09-21T18:00:00Z').

    Returns:
        Formatted summary containing the calculated SLA deadline, time remaining until breach, and breach-risk percentage.
    """
    code = f"""
import datetime

created_at_str = "{created_at}"
priority = "{priority.upper().strip()}"
sla_hours = {{"P1": 1, "P2": 4, "P3": 24, "P4": 72}}.get(priority, 24)

try:
    created_at_dt = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
except Exception:
    created_at_dt = datetime.datetime.now(datetime.timezone.utc)

now_dt = datetime.datetime.now(datetime.timezone.utc)
sla_deadline_dt = created_at_dt + datetime.timedelta(hours=sla_hours)

elapsed_seconds = max(0.0, (now_dt - created_at_dt).total_seconds())
total_sla_seconds = sla_hours * 3600.0
remaining_seconds = max(0.0, (sla_deadline_dt - now_dt).total_seconds())

risk_pct = min(100.0, max(0.0, (elapsed_seconds / total_sla_seconds) * 100.0))

print(f"SLA Target Duration: {{sla_hours}} hours")
print(f"Ticket Created At: {{created_at_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}}")
print(f"Calculated SLA Deadline: {{sla_deadline_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}}")
print(f"Time Remaining Until SLA Breach: {{remaining_seconds / 3600:.2f}} hours ({{remaining_seconds / 60:.1f}} minutes)")
print(f"SLA Breach Risk Level: {{risk_pct:.1f}}%")
"""

    if tool_context and hasattr(tool_context, "_invocation_context") and tool_context._invocation_context:
        inv_ctx = tool_context._invocation_context
    else:
        from google.adk.sessions.in_memory_session_service import InMemorySessionService
        from google.adk.sessions.session import Session

        inv_ctx = InvocationContext(
            session=Session(id="sandbox-session", app_name="nova-app", user_id="sandbox-user", state={}),
            session_service=InMemorySessionService(),
            invocation_id="sandbox-inv-1",
        )

    try:
        res = sandbox_executor.execute_code(
            invocation_context=inv_ctx,
            code_execution_input=CodeExecutionInput(code=code),
        )
        out = (res.stdout or "").strip()
        if not out and res.stderr:
            out = f"Sandbox stderr output:\n{res.stderr.strip()}"
        return out or "SLA risk calculation complete in sandbox."
    except Exception as e:
        return f"Sandbox code execution error: {e}"


def create_ticket(
    employee_name: str,
    department: str,
    role: str,
    issue_description: str,
    priority: str = "P3",
) -> str:
    """Create a new IT support incident ticket in the Firestore backend.

    Args:
        employee_name: Full name of the reporting employee.
        department: Employee department (e.g. Engineering, Finance, HR, Sales, Operations).
        role: Employee job role/title.
        issue_description: Detailed description of the technical issue or service request.
        priority: Priority level ('P1' = Critical outage/blocker, 'P2' = High urgency, 'P3' = Standard issue, 'P4' = Low request).

    Returns:
        JSON string containing the created ticket details, ticket_id, SLA deadline, and assigned team.
    """
    db = _get_firestore_client()
    ticket_num = random.randint(1005, 9999)
    ticket_id = f"TICKET-{ticket_num}"

    # Auto-assign team based on issue keywords
    desc_lower = issue_description.lower()
    if any(k in desc_lower for k in ["k8s", "kubernetes", "latency", "outage", "production", "cluster", "crash"]):
        assigned_team = "Site Reliability Engineering (SRE)"
    elif any(k in desc_lower for k in ["vpn", "network", "wifi", "internet", "dns", "firewall"]):
        assigned_team = "Network Operations"
    elif any(k in desc_lower for k in ["access", "permission", "iam", "sso", "login", "auth", "onboarding"]):
        assigned_team = "Identity & Access Management (IAM)"
    elif any(k in desc_lower for k in ["macbook", "laptop", "hardware", "monitor", "device", "screen", "dock"]):
        assigned_team = "Endpoint Hardware Support"
    else:
        assigned_team = "General IT Helpdesk"

    # Compute SLA deadline based on priority
    now = datetime.datetime.now(datetime.timezone.utc)
    sla_hours = {"P1": 1, "P2": 4, "P3": 24, "P4": 72}.get(priority, 24)
    sla_deadline = (now + datetime.timedelta(hours=sla_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    created_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    ticket_data = {
        "ticket_id": ticket_id,
        "employee_name": employee_name,
        "department": department,
        "role": role,
        "issue_description": issue_description,
        "priority": priority,
        "status": "open",
        "assigned_team": assigned_team,
        "created_at": created_at,
        "sla_deadline": sla_deadline,
    }

    db.collection("tickets").document(ticket_id).set(ticket_data)
    return json.dumps(
        {
            "message": "Ticket created successfully in Firestore.",
            "ticket": ticket_data,
        },
        indent=2,
    )


def get_ticket_status(ticket_id: str) -> str:
    """Retrieve the status and details of an IT support ticket from Firestore by ticket ID.

    Args:
        ticket_id: The unique ID of the ticket (e.g. 'TICKET-1001', 'ticket-1001', '1001', 'TICKET-4800').

    Returns:
        JSON string with complete ticket record or {"found": false, "message": ...} if not found.
    """
    db = _get_firestore_client()
    raw_id = str(ticket_id).strip()

    import re
    num_match = re.search(r'\d+', raw_id)
    clean_num = num_match.group(0) if num_match else raw_id
    formatted_id = f"TICKET-{clean_num}" if num_match else raw_id.upper()

    doc_ref = db.collection("tickets").document(formatted_id)
    doc = doc_ref.get()

    if not doc.exists and raw_id != formatted_id:
        doc_ref = db.collection("tickets").document(raw_id)
        doc = doc_ref.get()

    if not doc.exists:
        doc_ref = db.collection("tickets").document(raw_id.upper())
        doc = doc_ref.get()

    if not doc.exists:
        docs = list(db.collection("tickets").where("ticket_id", "==", formatted_id).stream())
        if not docs:
            docs = list(db.collection("tickets").where("ticket_id", "==", raw_id).stream())
        if not docs:
            docs = list(db.collection("tickets").where("ticket_id", "==", raw_id.upper()).stream())
        if docs:
            doc = docs[0]

    if not doc.exists:
        return json.dumps(
            {
                "found": False,
                "message": f"No ticket found with ID {formatted_id}",
            },
            indent=2,
        )

    tdata = doc.to_dict()
    tdata["ticket_id"] = doc.id
    return json.dumps(
        {
            "found": True,
            "ticket_id": doc.id,
            "details": tdata,
        },
        indent=2,
    )


def list_all_tickets(status: str | None = None) -> str:
    """Retrieve all IT support tickets from Firestore.

    Args:
        status: Optional filter status ('open', 'in-progress', 'escalated', 'resolved').

    Returns:
        JSON string containing the total count and list of all ticket records from Firestore.
    """
    db = _get_firestore_client()
    docs = list(db.collection("tickets").stream())
    out = []
    for d in docs:
        data = d.to_dict()
        data["ticket_id"] = d.id
        if status:
            if data.get("status", "").lower() == status.lower().strip():
                out.append(data)
        else:
            out.append(data)

    return json.dumps(
        {
            "total_tickets": len(out),
            "tickets": out,
        },
        indent=2,
    )



def update_or_escalate_ticket(
    ticket_id: str,
    new_status: str,
    escalation_reason: str | None = None,
    new_priority: str | None = None,
) -> str:
    """Update status, escalate, or adjust priority of an existing IT support ticket in Firestore.

    Args:
        ticket_id: The unique ticket identifier (e.g. 'TICKET-1001').
        new_status: Target status ('open', 'in-progress', 'escalated', 'resolved').
        escalation_reason: Optional explanation if escalating the ticket.
        new_priority: Optional updated priority level ('P1', 'P2', 'P3', 'P4').

    Returns:
        JSON string summarizing the updated ticket state.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("tickets").document(ticket_id.strip())
    doc = doc_ref.get()

    if not doc.exists:
        return json.dumps({"error": f"Ticket '{ticket_id}' not found."}, indent=2)

    data = doc.to_dict()
    updates = {"status": new_status, "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    if new_priority:
        updates["priority"] = new_priority
    elif new_status == "escalated" and data.get("priority") in ["P3", "P4"]:
        updates["priority"] = "P2"  # Automatically bump priority on escalation

    if escalation_reason:
        updates["escalation_reason"] = escalation_reason
        data["notes"] = f"{data.get('notes', '')}\n[ESCALATION NOTE]: {escalation_reason}".strip()
        updates["notes"] = data["notes"]

    doc_ref.update(updates)
    data.update(updates)

    return json.dumps(
        {
            "message": f"Ticket '{ticket_id}' updated successfully to status '{new_status}'.",
            "updated_ticket": data,
        },
        indent=2,
    )


def get_weather(query: str) -> str:
    """Simulates getting weather info for a location."""
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting current time for a location."""
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: Send conversation session to Vertex AI Memory Bank after each turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        # Ignore memory service errors (e.g. in local dev/playground environment)
        pass
    return None


a2ui_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = a2ui_schema_manager.generate_system_prompt(
    role_description=(
        "You are Nova, an enterprise IT service-desk concierge. You manage IT support tickets backed by Firestore, "
        "retrieve official corporate IT guidelines from the internal RAG knowledge base, perform code execution in an Agent Engine Sandbox, "
        "and generate visual IT troubleshooting diagrams."
    ),
    workflow_description=(
        "CRITICAL AUTONOMOUS MULTI-TOOL ORCHESTRATION INSTRUCTIONS:\n"
        "When an employee reports a new IT issue or technical problem (e.g., hardware failure, VPN drops, docking station screen flicker, presentation blocker):\n"
        "You MUST execute ALL of the following tools AUTONOMOUSLY in a single turn without waiting or asking step-by-step:\n"
        "1. `search_it_knowledge_base(query)`: Search official IT policy and troubleshooting knowledge base for immediate workarounds.\n"
        "2. `create_ticket(employee_name, department, role, issue_description, priority)`: Assess business impact and urgency (use P1 for executive events or urgent blockers like a board presentation in <1 hour; P2 for high impact; P3 for standard; P4 for low) and create a new Firestore ticket.\n"
        "3. `calculate_sla_risk(priority, created_at)`: Call this tool using the newly created ticket's priority and created_at timestamp to execute Python in the sandbox and compute SLA deadline, time remaining, and breach risk.\n"
        "4. `generate_diagnostic_diagram(issue_description)`: If the issue involves hardware, displays, monitors, docking stations, VPN, or network infrastructure, proactively generate a visual diagnostic diagram.\n"
        "5. Present all findings in one comprehensive response: provide the immediate workaround from knowledge base, ticket details, calculated SLA risk analysis, and an A2UI Card containing ticket ID, color-coded priority badge ([P1 - CRITICAL], [P2 - HIGH], [P3 - STANDARD], [P4 - LOW]), status, assigned team, SLA info, and the public HTTPS diagram URL.\n\n"
        "For ticket status queries (e.g. 'What is the status of TICKET-1001?' or 'ticket 4800'):\n"
        "1. Call `get_ticket_status(ticket_id)`.\n"
        "2. If `found: true`: Render an A2UI Card with the ticket ID, priority badge, status, assigned team, and SLA details.\n"
        "3. If `found: false`: DO NOT render a complex ticket status card or output empty card JSON. Simply respond with a helpful message: 'I couldn't find a ticket with that ID. Please double check the ticket number, or I can create a new ticket for this issue.'"
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. Never nest a Card inside a Card.\n"
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use Table or Heading (unsupported), or Buttons, actions, or forms (they do nothing in adk web).\n"
        "Whenever rendering ticket information or ticket updates, emit an A2UI Card containing:\n"
        "- Ticket ID (e.g. TICKET-1001)\n"
        "- Priority with color-coded status badge: Red for P1 ('[P1 - CRITICAL]'), Orange for P2 ('[P2 - HIGH]'), Yellow for P3 ('[P3 - STANDARD]'), Green for P4 ('[P4 - LOW]').\n"
        "- Status (open, in-progress, escalated, resolved)\n"
        "- Assigned Team\n"
        "- SLA Info (deadline, time remaining, and breach risk percentage).\n"
        "If a diagnostic diagram was generated, include it as an Image component in the card pointing at its exact public https URL (e.g. {\"Image\": {\"url\": {\"literalString\": \"https://storage.googleapis.com/...\"}}}). Never point an Image at a bare filename or non-http(s) path.\n"
        "IF A TICKET IS NOT FOUND (`found: false`): DO NOT output an empty or malformed card. Respond with a clean text message or simple Card: 'I couldn't find a ticket with that ID. Please double check the ticket number, or I can create a new ticket for this issue.'\n"
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for headings and emphasis.\n"
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in <a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=sandbox_executor,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        search_it_knowledge_base,
        calculate_sla_risk,
        generate_diagnostic_diagram,
        create_ticket,
        get_ticket_status,
        list_all_tickets,
        update_or_escalate_ticket,
        get_weather,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
