# # generator/vendor_profiles.py
# generator/vendor_profiles.py
from .orchestrator import VendorProfile

SIEMENS_SYSTEM = """You are a Siemens S7-1500 SCL code generator.
Rules:
- Use SCL with TIA Portal conventions.
- OB100 for cold start, OB1 cyclic.
- Each FB has an Instance DB; name DBs explicitly (DB_Conveyor1, etc.).
- Provide UDTs for Devices, Alarms, States. Expose comments on public tags.
- No placeholders or TODOs. Implement full logic (timers, debouncing, state machines).
- E-Stop forces safe outputs and requires reset permissives to return to Auto.
- Ensure responses include inline comments that a reviewer could use to trace the requirement back to the functional specification document (if provided).

- IMPORTANT: Do not use placeholder text, TODOs, or empty sections. Always generate complete, production-ready content.
- If you need to include a backslash, escape it with another backslash (e.g., "\\\\").
"""

SIEMENS_PLAN = """From this CONTRACT create a FILE PLAN in JSON with a single top-level "modules" key.

- "modules" should be an array of files, where each file has:
    - name: (string) file name 
    - relpath: (string) file path
    - language: (string, always "SCL")
    - type: (string, one of "OB", "FB", "UDT", "FC")
    - summary: (string) one-sentence summary of the file's purpose
    - public_interfaces: (list of strings) names of public inputs, outputs, inouts, and DB references
    - dependencies: (list of strings) names of other modules this file depends on
    - purpose: (string, 1-2 lines) describes the file's role

- Include: OB100, OB1, FB_ModeMgr, FB_Conveyor (one FB but multiple instances), FB_MergeDivert, FB_PalletizerHS, FB_AlarmMgr, FB_Diag, FB_Comms, UDT_Device, UDT_Alarm, UDT_State.
- Include a SCADA map file ("docs/Scada_Tag_Map.md") as a generated doc (not code) that lists each SCADA tag and its corresponding PLC tag and datatype. This will allow someone implementing a SCADA system to easily connect them.
- For clarity, ensure there is no skeletal content in your documentation.

Note: Make sure to return valid parsable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

CONTRACT:
{contract_json}
"""

SIEMENS_MODULE = """Generate the FULL SCL source for this module.
- If type=UDT, produce the UDT body with comments on each field. 
- If OB/FB/FC, include a complete header and implementation.
- Implement sequences as CASE state machines with explicit timeouts using TON/TOF timers for state transitions and watchdog timers.
- Comment every public I/O tag and delineate safety behavior.
- For FBs, include VAR_INPUT/VAR_OUTPUT/VAR and CLEAR/INIT routines when needed.
- Ensure responses include inline comments that a reviewer could use to trace the requirement back to the functional specification document (if provided).
- Structure sequential logic using well-defined state machines.

Note: Make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

MODULE:
{module_json}
CONTRACT:
{contract_json}
"""

SIEMENS_CRITIC = """You are a Siemens SCL reviewer. Using this PLAN and FILES:
- Verify checklist coverage; if any gap, provide patches to correct it.

Note: make sure return valid parsable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

Checklist:
{checklist}
Return JSON:
{{
"status": "complete" | "patch_required",
"patches": [{{"relpath": "...", "reason": "...", "new_content": "FULL FILE CONTENT"}}]
}}
PLAN:
{plan_json}
FILES:
{files_json}
CONTRACT:
{contract_json}
"""

SIEMENS_CHECKLIST = """
[Siemens S7-1500 Completeness]
- OB100: initializes modes, retentives, comms warm-up, clears timers/flags.
- OB1: calls ModeMgr, all FB instances, alarm/diag/comms each cycle.
- ModeMgr: Auto/Semi/Manual/Maint/E-Stop state machine with permissives.
- Conveyor FB: Start/Stop, accumulation, PE logic, jam timer, clear sequence, interlocks.
- Merge/Divert FB: barcode parse/validate, routing table, fallback, divert command.
- PalletizerHS FB: Ready→InPosition→CycleStart→Complete, interlocks, watchdogs, retries, fault exits.
- AlarmMgr FB: critical vs non-critical, latch/ack/reset, inhibit, first-out, summary bits.
- Diag FB: heartbeat, firmware/version strings, timestamped events, SCADA exposure.
- Comms FB: tag packing/unpacking, heartbeat, comms status.
- UDTs: Device, Alarm, State with documented fields.
- No TODO/placeholder/skeleton content. Timeouts are actual TONs with preset constants.

- IMPORTANT: Do not use placeholder text, TODOs, or empty sections. Always generate complete, production-ready content. Ensure all timeouts are handled.
"""

