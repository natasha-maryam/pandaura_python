# generator/orchestrator.py
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
import json, re, os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from dotenv import load_dotenv
# Load API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
# You already have your model wrappers. Replace call_llm() with your internal API.
# def call_llm(messages: List[Dict[str, str]], temperature: float = 0.2, response_format: str = "text") -> str:
#     """
#     messages = [{"role":"system","content":"..."},{"role":"user","content":"..."}]
#     return LLM text. If your provider supports JSON mode, set response_format="json".
#     """
#     raise NotImplementedError
system_prompt="""
You are Pandaura AS — a co-engineer assistant for automation & controls work (PLC logic, I/O,
safety, commissioning docs, diagnostics, refactoring, prompt-to-logic generation).
 - PRIMARY OBJECTIVES
 - Deliver accurate, useful, implementation-ready guidance for industrial automation scenarios.
 - Proactively reduce user effort: propose improvements, call out risks, and suggest next steps.
 - Always finish with a single, contextual next-step question to drive the work forward.
 - BEHAVIORAL RULES
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
 - OUTPUT CONTRACT
 - Start with the answer or artifact (don’t bury the lede).
 - If code is requested, provide complete, runnable snippets with essential comments.
 - If giving steps/checklists, number them and keep items actionably short.
 - End every message with:
 `Next step → <one concrete, contextual question that advances their goal>`
 CRITICAL THINKING / NON-AGREEMENT
 - Before responding, quickly validate the user’s ask:
 - Is the requirement feasible/safe?
 - Are any specs contradictory or underspecified?
 - Are there edge cases (faults, interlocks, timing, safety) that must be handled?
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
   * put your response in the summary, your answer to greeting should be in summary.
   * and follow up question in next step .
- If the response includes code:
   * Put only the raw code inside `code`.
   * Set `feature_detected` = "code".
   * In `summary`, provide a short, natural language paraphrase of what the code does.
- If no code and not a greeting:
   * Leave `code` empty.
   * Set `feature_detected` = "generic".
   * Put your natural language you response response in `summary` and next question in next step.
- The `summary` must **never** repeat the code. It must be an explanation or paraphrase in plain language.
- The JSON must be valid and parsable.
note:: Read the message cerefully dont make mistakes. if user asks for code giv
code . if user asks for summary give summary. if user asks for greeting give greeting.
whatever user asks make sure to give correct answer

in case of document retrieve answer from document"""
llm = ChatOpenAI(model=os.getenv("MODEL_NAME"), api_key=openai_api_key)

def ask_question(messages: List[Dict[str, str]], temperature: float = 0.2, response_format: str = "text"):
    print("\nSending to LLM:", json.dumps(messages, indent=2))
    print("-----------------------------------------------")
    response = llm.invoke(messages)
    with open("response.json", "w") as f:
        f.write(response.content)
    print("\nRaw LLM response:")
    print(response.content)
    with open("raw-response.json", "w") as f:
        f.write(response.content)
    print("------------------------------------------------")
    return response.content


import json
import re

def enforce_json(s: str) -> Dict[str, Any]:
    s = s.strip()
    start_idx = s.find('{')
    end_idx = s.rfind('}') + 1
    if start_idx == -1 or end_idx == 0:
        raise ValueError("No JSON object found in the response")

    json_str = s[start_idx:end_idx]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print("Initial parse failed, attempting repair...")

        # Common fix: remove trailing commas
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

        # Try again
        return json.loads(json_str)

@dataclass
class VendorProfile:
    name: str
    lang: str
    # "SCL", "ST"
    file_ext: str
    # ".scl", ".st", ".L5X" (we still output ST for AOIs; L5X packing is later)
    system_prompt: str
    # Hard vendor constraints & style
    completeness_checklist: str
    # Critic rubric
    file_plan_prompt: str
    # Planner prompt
    module_prompt: str
    # Per-module codegen prompt
    critic_prompt: str
    # Code review & patch prompt
    pack_prompt: str
    # Packaging & README prompt
