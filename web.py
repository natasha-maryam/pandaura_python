from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv
import json
import re
import uuid
import os

# Load environment variables
load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.chat_histories: dict[str, ChatMessageHistory] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if client_id not in self.chat_histories:
            self.chat_histories[client_id] = ChatMessageHistory()

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.chat_histories:
            del self.chat_histories[client_id]

manager = ConnectionManager()

# Initialize the LLM
llm = ChatOpenAI(
    model_name="gpt-4",
    temperature=0.7
)

system_prompt = """
You are Pandaura AS — a co-engineer assistant for automation & controls work (PLC logic, I/O,
safety, commissioning docs, diagnostics, refactoring, prompt-to-logic generation).
PRIMARY OBJECTIVES
1) Deliver accurate, useful, implementation-ready guidance for industrial automation scenarios.
2) Proactively reduce user effort: propose improvements, call out risks, and suggest next steps.
3) Always finish with a single, contextual next-step question to drive the work forward.
BEHAVIORAL RULES
- Co-Engineer Mindset: Do not blindly agree. If the user’s request has gaps, conflicts, or risky
assumptions, point them out and suggest fixes. Offer trade-offs where relevant.
- Truth & Auditability: If you’re unsure, say so clearly and either (a) reason it out with
assumptions or (b) ask for the specific info needed to proceed. Prefer verifiable references
(standards, manuals) when you cite facts.
- Admit Faults: If you realize you made a mistake, acknowledge it plainly, correct it, and keep
going.
- Brevity by Default: Prefer concise, high-signal answers. Use lists, code blocks, or tables only
when they improve clarity.
- User’s Format: Match the user’s target (e.g., Siemens S7-1500 SCL, Rockwell ST, Beckhoff
ST). Use clean naming, comments, and clear structure.
OUTPUT CONTRACT
- Start with the answer or artifact (don’t bury the lede).
- If code is requested, provide complete, runnable snippets with essential comments.
- If giving steps/checklists, number them and keep items actionably short.
- End every message with:
`Next step → <one concrete, contextual question that advances their goal>`
CRITICAL THINKING / NON-AGREEMENT
- Before responding, quickly validate the user’s ask:
• Is the requirement feasible/safe?
• Are any specs contradictory or underspecified?
• Are there edge cases (faults, interlocks, timing, safety) that must be handled?
- If something is wrong or risky, state it plainly, propose a safer/correct alternative, and explain
the impact in one sentence.
SAFETY & GUARDRAILS
- Refuse or safely redirect any request that involves: personal harm or self-harm; sexual
violence or sexual content involving minors; illegal activities, creation of malware or intrusive
surveillance; instructions to physically endanger people; discrimination or hate.
- Sensitive scenarios (e.g., suicide, self-harm): respond with a brief, compassionate refusal and
encourage seeking professional help or emergency services if there is imminent danger.
- Industrial safety: never bypass safety circuits/interlocks; never recommend defeating E-Stops,
guards, or standards compliance (e.g., IEC 62061/61508/60204-1, ISO 13849). If asked, refuse
and offer compliant alternatives.
- Data & Privacy: do not reveal secrets or proprietary content. Summarize rather than verbatim
copying when unsure about rights.
QUALITY BAR FOR LOGIC GENERATION
- Deterministic scan behavior; explicit timers; no hidden states.
- Clear modular structure (e.g., OB1/OB100 for Siemens; FBs with instance DBs; UDTs for
devices and alarms).
- Comment public tags and block headers with purpose and assumptions.
- Include test hooks: diagnostics/status bits, simple simulation flags, and a sanity checklist.
TONE & STYLE
- Professional, direct, and collaborative.
- No hype. No filler. Focus on outcomes.
END-OF-REPLY REQUIREMENT (MANDATORY)
- Every response MUST end with exactly one line in this format:
`Next step → <one specific, contextual question>`

OUTPUT CONTRACT
You must always respond in valid JSON format with the following fields:

{{
   "code": "<only the code if present, otherwise empty string>",
   "feature_detected": "<'code', 'greeting', or 'generic'>",
   "next_step": "<one contextual next-step question>",
   "file_name": "<always empty string for now>",
   "summary": "<short natural language explanation or paraphrase>"
}}

RULES:
- If the user’s message is casual (greeting, small talk, off-topic):
  * Leave `code` empty.
  * Set `feature_detected` = "greeting".
  * Put the natural language response in `summary`.
- If the response includes code:
  * Put only the raw code inside `code`.
  * Set `feature_detected` = "code".
  * In `summary`, provide a short, natural language paraphrase of what the code does.
- If no code and not a greeting:
  * Leave `code` empty.
  * Set `feature_detected` = "generic".
  * Put your natural language response in `summary`.
- The `summary` must **never** repeat the code. It must be an explanation or paraphrase in plain language.
- The JSON must be valid and parsable.
note:: Read the message cerefully dont make mistakes. if user asks for code giv
code . if user asks for summary give summary. if user asks for greeting give greeting.
whatever user asks make sure to give correct answer
"""

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)

    # Create the prompt with system message and chat history
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])

    # Create the chain
    chain = prompt | llm

    # Create a runnable with message history
    runnable_with_history = RunnableWithMessageHistory(
        chain,
        lambda session_id: manager.chat_histories.get(session_id, ChatMessageHistory()),
        input_messages_key="input",
        history_messages_key="history",
    )
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            print(f"Received message from {client_id}: {data}")
            
            try:
                # Parse the incoming message
                message_data = json.loads(data)
                user_message = message_data.get("message", "").strip()
                
                if not user_message:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Empty message received"
                    })
                    continue
                
                # Generate response
                print(f"Generating response for {client_id}")
                response = await runnable_with_history.ainvoke(
                    {"input": user_message},
                    {"configurable": {"session_id": client_id}}
                )
                
                resp_text = response.content.strip()

                # Initialize default structured response
                structured_response = {
                    "code": "",
                    "feature_detected": "generic",
                    "next_step": "",
                    "file_name": "",
                    "summary": ""
                }

                try:
                    # Try to parse response as JSON
                    parsed_response = json.loads(resp_text)
                    structured_response.update({
                        "code": parsed_response.get("code", ""),
                        "feature_detected": parsed_response.get("feature_detected", "generic"),
                        "next_step": parsed_response.get("next_step", ""),
                        "file_name": parsed_response.get("file_name", ""),
                        "summary": parsed_response.get("summary", "")
                    })
                except json.JSONDecodeError:
                    # Fallback to regex-based extraction
                    # Extract code block
                    code_match = re.search(r"```(?:\w+)?\n([\s\S]*?)```", resp_text)
                    if code_match:
                        structured_response["code"] = code_match.group(1).strip()
                        structured_response["feature_detected"] = "code"
                        summary = re.sub(r"```(?:\w+)?\n[\s\S]*?```", "", resp_text).strip()
                    else:
                        summary = resp_text
                        if any(word in resp_text.lower() for word in ["hello", "hi", "hey", "greetings"]):
                            structured_response["feature_detected"] = "greeting"

                    # Extract next_step
                    next_step_match = re.search(r"Next step\s*→\s*(.*)", summary)
                    if next_step_match:
                        structured_response["next_step"] = next_step_match.group(1).strip()
                        summary = re.sub(r"Next step\s*→\s*.*", "", summary).strip()

                    structured_response["summary"] = re.sub(r"\n\s*\n", "\n", summary).strip()

                # Ensure summary does not contain JSON or code
                if structured_response["code"]:
                    structured_response["summary"] = re.sub(
                        re.escape(structured_response["code"]), 
                        "", 
                        structured_response["summary"]
                    ).strip()
                structured_response["summary"] = re.sub(r"\{[\s\S]*\}", "", structured_response["summary"]).strip()

                # Send JSON response
                await websocket.send_json({
                    "type": "response",
                    "content": structured_response
                })
                print(f"Response sent to {client_id}: {json.dumps(structured_response, indent=2)}")
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "content": "Invalid JSON format. Please send a JSON object with a 'message' field."
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "content": f"Error processing message: {str(e)}"
                })
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {client_id}")
        manager.disconnect(client_id)
    except Exception as e:
        print(f"Unexpected error with {client_id}: {str(e)}")
        manager.disconnect(client_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)












# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.middleware.cors import CORSMiddleware
# from langchain_openai import ChatOpenAI
# from langchain.memory import ConversationBufferMemory
# from langchain.chains import ConversationChain
# from langchain_core.runnables.history import RunnableWithMessageHistory
# from dotenv import load_dotenv
# from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
# import json
# import os
# from langchain_community.chat_message_histories import ChatMessageHistory
# from langchain_core.chat_history import BaseChatMessageHistory
# from langchain_core.prompts import MessagesPlaceholder
# import uuid

# # Load environment variables
# load_dotenv()

# app = FastAPI()

# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: Dict[str, WebSocket] = {}
#         self.chat_histories: Dict[str, BaseChatMessageHistory] = {}

#     async def connect(self, websocket: WebSocket, client_id: str):
#         await websocket.accept()
#         self.active_connections[client_id] = websocket
#         if client_id not in self.chat_histories:
#             self.chat_histories[client_id] = ChatMessageHistory()

#     def disconnect(self, client_id: str):
#         if client_id in self.active_connections:
#             del self.active_connections[client_id]
#         if client_id in self.chat_histories:
#             del self.chat_histories[client_id]

# manager = ConnectionManager()

# # Initialize the LLM
# llm = ChatOpenAI(
#     model_name="gpt-4",
#     temperature=0.7
# )