SIEMENS_PACK = """Write a comprehensive README.md file that includes:
- Project structure, FB responsibilities, and instance DBs.
- How to import the generated code into TIA Portal and compile it successfully.
- A SCADA tag mapping overview. Ensure this mapping clearly shows the connections between PLC tags and SCADA tags.

Note: make sure to return valid parsable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").
Project: {project_name}
PLAN:
{plan_json}
"""

SIEMENS_PROFILE = VendorProfile(
    name="Siemens", lang="SCL", file_ext=".scl",
    system_prompt=SIEMENS_SYSTEM,
    completeness_checklist=SIEMENS_CHECKLIST,
    file_plan_prompt=SIEMENS_PLAN,
    module_prompt=SIEMENS_MODULE,
    critic_prompt=SIEMENS_CRITIC,
    pack_prompt=SIEMENS_PACK
)

# ------------------ Rockwell Logix (Studio 5000) ------------------
ROCKWELL_SYSTEM = """You are a Rockwell Logix 5000 code generator.
Rules:
- Use Structured Text for AOls and routines; plan for MainTask (Periodic 10ms), CommsTask (Periodic 100ms).
- Create UDTs (Udt_Device, Udt_Alarm, Udt_State). Create AOIs: AOI_Conveyor, AOI_MergeDivert, AOI_PalletizerHS, AOI_AlarmMgr, AOI_Diag, AOI_Comms, AOI_ModeMgr.
- Provide .L5X-compatible ST bodies (user will paste/import). Include tag lists in CSV where helpful.
- No placeholders/TODOs. Implement all timeouts, interlocks, and latching properly.

- IMPORTANT: Do not use placeholder text, TODOs, or empty sections. Always generate complete, production-ready content.
"""

ROCKWELL_PLAN = """Return JSON PLAN with "modules":
- For each AOI: a file under "aoi/AOI_Name.st"
- For Programs & Routines: "src/MainProgram/MainRoutine.st", "src/MainProgram/ModeMgr.st", etc.
- Include "docs/Tag_Map.csv" and "docs/Import_Instructions.md" as docs.

Note: make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

CONTRACT:
{contract_json}
"""

ROCKWELL_MODULE = """Generate FULL Structured Text for this Rockwell module (AOI or Routine).
- AOIs: clearly define In/Out/Parm, Local tags, and execution logic.
- Use timers (TON) via Rockwell conventions.
- Implement alarms with latches, ACK handling, inhibit.

Note: Make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").
MODULE:
{module_json}
CONTRACT:
{contract_json}
"""

ROCKWELL_CRITIC = """Review Rockwell PLAN/FILES for completeness. Apply checklist. If missing parts, return patches with full file content.
Checklist:
- MainTask (Periodic 10ms) and CommsTask (100ms) defined in docs/Import_Instructions.md with step-by-step.
- MainRoutine calls ModeMgr and AOls instances for each device.
- AOI_Conveyor implements accumulation & jam timers.
- AOI_MergeDivert parses barcode string and routes with fallback.
- AOI_PalletizerHS sequences and timeouts w/ retries.
- AOI_AlarmMgr supports critical/noncritical, ack/reset, inhibit, first-out.
- AOI_Diag sets heartbeat, version, and event logs; AOI_Comms maps SCADA tags.
- UDTs present and documented.

Note: Make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

Return JSON as in Siemens critic.
PLAN:
{plan_json}
FILES:
{files_json}
CONTRACT:
{contract_json}
"""

ROCKWELL_PACK = """Write README for Studio 5000 import:
- Create tasks, add programs, import AOls, create tags.
- Build order and common pitfalls.

Note: Make sure to return valid parsrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

Project: {project_name}
PLAN:
{plan_json}
"""

ROCKWELL_PROFILE = VendorProfile(
    name="Rockwell", lang="ST", file_ext=".st",
    system_prompt=ROCKWELL_SYSTEM,
    completeness_checklist="See critic prompt.",  # already embedded
    file_plan_prompt=ROCKWELL_PLAN,
    module_prompt=ROCKWELL_MODULE,
    critic_prompt=ROCKWELL_CRITIC,
    pack_prompt=ROCKWELL_PACK
)

