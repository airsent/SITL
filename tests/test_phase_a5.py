#!/usr/bin/env python3
"""Offline acceptance for BuildSpecDashboardSITL Phase A.5 (server-side sensor
health / system-status / statustext telemetry) + the renderer source pins that
consume them.

Imports the server module directly (needs pymavlink), so this suite runs on
the GCS venv, not bare python3. No network, no live vehicle — SYS_STATUS /
HEARTBEAT / STATUSTEXT are synthesized via a FakeMsg and fed straight into
srv._handle_status_msg; the *behavioral* proof against a real FC is the gated
live milestone. These lock the bitmask decode, the drain-once statustext
buffer, and that no model client is importable from the server module.

Run:  ~/.venvs/airsent-gcs/bin/python tests/test_phase_a5.py
"""
import sys, json, pathlib

GCS = pathlib.Path(__file__).resolve().parent.parent / "gcs"
sys.path.insert(0, str(GCS))
import airsent_server as srv
from pymavlink import mavutil

fails = []
def check(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(name)

class FakeMsg:
    def __init__(self, mtype, **fields):
        self._mtype = mtype
        for k, v in fields.items():
            setattr(self, k, v)
    def get_type(self):
        return self._mtype

def _reset():
    srv.telem.update({
        'sensors_present': None,
        'sensors_enabled': None,
        'sensors_health': None,
        'system_status': None,
        'sensor_health': {k: None for k in srv._SENSOR_BITS},
    })
    with srv._statustext_lock:
        srv._statustext_buf.clear()

print("T2 — honesty null (fresh import, before any handler call)")
p = srv.build_telemetry_payload()
check("T2.1 sensors_present is None", p['sensors_present'] is None)
check("T2.2 sensors_enabled is None", p['sensors_enabled'] is None)
check("T2.3 sensors_health is None", p['sensors_health'] is None)
check("T2.4 system_status is None", p['system_status'] is None)
check("T2.5 all 8 sensor_health values are None",
      all(v is None for v in p['sensor_health'].values()),
      str(p['sensor_health']))
check("T2.6 statustext_new == [] on fresh import", p['statustext_new'] == [])

print("T1 — SYS_STATUS bitmask decode + HEARTBEAT system_status passthrough")
B = mavutil.mavlink
GPS = B.MAV_SYS_STATUS_SENSOR_GPS
MAG = B.MAV_SYS_STATUS_SENSOR_3D_MAG
BARO = B.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE
BATT = B.MAV_SYS_STATUS_SENSOR_BATTERY
FLOW = B.MAV_SYS_STATUS_SENSOR_OPTICAL_FLOW
GYRO = B.MAV_SYS_STATUS_SENSOR_3D_GYRO
ACCEL = B.MAV_SYS_STATUS_SENSOR_3D_ACCEL
RNG = B.MAV_SYS_STATUS_SENSOR_LASER_POSITION   # the rangefinder bit — the one non-obvious mapping

present = GPS | MAG | BARO | BATT | GYRO | ACCEL | RNG
enabled = GPS | MAG | BARO | GYRO | ACCEL | RNG   # BATT present but NOT enabled
health  = GPS | MAG | GYRO | RNG                  # BARO+ACCEL enabled but unhealthy (FLOW absent throughout)

srv._handle_status_msg(FakeMsg(
    'SYS_STATUS',
    onboard_control_sensors_present=present,
    onboard_control_sensors_enabled=enabled,
    onboard_control_sensors_health=health,
))
p = srv.build_telemetry_payload()
check("T1.1 gps (present+enabled+healthy) -> True", p['sensor_health']['gps'] is True)
check("T1.2 mag (present+enabled+healthy) -> True", p['sensor_health']['mag'] is True)
check("T1.3 abs_pressure (present+enabled, unhealthy) -> False, not None",
      p['sensor_health']['abs_pressure'] is False)
check("T1.4 optical_flow (absent) -> None, not False",
      p['sensor_health']['optical_flow'] is None)
check("T1.5 battery (present, not enabled) -> None",
      p['sensor_health']['battery'] is None)
check("T1.10 gyro (present+enabled+healthy) -> True", p['sensor_health']['gyro'] is True)
check("T1.11 accel (present+enabled, unhealthy) -> False, not None",
      p['sensor_health']['accel'] is False)
check("T1.12 rangefinder (LASER_POSITION, present+enabled+healthy) -> True",
      p['sensor_health']['rangefinder'] is True)
check("T1.6 sensors_present raw int verbatim", p['sensors_present'] == present)
check("T1.7 sensors_enabled raw int verbatim", p['sensors_enabled'] == enabled)
check("T1.8 sensors_health raw int verbatim", p['sensors_health'] == health)

srv._handle_status_msg(FakeMsg('HEARTBEAT', system_status=5))
p = srv.build_telemetry_payload()
check("T1.9 HEARTBEAT system_status passthrough == 5", p['system_status'] == 5)

print("T3 — STATUSTEXT delivery (per-consumer cursor, once each, bytes decode, ordering)")
_reset()
# One consumer: cursor starts at head, each line arrives exactly once, no replay.
cur = srv._statustext_head()
srv._handle_status_msg(FakeMsg('STATUSTEXT', severity=4, text='Failsafe: Battery low'))
p1 = srv.build_telemetry_payload(cur); cur = p1['statustext_seq']
check("T3.1 first read returns the queued line",
      p1['statustext_new'] == [{'severity': 4, 'text': 'Failsafe: Battery low'}],
      str(p1['statustext_new']))
p2 = srv.build_telemetry_payload(cur); cur = p2['statustext_seq']
check("T3.2 next read at the advanced cursor is empty (no replay)", p2['statustext_new'] == [])
p3 = srv.build_telemetry_payload(cur); cur = p3['statustext_seq']
check("T3.3 third read is still empty (no duplication)", p3['statustext_new'] == [])

srv._handle_status_msg(FakeMsg('STATUSTEXT', severity=3, text=b'PreArm: check\x00\x00'))
p4 = srv.build_telemetry_payload(cur); cur = p4['statustext_seq']
check("T3.4 bytes decoded + trailing NULs stripped",
      p4['statustext_new'] == [{'severity': 3, 'text': 'PreArm: check'}],
      str(p4['statustext_new']))

srv._handle_status_msg(FakeMsg('STATUSTEXT', severity=6, text='line one'))
srv._handle_status_msg(FakeMsg('STATUSTEXT', severity=6, text='line two'))
p5 = srv.build_telemetry_payload(cur); cur = p5['statustext_seq']
check("T3.5 two-line feed preserves order in one read",
      p5['statustext_new'] == [
          {'severity': 6, 'text': 'line one'},
          {'severity': 6, 'text': 'line two'},
      ],
      str(p5['statustext_new']))

print("T3b — multi-consumer: every open page gets every line (a drain would split them)")
_reset()
# The real demo flow: pilot.html and dashboard.html both hold a :8765 socket.
c_pilot = srv._statustext_head()
c_dash  = srv._statustext_head()
srv._handle_status_msg(FakeMsg('STATUSTEXT', severity=4, text='Failsafe: GCS lost'))
pp = srv.build_telemetry_payload(c_pilot); c_pilot = pp['statustext_seq']
pd = srv.build_telemetry_payload(c_dash);  c_dash  = pd['statustext_seq']
check("T3b.1 consumer A receives the line",
      pp['statustext_new'] == [{'severity': 4, 'text': 'Failsafe: GCS lost'}],
      str(pp['statustext_new']))
check("T3b.2 consumer B receives the SAME line (not stolen by A)",
      pd['statustext_new'] == [{'severity': 4, 'text': 'Failsafe: GCS lost'}],
      str(pd['statustext_new']))
check("T3b.3 neither consumer sees it twice",
      srv.build_telemetry_payload(c_pilot)['statustext_new'] == [] and
      srv.build_telemetry_payload(c_dash)['statustext_new'] == [])
# A page opened AFTER the line was emitted starts at head — no backlog dump.
c_late = srv._statustext_head()
check("T3b.4 a late-joining consumer gets no backlog replay",
      srv.build_telemetry_payload(c_late)['statustext_new'] == [])
check("T3b.5 ring is bounded (no unbounded growth with no consumer attached)",
      srv._statustext_buf.maxlen == 200, str(srv._statustext_buf.maxlen))

print("T4 param_set — Phase B, not asserted here")

print("T8 — determinism/purity")
_reset()
srv._handle_status_msg(FakeMsg(
    'SYS_STATUS',
    onboard_control_sensors_present=present,
    onboard_control_sensors_enabled=enabled,
    onboard_control_sensors_health=health,
))
srv._handle_status_msg(FakeMsg('HEARTBEAT', system_status=4))
srv.build_telemetry_payload()  # drain the fixture once so the two calls below observe steady state
a = json.dumps(srv.build_telemetry_payload(), sort_keys=True)
b = json.dumps(srv.build_telemetry_payload(), sort_keys=True)
check("T8.1 repeat build_telemetry_payload() is byte-identical (no side effect on re-read)", a == b)

server_src = (GCS / "airsent_server.py").read_text()
check("T8.2 no anthropic client import ('import anthropic')", "import anthropic" not in server_src)
check("T8.3 no anthropic client import ('from anthropic')", "from anthropic" not in server_src)
check("T8.4 no openai client import ('import openai')", "import openai" not in server_src)

print("J — renderer source pins (stdlib text checks, same spirit as test_phase_a.py)")
telem_src = (GCS / "telemetry.js").read_text()
script_src = (GCS / "script.js").read_text()
check("J.1 telemetry.js reads sensor_health", "sensor_health" in telem_src)
check("J.2 telemetry.js reads statustext_new", "statustext_new" in telem_src)
check("J.3 telemetry.js writes new lines via prependEvent", "prependEvent" in telem_src)
check("J.4 telemetry.js defines the _SYS_STATUS_LIVE heuristic gate", "_SYS_STATUS_LIVE" in telem_src)
check("J.5 telemetry.js MAV_STATE map covers CRITICAL/EMERGENCY",
      "'CRITICAL'" in telem_src and "'EMERGENCY'" in telem_src)
check("J.6 script.js reads the same _SYS_STATUS_LIVE heuristic gate", "_SYS_STATUS_LIVE" in script_src)

print()
if fails:
    print(f"FAILED ({len(fails)}): " + ", ".join(fails))
    sys.exit(1)
print("ALL PASS")