# system_prompt = """
# You are Pandaura AS — a co-engineer assistant for automation & controls work (PLC logic, I/O,
# safety, commissioning docs, diagnostics, refactoring, prompt-to-logic generation).
# PRIMARY OBJECTIVES
# 1) Deliver accurate, useful, implementation-ready guidance for industrial automation scenarios.
# 2) Proactively reduce user effort: propose improvements, call out risks, and suggest next steps.
# 3) Always finish with a single, contextual next-step question to drive the work forward.
# BEHAVIORAL RULES
# - Co-Engineer Mindset: Do not blindly agree. If the user’s request has gaps, conflicts, or risky
# assumptions, point them out and suggest fixes. Offer trade-offs where relevant.
# - Truth & Auditability: If you’re unsure, say so clearly and either (a) reason it out with
# assumptions or (b) ask for the specific info needed to proceed. Prefer verifiable references
# (standards, manuals) when you cite facts.
# - Admit Faults: If you realize you made a mistake, acknowledge it plainly, correct it, and keep
# going.
# - Brevity by Default: Prefer concise, high-signal answers. Use lists, code blocks, or tables only
# when they improve clarity.
# - User’s Format: Match the user’s target (e.g., Siemens S7-1500 SCL, Rockwell ST, Beckhoff
# ST). Use clean naming, comments, and clear structure.
# OUTPUT CONTRACT
# - Start with the answer or artifact (don’t bury the lede).
# - If code is requested, provide complete, runnable snippets with essential comments.
# - If giving steps/checklists, number them and keep items actionably short.
# - End every message with:
# `Next step → <one concrete, contextual question that advances their goal>`
# CRITICAL THINKING / NON-AGREEMENT
# - Before responding, quickly validate the user’s ask:
# • Is the requirement feasible/safe?
# • Are any specs contradictory or underspecified?
# • Are there edge cases (faults, interlocks, timing, safety) that must be handled?
# - If something is wrong or risky, state it plainly, propose a safer/correct alternative, and explain
# the impact in one sentence.SAFETY & GUARDRAILS
# - Refuse or safely redirect any request that involves: personal harm or self-harm; sexual
# violence or sexual content involving minors; illegal activities, creation of malware or intrusive
# surveillance; instructions to physically endanger people; discrimination or hate.
# - Sensitive scenarios (e.g., suicide, self-harm): respond with a brief, compassionate refusal and
# encourage seeking professional help or emergency services if there is imminent danger.
# - Industrial safety: never bypass safety circuits/interlocks; never recommend defeating E-Stops,
# guards, or standards compliance (e.g., IEC 62061/61508/60204-1, ISO 13849). If asked, refuse
# and offer compliant alternatives.
# - Data & Privacy: do not reveal secrets or proprietary content. Summarize rather than verbatim
# copying when unsure about rights.
# QUALITY BAR FOR LOGIC GENERATION
# - Deterministic scan behavior; explicit timers; no hidden states.
# - Clear modular structure (e.g., OB1/OB100 for Siemens; FBs with instance DBs; UDTs for
# devices and alarms).
# - Comment public tags and block headers with purpose and assumptions.
# - Include test hooks: diagnostics/status bits, simple simulation flags, and a sanity checklist.
# TONE & STYLE
# - Professional, direct, and collaborative.
# - No hype. No filler. Focus on outcomes.
# END-OF-REPLY REQUIREMENT (MANDATORY)
# - Every response MUST end with exactly one line in this format next step:
# <one specific, contextual question>

# OUTPUT CONTRACT
# You must always respond in valid JSON format with the following fields:

# {{
#    "code": "<only the code if present, otherwise empty string>",
#    "feature_detected": "<'code', 'greeting', or 'generic'>",
#    "next_step": "<one contextual next-step question>",
#    "file_name": "<always empty string for now>",
#    "summary": "<short natural language explanation or paraphrase>"
# }}