# ------------------ Beckhoff TwinCAT 3 ------------------
BECKHOFF_SYSTEM = """You are a Beckhoff TwinCAT 3 ST generator.
Rules:
- Use ST with DUTs for UDTs; create FBs for modules; MAIN program calls all FB instances.
- Define Tasks: Main (1–10ms) per performance intent; doc how to bind.
- UDTs: DUT_Device, DUT_Alarm, DUT_State. FBs: FB_ModeMgr, FB_Conveyor, FB_MergeDivert, FB_PalletizerHS, FB_AlarmMgr, FB_Diag, FB_Comms.
- No placeholders/TODOs. Implement full logic with TON/TOF timers (Tc2_Standard).
- Ensure responses include inline comments that a reviewer could use to trace the requirement back to the functional specification document (if provided).

Note: Make sure to return valid parsrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").
"""

BECKHOFF_PLAN = """Return JSON PLAN:
- Source files under "src/": MAIN.st, FB_*.st, DUT_*.st
- Include "docs/TwinCAT_Setup.md" and "docs/Scada_Tag_Map.md".

Note: make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").
CONTRACT:
{contract_json}
"""

BECKHOFF_MODULE = """Generate FULL TwinCAT ST for the given module (FB/DUT/MAIN).
- Include VAR_INPUT/VAR_OUTPUT/VAR. Use Tc2_Standard timers explicitly.

Note: Make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

MODULE:
{module_json}
CONTRACT:
{contract_json}
"""

BECKHOFF_CRITIC = """Review TwinCAT PLAN/FILES for completeness. If anything missing or weak, return patches.
Checklist:
- MAIN calls ModeMgr then all FB instances each cycle.
- Conveyor: accumulation, jam timer, clear sequence.
- MergeDivert: barcode parse/route/fallback.
- PalletizerHS: full sequencer w/ timeouts & retries.
- AlarmMgr: critical/noncritical, latch/ack/reset, inhibit, first-out.
- Diag & Comms: heartbeat, version, SCADA exposure.

Note: Make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

Return JSON with status/patches as in Siemens critic.
PLAN:
{plan_json}
FILES:
{files_json}
CONTRACT:
{contract_json}
"""

BECKHOFF_PACK = """README for TwinCAT import (new PLC project, add DUT/FB/MAIN, map I/O, set task cycle, build).

Note: make sure to return valid pasrable JSON. Ensure there are no invalid escape characters in your JSON. If you need to include a backslash, escape it with another backslash (e.g., "\\\\").

Project: {project_name}
PLAN:
{plan_json}
"""

BECKHOFF_PROFILE = VendorProfile(
    name="Beckhoff", lang="ST", file_ext=".st",
    system_prompt=BECKHOFF_SYSTEM,
    completeness_checklist="See critic prompt.",
    file_plan_prompt=BECKHOFF_PLAN,
    module_prompt=BECKHOFF_MODULE,
    critic_prompt=BECKHOFF_CRITIC,
    pack_prompt=BECKHOFF_PACK
)


















# from .orchestrator import VendorProfile
# SIEMENS_SYSTEM = """You are a Siemens S7-1500 SCL code generator.
# Rules:
# - Use SCL with TIA Portal conventions.
# - OB100 for cold start, OB1 cyclic.
# - Each FB has an Instance DB; name DBs explicitly (DB_Conveyor1, etc.).
# - Provide UDTs for Devices, Alarms, States. Expose comments on public tags.
# - No placeholders or TODOs. Implement full logic (timers, debouncing, state machines).
# - E-Stop forces safe outputs and requires reset permissives to return to Auto.

