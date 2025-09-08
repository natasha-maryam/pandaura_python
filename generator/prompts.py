# generator/prompts.py
SPEC_CONTRACT_SYSTEM = """You produce STRICT JSON contracts for PLC control
projects.
- No commentary, no code, no markdown.
- Must enumerate every subsystem, state, alarm, sequence, handshake, timeout, diagnostic,
SCADA tag, and performance constraint.
- Include arrays with counts for instances (e.g., conveyors[], scanners[], merges[]).
- Include vendor-agnostic requirements plus vendor mapping notes for Siemens S7-1500,
Rockwell Logix, Beckhoff TwinCAT 3.
"""
SPEC_CONTRACT_USER = """Build a complete contract from the following spec. Resolve
ambiguities conservatively.
Return JSON with keys:
- "modes": full list with transitions, permissives, estop behavior
- "conveyors": accumulation, jam detection, sensors, timers, clear sequence
- "merge_divert": barcode schema, routing table, fallback paths
- "palletizer_handshake": states, interlocks, watchdogs, retries, fault exits- "alarms": critical/noncritical, class, latch/ack/reset, inhibit, first-out
- "diagnostics": SCADA exposure, heartbeat, versioning, timestamped events
- "comms": interfaces (SCADA/PLC), tag naming rules
- "redundancy": if spec references it, model software/state equivalents
- "vendor_mapping": keys: siemens, rockwell, beckhoff (notes per vendor)
- "instances": counts and identities for each device/subsystem
- "udts": list of required UDT/DUT structures and fields
- "test_cases": Gherkin-style acceptance tests for each feature
SPEC:
{spec_text}
"""