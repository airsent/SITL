#!/usr/bin/env python3
"""Offline acceptance for BuildSpecDashboardSITL Phase A (C3 seam + honesty package).

Source-structure assertions over the shipped gcs/ files — no browser/jsdom, no
network, no install (stdlib only). The *behavioral* proof of T6/T7 is the gated
live milestone `live_dashboard_failsafe`; these lock the shipped source has the
required shape and that the demo residue / failsafe-lie are gone.

Run:  python3 tests/test_phase_a.py
"""
import re, sys, pathlib

GCS = pathlib.Path(__file__).resolve().parent.parent / "gcs"
telem = (GCS / "telemetry.js").read_text()
script = (GCS / "script.js").read_text()
dash = (GCS / "dashboard.html").read_text()
pilot = (GCS / "pilot.html").read_text()

fails = []
def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)

LOCAL_DEV = "location.hostname==='localhost' || location.hostname==='127.0.0.1'"

print("T5 — endpoint seam (localhost -> local SITL WS, else VPS), idiom verbatim vs pilot.html")
# telemetry seam
check("T5.1 telem _LOCAL_DEV idiom present", LOCAL_DEV in telem)
check("T5.2 telem local branch -> ws://<host>:TELEM_PORT", "ws://${location.hostname}:${TELEM_PORT}" in telem)
check("T5.3 telem remote branch -> VPS /telem", "wss://console.airsent.tech/telem" in telem)
check("T5.4 telem socket uses the switched URL var", "new WebSocket(TELEM_WS_URL)" in telem)
check("T5.5 telem hardcoded VPS URL removed from socket ctor",
      'new WebSocket("wss://console.airsent.tech/telem")' not in telem)
# command seam
check("T5.6 cmd _LOCAL_DEV idiom present", LOCAL_DEV in script)
check("T5.7 cmd local branch -> ws://<host>:CMD_PORT", "ws://${location.hostname}:${CMD_PORT}" in script)
check("T5.8 cmd remote branch -> VPS /cmd", "wss://console.airsent.tech/cmd" in script)
check("T5.9 cmd socket uses the switched URL var", "new WebSocket(CMD_WS_URL)" in script)
check("T5.10 cmd hardcoded VPS URL removed from socket ctor",
      'new WebSocket("wss://console.airsent.tech/cmd")' not in script)
# idiom byte-identical to pilot.html
check("T5.11 idiom byte-identical to pilot.html", LOCAL_DEV in pilot)

print("T6 — camera WHEP fetches gated on localhost (no prod video in a local sim demo)")
check("T6.1 dashboard defines _LOCAL_DEV", LOCAL_DEV in dash)
for cam in ("frontcam", "downcam"):
    # the whep fetch for each cam must be preceded (within its promise chain) by a _LOCAL_DEV skip guard
    idx = dash.find(f"/video/{cam}/whep")
    window = dash[max(0, idx - 400):idx] if idx != -1 else ""
    check(f"T6.2 {cam} whep fetch exists", idx != -1)
    check(f"T6.3 {cam} whep fetch guarded by `if(_LOCAL_DEV) return null`",
          "if(_LOCAL_DEV) return null" in window)

print("T7 — no-lie: failsafe controls are labelled local policy, never aircraft config")
# 2026-10-20: upstream (FlightConsole 3ea0fb6) replaced the four disabled flight-mode
# selects with Activate/Deactivate toggles for a browser-local failsafe policy
# (FAILSAFE.md). The Phase A rule still holds: nothing may read as a vehicle change.
check("T7.1 exactly 4 failsafe selects, offering only Activate/Deactivate",
      dash.count('class="failsafe-select"') == 4 and
      dash.count('<option value="true">Activate</option>') == 4 and
      not re.search(r'class="failsafe-select"[^>]*>\s*<option>(RTL|LAND|HOLD)', dash),
      f'total={dash.count(chr(34)+"failsafe-select"+chr(34))}')
