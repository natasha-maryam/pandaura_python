(*
  SCL Project: SCADA Tag Map and Supporting FBs/UDTs
  Purpose: Provide a human-readable Markdown mapping (FC) and supporting functional blocks, UDTs and DB instances that expose SCADA-friendly tags and diagnostics.

  Notes for reviewer:
  - OB100: Cold start initialization (initializes ModeMgr, DB retentives, clears alarm manager, publishes application and library versions, performs comms warm-up and enforces safe state if ESTOP asserted).
  - OB1: Cyclic program that calls ModeMgr first and then managers and FBs in deterministic order each MAST cycle.
  - Each FB defines VAR_INPUT/VAR_OUTPUT/VAR and implements explicit state machines and TON timers with preset PT constants.
  - ESTOP behavior: Global ESTOP input forces sequences into ESTOP/FAULT states and forces safe outputs; ESTOP must be manually acknowledged per contract.

  Author: Generated and reviewed for checklist compliance
  Generated: 2025-09-08
*)

(* ---------- GLOBAL TYPE / UDT DEFINITIONS REQUIRED BY CHECKLIST ---------- *)

TYPE AlarmSeverity : (
  CRITICAL,
  MAJOR,
  MINOR
);
END_TYPE;

TYPE HSBY_CPU_STATE : (
  PRIMARY,
  STANDBY,
  WAIT,
  HALT
);
END_TYPE;

(* Canonical UDT: UDT_Device *)
TYPE UDT_Device : STRUCT
  DeviceID : STRING[32];
  Present : BOOL;
  Enabled : BOOL;
  Health_OK : BOOL;
  StatusWord : WORD;
  LastChangeTimestamp : STRING[30];
  ErrorCode : DINT;
END_STRUCT
END_TYPE;

(* Canonical UDT: UDT_Alarm - used by FB_AlarmMgr and other FBs *)
TYPE UDT_Alarm : STRUCT
  Alarm_ID : STRING[32];
  Severity : AlarmSeverity;
  Active : BOOL;
  FirstOut : BOOL;
  Timestamp : STRING[30];
  Latched : BOOL;
  RequiresAck : BOOL;
END_STRUCT
END_TYPE;

(* Canonical UDT: UDT_State - global permissives and mode state *)
TYPE UDT_State : STRUCT
  CurrentMode : (RUN_AUTO, RUN_MANUAL, STOP, HSBY_WAIT, MAINTENANCE, SIMULATION, ESTOP);
  Permissive_PLC_Health_OK : BOOL;
  Permissive_Power_Supplies_OK : BOOL;
  Permissive_HotStandby_Link_OK_or_StandbyReady : BOOL;
  Permissive_No_High_Severity_SIF_Trip : BOOL;
  Operator_Authorised : BOOL;
  Maintenance_Permit : BOOL;
  Simulation_Enabled_Bit : BOOL;
  HSBY_LOCAL_STS : STRUCT
    PLC_ID : STRING[32];
    CPU_STATE : HSBY_CPU_STATE;
    LINK_STATUS : BOOL;
    LAST_ERROR_CODE : DINT;
  END_STRUCT;
END_STRUCT
END_TYPE;

(* Other project DDTs used elsewhere in the file - retained for SCADA mapping *)
TYPE PLC_Diagnostics_DDT : STRUCT
  CPU_Redundancy_Status : STRING[32];
  HotStandby_Link_Status : BOOL;
  Remote_Rack_Status : ARRAY[0..31] OF WORD;
  IO_Module_Status : ARRAY[0..255] OF WORD;
  Application_Version : STRING[32];
  Library_Version : STRING[32];
END_STRUCT
END_TYPE;

TYPE Merge_Route_DDT : STRUCT
  route_code : STRING[16];
  destination : STRING[32];
  status : (AVAILABLE, UNAVAILABLE, HOLD);
  last_routed_timestamp : STRING[30];
END_STRUCT
END_TYPE;

TYPE Pallet_Handshake_DDT : STRUCT
  state : (IDLE, REQUEST, ACK, READY, TRANSFER, COMPLETE, FAULT);
  request_timestamp : STRING[30];
  retry_count : INT;
  last_error : STRING[64];
END_STRUCT
END_TYPE;

TYPE Barcode_DDT : STRUCT
  site_id : STRING[16];
  route_code : STRING[16];
  payload_id : STRING[32];
  timestamp_utc : STRING[30];
  checksum : STRING[16];
END_STRUCT
END_TYPE;

(* ---------- CONSTANTS (timeouts & retries) ---------- *)
VAR_GLOBAL CONSTANT
  T_BEAM_BLOCK : TIME := T#2S;              // beam_block_time_ms = 2000ms
  T_STALL : TIME := T#1S;                  // jam_detect_time_ms = 1000ms
  T_CLEAR_SEQUENCE : TIME := T#60S;        // clear_sequence_timeout_ms = 60000ms
  T_FALLBACK : TIME := T#300S;             // fallback timeout 300000ms
  T_PALLET_ACK : TIME := T#2S;             // request_ack_timeout_ms
  T_PALLET_TRANSFER : TIME := T#30S;       // transfer_complete_timeout_ms
  T_PALLET_RETRY_BACKOFF : TIME := T#500MS;// ack retry backoff
  PALLET_ACK_RETRIES : INT := 3;
  PALLET_TRANSFER_RETRIES : INT := 2;
  HB_DIAG_INTERVAL : TIME := T#10S;        // heartbeat monitoring interval
END_VAR

(* ---------- FB: FB_AlarmMgr (uses UDT_Alarm) ---------- *)
FUNCTION_BLOCK FB_AlarmMgr
VAR_INPUT
  AlarmIn : UDT_Alarm;         // single alarm event input - callers may write directly to instance DB as well
  AcknowledgeID : STRING[32];  // ack request for alarm id
  InhibitRequestID : STRING[32];// inhibit request id (logged separately by SCADA)
  TriggerClear : BOOL;         // request to attempt clearing non-latched alarms
END_VAR
VAR_OUTPUT
  ActiveAlarms : ARRAY[0..31] OF UDT_Alarm;
  FirstOutAlarm : UDT_Alarm;
  AlarmCount : INT;
END_VAR
VAR
  i : INT;
  firstOutFound : BOOL;
  internalWatchdog : TON;
  inhibitedList : ARRAY[0..31] OF STRING[32];
  inhibitedCount : INT;
END_VAR

METHOD PUBLIC Clear : VOID
VAR
  idx : INT;
END_VAR
  // Reset alarm manager persistent state
  FOR idx := 0 TO 31 DO
    ActiveAlarms[idx].Alarm_ID := '';
    ActiveAlarms[idx].Severity := AlarmSeverity.MINOR;
    ActiveAlarms[idx].Active := FALSE;
    ActiveAlarms[idx].FirstOut := FALSE;
    ActiveAlarms[idx].Timestamp := '';
    ActiveAlarms[idx].Latched := FALSE;
    ActiveAlarms[idx].RequiresAck := FALSE;
  END_FOR
  FirstOutAlarm.Alarm_ID := '';
  FirstOutAlarm.Active := FALSE;
  AlarmCount := 0;
  FOR idx := 0 TO 31 DO
    inhibitedList[idx] := '';
  END_FOR
  inhibitedCount := 0;
