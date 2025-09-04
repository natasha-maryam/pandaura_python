from dataclasses import dataclass
from typing import Dict, Any, List
import json, os, re
from openai import OpenAI
from dotenv import load_dotenv
from .vendor_profiles import (
    SIEMENS_PROFILE,
    ROCKWELL_PROFILE,
    BECKHOFF_PROFILE,
    GENERIC_PROFILE,
)
# profile = {
# #     "siemens": SIEMENS_PROFILE,
# #     "rockwell": ROCKWELL_PROFILE,
# #     "beckhoff": BECKHOFF_PROFILE,
# #     "generic": GENERIC_PROFILE,
# # }.get(vendor.lower())

load_dotenv()
client = OpenAI()

# ----------------------------
# HELPER: Call LLM
# ----------------------------


def detect_vendor_from_spec(spec_text: str) -> str:
    spec_lower = spec_text.lower()
    if "siemens" in spec_lower or "s7" in spec_lower or "tia" in spec_lower:
        return "siemens"
    elif "rockwell" in spec_lower or "logix" in spec_lower or "studio 5000" in spec_lower:
        return "rockwell"
    elif "beckhoff" in spec_lower or "twincat" in spec_lower:
        return "beckhoff"
    else:
        return "generic"   # fallback


def call_llm(messages: List[Dict[str, str]], temperature: float = 0.2, response_format: str = "text") -> str:
    kwargs = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": temperature,
    }

    if response_format == "json":
        if not any("json" in m["content"].lower() for m in messages):
            messages.insert(0, {"role": "system", "content": "Return valid JSON only."})
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()

# ----------------------------
# Vendor Profiles
# ----------------------------
@dataclass
class VendorProfile:
    name: str
    lang: str
    file_ext: str
    system_prompt: str

SIEMENS_PROFILE = VendorProfile(
    name="Siemens", lang="SCL", file_ext=".scl",
    system_prompt="""You are a Siemens S7-1500 SCL code generator.
Generate FULL compilable SCL with OB1, OB100, FBs, UDTs. 
Include: Conveyor logic, alarms, modes, palletizer handshake. 
No TODOs or placeholders. Use standard Siemens conventions."""
)

ROCKWELL_PROFILE = VendorProfile(
    name="Rockwell", lang="ST", file_ext=".st",
    system_prompt="""You are a Rockwell Logix 5000 Structured Text generator.
Generate full AOIs, Routines, and UDTs in Structured Text. 
Include: Conveyor AOI, ModeMgr, AlarmMgr, Palletizer handshake. 
No TODOs or placeholders. Must be valid for Studio 5000."""
)

BECKHOFF_PROFILE = VendorProfile(
    name="Beckhoff", lang="ST", file_ext=".st",
    system_prompt="""You are a Beckhoff TwinCAT 3 ST code generator.
Generate full FBs, DUTs, and MAIN program in Structured Text. 
Include: Conveyor FB, ModeMgr, AlarmMgr, Palletizer handshake. 
No TODOs or placeholders. Must be valid for TwinCAT 3."""
)

VENDOR_MAP = {
    "siemens": SIEMENS_PROFILE,
    "rockwell": ROCKWELL_PROFILE,
    "beckhoff": BECKHOFF_PROFILE,
}