# RULES:
# - If the user’s message is casual (greeting, small talk, off-topic):
#   * Leave `code` empty.
#   * Set `feature_detected` = "greeting".
#   * Put the natural language response in `summary`.
# - If the response includes code:
#   * Put only the raw code inside `code`.
#   * Set `feature_detected` = "code".
#   * In `summary`, provide a short, natural language paraphrase of what the code does.
# - If no code and not a greeting:
#   * Leave `code` empty.
#   * Set `feature_detected` = "generic".
#   * Put your natural language response in `summary`.
# - The `summary` must **never** repeat the code. It must be an explanation or paraphrase in plain language.
# - The JSON must be valid and parsable.
# """

# @app.websocket("/ws/chat")
# async def websocket_endpoint(websocket: WebSocket):
#     client_id = str(uuid.uuid4())
#     await manager.connect(websocket, client_id)

#     # Create the prompt with system message and chat history
#     prompt = ChatPromptTemplate.from_messages([
#         ("system", system_prompt),
#         MessagesPlaceholder(variable_name="history"),
#         ("human", "{input}")
#     ])

#     # Create the chain
#     chain = prompt | llm

#     # Create a runnable with message history
#     runnable_with_history = RunnableWithMessageHistory(
#         chain,
#         lambda session_id: manager.chat_histories.get(session_id, ChatMessageHistory()),
#         input_messages_key="input",
#         history_messages_key="history",
#     )
    
#     try:
#         while True:
#             # Receive message from client
#             data = await websocket.receive_text()
#             print(f"Received message from {client_id}: {data}") 
            
#             try:
#                 # Parse the incoming message
#                 message_data = json.loads(data)
#                 user_message = message_data.get("message", "").strip()
                
#                 if not user_message:
#                     await websocket.send_json({
#                         "type": "error",
#                         "content": "Empty message received"
#                     })
#                     continue
                
#                 # Generate response
#                 print(f"Generating response for {client_id}")
#                 response = await runnable_with_history.ainvoke(
#                     {"input": user_message},
#                     {"configurable": {"session_id": client_id}}
#                 )
                
#                 # # Send the response back to the client
#                 # await websocket.send_json({
#                 #     "type": "response",
#                 #     "content": response.content
#                 # })
#                 # import re

#                 # resp_text = response.content.strip()

#                 # # 1. Extract next_step (last line starting with "Next step →")
#                 # next_step_match = re.search(r"Next step\s*→\s*(.*)", resp_text)
#                 # next_step = next_step_match.group(1).strip() if next_step_match else ""

#                 # # 2. Detect code blocks
#                 # code_match = re.search(r"```(?:\w+)?\n([\s\S]*?)```", resp_text)
#                 # if code_match:
#                 #     feature_detected = "code"
#                 #     code = code_match.group(1).strip()
#                 #     summary = code  # or resp_text without code
#                 # else:
#                 #     # Greeting detection (basic)
#                 #     if any(word in resp_text.lower() for word in ["hello", "hi", "hey", "greetings"]):
#                 #         feature_detected = "greeting"
#                 #         code = ""
#                 #         summary = resp_text
#                 #     else:
#                 #         feature_detected = "generic"
#                 #         code = ""
#                 #         summary = resp_text

#                 # # 3. Build structured response
#                 # structured_response = {
#                 #     "code": code,
#                 #     "feature_detected": feature_detected,
#                 #     "next_step": next_step,
#                 #     "file_name": "",
#                 #     "summary": summary
#                 # }

#                 resp_text = response.content.strip()

#                 try:
#                     # The model should already return valid JSON
#                     structured_response = json.loads(resp_text)
#                 except json.JSONDecodeError:
#                     # fallback if model failed JSON formatting
#                     structured_response = {
#                         "code": "",
#                         "feature_detected": "generic",
#                         "next_step": "",
#                         "file_name": "",
#                         "summary": resp_text
#                     }
#                 # 4. Send JSON response
#                 await websocket.send_json({
#                     "type": "response",
#                     "content": structured_response
#                 })
#                 print(structured_response)
#                 print(f"Response sent to {client_id}")  # Debug log
                
#             except json.JSONDecodeError:
#                 # print(f"JSON Error for {client_id}: {error_msg}")  # Debug log
#                 await websocket.send_json({
#                     "type": "error",
#                     "content": "Invalid JSON format. Please send a JSON object with a 'message' field."
#                 })
#             except Exception as e:
#                 # print(f"Error for {client_id}: {error_msg}")  # Debug log
#                 await websocket.send_json({
#                     "type": "error",
#                     "content": f"Error processing message: {str(e)}"
#                 })
                
#     except WebSocketDisconnect:
#         print(f"WebSocket disconnected: {client_id}")  # Debug log
#         manager.disconnect(client_id)
#     except Exception as e:
#         print(f"Unexpected error with {client_id}: {str(e)}")
#         manager.disconnect(client_id)

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)