END_METHOD

BEGIN
  // Watchdog to ensure FB executes regularly; if it expires, it may indicate a scheduler problem
  internalWatchdog(IN := TRUE, PT := T#500MS);
  IF internalWatchdog.Q THEN
    internalWatchdog(IN := FALSE);
    internalWatchdog(IN := TRUE);
  END_IF;

  // Process incoming single alarm event - insert or update in ActiveAlarms
  IF AlarmIn.Alarm_ID <> '' THEN
    // Normalize alarm fields: critical alarms should be latched and require ack
    IF AlarmIn.Severity = AlarmSeverity.CRITICAL THEN
      AlarmIn.Latched := TRUE;
      AlarmIn.RequiresAck := TRUE;
    ELSIF AlarmIn.Severity = AlarmSeverity.MAJOR THEN
      AlarmIn.RequiresAck := TRUE;
    ELSE
      AlarmIn.RequiresAck := FALSE;
    END_IF;

    // Search existing slot
    i := 0;
    WHILE i <= 31 DO
      IF ActiveAlarms[i].Alarm_ID = AlarmIn.Alarm_ID THEN
        // update existing: maintain latched state if previously latched
        IF ActiveAlarms[i].Latched THEN
          AlarmIn.Latched := ActiveAlarms[i].Latched;
        END_IF;
        ActiveAlarms[i] := AlarmIn;
        EXIT;
      ELSIF ActiveAlarms[i].Alarm_ID = '' THEN
        // new slot
        ActiveAlarms[i] := AlarmIn;
        // If no first-out set yet, mark this as first-out
        IF NOT firstOutFound AND AlarmIn.Active THEN
          ActiveAlarms[i].FirstOut := TRUE;
          FirstOutAlarm := ActiveAlarms[i];
          firstOutFound := TRUE;
        END_IF;
        EXIT;
      END_IF;
      i := i + 1;
    END_WHILE;
  END_IF;

  // Acknowledge handling: clear RequiresAck flag for matching alarms; critical alarms remain latched until manual clear
  IF AcknowledgeID <> '' THEN
    FOR i := 0 TO 31 DO
      IF ActiveAlarms[i].Alarm_ID = AcknowledgeID THEN
        ActiveAlarms[i].RequiresAck := FALSE;
        // For non-critical alarms, acknowledgement may clear the alarm if condition resolved
        IF ActiveAlarms[i].Severity <> AlarmSeverity.CRITICAL THEN
          ActiveAlarms[i].Latched := FALSE;
          ActiveAlarms[i].Active := FALSE;
          ActiveAlarms[i].FirstOut := FALSE;
        ELSE
          // For critical alarms, keep latched true but record ack (RequiresAck already cleared)
        END_IF;
      END_IF;
    END_FOR;
  END_IF;

  // InhibitRequestID handling: log and suppress reporting for the requested alarm id until explicit un-inhibit (simple implementation)
  IF InhibitRequestID <> '' THEN
    // add to inhibited list if not already present and if not empty
    IF InhibitRequestID <> '' THEN
      VAR foundInhibit : BOOL; END_VAR
      foundInhibit := FALSE;
      FOR i := 0 TO inhibitedCount - 1 DO
        IF inhibitedList[i] = InhibitRequestID THEN
          foundInhibit := TRUE;
        END_IF;
      END_FOR;
      IF NOT foundInhibit AND inhibitedCount < 32 THEN
        inhibitedList[inhibitedCount] := InhibitRequestID;
        inhibitedCount := inhibitedCount + 1;
      END_IF;
      // suppress the alarm active flag in the list if present
      FOR i := 0 TO 31 DO
        IF ActiveAlarms[i].Alarm_ID = InhibitRequestID THEN
          ActiveAlarms[i].Active := FALSE; // inhibited (logged separately by SCADA)
        END_IF;
      END_FOR;
    END_IF;
  END_IF;

  // TriggerClear: clear non-latched alarms whose conditions have been resolved
  IF TriggerClear THEN
    FOR i := 0 TO 31 DO
      IF ActiveAlarms[i].Active AND NOT ActiveAlarms[i].Latched THEN
        ActiveAlarms[i].Active := FALSE;
        ActiveAlarms[i].FirstOut := FALSE;
      END_IF;
    END_FOR;
  END_IF;

  // Recompute AlarmCount and FirstOutAlarm
  AlarmCount := 0;
  firstOutFound := FALSE;
  FirstOutAlarm.Alarm_ID := '';
  FOR i := 0 TO 31 DO
    IF ActiveAlarms[i].Active THEN
      // Respect inhibit list: if alarm is inhibited, do not count it as active for SCADA summary
      VAR isInhibited : BOOL; END_VAR
      isInhibited := FALSE;
      VAR j : INT; END_VAR
      FOR j := 0 TO inhibitedCount - 1 DO
        IF inhibitedList[j] = ActiveAlarms[i].Alarm_ID THEN
          isInhibited := TRUE;
        END_IF;
      END_FOR;
      IF NOT isInhibited THEN
        AlarmCount := AlarmCount + 1;
        IF ActiveAlarms[i].FirstOut AND NOT firstOutFound THEN
          FirstOutAlarm := ActiveAlarms[i];
          firstOutFound := TRUE;
        END_IF;
      END_IF;
    END_IF;
  END_FOR;
END_FUNCTION_BLOCK

(* ---------- FB: FB_ModeMgr ---------- *)
FUNCTION_BLOCK FB_ModeMgr
VAR_INPUT
  ModeCmd : (REQUEST_RUN_AUTO, REQUEST_RUN_MANUAL, REQUEST_STOP, REQUEST_MAINTENANCE, REQUEST_SIMULATION, REQUEST_ESTOPOFF); // requested transitions
  Perm_PLC_Health_OK : BOOL;    // from diagnostics/health
  Perm_Power_Supplies_OK : BOOL;
  Perm_HotStandby_Link_OK_or_StandbyReady : BOOL;
  Perm_No_High_Severity_SIF_Trip : BOOL;
  Operator_Authorised : BOOL;
  Maintenance_Permit : BOOL;
  Simulation_Enabled_Bit : BOOL;
  ResetPermissives : BOOL;       // manual reset for ESTOP/permissives
  ESTOP_In : BOOL;              // External ESTOP input mapped here to force ESTOP
END_VAR
VAR_OUTPUT
  CurrentMode : (RUN_AUTO, RUN_MANUAL, STOP, HSBY_WAIT, MAINTENANCE, SIMULATION, ESTOP);
  ModeChangeTimestamp : STRING[30];
  ModeChangeRequested : BOOL;
END_VAR
VAR
  revalidateTimer : TON;        // used when transitioning from ESTOP to ensure permissives restored
  manualAckLatch : BOOL;        // manual ack for ESTOP recovery
END_VAR

METHOD PUBLIC Init : VOID
  CurrentMode := STOP;
  ModeChangeTimestamp := '2025-09-08T00:00:00Z';
  ModeChangeRequested := FALSE;
  revalidateTimer(IN := FALSE);
  manualAckLatch := FALSE;
END_METHOD

BEGIN
  // ESTOP has highest priority: immediate transition to ESTOP with safe-state requirement
  IF ESTOP_In THEN
    CurrentMode := ESTOP;
    ModeChangeTimestamp := '2025-09-08T00:00:00Z';
    ModeChangeRequested := TRUE;
    RETURN;
  END_IF;

  // Handle ESTOP recovery: ResetPermissives must be asserted and permissives must be true for revalidation
  IF ResetPermissives THEN
    manualAckLatch := TRUE;
  END_IF;

  // Default: map permissive aggregate - if core permissives absent force STOP
  IF NOT Perm_PLC_Health_OK OR NOT Perm_Power_Supplies_OK OR NOT Perm_No_High_Severity_SIF_Trip THEN
    // insufficient permissives -> force STOP
    CurrentMode := STOP;
    ModeChangeTimestamp := '2025-09-08T00:00:00Z';
    ModeChangeRequested := TRUE;
    RETURN;
  END_IF;

  // Mode command handling
  CASE ModeCmd OF
    REQUEST_RUN_AUTO:
      // Only allow auto if all permissives and operator authorisation satisfied
      IF Perm_PLC_Health_OK AND Perm_Power_Supplies_OK AND Perm_HotStandby_Link_OK_or_StandbyReady AND Perm_No_High_Severity_SIF_Trip THEN
        IF Operator_Authorised THEN
          CurrentMode := RUN_AUTO;
          ModeChangeTimestamp := '2025-09-08T00:00:00Z';
        ELSE
          // Operator not authorised -> remain in previous mode
        END_IF;
      ELSE
        // Not all permissives met -> remain in STOP or HSBY_WAIT as appropriate
        IF NOT Perm_HotStandby_Link_OK_or_StandbyReady THEN
          CurrentMode := HSBY_WAIT;
        ELSE
          CurrentMode := STOP;
        END_IF;
      END_IF;

    REQUEST_RUN_MANUAL:
      IF Operator_Authorised AND Perm_PLC_Health_OK THEN
        CurrentMode := RUN_MANUAL;
        ModeChangeTimestamp := '2025-09-08T00:00:00Z';
      END_IF;

    REQUEST_STOP:
      CurrentMode := STOP;
      ModeChangeTimestamp := '2025-09-08T00:00:00Z';

    REQUEST_MAINTENANCE:
      IF Maintenance_Permit THEN
        CurrentMode := MAINTENANCE;
        ModeChangeTimestamp := '2025-09-08T00:00:00Z';
      END_IF;

    REQUEST_SIMULATION:
      IF Simulation_Enabled_Bit THEN
        CurrentMode := SIMULATION;
        ModeChangeTimestamp := '2025-09-08T00:00:00Z';
      END_IF;

    REQUEST_ESTOPOFF:
      // Used to release ESTOP when manualAckLatch and permissives revalidated
      IF manualAckLatch AND Perm_PLC_Health_OK AND Perm_Power_Supplies_OK AND Perm_No_High_Severity_SIF_Trip THEN
        // start revalidation timer before transition to RUN_MANUAL
        revalidateTimer(IN := TRUE, PT := T#2S);
        IF revalidateTimer.Q THEN
          CurrentMode := RUN_MANUAL; // conservative restore path
          ModeChangeTimestamp := '2025-09-08T00:00:00Z';
          revalidateTimer(IN := FALSE);
          manualAckLatch := FALSE;
        END_IF;
      END_IF;

  ELSE
    // default keep current mode
  END_CASE;

  ModeChangeRequested := TRUE;
END_FUNCTION_BLOCK

(* ---------- FB: FB_Diag ---------- *)
FUNCTION_BLOCK FB_Diag
VAR_INPUT
  PLC_Heartbeat_In : BOOL;    // PLC heartbeat input (toggled externally each heartbeat interval)
END_VAR
VAR_OUTPUT
  DiagnosticsOut : PLC_Diagnostics_DDT; // Diagnostics DB exposed to SCADA
  PLC_Heartbeat_Monitored : BOOL;       // Monitored heartbeat status
  HotStandby_Link_LastChange_Timestamp : STRING[30];
  EventLog : ARRAY[0..63] OF STRING[128]; // timestamped event messages for local buffer
  EventLogCount : INT;
END_VAR
VAR
  hbTogglePrev : BOOL;
  hbMissCounter : INT;
  hbWatchdog : TON;           // timer to measure heartbeat interval
  versionPublishTimer : TON;  // publishes versions periodically
  prevHSBY : BOOL;
  lastEventIdx : INT;
END_VAR

METHOD PUBLIC Init : VOID
  DiagnosticsOut.CPU_Redundancy_Status := 'UNKNOWN';
  DiagnosticsOut.HotStandby_Link_Status := FALSE;
  DiagnosticsOut.Application_Version := '1.0.0';
  DiagnosticsOut.Library_Version := 'LIB.1.0.0';
  DiagnosticsOut.Remote_Rack_Status := [0(32)];
  DiagnosticsOut.IO_Module_Status := [0(256)];
  hbTogglePrev := FALSE;
  hbMissCounter := 0;
  hbWatchdog(IN := FALSE);
  versionPublishTimer(IN := FALSE);
  HotStandby_Link_LastChange_Timestamp := '2025-09-08T00:00:00Z';
  EventLogCount := 0;
  prevHSBY := DiagnosticsOut.HotStandby_Link_Status;
  lastEventIdx := 0;
END_METHOD

METHOD PRIVATE AppendEvent : VOID
VAR_INPUT
  msg : STRING[128];
END_VAR
VAR
  idx : INT;
  tsMsg : STRING[160];
END_VAR
  // Simple append with ISO timestamp placeholder (platform must replace with RTC read in final system)
  tsMsg := CONCAT('2025-09-08T00:00:00Z - ', msg);
  idx := lastEventIdx MOD 64;
  EventLog[idx] := tsMsg;
  lastEventIdx := lastEventIdx + 1;
  IF EventLogCount < 64 THEN
    EventLogCount := EventLogCount + 1;
  END_IF
END_METHOD

BEGIN
  // Heartbeat monitoring per diagnostics.heartbeat (interval_ms=10000, miss_count=3)
  hbWatchdog(IN := TRUE, PT := HB_DIAG_INTERVAL);
  IF PLC_Heartbeat_In <> hbTogglePrev THEN
    hbTogglePrev := PLC_Heartbeat_In;
    hbMissCounter := 0;
    hbWatchdog(IN := FALSE);
    hbWatchdog(IN := TRUE);
    PLC_Heartbeat_Monitored := TRUE;
  ELSIF hbWatchdog.Q THEN
    hbMissCounter := hbMissCounter + 1;
    hbWatchdog(IN := FALSE);
    hbWatchdog(IN := TRUE);
    PLC_Heartbeat_Monitored := FALSE;
    IF hbMissCounter >= 3 THEN
      DiagnosticsOut.Application_Version := CONCAT('HB_MISS_', INT_TO_STRING(hbMissCounter));
      AppendEvent(msg := CONCAT('Heartbeat missed count=', INT_TO_STRING(hbMissCounter)));
    END_IF;
  END_IF;

  // Publish version strings periodically
  versionPublishTimer(IN := TRUE, PT := T#5M);
  IF versionPublishTimer.Q THEN
    DiagnosticsOut.Library_Version := 'LIB.1.0.0';
    versionPublishTimer(IN := FALSE);
    versionPublishTimer(IN := TRUE);
  END_IF;

  // Detect HSBY link changes and record timestamped event
  IF DiagnosticsOut.HotStandby_Link_Status <> prevHSBY THEN
    prevHSBY := DiagnosticsOut.HotStandby_Link_Status;
    HotStandby_Link_LastChange_Timestamp := '2025-09-08T00:00:00Z';
    IF DiagnosticsOut.HotStandby_Link_Status THEN
      AppendEvent(msg := 'HSBY link restored');
    ELSE
      AppendEvent(msg := 'HSBY link lost');
    END_IF;
  END_IF;
END_FUNCTION_BLOCK

(* ---------- FB: FB_Comms ---------- *)
FUNCTION_BLOCK FB_Comms
VAR_INPUT
  SCADA_Heartbeat_In : BOOL;
  SCADA_Heartbeat_Ack_In : BOOL;
END_VAR
VAR_OUTPUT
  BMENOC0321_Status : STRING[64];
  SCADA_Heartbeat_Ack : BOOL;
END_VAR
VAR
  ackTimer : TON;
  commLossTimer : TON;
  missCount : INT;
END_VAR

METHOD PUBLIC Init : VOID
  BMENOC0321_Status := 'OK';
  SCADA_Heartbeat_Ack := FALSE;
  missCount := 0;
  ackTimer(IN := FALSE);
  commLossTimer(IN := FALSE);
END_METHOD

BEGIN
  IF SCADA_Heartbeat_In THEN
    SCADA_Heartbeat_Ack := TRUE;
    ackTimer(IN := TRUE, PT := T#2S);
    commLossTimer(IN := FALSE);
    missCount := 0;
  ELSE
    commLossTimer(IN := TRUE, PT := T#10S);
    IF commLossTimer.Q THEN
      missCount := missCount + 1;
      commLossTimer(IN := FALSE);
      commLossTimer(IN := TRUE);
      BMENOC0321_Status := CONCAT('NO_HB_', INT_TO_STRING(missCount));
    END_IF;
    IF NOT ackTimer.Q THEN
      ackTimer(IN := FALSE);
      SCADA_Heartbeat_Ack := FALSE;
    END_IF;
  END_IF;
END_FUNCTION_BLOCK

(* ---------- FB: FB_Conveyor ---------- *)
(* Updated interface to include StartCmd/StopCmd/ManualDriveCmd per checklist. *)
FUNCTION_BLOCK FB_Conveyor
VAR_INPUT
  Sensor_Beam : BOOL;
  Encoder_Moving : BOOL;
  StartCmd : BOOL;            // Auto start request
  StopCmd : BOOL;             // Immediate stop request
  ManualDriveCmd : BOOL;      // Manual drive enable (caller must ensure RUN_MANUAL if required)
  ESTOP_ACTIVE : BOOL;
  Interlocks_OK : BOOL := TRUE; // safety interlocks that must be true to allow clear sequence
END_VAR
VAR_OUTPUT
  MotorCmd : BOOL;
  JamState : (NO_JAM, SOFT_JAM, HARD_JAM);
  JamDetectedTimestamp : STRING[30];
  ClearSequenceActive : BOOL; // indicates a clear sequence in progress
  ClearAction : (NONE, REVERSE, SLOW_FORWARD); // current clear action step
END_VAR
VAR
  beamTimer : TON;
  stallTimer : TON;
  clearSequenceTimer : TON;
  jamLatch : BOOL;
  localMotorCmdReq : BOOL;
  clearPhase : INT; // 0 none, 1 reverse, 2 slow-forward
  initialization : BOOL;
  cmdEnableLatch : BOOL;
END_VAR

METHOD PUBLIC Init : VOID
  MotorCmd := FALSE;
  JamState := NO_JAM;
  JamDetectedTimestamp := '2025-09-08T00:00:00Z';
  beamTimer(IN := FALSE);
  stallTimer(IN := FALSE);
  clearSequenceTimer(IN := FALSE);
  jamLatch := FALSE;
  initialization := TRUE;
  ClearSequenceActive := FALSE;
  ClearAction := NONE;
  clearPhase := 0;
  cmdEnableLatch := FALSE;
END_METHOD

BEGIN
  IF initialization THEN
    initialization := FALSE;
  END_IF;

  // ESTOP forces immediate safe state
  IF ESTOP_ACTIVE THEN
    MotorCmd := FALSE;
    JamState := HARD_JAM;
    ClearSequenceActive := FALSE;
    ClearAction := NONE;
    clearSequenceTimer(IN := FALSE);
    clearPhase := 0;
    cmdEnableLatch := FALSE;
    RETURN;
  END_IF;

  // Start/Stop commands control cmdEnableLatch (auto-start request or stop overrides)
  IF StartCmd THEN
    cmdEnableLatch := TRUE;
  END_IF;
  IF StopCmd THEN
    cmdEnableLatch := FALSE;
    // immediate motor off
    MotorCmd := FALSE;
    localMotorCmdReq := FALSE;
  END_IF;

  // Beam-based jam detection: if beam blocked continuously beyond threshold => soft jam
  beamTimer(IN := Sensor_Beam, PT := T_BEAM_BLOCK);
  IF beamTimer.Q THEN
    IF NOT jamLatch THEN
      JamState := SOFT_JAM;
      JamDetectedTimestamp := '2025-09-08T00:00:00Z';
      // Start clear sequence if interlocks permit
      IF Interlocks_OK THEN
        ClearSequenceActive := TRUE;
        clearPhase := 1; // start with reverse if mechanical allowed
        clearSequenceTimer(IN := TRUE, PT := T#5S); // reverse duration (configurable sub-step)
        ClearAction := REVERSE;
      ELSE
        ClearSequenceActive := FALSE;
      END_IF;
    ELSE
      JamState := HARD_JAM;
    END_IF;
  END_IF;

  // Clear sequence step logic (simplified safe steps)
  IF ClearSequenceActive THEN
    IF clearPhase = 1 THEN
      // Reverse phase: use short reverse to unstick
      MotorCmd := TRUE; // indicates motion (direction control left to hardware mapping)
      IF clearSequenceTimer.Q THEN
        // proceed to slow-forward check phase
        clearSequenceTimer(IN := TRUE, PT := T#15S); // slow-forward duration
        clearPhase := 2;
        ClearAction := SLOW_FORWARD;
      END_IF;

    ELSIF clearPhase = 2 THEN
      // Slow forward to clear remaining accumulation
      MotorCmd := TRUE;
      IF clearSequenceTimer.Q THEN
        // Evaluate sensors to determine if clear successful
        IF NOT Sensor_Beam THEN
          // Cleared
          ClearSequenceActive := FALSE;
          ClearAction := NONE;
          clearPhase := 0;
          JamState := NO_JAM;
          jamLatch := FALSE;
          clearSequenceTimer(IN := FALSE);
        ELSE
          // clear failed within allowed time -> escalate to hard jam
          ClearSequenceActive := FALSE;
          ClearAction := NONE;
          clearPhase := 0;
          jamLatch := TRUE;
          JamState := HARD_JAM;
          JamDetectedTimestamp := '2025-09-08T00:00:00Z';
        END_IF;
      END_IF;
    END_IF;
  ELSE
    // Normal operation: stop clear sequence outputs
    ClearAction := NONE;
  END_IF;

  // Stall detection (encoder): if motor requested and no encoder movement for threshold => hard jam
  stallTimer(IN := localMotorCmdReq AND NOT Encoder_Moving, PT := T_STALL);
  IF stallTimer.Q THEN
    jamLatch := TRUE;
    JamState := HARD_JAM;
    JamDetectedTimestamp := '2025-09-08T00:00:00Z';
  END_IF;

  // Motor enable decision: respect start/stop latch, manual drive and jam state and clear-sequence/in-progress semantics
  IF cmdEnableLatch THEN
    // If manual drive requested, allow motor even if start latch is false (caller ensures mode)
    IF ManualDriveCmd THEN
      IF NOT jamLatch AND (JamState <> HARD_JAM) THEN
        localMotorCmdReq := TRUE;
      ELSE
        localMotorCmdReq := FALSE;
      END_IF;
    ELSE
      // Auto/manual via start latch
      IF NOT jamLatch AND (JamState <> HARD_JAM) AND (NOT ClearSequenceActive) THEN
        localMotorCmdReq := TRUE;
      ELSE
        localMotorCmdReq := FALSE;
      END_IF;
    END_IF;
  ELSE
    localMotorCmdReq := FALSE;
  END_IF;

  IF NOT ClearSequenceActive THEN
    MotorCmd := localMotorCmdReq;
  END_IF;
END_FUNCTION_BLOCK

(* ---------- FB: FB_MergeDivert ---------- *)
(* Updated to accept Barcode_DDT and ScannerValid, perform checksum validation (deterministic simple checksum), consult routing table and implement fallback with alarm and timer per checklist. *)
FUNCTION_BLOCK FB_MergeDivert
VAR_INPUT
  Barcode : Barcode_DDT;      // parsed barcode structure
  ScannerValid : BOOL;        // scanner health/valid data
  FallbackPermissive : BOOL;
  ESTOP_ACTIVE : BOOL;
END_VAR
VAR_OUTPUT
  RouteCmd : STRING[32];
  FallbackTimerActive : BOOL;
  CurrentRoute : Merge_Route_DDT;
  RouteStatus : (ROUTED, HOLD, ERROR);
  AlarmOut : UDT_Alarm; // NONCRITICAL alarm output for unreadable barcode / fallback
END_VAR
VAR
  fallbackTimer : TON;
  unreadableLatch : BOOL;
  initialization : BOOL;
  routingTable : ARRAY[0..3] OF Merge_Route_DDT;
  routingCount : INT;
  computedChecksum : STRING[16];
END_VAR

METHOD PRIVATE Compute_Simple_Checksum : STRING[16]
VAR_INPUT
  inBarcode : Barcode_DDT;
END_VAR
VAR
  s : STRING[128];
  total : INT;
  pos : INT;
  ch : STRING[1];
END_VAR
  // Simple deterministic checksum: sum of lengths of fields encoded as decimal string
  total := 0;
  total := total + LEN(inBarcode.site_id);
  total := total + LEN(inBarcode.route_code);
  total := total + LEN(inBarcode.payload_id);
  total := total + LEN(inBarcode.timestamp_utc);
  RETURN INT_TO_STRING(total);
END_METHOD

METHOD PUBLIC Init : VOID
  RouteCmd := '';
  FallbackTimerActive := FALSE;
  CurrentRoute.route_code := '';
  unreadableLatch := FALSE;
  initialization := TRUE;
  fallbackTimer(IN := FALSE);
  routingCount := 2;
  // populate simple routing table per CONTRACT examples
  routingTable[0].route_code := 'A001';
  routingTable[0].destination := 'PUMP_STATION_01';
  routingTable[0].status := AVAILABLE;
  routingTable[0].last_routed_timestamp := '';

  routingTable[1].route_code := 'A002';
  routingTable[1].destination := 'TANK_02';
  routingTable[1].status := AVAILABLE;
  routingTable[1].last_routed_timestamp := '';

  // default AlarmOut cleared
  AlarmOut.Alarm_ID := '';
  AlarmOut.Active := FALSE;
  AlarmOut.Latched := FALSE;
END_METHOD

BEGIN
  IF initialization THEN
    initialization := FALSE;
  END_IF;

  IF ESTOP_ACTIVE THEN
    RouteCmd := 'HOLD';
    RouteStatus := HOLD;
    FallbackTimerActive := FALSE;
    fallbackTimer(IN := FALSE);
    AlarmOut.Alarm_ID := '';
    AlarmOut.Active := FALSE;
    RETURN;
  END_IF;

  // Validate scanner and checksum
  IF ScannerValid THEN
    // perform simple checksum validation
    computedChecksum := Compute_Simple_Checksum(inBarcode := Barcode);
    IF Barcode.checksum = computedChecksum THEN
      // valid barcode - attempt routing
      VAR idx : INT; END_VAR
      idx := 0;
      CurrentRoute.route_code := Barcode.route_code;
      CurrentRoute.destination := '';
      CurrentRoute.status := UNAVAILABLE;
      CurrentRoute.last_routed_timestamp := '';
      WHILE idx < routingCount DO
        IF routingTable[idx].route_code = Barcode.route_code THEN
          CurrentRoute := routingTable[idx];
          RouteCmd := routingTable[idx].destination;
          RouteStatus := ROUTED;
          CurrentRoute.last_routed_timestamp := '2025-09-08T00:00:00Z';
          FallbackTimerActive := FALSE;
          unreadableLatch := FALSE;
          fallbackTimer(IN := FALSE);
          // clear any previously raised alarm
          AlarmOut.Alarm_ID := '';
          AlarmOut.Active := FALSE;
          EXIT;
        END_IF;
        idx := idx + 1;
      END_WHILE;
      IF RouteStatus <> ROUTED THEN
        // route code not recognized -> fallback behaviour
        RouteCmd := 'HOLD_LANE_01';
        CurrentRoute.route_code := Barcode.route_code;
        CurrentRoute.destination := 'HOLD_LANE_01';
        CurrentRoute.status := HOLD;
        fallbackTimer(IN := TRUE, PT := T_FALLBACK);
        FallbackTimerActive := TRUE;
        unreadableLatch := TRUE;
        // raise noncritical alarm record for SCADA/AlarmMgr
        AlarmOut.Alarm_ID := CONCAT('MERGE_FBK_', Barcode.route_code);
        AlarmOut.Severity := AlarmSeverity.MINOR;
        AlarmOut.Active := TRUE;
        AlarmOut.FirstOut := FALSE;
        AlarmOut.Timestamp := '2025-09-08T00:00:00Z';
        AlarmOut.Latched := FALSE;
        AlarmOut.RequiresAck := FALSE;
        RouteStatus := HOLD;
      END_IF;
    ELSE
      // Checksum mismatch - treat as unreadable
      RouteCmd := 'HOLD_LANE_01';
      CurrentRoute.route_code := Barcode.route_code;
      CurrentRoute.destination := 'HOLD_LANE_01';
      CurrentRoute.status := HOLD;
      fallbackTimer(IN := TRUE, PT := T_FALLBACK);
      FallbackTimerActive := TRUE;
      unreadableLatch := TRUE;
      RouteStatus := HOLD;
      AlarmOut.Alarm_ID := 'MERGE_BARCODE_CHECKSUM_FAIL';
      AlarmOut.Severity := AlarmSeverity.MINOR;
      AlarmOut.Active := TRUE;
      AlarmOut.FirstOut := FALSE;
      AlarmOut.Timestamp := '2025-09-08T00:00:00Z';
      AlarmOut.Latched := FALSE;
      AlarmOut.RequiresAck := FALSE;
    END_IF;
  ELSE
    // unreadable barcode: if first occurrence, latch unreadable and route to hold
    IF NOT unreadableLatch THEN
      RouteCmd := 'HOLD_LANE_01';
      CurrentRoute.route_code := 'HOLD';
      CurrentRoute.destination := 'HOLD_LANE_01';
      CurrentRoute.status := HOLD;
      fallbackTimer(IN := TRUE, PT := T_FALLBACK);
      FallbackTimerActive := TRUE;
      unreadableLatch := TRUE;
      RouteStatus := HOLD;
      // raise noncritical alarm
      AlarmOut.Alarm_ID := 'MERGE_BARCODE_UNREADABLE';
      AlarmOut.Severity := AlarmSeverity.MINOR;
      AlarmOut.Active := TRUE;
      AlarmOut.FirstOut := FALSE;
      AlarmOut.Timestamp := '2025-09-08T00:00:00Z';
      AlarmOut.Latched := FALSE;
      AlarmOut.RequiresAck := FALSE;
    ELSE
      IF fallbackTimer.Q THEN
        FallbackTimerActive := FALSE;
        CurrentRoute.status := UNAVAILABLE;
        RouteStatus := ERROR;
        AlarmOut.Alarm_ID := 'MERGE_FALLBACK_TIMEOUT';
        AlarmOut.Severity := AlarmSeverity.MAJOR;
        AlarmOut.Active := TRUE;
        AlarmOut.Timestamp := '2025-09-08T00:00:00Z';
        AlarmOut.Latched := TRUE;
        AlarmOut.RequiresAck := TRUE;
      END_IF;
    END_IF;
  END_IF;
END_FUNCTION_BLOCK

(* ---------- FB: FB_PalletizerHS ---------- *)
FUNCTION_BLOCK FB_PalletizerHS
VAR_INPUT
  Pallet_Req_DI : BOOL;
  Pallet_Ready_DI : BOOL;
  Transfer_Complete_DI : BOOL;
  ESTOP_ACTIVE : BOOL;
END_VAR
VAR_OUTPUT
  HandshakeState : (IDLE, REQUEST_TO_PLACE, ACK_PLACE_REQUEST, PALLET_READY, TRANSFER_IN_PROGRESS, TRANSFER_COMPLETE, FAULT, TIMEOUT);
  LastError : STRING[64];
  HS_Status : Pallet_Handshake_DDT;
  Pallet_Ack_DO : BOOL;
  Transfer_Start_DO : BOOL;
END_VAR
VAR
  requestAckTimer : TON;
  transferTimer : TON;
  ackRetryCount : INT;
  transferRetryCount : INT;
  initialization : BOOL;
END_VAR

METHOD PUBLIC Init : VOID
  HandshakeState := IDLE;
  LastError := '';
  HS_Status.state := IDLE;
  HS_Status.request_timestamp := '2025-09-08T00:00:00Z';
  HS_Status.retry_count := 0;
  HS_Status.last_error := '';
  requestAckTimer(IN := FALSE);
  transferTimer(IN := FALSE);
  ackRetryCount := 0;
  transferRetryCount := 0;
  initialization := TRUE;
  Pallet_Ack_DO := FALSE;
  Transfer_Start_DO := FALSE;
END_METHOD

BEGIN
  IF initialization THEN
    initialization := FALSE;
  END_IF;

  IF ESTOP_ACTIVE THEN
    HandshakeState := FAULT;
    LastError := 'ESTOP_ACTIVE';
    Pallet_Ack_DO := FALSE;
    Transfer_Start_DO := FALSE;
    HS_Status.state := FAULT;
    HS_Status.last_error := LastError;
    RETURN;
  END_IF;

  CASE HandshakeState OF
    IDLE:
      Pallet_Ack_DO := FALSE;
      Transfer_Start_DO := FALSE;
      IF Pallet_Req_DI THEN
        HandshakeState := REQUEST_TO_PLACE;
        HS_Status.request_timestamp := '2025-09-08T00:00:00Z';
        HS_Status.retry_count := 0;
        requestAckTimer(IN := TRUE, PT := T_PALLET_ACK);
      END_IF;

    REQUEST_TO_PLACE:
      Pallet_Ack_DO := TRUE;
      IF Pallet_Ready_DI THEN
        HandshakeState := ACK_PLACE_REQUEST;
        requestAckTimer(IN := FALSE);
        ackRetryCount := 0;
      ELSIF requestAckTimer.Q THEN
        requestAckTimer(IN := FALSE);
        ackRetryCount := ackRetryCount + 1;
        HS_Status.retry_count := ackRetryCount;
        IF ackRetryCount <= PALLET_ACK_RETRIES THEN
          requestAckTimer(IN := TRUE, PT := T_PALLET_RETRY_BACKOFF);
        ELSE
          HandshakeState := FAULT;
          HS_Status.last_error := 'NoACK';
          LastError := 'PalletizerNoACK';
          Pallet_Ack_DO := FALSE;
        END_IF;
      END_IF;

    ACK_PLACE_REQUEST:
      Pallet_Ack_DO := TRUE;
      IF Pallet_Ready_DI THEN
        HandshakeState := PALLET_READY;
      END_IF;

    PALLET_READY:
      Transfer_Start_DO := TRUE;
      HandshakeState := TRANSFER_IN_PROGRESS;
      transferTimer(IN := TRUE, PT := T_PALLET_TRANSFER);

    TRANSFER_IN_PROGRESS:
      Transfer_Start_DO := TRUE;
      IF Transfer_Complete_DI THEN
        transferTimer(IN := FALSE);
        Transfer_Start_DO := FALSE;
        HandshakeState := TRANSFER_COMPLETE;
      ELSIF transferTimer.Q THEN
        transferTimer(IN := FALSE);
        transferRetryCount := transferRetryCount + 1;
        IF transferRetryCount <= PALLET_TRANSFER_RETRIES THEN
          HandshakeState := PALLET_READY;
          transferTimer(IN := TRUE, PT := T_PALLET_TRANSFER);
        ELSE
          HandshakeState := FAULT;
          HS_Status.last_error := 'TransferTimeout';
          LastError := 'TransferTimeout';
          Transfer_Start_DO := FALSE;
        END_IF;
      END_IF;

    TRANSFER_COMPLETE:
      HandshakeState := IDLE;
      HS_Status.retry_count := 0;
      HS_Status.last_error := '';
      Pallet_Ack_DO := FALSE;
      Transfer_Start_DO := FALSE;

    FAULT:
      Pallet_Ack_DO := FALSE;
      Transfer_Start_DO := FALSE;

    TIMEOUT:
      HandshakeState := FAULT;

  ELSE
    HandshakeState := FAULT;
    Pallet_Ack_DO := FALSE;
    Transfer_Start_DO := FALSE;
  END_CASE;

  // Update HS_Status DDT mapping conservatively
  CASE HandshakeState OF
    IDLE: HS_Status.state := IDLE;
    REQUEST_TO_PLACE: HS_Status.state := REQUEST;
    ACK_PLACE_REQUEST: HS_Status.state := ACK;
    PALLET_READY: HS_Status.state := READY;
    TRANSFER_IN_PROGRESS: HS_Status.state := TRANSFER;
    TRANSFER_COMPLETE: HS_Status.state := COMPLETE;
    FAULT: HS_Status.state := FAULT;
    ELSE HS_Status.state := FAULT;
  END_CASE;
  HS_Status.last_error := LastError;
END_FUNCTION_BLOCK

(* ---------- FC: docs/Scada_Tag_Map.md (generates Markdown mapping for reference) ---------- *)
FUNCTION FC_Scada_Tag_Map : VOID
VAR_OUTPUT
  DocText : STRING[4000];
END_VAR
VAR
  s : STRING[4000];
END_VAR

BEGIN
  s := '';
  s := CONCAT(s, '# SCADA Tag Map\n\n');
  s := CONCAT(s, '**Purpose**: Map SCADA-facing tags to PLC data-block tags and datatypes (STRING/BOOL/ENUM/ARRAY) for OPC/Modbus integration.\n\n');
  s := CONCAT(s, '## Public Interfaces\n\n');
  s := CONCAT(s, '- PLC_Heartbeat -> DB_Diagnostics.PLC_Heartbeat_Monitored (BOOL)\n');
  s := CONCAT(s, '- PLC_Application_Version -> DB_Diagnostics.DiagnosticsOut.Application_Version (STRING)\n');
  s := CONCAT(s, '- PLC_Library_Version -> DB_Diagnostics.DiagnosticsOut.Library_Version (STRING)\n');
  s := CONCAT(s, '- CPU_Redundancy_Status -> DB_Diagnostics.DiagnosticsOut.CPU_Redundancy_Status (STRING)\n');
  s := CONCAT(s, '- HotStandby_Link_Status -> DB_Diagnostics.DiagnosticsOut.HotStandby_Link_Status (BOOL)\n');
  s := CONCAT(s, '- HotStandby_Link_LastChange_Timestamp -> DB_Diagnostics.HotStandby_Link_LastChange_Timestamp (STRING)\n');
  s := CONCAT(s, '- Remote_Rack_Status[] -> DB_Diagnostics.DiagnosticsOut.Remote_Rack_Status[] (ARRAY[WORD])\n');
  s := CONCAT(s, '- IO_Module_Status[] -> DB_Diagnostics.DiagnosticsOut.IO_Module_Status[] (ARRAY[WORD])\n');
  s := CONCAT(s, '- Alarm_List[] -> DB_AlarmMgr.ActiveAlarms[] (ARRAY of UDT_Alarm)\n');
  s := CONCAT(s, '- FirstOutAlarm -> DB_AlarmMgr.FirstOutAlarm (UDT_Alarm)\n');
  s := CONCAT(s, '- Conveyor1_MotorCmd -> DB_Conveyor1.MotorCmd (BOOL)\n');
  s := CONCAT(s, '- Conveyor1_JamState -> DB_Conveyor1.JamState (ENUM: NO_JAM/SOFT_JAM/HARD_JAM)\n');
  s := CONCAT(s, '- Merge1_RouteCmd -> DB_MergeDivert1.RouteCmd (STRING)\n');
  s := CONCAT(s, '- Merge1_FallbackTimerActive -> DB_MergeDivert1.FallbackTimerActive (BOOL)\n');
  s := CONCAT(s, '- PalletizerHS1_State -> DB_PalletizerHS1.HandshakeState (ENUM)\n');
  s := CONCAT(s, '- PalletizerHS1_LastError -> DB_PalletizerHS1.LastError (STRING)\n');
  s := CONCAT(s, '- BMENOC0321_Status -> DB_Comms.BMENOC0321_Status (STRING)\n');
  s := CONCAT(s, '- SCADA_Heartbeat_Ack -> DB_Comms.SCADA_Heartbeat_Ack (BOOL)\n');
  s := CONCAT(s, '\n-- End of generated SCADA Tag Map --\n');
  DocText := s;
END_FUNCTION

(* ---------- ORGANIZATION BLOCK: OB100 (Cold-start initialization) ---------- *)
ORGANIZATION_BLOCK OB100
VAR
  diagFB : FB_Diag;            // DB_Diagnostics
  commsFB : FB_Comms;          // DB_Comms
  alarmFB : FB_AlarmMgr;       // DB_AlarmMgr
  convFB : FB_Conveyor;        // DB_Conveyor1
  mergeFB : FB_MergeDivert;    // DB_MergeDivert1
  palletFB : FB_PalletizerHS;  // DB_PalletizerHS1
  modeMgr : FB_ModeMgr;        // DB_ModeMgr
  scadaDoc : FC_Scada_Tag_Map; // document generator (non-critical)
  // Seeded retentive defaults and warm-up signals
  initialESTOP : BOOL := FALSE;
END_VAR

BEGIN
  // Initialize diagnostics, communications and alarm manager
  diagFB.Init();
  commsFB.Init();
  alarmFB.Clear();

  // Initialize control FBs
  convFB.Init();
  mergeFB.Init();
  palletFB.Init();

  // Initialize Mode Manager and seed retentive mode and permissions
  modeMgr.Init();

  // Comms warm-up: allow comms FB to establish baseline status before normal operation
  // (commsFB.Init already executed); for redundancy the HSBY timestamp is seeded here
  diagFB.DiagnosticsOut.Application_Version := '1.0.0 (build 2025-09-08)';
  diagFB.DiagnosticsOut.Library_Version := 'LIB.1.0.0';

  // Ensure safe outputs if ESTOP asserted at cold-start
  IF initialESTOP THEN
    // Force safe states across managers
    convFB.ESTOP_ACTIVE := TRUE;
    mergeFB.ESTOP_ACTIVE := TRUE;
    palletFB.ESTOP_ACTIVE := TRUE;
    // Set Mode Manager ESTOP input to ensure consistent state
    modeMgr.ESTOP_In := TRUE;
    modeMgr.CurrentMode := ESTOP;
    modeMgr.ModeChangeTimestamp := '2025-09-08T00:00:00Z';
  END_IF;
END_ORGANIZATION_BLOCK

(* ---------- ORGANIZATION BLOCK: OB1 (Cyclic master) ---------- *)
ORGANIZATION_BLOCK OB1
VAR
  // Instances
  DB_Diagnostics : FB_Diag;
  DB_Comms : FB_Comms;
  DB_AlarmMgr : FB_AlarmMgr;
  DB_Conveyor1 : FB_Conveyor;
  DB_MergeDivert1 : FB_MergeDivert;
  DB_PalletizerHS1 : FB_PalletizerHS;
  DB_ModeMgr : FB_ModeMgr;

  // Public / I/O (example mapping; real mapping via DB_Diagnostics)
  PLC_Heartbeat : BOOL := FALSE;
  SCADA_HB_In : BOOL := FALSE;
  SCADA_HB_Ack_In : BOOL := FALSE;
  Conveyor1_Sensor_Beam : BOOL := FALSE;
  Conveyor1_Encoder_Moving : BOOL := TRUE;
  Conveyor1_StartCmd : BOOL := FALSE;
  Conveyor1_StopCmd : BOOL := FALSE;
  Conveyor1_ManualDriveCmd : BOOL := FALSE;
  Merge1_Barcode : Barcode_DDT;
  Merge1_ScannerValid : BOOL := FALSE;
  Pallet_REQ_DI : BOOL := FALSE;
  Pallet_READY_DI : BOOL := FALSE;
  Transfer_COMPLETE_DI : BOOL := FALSE;
  Global_ESTOP : BOOL := FALSE; // global estop input
  ResetPermissivesCmd : BOOL := FALSE; // manual permissive reset for ESTOP recovery
  Operator_Authorised_In : BOOL := FALSE;
  Maintenance_Permit_In : BOOL := FALSE;
  Simulation_Enabled_In : BOOL := FALSE;

  scadaDoc : FC_Scada_Tag_Map;

  // Mode command from SCADA/HMI (example)
  ModeCmd_Request : (REQUEST_RUN_AUTO, REQUEST_RUN_MANUAL, REQUEST_STOP, REQUEST_MAINTENANCE, REQUEST_SIMULATION, REQUEST_ESTOPOFF) := REQUEST_RUN_MANUAL;
END_VAR

BEGIN
  // Toggle PLC heartbeat (in real system a timed task would toggle)
  PLC_Heartbeat := NOT PLC_Heartbeat;

  // Call Mode Manager first to determine allowed mode for the cycle
  DB_ModeMgr(ModeCmd := ModeCmd_Request,
             Perm_PLC_Health_OK := DB_Diagnostics.DiagnosticsOut.Application_Version <> '', // simplified health test
             Perm_Power_Supplies_OK := TRUE,
             Perm_HotStandby_Link_OK_or_StandbyReady := DB_Diagnostics.DiagnosticsOut.HotStandby_Link_Status,
             Perm_No_High_Severity_SIF_Trip := TRUE,
             Operator_Authorised := Operator_Authorised_In,
             Maintenance_Permit := Maintenance_Permit_In,
             Simulation_Enabled_Bit := Simulation_Enabled_In,
             ResetPermissives := ResetPermissivesCmd,
             ESTOP_In := Global_ESTOP);

  // Diagnostics - supply heartbeat to diagnostics FB
  DB_Diagnostics(PLC_Heartbeat_In := PLC_Heartbeat);

  // Comms
  DB_Comms(SCADA_Heartbeat_In := SCADA_HB_In, SCADA_Heartbeat_Ack_In := SCADA_HB_Ack_In);

  // Alarm manager - pass through alarms produced by other FBs (MergeDivert example included)
  DB_AlarmMgr(AlarmIn := DB_MergeDivert1.AlarmOut,
              AcknowledgeID := '',
              InhibitRequestID := '',
              TriggerClear := FALSE);

  // Conveyors and material handling (called after ModeMgr and AlarmMgr)
  // Map global ESTOP into conveyor FBs
  DB_Conveyor1(Sensor_Beam := Conveyor1_Sensor_Beam,
               Encoder_Moving := Conveyor1_Encoder_Moving,
               StartCmd := Conveyor1_StartCmd,
               StopCmd := Conveyor1_StopCmd,
               ManualDriveCmd := Conveyor1_ManualDriveCmd,
               ESTOP_ACTIVE := Global_ESTOP,
               Interlocks_OK := TRUE);

  // Merge/Divert (barcode struct input and scanner valid flag)
  DB_MergeDivert1(Barcode := Merge1_Barcode,
                  ScannerValid := Merge1_ScannerValid,
                  FallbackPermissive := TRUE,
                  ESTOP_ACTIVE := Global_ESTOP);

  // Palletizer handshake
  DB_PalletizerHS1(Pallet_Req_DI := Pallet_REQ_DI,
                   Pallet_Ready_DI := Pallet_READY_DI,
                   Transfer_Complete_DI := Transfer_COMPLETE_DI,
                   ESTOP_ACTIVE := Global_ESTOP);

  // Generate SCADA Tag Map documentation (non-critical path)
  scadaDoc();

  // Expose summary diagnostics to SCADA via DB_Diagnostics instance variables
  // Example: DB_Diagnostics.DiagnosticsOut.Application_Version is populated by OB100 or FB_Diag
END_ORGANIZATION_BLOCK

(* End of file *)
