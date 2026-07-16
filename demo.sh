#!/usr/bin/env bash
#
# demo.sh — one-command Airsent SITL *dashboard* demo.
#
# Brings up a CLEAN ArduCopter SITL, starts the bundled dashboard server in
# --sim mode, serves the browser console, opens it, and prints the flight steps.
# Ctrl-C tears the whole demo down. Everything it needs is in THIS repo — the
# ArduCopter SITL (run.sh) and the Airsent GCS console (gcs/).
#
#   ./demo.sh                # clean restart of SITL (most reliable) + full demo
#   NO_RESTART=1 ./demo.sh   # reuse the running SITL (faster; only if it's clean)
#   DEMO_OPEN=0  ./demo.sh   # don't auto-open the browser, just print the URL
#
# Run ./run.sh in another terminal first if no SITL container is up yet.
#
# Then, in the pilot console that opens:
#   click MANUAL → ▲ Takeoff (confirm) → fly WASD / Space-Shift / Q-E → ▼ Land
#
# Pieces it wires together (all in-repo):
#   SITL       ./            ArduCopter SITL, MAVLink :5760   (run.sh)
#   dashboard  ./gcs         Airsent GCS console + airsent_server.py --sim
#   venv       ~/.venvs/airsent-gcs   pymavlink + websockets + numpy
#
# WHY the clean restart: a demo can only arm if the vehicle has no latched GCS
# failsafe. The dashboard server sends no GCS heartbeat, so once FS_GCS_ENABLE is
# on (e.g. the autonomy module sets it) the vehicle latches "PreArm: GCS failsafe
# on" and won't arm. Restarting SITL wipes EEPROM (entrypoint -w) → FS_GCS_ENABLE
# defaults to 0 → clean, armable vehicle. (The real fix is a heartbeat thread in
# the server; until then, this guarantees a reliable demo.)
#
set -euo pipefail

# ── Config (override via env) ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GCS_DIR="${GCS_DIR:-$SCRIPT_DIR/gcs}"       # bundled Airsent console (in-repo)
SITL_DIR="${SITL_DIR:-$SCRIPT_DIR}"         # run.sh lives at the repo root
VENV="${VENV:-$HOME/.venvs/airsent-gcs}"
HTTP_PORT="${HTTP_PORT:-8000}"
DEMO_OPEN="${DEMO_OPEN:-1}"          # 1 = auto-open browser; 0 = just print URL
NO_RESTART="${NO_RESTART:-0}"        # 1 = reuse running SITL instead of restarting
MAV_URL="tcp:127.0.0.1:5760"
PY="$VENV/bin/python"
LOG="${TMPDIR:-/tmp}/airsent-demo-server.log"

# ── tiny output helpers ──────────────────────────────────────────────────────
say(){  printf '\033[36m>> %s\033[0m\n' "$*"; }
warn(){ printf '\033[33m!! %s\033[0m\n' "$*" >&2; }
die(){  printf '\033[31mxx %s\033[0m\n' "$*" >&2; exit 1; }

# ── teardown (runs once, on any exit) ────────────────────────────────────────
SERVER_PID=""; HTTP_PID=""
cleanup(){
  echo
  say "shutting down demo…"
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
  [ -n "$HTTP_PID"   ] && kill "$HTTP_PID"   2>/dev/null || true
  say "done. SITL container left running."
}
trap 'exit 130' INT TERM
trap cleanup EXIT

# ── helper: connect (quietly), clear failsafe, WAIT UNTIL ACTUALLY ARMABLE ────
# Gates READY on real arm-readiness (EKF/GPS settled) by test-arming then
# disarming — a fixed sleep is unreliable because fresh-boot settle time varies.
# Suppresses pymavlink's "EOF on TCP socket" chatter during the boot window.
sitl_ready(){
  "$PY" - "$MAV_URL" <<'PY'
import sys, time, os, contextlib
from pymavlink import mavutil
url = sys.argv[1]; dn = open(os.devnull, 'w'); m = None

# 1. connect (tolerate the boot window)
t_end = time.time() + 60
while time.time() < t_end:
    try:
        with contextlib.redirect_stdout(dn):
            m = mavutil.mavlink_connection(url)
            hb = m.wait_heartbeat(timeout=6)
        if hb:
            break
    except Exception:
        pass
    m = None; time.sleep(2)
if not m:
    sys.exit(1)                          # never heard a heartbeat

sysid = m.target_system
m.mav.param_set_send(sysid, 1, b'FS_GCS_ENABLE', 0,
                     mavutil.mavlink.MAV_PARAM_TYPE_INT8)
time.sleep(0.5)

# 2. poll until the vehicle actually arms (EKF/GPS ready), then disarm
armed = False; last = ""
t_end = time.time() + 100
while time.time() < t_end:
    m.set_mode('GUIDED')
    m.mav.command_long_send(sysid, 1,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0,0,0,0,0,0)
    t = time.time()
    while time.time() - t < 2:
        with contextlib.redirect_stdout(dn):
            msg = m.recv_match(type=['STATUSTEXT','HEARTBEAT'], blocking=True, timeout=1)
        if not msg:
            continue
        if msg.get_type() == 'STATUSTEXT':
            last = msg.text
        elif msg.get_type() == 'HEARTBEAT':
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    if armed:
        break
    time.sleep(2)
if not armed:
    print(f"  not armable (last prearm note: {last or 'none'})")
    sys.exit(2)                          # settled-timeout / prearm block

m.mav.command_long_send(sysid, 1,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 0, 0,0,0,0,0,0)   # leave disarmed
time.sleep(1)
print("  vehicle clean + armable — ready to fly from the browser")
PY
}