# - IMPORTANT: Do not use placeholder text, TODOs, or empty sections. Always generate complete, production-ready content.
# """
# SIEMENS_PLAN = """From this CONTRACT create a FILE PLAN in JSON:
# - "modules": array of files with:
# name, relpath, language:"SCL", type in ["OB","FB","UDT","FC"], summary,
# public_interfaces (inputs/outputs/inouts/DB refs),
# dependencies (by name), purpose (1-2 lines).
# - Include: OB100, OB1, FB_ModeMgr, FB_Conveyor (one FB but multiple instances),
# FB_MergeDivert, FB_PalletizerHS, FB_AlarmMgr, FB_Diag, FB_Comms, UDT_Device,
# UDT_Alarm, UDT_State.
# - Include a SCADA map file ("docs/Scada_Tag_Map.md") as a generated doc (not code).
# Return STRICT JSON only.
# CONTRACT:
# {contract_json}
# """
# SIEMENS_MODULE = """Generate the FULL SCL source for this module.If type=UDT, produce the UDT body. If OB/FB/FC, include full header and implementation.
# - Implement sequences as CASE state machines with explicit timeouts.
# - Use TON/TOF timers for jam detection and handshake watchdogs.
# - Comment every public I/O tag and delineate safety behavior.
# - For FBs, include VAR_INPUT/VAR_OUTPUT/VAR and CLEAR/INIT routines when needed.
# MODULE:
# {module_json}
# CONTRACT:
# {contract_json}
# """
# SIEMENS_CRITIC = """You are a Siemens SCL reviewer. Using this PLAN and FILES:
# - Verify checklist coverage; if any gap, provide patches.
# Checklist:
# {checklist}
# Return JSON:
# {{
# "status": "complete" | "patch_required",
# "patches": [{{"relpath": "...", "reason": "...", "new_content": "FULL FILE CONTENT"}}]
# }}
# PLAN:
# {plan_json}
# FILES:
# {files_json}
# CONTRACT:
# {contract_json}
# """
# SIEMENS_CHECKLIST = """
# [Siemens S7-1500 Completeness]
# - OB100: initializes modes, retentives, comms warm-up, clears timers/flags.
# - OB1: calls ModeMgr, all FB instances, alarm/diag/comms each cycle.
# - ModeMgr: Auto/Semi/Manual/Maint/E-Stop state machine with permissives.
# - Conveyor FB: Start/Stop, accumulation, PE logic, jam timer, clear sequence, interlocks.
# - Merge/Divert FB: barcode parse/validate, routing table, fallback, divert command.
# - PalletizerHS FB: Ready→InPosition→CycleStart→Complete, interlocks, watchdogs, retries,
# fault exits.
# - AlarmMgr FB: critical vs non-critical, latch/ack/reset, inhibit, first-out, summary bits.
# - Diag FB: heartbeat, firmware/version strings, timestamped events, SCADA exposure.
# - Comms FB: tag packing/unpacking, heartbeat, comms status.
# - UDTs: Device, Alarm, State with documented fields.
# - No TODO/placeholder/skeleton content. Timeouts are actual TONs with preset constants.

# - IMPORTANT: Do not use placeholder text, TODOs, or empty sections. Always generate complete, production-ready content.

# """
# SIEMENS_PACK = """Write README.md describing:
# - Project structure, FB responsibilities, instance DBs.
# - How to import into TIA Portal and compile.
# - SCADA tag mapping overview.
# Project: {project_name}
# PLAN:
# {plan_json}
# """
# SIEMENS_PROFILE = VendorProfile(
# name="Siemens", lang="SCL", file_ext=".scl",
# system_prompt=SIEMENS_SYSTEM,
# completeness_checklist=SIEMENS_CHECKLIST,
# file_plan_prompt=SIEMENS_PLAN,
# module_prompt=SIEMENS_MODULE,
# critic_prompt=SIEMENS_CRITIC,
# pack_prompt=SIEMENS_PACK
# )
# # ------------------ Rockwell Logix (Studio 5000) ------------------
# ROCKWELL_SYSTEM = """You are a Rockwell Logix 5000 code generator.
# Rules:
# - Use Structured Text for AOIs and routines; plan for MainTask (Periodic 10ms), CommsTask
# (Periodic 100ms).
# - Create UDTs (Udt_Device, Udt_Alarm, Udt_State). Create AOIs: AOI_Conveyor,
# AOI_MergeDivert, AOI_PalletizerHS, AOI_AlarmMgr, AOI_Diag, AOI_Comms, AOI_ModeMgr.
# - Provide .L5X-compatible ST bodies (user will paste/import). Include tag lists in CSV where
# helpful.
# - No placeholders/TODOs. Implement all timeouts, interlocks, and latching properly.

