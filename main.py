from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from generator.orchestrator import Orchestrator
from typing import Optional
import os

# Initialize FastAPI
app = FastAPI(
    title="PLC Code Generator API",
    description="API for generating PLC code from specifications",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize orchestrator
orchestrator = Orchestrator("output")

class CodeRequest(BaseModel):
    spec_text: str
    project_name: str = "PandauraProject"
    vendor: Optional[str] = None

@app.post("/generate_code")
async def generate_code(request: CodeRequest):
    """
    Generate PLC code based on the provided specification.
    
    - **spec_text**: Detailed specification of the PLC program
    - **project_name**: Name for the generated project (default: "PandauraProject")
    - **vendor**: Optional vendor (siemens, rockwell, beckhoff). Auto-detected if not provided.
    """
    try:
        result = orchestrator.generate(
            spec_text=request.spec_text,
            vendor=request.vendor,
            project_name=request.project_name
        )
        return {
            "status": "success",
            "data": result,
            "message": "Code generated successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(e)
            }
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "plc-code-generator"}

# Local dev entrypoint
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)










# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from openai import OpenAI
# from dotenv import load_dotenv
# import os
# from typing import Dict, Any, List
# from dataclasses import dataclass  # Added this import
# import json

# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# print(client)

# app = FastAPI()

# class CodeRequest(BaseModel):
#     spec_text: str

# @dataclass
# class VendorProfile:
#     name: str
#     lang: str
#     file_ext: str
#     system_prompt: str
#     completeness_checklist: str
#     file_plan_prompt: str
#     module_prompt: str
#     critic_prompt: str
#     pack_prompt: str

# SIEMENS_PROFILE = VendorProfile(
#     name="siemens",
#     lang="SCL",
#     file_ext=".scl",
#     system_prompt="You are a Siemens S7-1500 SCL code generator. Follow IEC 61131-3, use clean structure with OB1, OB100, FBs, instance DBs, and UDTs. Comment every public tag and FB header.",
#     completeness_checklist="Check for OB1 (cyclic), OB100 (startup with E-Stop), FBs (Conveyors, Merge/Divert, PalletizerHS, Modes, Alarms, Diag, Comms) with instance DBs, UDTs for devices/alarms/state, operating modes (Auto, Semi, Manual, Maintenance, E-Stop), alarms (critical/non-critical), communications.",
#     file_plan_prompt="Plan Siemens S7-1500 SCL project structure based on spec: list modules, files, interfaces, tasks/OBs, UDTs.",
#     module_prompt="Generate Siemens SCL code for module {module} based on spec and plan.",
#     critic_prompt="Review generated SCL code for completeness per checklist: OB1, OB100, FBs with instance DBs, UDTs, modes, alarms, communications. Patch missing parts.",
#     pack_prompt="Package SCL code with README."
# )

# def call_llm(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
#     print("Sending request:", messages)  # Debug print
#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=messages,
#             temperature=temperature
#         )
#         print("Received response:", response)  # Debug print
#         return response.choices[0].message.content
#     except Exception as e:
#         print("API Error:", str(e))  # Debug error
#         raise

# def enforce_json(s: str) -> Dict[str, Any]:
#     import re, json
#     s = s.strip()
#     # Extract JSON from code block if present
#     match = re.search(r'```json\n(.*)\n```', s, re.DOTALL)  # Corrected regex to capture content between ```json and ```
#     if match:
#         s = match.group(1).strip()
#     else:
#         match = re.search(r'\{.*\}', s, re.DOTALL)
#         if match:
#             s = match.group(0)
#     return json.loads(s)

# class Orchestrator:
#     def __init__(self, out_dir: str):
#         self.out_dir = out_dir
#         os.makedirs(self.out_dir, exist_ok=True)

#     def generate(self, spec_text: str, vendor: str = "siemens") -> Dict[str, Any]:
#         profile = {"siemens": SIEMENS_PROFILE}
#         if vendor not in profile:
#             raise ValueError(f"Unsupported vendor: {vendor}")

#         # Pass 1: Spec → Contract
#         messages = [
#             {"role": "system", "content": "Generate a strict JSON contract of all required components based on the spec."},
#             {"role": "user", "content": spec_text}
#         ]
#         contract = enforce_json(call_llm(messages))

#         # Mock Plan and Code for demo
#         plan = {
#             "modules": [fb["name"].replace("FB_", "") for fb in contract["project"]["structure"]["function_blocks"]]
#         }
#         code = {}
#         for module in plan["modules"]:
#             code[module] = f"// Mock SCL code for {module}\nFUNCTION_BLOCK FB_{module}\nBEGIN\n  // Placeholder logic for {module}\nEND_FUNCTION_BLOCK"

#         # Save mock outputs
#         for module, content in code.items():
#             with open(os.path.join(self.out_dir, f"FB_{module}.scl"), "w") as f:
#                 f.write(content)

#         return {"status": "success", "files": [f"FB_{m}.scl" for m in plan["modules"]]}

# @app.post("/generate_code")
# async def generate_code(request: CodeRequest):
#     orchestrator = Orchestrator(out_dir="output")
#     try:
#         result = orchestrator.generate(request.spec_text, vendor="siemens")
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.1", port=8000)  # Fixed IP to 0.0.0.1 (was 0.0.0.0)