# generator/vendor_profiles.py
from dataclasses import dataclass

@dataclass
class VendorProfile:
    name: str
    lang: str          # "SCL" or "ST"
    file_ext: str      # ".scl" or ".st"
    system_prompt: str
    completeness_checklist: str
    file_plan_prompt: str
    module_prompt: str
    critic_prompt: str
    pack_prompt: str



SIEMENS_PROFILE = VendorProfile(
    name="siemens",
    lang="SCL",
    file_ext=".scl",
    system_prompt="Generate Siemens S7-1500 SCL code...",
    completeness_checklist="Check OB1, OB100, FBs...",
    file_plan_prompt="Plan Siemens S7-1500 project...",
    module_prompt="Generate SCL code for module {module}...",
    critic_prompt="Review Siemens SCL code...",
    pack_prompt="Bundle Siemens project files..."
)
ROCKWELL_PROFILE = VendorProfile(
    name="rockwell",
    lang="ST",
    file_ext=".st",
    system_prompt="Generate Rockwell ST code...",
    completeness_checklist="Check routines, tags...",
    file_plan_prompt="Plan Rockwell ST project...",
    module_prompt="Generate ST code for module {module}...",
    critic_prompt="Review Rockwell ST code...",
    pack_prompt="Bundle Rockwell project files..."
)

BECKHOFF_PROFILE = VendorProfile(
    name="beckhoff",
    lang="ST",
    file_ext=".st",
    system_prompt="Generate Beckhoff ST code...",
    completeness_checklist="Check POU, GVL...",
    file_plan_prompt="Plan Beckhoff ST project...",
    module_prompt="Generate ST code for module {module}...",
    critic_prompt="Review Beckhoff ST code...",
    pack_prompt="Bundle Beckhoff project files..."
)


VENDOR_PROFILES = {
    "siemens": SIEMENS_PROFILE,
    "rockwell": ROCKWELL_PROFILE,
    "beckhoff": BECKHOFF_PROFILE,
}

GENERIC_SYSTEM = """You are a generic IEC 61131-3 Structured Text generator.
Rules:
- Produce portable ST code (no vendor-specific syntax).
- Use FUNCTION_BLOCKs, VAR_INPUT/OUTPUT, CASE for state machines.
- Always include clear comments.
"""

GENERIC_PLAN = """Return JSON PLAN with modules:
- One MAIN program
- A few FUNCTION_BLOCKs (FB_Conveyor, FB_Alarm, FB_ModeMgr)
- UDTs for Device, State, Alarm
CONTRACT:
{contract_json}
"""

GENERIC_MODULE = """Generate FULL Structured Text code for this module.
MODULE:
{module_json}
CONTRACT:
{contract_json}
"""

GENERIC_CRITIC = """Review GENERIC PLAN/FILES for completeness.
Checklist:
- MAIN program calls FBs
- FB_Conveyor implements start/stop, jam timer, interlocks
- FB_Alarm handles latches/acks
- ModeMgr implements Auto/Manual/Stop
Return JSON with status/patches.
PLAN:
{plan_json}
FILES:
{files_json}
CONTRACT:
{contract_json}
"""

GENERIC_PACK = """README for importing Generic ST project.
Project: {project_name}
PLAN:
{plan_json}
"""

GENERIC_PROFILE = VendorProfile(
    name="generic",
    lang="pseudo",
    file_ext=".txt",
    system_prompt="Generate vendor-agnostic IEC 61131-3 pseudo-code...",
    completeness_checklist="Check all required behaviors...",
    file_plan_prompt="Plan a generic PLC project structure...",
    module_prompt="Generate generic pseudo-code for module {module}...",
    critic_prompt="Review generic pseudo-code...",
    pack_prompt="Bundle generic project files..."
)
