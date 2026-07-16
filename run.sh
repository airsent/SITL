#!/usr/bin/env bash
#
# Airsent SITL — one-command ArduCopter Software-In-The-Loop.
#
# ArduCopter is Airsent's PRODUCTION flight stack: the Pixhawk 6 runs ArduCopter, and
# the GCS + Jetson server speak ArduCopter-flavored MAVLink (GUIDED mode, NAV_TAKEOFF,
# ArduPilot params). Use this to develop/test the GCS and the autonomy module against a
# simulated drone before touching hardware. (PX4 SITL is kept under px4/ as a reference
# substrate only — it does NOT match the real command layer.)
#
# VERIFIED on Apple Silicon + Docker Desktop (2026-07-09): heartbeat + full telemetry to
# the host, and a full GUIDED  arm -> NAV_TAKEOFF -> velocity teleop (WASD) -> LAND driven
# end-to-end through Airsent's OWN GCS over MAVLink.
#
# Wraps the maintained `radarku/ardupilot-sitl` image (adopt-don't-invent). SITL exposes a
# MAVLink TCP *server* on port 5760, which we publish to the host.
#
# Usage:
#   ./run.sh                          # boot ArduCopter SITL (home = ASU Tempe)
#   LAT=.. LON=.. ALT=.. ./run.sh     # custom home location
#   MODEL=quad ./run.sh               # different copter frame
#
# Connect a GCS / MAVSDK / pymavlink to:   tcp:127.0.0.1:5760
# NOTE: ArduCopter blocks ARMING for ~20-40s after boot while EKF/GPS settle — wait for it.

set -euo pipefail

IMAGE="radarku/ardupilot-sitl:latest"
VEHICLE="ArduCopter"
MODEL="${MODEL:-+}"
# Home: ASU Tempe campus (Airsent's first delivery turf).
LAT="${LAT:-33.4213}"
LON="${LON:--111.9327}"
ALT="${ALT:-360}"
DIR="${DIR:-0}"

if ! docker info >/dev/null 2>&1; then
  echo "!! Docker daemon not reachable. Start Docker Desktop and retry." >&2
  exit 1
fi

# The published image is amd64; on Apple Silicon it runs under Docker's emulation
# (measured ~0.93x real-time — fine for SITL). On an amd64 host it runs natively.
echo ">> ArduCopter SITL — MAVLink TCP server on tcp://127.0.0.1:5760  (home ${LAT},${LON})"
echo ">> connect a GCS / pymavlink to  tcp:127.0.0.1:5760  (allow ~30s before ARM)"
exec docker run --rm -it \
  --platform linux/amd64 \
  -p 5760:5760 \
  -e VEHICLE="${VEHICLE}" -e MODEL="${MODEL}" \
  -e LAT="${LAT}" -e LON="${LON}" -e ALT="${ALT}" -e DIR="${DIR}" \
  --log-opt max-size=20m --log-opt max-file=3 \
  "${IMAGE}"
