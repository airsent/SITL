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

print("T7 — no-lie: disabled selects + bindFailsafeControls writes nothing to the event log")
check("T7.1 exactly 4 failsafe selects, all disabled",
      dash.count('class="failsafe-select" disabled') == 4 and
      dash.count('class="failsafe-select"') == 4,
      f'disabled={dash.count(chr(34)+"failsafe-select"+chr(34)+" disabled")} total={dash.count(chr(34)+"failsafe-select"+chr(34))}')
# extract bindFailsafeControls body and assert no event-log write
m = re.search(r"function bindFailsafeControls\s*\([^)]*\)\s*\{(.*?)\n\}", script, re.S)
body = m.group(1) if m else None
check("T7.2 bindFailsafeControls found", body is not None)
check("T7.3 bindFailsafeControls writes no event-log line",
      body is not None and "prependEvent" not in body)
check("T7.4 the old 'SET TO' lie string is gone from that function",
      body is not None and "SET TO" not in body)

print("Sweep — demo residue hidden in real mode")
check("S.1 mission timer starts at 0 in real mode",
      "isRealMode ? 0 : (25 * 60 + 38)" in script or "isRealMode?0:(25*60+38)" in script.replace(" ", ""))
check("S.2 RSSI 255 sentinel renders '--' not a plausible number",
      "=== 255" in telem and '"--"' in telem)

print()
if fails:
    print(f"FAILED ({len(fails)}): " + ", ".join(fails))
    sys.exit(1)
print("ALL PASS")