# extract bindFailsafeControls body and assert any event-log write says LOCAL POLICY
m = re.search(r"function bindFailsafeControls\s*\([^)]*\)\s*\{(.*?)\n\}", script, re.S)
body = m.group(1) if m else None
check("T7.2 bindFailsafeControls found", body is not None)
check("T7.3 any event-log line it writes is labelled LOCAL POLICY and sends no command",
      body is not None and
      ("prependEvent" not in body or "LOCAL POLICY" in body) and
      "cmdSocket" not in body and "sendCommand" not in body)
check("T7.4 the old 'SET TO' lie string is gone from that function",
      body is not None and "SET TO" not in body)

print("Sweep — demo residue hidden in real mode")
check("S.1 mission timer starts at 0 in real mode",
      "isRealMode ? 0 : (25 * 60 + 38)" in script or "isRealMode?0:(25*60+38)" in script.replace(" ", ""))
check("S.2 RSSI 255 sentinel renders '--' not a plausible number",
      "=== 255" in telem and '"--"' in telem)

print("R1 — confirm-slider cannot latch (regression, 2026-09-07)")
# A slide abandoned outside the window used to leave dragging=true, so the next
# stray mousemove anywhere on the page completed it. Reproduced live against SITL:
# a 40% drag on LAND + one unrelated mousemove sent MAV_CMD_DO_SET_MODE -> LAND.
check("R1.1 mousemove aborts when no mouse button is held",
      "e.buttons===0" in pilot.replace(" ", ""))
check("R1.2 the abort path is a named handler, not inline duplication",
      "function abortDrag()" in pilot)
check("R1.3 closeSlide() cancels an in-progress drag",
      re.search(r"function closeSlide\(\)\s*\{[^}]*slideAbortDrag", pilot, re.S) is not None)
check("R1.4 window blur cancels an in-progress drag",
      "addEventListener('blur'" in pilot and "slideAbortDrag" in pilot)
check("R1.5 touchcancel resets the drag too",
      "ontouchcancel" in pilot)

print("R2 — actuators.html no longer fabricates in real mode (regression, 2026-09-07)")
act = (GCS / "actuators.html").read_text()
check("R2.1 the page reads airsentMode and derives isActual",
      "airsentMode" in act and "isActual" in act)
check("R2.2 the 1s simulation loop is inside the demo branch only",
      re.search(r"if\s*\(isActual\)\s*\{.*?\}\s*else\s*\{[^}]*setInterval\(updateActuatorPage",
                act, re.S) is not None)
check("R2.3 real mode renders '--' instead of random numbers",
      "renderNoBackend" in act and '"--"' in act)
check("R2.4 real mode says the backend is not wired",
      "NOT WIRED" in act)
check("R2.5 demo mode is badged so it can't be read as vehicle data",
      "DEMO — SIMULATED ACTUATOR DATA" in act)
check("R2.6 the randomSeries charts are gated too",
      "drawDemoCharts" in act and "drawFlatCharts" in act)

print()
print("R3 — ASC v2 failsafe page works against local SITL (2026-10-20)")
fsh = (GCS / "failsafe.html").read_text()
bridge = (GCS / "failsafe-bridge.js").read_text()
check("R3.1 failsafe.html loads the check catalog before failsafe-auto.js",
      0 <= fsh.find("asc-check-catalog.js") < fsh.find("failsafe-auto.js"))
check("R3.2 failsafe bridge reads the local sim server on localhost",
      LOCAL_DEV in bridge and "8765" in bridge)
check("R3.3 direct local frames are fresh, relayed frames still use telemetry_age",
      "(_LOCAL_DEV?0:null)" in bridge.replace(" ", "") and "telemetry_age" in bridge)

if fails:
    print(f"FAILED ({len(fails)}): " + ", ".join(fails))
    sys.exit(1)
print("ALL PASS")
