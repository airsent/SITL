#!/usr/bin/env python3
"""
Airsent SITL — MAVLink fan-out.

SITL exposes a single-client MAVLink *TCP* server on :5760. This reads it once
(reliably) and rebroadcasts over UDP to any number of consumers — the MAVProxy
map, teleop.py, QGC, a logger — and relays their commands back. It's the hub that
lets the visualizer AND the flyer share one sim.

(Why not point MAVProxy straight at tcp:5760? MAVProxy's TCP reader stalls against
the Docker-published SITL port under emulation; a plain pymavlink TCP read does
not. So we do the TCP read here and hand MAVProxy a clean UDP feed — which is how
sim_vehicle wires MAVProxy anyway.)

Run (after ./run.sh):   python fanout.py
Then:
  MAVProxy map/console:  mavproxy.py --master=udp:127.0.0.1:14650 --console --map
  teleop:                python teleop.py            (connects udpin:14551)
"""
import sys, time
from pymavlink import mavutil

MASTER = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5760"
OUT_PORTS = [14650, 14551]     # 14650 = MAVProxy map · 14551 = teleop.py

print(f"[fanout] master {MASTER} — waiting heartbeat ...")
master = mavutil.mavlink_connection(MASTER, source_system=255)
if master.wait_heartbeat(timeout=40) is None:
    sys.exit("[fanout] no heartbeat — is ./run.sh up?")
print(f"[fanout] linked sys {master.target_system}; fanning out to udp {OUT_PORTS}")
master.mav.request_data_stream_send(master.target_system, master.target_component,
                                    mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
outs = [mavutil.mavlink_connection(f"udpout:127.0.0.1:{p}", source_system=255)
        for p in OUT_PORTS]

while True:
    m = master.recv_msg()                 # SITL -> consumers
    if m is not None:
        buf = m.get_msgbuf()
        for o in outs:
            try:
                o.write(buf)              # tolerate a consumer that isn't up yet
            except OSError:
                pass                      # ECONNREFUSED (no listener) — ignore; recovers
    for o in outs:                        # consumers -> SITL (commands)
        try:
            r = o.recv_msg()
        except OSError:
            r = None
        if r is not None:
            master.write(r.get_msgbuf())
    time.sleep(0.0005)
