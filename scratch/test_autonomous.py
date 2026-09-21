import asyncio
import json
from app.agent import app, root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def main():
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="app", user_id="test_user")
    runner = Runner(app=app, session_service=session_service)
    
    prompt = "My laptop screen keeps turning black when connected to the corporate VPN dock in London, and I have a board presentation in 30 minutes."
    print(f"--- USER PROMPT ---\n{prompt}\n")
    
    user_content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    
    events = []
    async for event in runner.run_async(user_id="test_user", session_id=session.id, new_message=user_content):
        events.append(event)
        print(f"EVENT: author={getattr(event, 'author', '')}, type={type(event).__name__}")
        if hasattr(event, "content") and event.content:
            for part in getattr(event.content, "parts", []):
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    print(f"  [TOOL CALL]: {fc.name}({fc.args})")
                elif getattr(part, "function_response", None):
                    fr = part.function_response
                    print(f"  [TOOL RESPONSE]: {fr.name} -> {str(fr.response)[:150]}...")
                elif getattr(part, "text", None):
                    print(f"  [TEXT PART]: {part.text[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
