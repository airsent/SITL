#!/usr/bin/env bash
#
# Airsent SITL — one-command launcher for PX4 Software-In-The-Loop.
#
# VERIFIED working on Apple Silicon + Docker Desktop (2026-07-08): telemetry reaches the
# host and a GCS can arm + command an autonomous takeoff over MAVLink.
#
# Wraps the maintained `jonasvautherin/px4-gazebo-headless` image (adopt-don't-invent).
# The container runs PX4 SITL + headless Gazebo and PUSHES MAVLink to a ground station
# (QGroundControl) on the HOST:
#   - UDP 14550 -> QGroundControl
#   - UDP 14540 -> MAVSDK / MAVROS
#
# Usage:
#   ./run.sh                  # boot SITL against this machine's ground station
#   PX4_TAG=1.16.0 ./run.sh   # pin a different PX4 release tag
#
# Then open QGroundControl. If it doesn't auto-connect, add a UDP comm link on port 14550
# (see README). Do NOT publish 14550 with -p — it collides with QGC binding the same port.

set -euo pipefail

IMAGE="jonasvautherin/px4-gazebo-headless:${PX4_TAG:-1.17.0}"
OS="$(uname -s)"
# Cap the (very chatty) Gazebo log so a long sim session can't fill the disk.
LOG_OPTS=(--log-opt max-size=20m --log-opt max-file=3)

if ! docker info >/dev/null 2>&1; then
  echo "!! Docker daemon not reachable. Start Docker Desktop and retry." >&2
  exit 1
fi

case "${OS}" in
  Linux)
    # Host networking: container shares the host stack, default broadcast reaches
    # QGC on localhost. Simplest and most reliable path.
    exec docker run --rm -it "${LOG_OPTS[@]}" --network host "${IMAGE}"
    ;;
  Darwin|MINGW*|MSYS*|CYGWIN*)
    # Docker Desktop has no host networking. Resolve the host's container-visible
    # address and tell SITL to unicast MAVLink there (both QGC + MAVSDK targets).
    # The container-initiated UDP flow also carries command replies back, so we do
    # NOT publish any ports.
    HOST_IP="$(docker run --rm busybox getent hosts host.docker.internal 2>/dev/null | awk '{print $1}' | head -1 || true)"
    HOST_IP="${HOST_IP:-192.168.65.254}"
    echo ">> pushing MAVLink to host ${HOST_IP} (QGC udp/14550, MAVSDK udp/14540)"
    exec docker run --rm -it "${LOG_OPTS[@]}" "${IMAGE}" "${HOST_IP}" "${HOST_IP}"
    ;;
  *)
    echo "!! Unrecognized OS '${OS}'. Falling back to default broadcast." >&2
    exec docker run --rm -it "${LOG_OPTS[@]}" "${IMAGE}"
    ;;
esac