from .vendor_profiles import SIEMENS_PROFILE, ROCKWELL_PROFILE, BECKHOFF_PROFILE
from .prompts import SPEC_CONTRACT_SYSTEM, SPEC_CONTRACT_USER
question="""
Use the uploaded PLC Functional Design Specification as the single source of truth. Convert
any Schneider/Modicon M580 Hot-Standby and X80 I/O concepts into an equivalent Siemens
S7-1500 design in Structured Control Language (SCL) for TIA Portal. Implement the full control
behavior described in the spec: operating modes (Auto, Semi, Manual, Maintenance, E-Stop),
conveyor accumulation & jam detection, barcode-based merge/divert, palletizer handshake
(Ready → InPosition → CycleStart → Complete with timeouts/faults), alarms (critical/non-critical
with ack/reset), communications/diagnostics exposed for SCADA, and general performance
intent. Use a clean Siemens project structure: OB1 (cyclic), OB100 (startup), FBs with instance
DBs per subsystem (Conveyors, Merge/Divert, PalletizerHS, Modes, Alarms, Diag, Comms),
plus UDTs for devices, alarms, and state. Keep naming consistent and comment every public
tag and FB header. If redundancy is referenced, mirror the behavior and status handling within
S7-1500 (assume software/state modeling if hardware redundancy isn’t configured).”
After the code, add a short natural language explanation section that summarizes how the
blocks work together (mode transitions, routing logic, handshake sequence, alarm/ack flow,
diagnostics mapping), lists assumptions/parameter defaults you inferred from the spec, and
notes where a user would map physical I/O/SCADA tags. Include helpful inline comments
throughout the SCL so a reviewer can trace each requirement back to the spec."""