# ── helper: wait until a local TCP port is accepting ─────────────────────────
wait_port(){
  local port="$1" i
  for i in $(seq 1 40); do
    (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && { exec 3>&- 3<&-; return 0; }
    sleep 0.5
  done
  return 1
}

# ── 0. preflight ─────────────────────────────────────────────────────────────
command -v docker  >/dev/null || die "docker not found — install/start Docker Desktop."
docker info >/dev/null 2>&1   || die "docker daemon not reachable — start Docker Desktop."
command -v python3 >/dev/null || die "python3 not found."
[ -d "$GCS_DIR" ]             || die "bundled console missing at $GCS_DIR (expected ./gcs)."
[ -f "$GCS_DIR/airsent_server.py" ] || die "airsent_server.py not in $GCS_DIR."

# ── 1. venv with deps (self-heals) ───────────────────────────────────────────
if [ ! -x "$PY" ] || ! "$PY" -c "import pymavlink,websockets,numpy" 2>/dev/null; then
  say "setting up venv at $VENV …"
  [ -x "$PY" ] || python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check pymavlink websockets numpy
fi

# ── 2. bring up a CLEAN SITL on :5760 ────────────────────────────────────────
cid="$(docker ps -aq --filter ancestor=radarku/ardupilot-sitl:latest | head -1 || true)"
restarted=0
if [ "$NO_RESTART" = "1" ]; then
  say "reusing running SITL (NO_RESTART=1) — arming may fail if it isn't clean."
elif [ -n "${cid:-}" ]; then
  say "restarting SITL for a clean vehicle (set NO_RESTART=1 to skip)…"
  docker restart "$cid" >/dev/null || true
  restarted=1
  say "letting SITL boot (~20s)…"; sleep 20
else
  warn "No SITL container found — start it in another terminal:"
  warn "    (cd $SITL_DIR && ./run.sh)"
fi
say "waiting for MAVLink heartbeat + EKF/GPS settle (until armable; fresh boot ~30–60s)…"
rc=0; sitl_ready || rc=$?
if [ "$rc" -ne 0 ]; then
  case "$rc" in
    2) die "SITL came up but never became armable — check the sim (a fresh restart usually fixes it).";;
    *) die "SITL never responded on $MAV_URL — is it running? (cd $SITL_DIR && ./run.sh)";;
  esac
fi
say "SITL ready."

# ── 3. free our ports, then start the dashboard server (--sim) ───────────────
for p in 8765 8766 8767 "$HTTP_PORT"; do
  lsof -ti "tcp:$p" 2>/dev/null | xargs kill -9 2>/dev/null || true
done
say "starting dashboard server (--sim) … log: $LOG"
( cd "$GCS_DIR" && exec "$PY" -u airsent_server.py --sim ) >"$LOG" 2>&1 &
SERVER_PID=$!
wait_port 8767 || die "dashboard server didn't open :8767 — see $LOG"
wait_port 8765 || die "dashboard server didn't open :8765 — see $LOG"
say "dashboard server up (telemetry :8765 · commands :8767)."

# ── 4. serve the browser console (static files) ──────────────────────────────
say "serving web console on :$HTTP_PORT …"
( cd "$GCS_DIR" && exec python3 -m http.server "$HTTP_PORT" ) >/dev/null 2>&1 &
HTTP_PID=$!
wait_port "$HTTP_PORT" || die "static server didn't open :$HTTP_PORT."

# ── 5. open + print the flight steps ─────────────────────────────────────────
URL="http://localhost:$HTTP_PORT/fly-local.html"
if [ "$DEMO_OPEN" = "1" ] && command -v open >/dev/null; then
  open "$URL" || true
fi
cat <<EOF

  ┌──────────────────────────────────────────────────────────────┐
  │   Airsent SITL — dashboard demo is READY                       │
  └──────────────────────────────────────────────────────────────┘

   OPEN:  $URL

   In the pilot console:
     1. Wait for the top badge to read   ● TELEM: PIXHAWK   (green)
     2. Click  ▲ Takeoff  → confirm the slide   (arms → GUIDED → climbs to set alt)
     3. Once it's hovering, click  Manual  to take the sticks
     4. Fly:   W A S D = move · Space/Shift = up/down · Q/E = yaw
     5. Click  ▼ Land        (⌂ RTH = return to launch)
   (Take off BEFORE switching to Manual — Manual streams velocity that would
    otherwise override the takeoff climb.)

   Note: only the pilot console commands the sim. dashboard/health/
   sensor-status point at the production VPS; mission/parameters/
   actuators are UI mockups (no backend).

   Press Ctrl-C here to shut the demo down.

EOF

# hold until Ctrl-C; the EXIT trap tears everything down
wait
