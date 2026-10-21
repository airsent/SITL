#!/usr/bin/env python3
"""Inject real faults into ArduCopter SITL and watch ASC (failsafe.html) react.

The console server holds MAVLink :5760, so this talks to the sim on the spare
port :5762. Every fault is a genuine SITL condition — the autopilot sees it the
same way it would on hardware — so you see two things at once:
  1. ASC (observation only) flag the check on failsafe.html / `watch`
  2. ArduPilot's OWN failsafe respond (RTL / LAND) if the vehicle is armed

Usage (with ./demo.sh running):
  python asc_faults.py watch            # live terminal view of non-OK ASC checks
  python asc_faults.py gps   [on|off]   # GNSS goes dark   -> gps_fix / gps_fresh
  python asc_faults.py rc    [on|off]   # RC receiver lost -> rc_fresh / rc_rssi
  python asc_faults.py batt  [on|off]   # pack sags to 10.2V -> battery_voltage
  python asc_faults.py fence [on|off]   # 5 m altitude fence; fly above it -> fence_breach
  python asc_faults.py link  [on|off]   # freeze the flight controller -> fc_heartbeat STALE
  python asc_faults.py clear            # undo every fault

`on` is the default. Restarting via ./demo.sh also resets the sim (params are wiped).
"""
import asyncio, json, os, subprocess, sys, time

FAULT_URL = os.environ.get("FAULT_MAV_URL", "tcp:127.0.0.1:5762")
TELEM_WS = os.environ.get("TELEM_WS", "ws://localhost:8765")
CONTAINER = os.environ.get("SITL_CONTAINER", "airsent-sitl-org-arducopter-sitl-1")

# (param, fault value, normal value). GPS has two names across ArduPilot versions.
PARAM_FAULTS = {
    "gps":   [("SIM_GPS1_ENABLE", 0, 1), ("SIM_GPS_DISABLE", 1, 0)],
    "rc":    [("SIM_RC_FAIL", 1, 0)],
    "batt":  [("SIM_BATT_VOLTAGE", 10.2, 12.6)],
    "fence": [("FENCE_TYPE", 1, 7), ("FENCE_ALT_MAX", 5, 100), ("FENCE_ENABLE", 1, 0)],
}


def connect():
    """SITL's spare TCP port briefly refuses a reconnect after a close, so retry."""
    from pymavlink import mavutil
    for _ in range(5):
        m = mavutil.mavlink_connection(FAULT_URL, source_system=254)
        if m.wait_heartbeat(timeout=4):
            return m
        m.close()
        time.sleep(2)
    sys.exit(f"no heartbeat on {FAULT_URL} — is ./demo.sh running?")


def set_param(m, name, value):
    """PARAM_SET then wait for the PARAM_VALUE echo. False if the param doesn't exist."""
    from pymavlink import mavutil
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value),
                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    end = time.time() + 3
    while time.time() < end:
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
        if msg and msg.param_id.rstrip("\x00") == name:
            return abs(msg.param_value - float(value)) < 1e-3
    return False


def param_fault(kind, on, m=None):
    m = m or connect()
    applied = []
    for name, bad, good in PARAM_FAULTS[kind]:
        if set_param(m, name, bad if on else good):
            applied.append(name)
            if kind == "gps":
                break  # first name that exists wins
    if not applied:
        sys.exit(f"sim rejected {kind}: none of {[p for p, _, _ in PARAM_FAULTS[kind]]} exist")
    print(f"{kind} fault {'ON' if on else 'OFF'}  ({', '.join(applied)})")


def link_fault(on):
    verb = "pause" if on else "unpause"
    r = subprocess.run(["docker", verb, CONTAINER], capture_output=True, text=True)
    if r.returncode and "not paused" not in r.stderr and "already paused" not in r.stderr:
        sys.exit(r.stderr.strip())
    print(f"link fault {'ON — flight controller frozen' if on else 'OFF — flight controller running'}")


async def watch():
    import websockets
    last = None
    async with websockets.connect(TELEM_WS) as ws:
        while True:
            d = json.loads(await ws.recv())
            asc = d.get("asc")
            if not isinstance(asc, dict) or asc.get("sequence") == last:
                continue
            last = asc.get("sequence")
            checks = asc.get("checks") or []
            bad = [c for c in checks if c.get("status") in ("CRITICAL", "WARNING", "STALE")]
            os.system("clear")
            print(f"ASC seq {last} · mode {d.get('flight_mode')} · armed {d.get('armed')} · "
                  f"alt {d.get('alt')} m · counts {asc.get('counts')}\n")
            for c in sorted(bad, key=lambda c: c.get("status")):
                print(f"  {c.get('status'):8} {c.get('id'):22} {c.get('reason') or c.get('detail') or ''}")
            if not bad:
                print("  no CRITICAL / WARNING / STALE checks")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__); return
    kind, on = args[0], (len(args) < 2 or args[1] != "off")
    if kind == "watch":
        try: asyncio.run(watch())
        except KeyboardInterrupt: pass
    elif kind == "link":
        link_fault(on)
    elif kind in PARAM_FAULTS:
        param_fault(kind, on)
    elif kind == "clear":
        link_fault(False)
        m = connect()
        for k in PARAM_FAULTS:
            param_fault(k, False, m)
    else:
        sys.exit(f"unknown fault '{kind}' — see --help")


if __name__ == "__main__":
    main()