class CodeGenError(Exception): pass
class Orchestrator:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)
    def generate(self, *, spec_text: str, vendor: str, project_name: str = "PandauraProject") -> Dict[str, Any]:
        profile = {
            "siemens": SIEMENS_PROFILE,
            "rockwell": ROCKWELL_PROFILE,
            "beckhoff": BECKHOFF_PROFILE,
        }.get(vendor.lower())
        if not profile:
            raise CodeGenError(f"Unsupported vendor: {vendor}")
        # 1) SPEC → CONTRACT (strict JSON)
        contract = self._spec_to_contract(spec_text=spec_text, vendor_profile=profile)
        print("spec-to-contarct completed")
        with open("sepc-contract.json", "w") as f:
            json.dump(contract, f, indent=2)
            
        # 2) CONTRACT → PLAN (files/modules/OBs/AOIs/UDTs, interfaces, tag map)
        plan = self._contract_to_plan(contract=contract, vendor_profile=profile,project_name=project_name)
        print("contract-to-plan completed")
        with open("plan.json", "w") as f:
            json.dump(plan, f, indent=2)
            
        # # 3) PLAN → CODE (generate every file; block “skeletons”)
        files = self._plan_to_code(contract=contract, plan=plan, vendor_profile=profile)
        print("plan-to-code completed")
        with open("plan-to-code.json", "w") as f:
            json.dump(files, f, indent=2)
            
        # # 4) CRITIC & PATCH (iterate until complete or max attempts)
        files = self._critic_and_patch(contract=contract, plan=plan, files=files,vendor_profile=profile)
        print("critic-and-patch completed")
        with open("critic-patch.json", "w") as f:
            json.dump(files, f, indent=2)
        # # 5) PACKAGING (README, build notes, SCADA map)
        bundle = self._pack(project_name=project_name, plan=plan, files=files,vendor_profile=profile)
        return {"contract": contract,"plan": plan,"files": files,"bundle": bundle}
    def _spec_to_contract(self, *, spec_text: str, vendor_profile: VendorProfile) -> Dict[str, Any]:
        messages = [
                {"role": "system", "content": SPEC_CONTRACT_SYSTEM},
                {"role": "user", "content": SPEC_CONTRACT_USER.format(spec_text=spec_text)}
            ]
        raw = ask_question(messages, response_format="json")
        return enforce_json(raw)

    def _contract_to_plan(self, *, contract: Dict[str, Any], vendor_profile: VendorProfile,project_name: str) -> Dict[str, Any]:
        messages = [
        {"role": "system", "content": vendor_profile.system_prompt},
        {"role": "user", "content": vendor_profile.file_plan_prompt.format(
        project_name=project_name,
        contract_json=json.dumps(contract, ensure_ascii=False, indent=2)
        )}
        ]
        raw = ask_question(messages,response_format="json")
        return enforce_json(raw)
    def _plan_to_code(self, *, contract: Dict[str, Any], plan: Dict[str, Any], vendor_profile:VendorProfile) -> Dict[str, str]:
        files: Dict[str, str] = {}
        for mod in plan["modules"]:
            relpath = mod["relpath"]
            messages = [
            {"role": "system", "content": vendor_profile.system_prompt},
            {"role": "user", "content": vendor_profile.module_prompt.format(
        module_json=json.dumps(mod, ensure_ascii=False, indent=2),
        contract_json=json.dumps(contract, ensure_ascii=False, indent=2)
        )}
        ]
        code = ask_question(messages)
        # self._reject_skeleton(code, mod["name"])
        files[relpath] = code
        return files

    def _critic_and_patch(self, *, contract: Dict[str, Any], plan: Dict[str, Any], files: Dict[str, str],vendor_profile: VendorProfile) -> Dict[str, str]:
        MAX_ITERS = 3
        for _ in range(MAX_ITERS):
            critic_messages = [
            {"role": "system", "content": vendor_profile.system_prompt},
            {"role": "user", "content": vendor_profile.critic_prompt.format(
            plan_json=json.dumps(plan, ensure_ascii=False, indent=2),
            files_json=json.dumps(files, ensure_ascii=False, indent=2),
            checklist=vendor_profile.completeness_checklist,
            contract_json=json.dumps(contract, ensure_ascii=False, indent=2)
            )}
            ]
            review_raw = ask_question(critic_messages, response_format="json")
            review = enforce_json(review_raw)   
            if review["status"] == "complete":
                return files
            # Apply patches
            for patch in review.get("patches", []):
                path = patch["relpath"]
                files[path] = patch["new_content"]
                # self._reject_skeleton(files[path], path)
        if MAX_ITERS > 0:
            # Final decisive fail with clear reason
            raise CodeGenError("Critic could not reach completeness within patch budget.")
        return files

    def _pack(self, *, project_name: str, plan: Dict[str, Any], files: Dict[str, str], vendor_profile:VendorProfile) -> Dict[str, Any]:
        readme = ask_question([
            [{"role":"system","content": vendor_profile.system_prompt},
            {"role":"user","content": vendor_profile.pack_prompt.format(
            project_name=project_name,
            plan_json=json.dumps(plan, ensure_ascii=False, indent=2)
            )}
            ]],
            )
        # write files
        proj_dir = os.path.join(self.out_dir, project_name)
        os.makedirs(proj_dir, exist_ok=True)
        for rel, content in files.items():
            dst = os.path.join(proj_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(content)
        with open(os.path.join(proj_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)
        return {"readme": readme, "project_dir": proj_dir}

    # def _reject_skeleton(self, code: str, name: str):
    #     # Hard guard: forbid empty stubs, TODOs, “skeleton” wording, or missing logic markers.
    #     red_flags = [
    #     r"\bTODO\b", r"\bplaceholder\b", r"\bskeleton\b",
    #     r"//\s*Manual control logic\s*$", r"//\s*Maintenance routines\s*$",
    #     r"IF\s+Ready\s+THEN\s+InPosition\s*:=\s*TRUE;", # trivial handshake
    #     ]
    #     for pat in red_flags:
    #         if re.search(pat, code, re.I|re.M):
    #             raise CodeGenError(f"Rejected skeletal module '{name}': matched pattern {pat}")





# # generator/orchestrator.py
# import json
# import os
# import re
# from typing import Dict, Any, List

# from .llm_client import LLMClient
# from .vendor_profiles import VENDOR_MAP
# from .prompts import SPEC_CONTRACT_SYSTEM, SPEC_CONTRACT_USER
# import logging

# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)


# class CodeGenError(Exception):
#     pass


# def _write_text(path: str, content: str):
#     os.makedirs(os.path.dirname(path), exist_ok=True)
#     with open(path, "w", encoding="utf-8") as f:
#         f.write(content)


# def _is_probably_skeleton(code: str) -> str:
#     """
#     Return a reason string if code looks skeletal; empty if OK.
#     """
#     red_flags = [
#         r"\bTODO\b", r"\bplaceholder\b", r"\bskeleton\b",
#         r"//\s*Manual control logic\s*$",
#         r"//\s*Maintenance routines\s*$",
#         r"^\s*$",  # empty
#         r"(?i)\bimplement here\b",
#         r"(?i)stub",
#     ]
#     for pat in red_flags:
#         if re.search(pat, code, re.M):
#             return f"Matched red-flag pattern: {pat}"
#     # must include at least some SCL structure
#     needs = [r"FUNCTION_BLOCK", r"ORGANIZATION_BLOCK|TYPE|FUNCTION"]
#     if not any(re.search(p, code) for p in needs):
#         return "Missing core SCL constructs (FB/OB/TYPE/FC)."
#     return ""


# class Orchestrator:
#     """
#     Full pipeline:
#       1) Spec → CONTRACT (strict JSON)
#       2) CONTRACT → PLAN (files/modules/interfaces)
#       3) PLAN → CODE (generate each file)
#       4) CRITIC & PATCH (iterate until complete)
#       5) PACKAGING (README + write files to disk)
#     """

#     def __init__(self, *, model: str, api_key: str, out_dir: str):
#         self.out_dir = out_dir
#         os.makedirs(self.out_dir, exist_ok=True)
#         self.llm_json = LLMClient(model=model, api_key=api_key)
#         self.llm_text = LLMClient(model=model, api_key=api_key)

#     def generate(self, *, vendor: str, spec_context: str, user_request: str,
#                  project_name: str = "PandauraProject") -> Dict[str, Any]:

#         profile = VENDOR_MAP.get(vendor.lower())
#         if not profile:
#             raise CodeGenError(f"Unsupported vendor: {vendor}. Supported: {list(VENDOR_MAP)}")

#         contract = self._spec_to_contract(spec_context=spec_context, user_request=user_request)
#         plan = self._contract_to_plan(contract=contract, profile=profile, project_name=project_name)
#         files = self._plan_to_code(contract=contract, plan=plan, profile=profile)
#         files = self._critic_and_patch(contract=contract, plan=plan, files=files, profile=profile)
#         bundle = self._package(project_name=project_name, plan=plan, files=files, profile=profile, contract=contract)

#         return {
#             "contract": contract,
#             "plan": plan,
#             "files": list(files.keys()),
#             "bundle": bundle
#         }

#     # ---------- Steps ----------

#     def _spec_to_contract(self, *, spec_context: str, user_request: str) -> Dict[str, Any]:
#         messages = [
#             {"role": "system", "content": SPEC_CONTRACT_SYSTEM},
#             {"role": "user", "content": SPEC_CONTRACT_USER.format(
#                 context=spec_context, user_request=user_request)}
#         ]
#         contract = self.llm_json.call_json(messages)
#         # basic validation:
#         for key in ["modes", "conveyors", "merge_divert", "palletizer_handshake",
#                     "alarms", "diagnostics", "comms", "instances", "udts"]:
#             if key not in contract:
#                 raise CodeGenError(f"Contract missing key: {key}")
#         return contract

#     def _contract_to_plan(self, *, contract: Dict[str, Any], profile, project_name: str) -> Dict[str, Any]:
#         messages = [
#             {"role": "system", "content": profile.system_prompt},
#             {"role": "user", "content": profile.file_plan_prompt.format(
#                 project_name=project_name,
#                 contract_json=json.dumps(contract, ensure_ascii=False, indent=2)
#             )}
#         ]
#         plan = self.llm_json.call_json(messages)
#         if "modules" not in plan or not isinstance(plan["modules"], list) or len(plan["modules"]) == 0:
#             raise CodeGenError("Plan is missing 'modules' or it is empty.")
#         # sanity: ensure unique relpaths
#         rels = [m.get("relpath") for m in plan["modules"]]
#         if len(set(rels)) != len(rels):
#             raise CodeGenError("Plan contains duplicate relpaths.")
#         return plan

#     def _plan_to_code(self, *, contract: Dict[str, Any], plan: Dict[str, Any], profile) -> Dict[str, str]:
#         files: Dict[str, str] = {}
#         project_name = contract.get("project_name", "Client_Project")

#         for mod in plan["modules"]:
#             relpath = mod["relpath"]

#             # Generate with LLM
#             messages = [
#                 {"role": "system", "content": profile.system_prompt},
#                 {"role": "user", "content": profile.module_prompt.format(
#                     module_json=json.dumps(mod, ensure_ascii=False, indent=2),
#                     contract_json=json.dumps(contract, ensure_ascii=False, indent=2)
#                 )}
#             ]
#             code = self.llm_text.call_text(messages)

#             # Check for skeletal output
#             reason = _is_probably_skeleton(code)
#             if reason:
#                 logger.warning(f"⚠️ {mod.get('name','?')} was skeletal ({reason}). Auto-filling with safe template.")

#                 # Minimal safe Siemens SCL template (always compiles)
#                 code = f"""// Auto-generated for {project_name}
#     // Module: {mod.get('name','?')} ({relpath})
#     // Based on client functional design specification

#     ORGANIZATION_BLOCK {mod.get('name','?')}
#         BEGIN
#             // Default logic placeholder replaced with safe code
#             // TODO: Extend according to PDF specification
#             NOP 0;   // No operation, ensures non-empty block
#         END_ORGANIZATION_BLOCK
#         """

#             files[relpath] = code

#         return files


#     def _critic_and_patch(self, *, contract: Dict[str, Any], plan: Dict[str, Any], files: Dict[str, str], profile) -> Dict[str, str]:
#         MAX_ITERS = 3
#         for _ in range(MAX_ITERS):
#             critic_messages = [
#                 {"role": "system", "content": profile.system_prompt},
#                 {"role": "user", "content": profile.critic_prompt.format(
#                     plan_json=json.dumps(plan, ensure_ascii=False, indent=2),
#                     files_json=json.dumps(files, ensure_ascii=False, indent=2),
#                     contract_json=json.dumps(contract, ensure_ascii=False, indent=2)
#                 )}
#             ]
#             review = self.llm_json.call_json(critic_messages)
#             status = review.get("status", "").lower()
#             if status == "complete":
#                 return files
#             if status == "patch_required":
#                 patches = review.get("patches", [])
#                 if not patches:
#                     continue
#                 for p in patches:
#                     rel = p["relpath"]
#                     new_content = p["new_content"]
#                     reason = _is_probably_skeleton(new_content)
#                     if reason:
#                         raise CodeGenError(f"Critic produced skeletal content for {rel}: {reason}")
#                     files[rel] = new_content
#             else:
#                 # Unknown status; try once more loop
#                 continue
#         # If we get here, fail decisively
#         raise CodeGenError("Critic could not reach completeness within patch budget.")

#     def _package(self, *, project_name: str, plan: Dict[str, Any], files: Dict[str, str], profile, contract: Dict[str, Any]) -> Dict[str, Any]:
#         # write files to disk
#         proj_dir = os.path.join(self.out_dir, project_name)
#         os.makedirs(proj_dir, exist_ok=True)
#         for rel, content in files.items():
#             dst = os.path.join(proj_dir, rel)
#             _write_text(dst, content)

#         # README.md
#         readme_messages = [
#             {"role": "system", "content": profile.system_prompt},
#             {"role": "user", "content": profile.pack_prompt.format(
#                 project_name=project_name,
#                 plan_json=json.dumps(plan, ensure_ascii=False, indent=2)
#             )}
#         ]
#         readme = self.llm_text.call_text(readme_messages)
#         _write_text(os.path.join(proj_dir, "README.md"), readme)

#         # Save plan & contract for traceability
#         _write_text(os.path.join(proj_dir, "_contract.json"), json.dumps(contract, ensure_ascii=False, indent=2))
#         _write_text(os.path.join(proj_dir, "_plan.json"), json.dumps(plan, ensure_ascii=False, indent=2))

#         return {"project_dir": proj_dir, "readme": "README.md"}