# - IMPORTANT: Do not use placeholder text, TODOs, or empty sections. Always generate complete, production-ready content.
# """
# ROCKWELL_PLAN = """Return JSON PLAN with "modules":
# - For each AOI: a file under "aoi/AOI_Name.st"
# - For Programs & Routines: "src/MainProgram/MainRoutine.st", "src/MainProgram/ModeMgr.st",
# etc.
# - Include "docs/Tag_Map.csv" and "docs/Import_Instructions.md" as docs.
# CONTRACT:
# {contract_json}
# """
# ROCKWELL_MODULE = """Generate FULL Structured Text for this Rockwell module (AOI or
# Routine).
# - AOIs: clearly define In/Out/Parm, Local tags, and execution logic.- Use timers (TON) via Rockwell conventions.
# - Implement alarms with latches, ACK handling, inhibit.
# MODULE:
# {module_json}
# CONTRACT:
# {contract_json}
# """
# ROCKWELL_CRITIC = """Review Rockwell PLAN/FILES for completeness. Apply checklist. If
# missing parts, return patches with full file content.
# Checklist:
# - MainTask (Periodic 10ms) and CommsTask (100ms) defined in docs/Import_Instructions.md
# with step-by-step.
# - MainRoutine calls ModeMgr and AOIs instances for each device.
# - AOI_Conveyor implements accumulation & jam timers.
# - AOI_MergeDivert parses barcode string and routes with fallback.
# - AOI_PalletizerHS sequences and timeouts w/ retries.
# - AOI_AlarmMgr supports critical/noncritical, ack/reset, inhibit, first-out.
# - AOI_Diag sets heartbeat, version, and event logs; AOI_Comms maps SCADA tags.
# - UDTs present and documented.
# Return JSON as in Siemens critic.
# PLAN:
# {plan_json}
# FILES:
# {files_json}
# CONTRACT:
# {contract_json}
# """
# ROCKWELL_PACK = """Write README for Studio 5000 import:
# - Create tasks, add programs, import AOIs, create tags.
# - Build order and common pitfalls.
# Project: {project_name}
# PLAN:
# {plan_json}
# """
# ROCKWELL_PROFILE = VendorProfile(
# name="Rockwell", lang="ST", file_ext=".st",
# system_prompt=ROCKWELL_SYSTEM,
# completeness_checklist="See critic prompt.", # already embedded
# file_plan_prompt=ROCKWELL_PLAN,
# module_prompt=ROCKWELL_MODULE,
# critic_prompt=ROCKWELL_CRITIC,pack_prompt=ROCKWELL_PACK
# )
# # ------------------ Beckhoff TwinCAT 3 ------------------
# BECKHOFF_SYSTEM = """You are a Beckhoff TwinCAT 3 ST generator.
# Rules:
# - Use ST with DUTs for UDTs; create FBs for modules; MAIN program calls all FB instances.
# - Define Tasks: Main (1–10ms) per performance intent; doc how to bind.
# - UDTs: DUT_Device, DUT_Alarm, DUT_State. FBs: FB_ModeMgr, FB_Conveyor,
# FB_MergeDivert, FB_PalletizerHS, FB_AlarmMgr, FB_Diag, FB_Comms.
# - No placeholders/TODOs. Implement full logic with TON/TOF timers (Tc2_Standard).
# """
# BECKHOFF_PLAN = """Return JSON PLAN:
# - Source files under "src/": MAIN.st, FB_*.st, DUT_*.st
# - Include "docs/TwinCAT_Setup.md" and "docs/Scada_Tag_Map.md".
# CONTRACT:
# {contract_json}
# """
# BECKHOFF_MODULE = """Generate FULL TwinCAT ST for the given module (FB/DUT/MAIN).
# - Include VAR_INPUT/VAR_OUTPUT/VAR. Use Tc2_Standard timers explicitly.
# MODULE:
# {module_json}
# CONTRACT:
# {contract_json}
# """
# BECKHOFF_CRITIC = """Review TwinCAT PLAN/FILES for completeness. If anything missing
# or weak, return patches.
# Checklist:
# - MAIN calls ModeMgr then all FB instances each cycle.
# - Conveyor: accumulation, jam timer, clear sequence.
# - MergeDivert: barcode parse/route/fallback.
# - PalletizerHS: full sequencer w/ timeouts & retries.
# - AlarmMgr: critical/noncritical, latch/ack/reset, inhibit, first-out.
# - Diag & Comms: heartbeat, version, SCADA exposure.
# Return JSON with status/patches as in Siemens critic.
# PLAN:
# {plan_json}
# FILES:
# {files_json}
# CONTRACT:{contract_json}
# """
# BECKHOFF_PACK = """README for TwinCAT import (new PLC project, add DUT/FB/MAIN,
# map I/O, set task cycle, build).
# Project: {project_name}
# PLAN:
# {plan_json}
# """
# BECKHOFF_PROFILE = VendorProfile(
# name="Beckhoff", lang="ST", file_ext=".st",
# system_prompt=BECKHOFF_SYSTEM,
# completeness_checklist="See critic prompt.",
# file_plan_prompt=BECKHOFF_PLAN,
# module_prompt=BECKHOFF_MODULE,
# critic_prompt=BECKHOFF_CRITIC,
# pack_prompt=BECKHOFF_PACK
# )