# ----------------------------
# Orchestrator
# ----------------------------
class Orchestrator:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)

    def _detect_vendor(self, spec_text: str) -> Any:
        """Auto-detect vendor from the spec text if not provided."""
        text_lower = spec_text.lower()
        if "siemens" in text_lower or "s7" in text_lower:
            return SIEMENS_PROFILE
        elif "rockwell" in text_lower or "allen-bradley" in text_lower:
            return ROCKWELL_PROFILE
        elif "beckhoff" in text_lower or "twincat" in text_lower:
            return BECKHOFF_PROFILE
        else:
            return GENERIC_PROFILE

    def generate(
        self,
        *,
        spec_text: str,
        vendor: str = None,
        project_name: str = "PandauraProject"
    ) -> Dict[str, Any]:
        # Pick profile either from explicit vendor or auto-detect
        profile = (
            VENDOR_MAP.get(vendor.lower()) if vendor else self._detect_vendor(spec_text)
        )
        if not profile:
            return {
                "status": "error",
                "files": [],
                "message": f"Unsupported vendor: {vendor}",
            }

        # Build messages for LLM
        messages = [
            {"role": "system", "content": profile.system_prompt},
            {
                "role": "user",
                "content": f"Spec: {spec_text}\nGenerate full {profile.lang} project code with all required modules.",
            },
        ]

        code = call_llm(messages, temperature=0.2, response_format="text")

        # Ensure non-empty code
        if not code or "TODO" in code or "skeleton" in code.lower():
            return {
                "status": "error",
                "files": [],
                "message": "Code generation failed or returned skeleton.",
            }

        # Save file
        proj_dir = os.path.join(self.out_dir, project_name)
        os.makedirs(proj_dir, exist_ok=True)
        file_path = os.path.join(proj_dir, f"Main{profile.file_ext}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        return {"status": "success", "files": [file_path]}















# # generator/orchestrator.py
# import os
# import json
# from typing import Dict, Any, List
# from openai import OpenAI
# from .vendor_profiles import VENDOR_PROFILES
# from dotenv import load_dotenv

# load_dotenv()
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# client = OpenAI()

# class Orchestrator:
#     def __init__(self, out_dir: str = "output"):
#         self.out_dir = out_dir
#         os.makedirs(self.out_dir, exist_ok=True)

#     def _call_llm(self, messages: List[Dict[str, str]], json_mode: bool = False) -> str:
#         kwargs = {
#             "model": "gpt-4o-mini",
#             "messages": messages,
#             "temperature": 0.2,
#         }
#         if json_mode:
#             kwargs["response_format"] = {"type": "json_object"}
#         response = client.chat.completions.create(**kwargs)
#         return response.choices[0].message.content

#     def _enforce_json(self, s: str) -> Dict[str, Any]:
#         import re
#         s = s.strip()
#         match = re.search(r'\{.*\}', s, re.DOTALL)
#         if match:
#             return json.loads(match.group(0))
#         raise ValueError("No JSON object found in response")

#     def generate(self, spec_text: str, vendor: str) -> Dict[str, Any]:
#         profile = VENDOR_PROFILES.get(vendor)
#         if not profile:
#             raise ValueError(f"Unsupported vendor: {vendor}")

#         # Pass 1: Spec → Contract
#         messages = [
#             {"role": "system", "content": "Extract a strict JSON contract of all required components. Respond only in JSON."},
#             {"role": "user", "content": spec_text}
#         ]
#         contract = self._enforce_json(self._call_llm(messages, json_mode=True))

#         # Pass 2: Contract → Plan
#         messages = [
#             {"role": "system", "content": profile.file_plan_prompt},
#             {"role": "user", "content": json.dumps(contract)}
#         ]
#         plan = self._enforce_json(self._call_llm(messages, json_mode=True))

#         # Pass 3: Plan → Code
#         code = {}
#         for module in plan.get("modules", []):
#             messages = [
#                 {"role": "system", "content": profile.module_prompt.format(module=module)},
#                 {"role": "user", "content": json.dumps(plan)}
#             ]
#             code[module] = self._call_llm(messages, json_mode=False)

#         # Pass 4: Critic & Patch
#         messages = [
#             {"role": "system", "content": profile.critic_prompt},
#             {"role": "user", "content": "\n".join(code.values())}
#         ]
#         critique = self._enforce_json(self._call_llm(messages, json_mode=True))
#         if critique.get("incomplete"):
#             for patch in critique.get("patches", []):
#                 messages = [
#                     {"role": "system", "content": profile.module_prompt.format(module=patch["module"])},
#                     {"role": "user", "content": patch["description"]}
#                 ]
#                 code[patch["module"]] += "\n" + self._call_llm(messages, json_mode=False)

#         if not code:  
#             demo_module = "Main"
#             demo_content = f"// Demo {vendor} program\nPROGRAM Main\n    // TODO: Conveyor, Alarms, Modes\nEND_PROGRAM"
#             code[demo_module] = demo_content

#         # Save outputs
#         generated_files = []
#         for module, content in code.items():
#             filename = f"{module}{profile.file_ext}"
#             filepath = os.path.join(self.out_dir, filename)
#             with open(filepath, "w") as f:
#                 f.write(content)
#             generated_files.append(filename)

#         return {"status": "success", "files": generated_files}
