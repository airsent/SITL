# AirSent ASC v2 — existing Failsafes page

**Status: prototype / observation-only software. Do not fly the updated Jetson code without SITL, propless bench and HIL review.**

This release extends the previously integrated ASC v1 code. It is **not a new webpage** and **does not implement all 40 previously discussed follow-up tasks**. Hardware integration, authenticated operator authorization, real onboard parameter audit, phase-aware fallback policies, and flight validation remain necessary.

## At a glance

- The existing ASC top strip is compact again: `ASC [ON/OFF] | FAULTS | 12 SYSTEM CHECKS · OFF` when the display is off; no explanatory paragraph in the strip.
- The new **CHECKS ▾** dropdown appears on that same strip, *inside `failsafe.html`*. It lists **64 defined checks** grouped by the original 12 failsafe groups, with **SYSTEM**, **STATUS**, and **FIND** filters. When disconnected, the check catalog is still listed, but every status is UNKNOWN. The UI never makes absent telemetry green.
- The Jetson's existing MAVLink reader handles additional **read-only** events (`MISSION_CURRENT`, `MISSION_COUNT`, `MISSION_ITEM_REACHED`, `FENCE_STATUS`, `HOME_POSITION`, `ESC_TELEMETRY_1_TO_4`, `BATTERY_STATUS`, `EXTENDED_SYS_STATE`, and pre-arm `STATUSTEXT`), plus EKF velocity variance. The data are checked for freshness. An `OK` here proves only the *particular observation*, not firmware configuration, motor health, return energy, landing safety, or hardware suitability.
- Adds seven named Jetson worker-thread liveness checks and a Jetson↔VPS command-*transport* connection check. Command-transport presence is **not** an authenticated operator heartbeat.
- SQLite transition history is available using `ASC_SQLITE_PATH`. The event store records bounded diagnostic status transitions (including initial WARNING/CRITICAL/STALE observations), not images or raw telemetry. It does not control the aircraft.
- Retains the v1 telemetry-staleness treatment, camera-frame freshness, Jetson status checks, range/optical-flow independence, and expired GUIDED velocity transport guard.
- The **ASC switch only controls frontend display**. The Jetson's checks run independently. Fault count continues showing detected critical observations even when the display switch is OFF; when no backend evidence exists, count is `—`, not a fabricated zero.

## Files added and updated

| Location | Change |
| --- | --- |
| `asc/engine.py` | 64-check catalog, FC evidence evaluation, thread/transport checks, group rollups, transitions |
| `asc/store.py` | New SQLite diagnostic incident store with retention cap |
| `airsent_server.py` | Read-only MAVLink ingest, worker monitoring, optional database hookup |
| `asc-check-catalog.js` | New offline-visible browser catalog synced with Python check registry |
| `failsafe.html` | Restored compact ASC strip plus CHECKS dropdown, no extra page |
| `failsafe-auto.js` | Same-page dropdown, search/filters, accurate stale/unknown handling |
| `failsafe.css` | Dropdown overlay and original-style compact strip |
| `tests/test_asc_v2.py` | New Python regression and SQLite tests |
| `tests/browser_smoke.py` | Same-page UI mock regression test |

The rest of the project remains the v1 integrated source. The prior command timeout change is still included; compare the full diff before deployment.

## Getting started without a drone

From the project directory:

```bash
python -m unittest discover -s tests -v
python -m compileall -q asc airsent_server.py telemetry_server.py
node --check failsafe-auto.js
node --check asc-check-catalog.js
```

Serve the **whole** project directory through the same static web server as the other AirSent pages and open `failsafe.html`. The component list is available even with no Jetson connected. Live readings require the existing `/telem` WebSocket route, the running Jetson telemetry process and MAVLink sensor streams.

**Do not open the HTML as an isolated file and assume WebSocket telemetry will work.** The code expects the existing AirSent console environment, source files, server configuration and supporting dependencies.

## Optional persistent event history on Jetson

Before starting the Jetson service, choose an **operator-managed, writable, backed-up** directory with sufficient space, then set:

```bash
export ASC_SQLITE_PATH=/home/airsent/asc-data/asc-events.sqlite
```

The folder is created if permissions allow. The current SQLite retention cap is 20,000 transition rows; the file and WAL/shm require adequate writable storage. If not configured, ASC runs with `event_storage=NOT_CONFIGURED`; the check `asc_event_storage` remains `UNKNOWN`. SQLite files are **local on the Jetson** and **are not exposed by a new browser API** in this version. Protect access, account for privacy, and manage backup/archive/retention externally. The older optional `ASC_EVENT_JSONL` mode remains available, but avoid running both persistent formats without a reason.

## What is NOT finished

1. **Security/remote control**: backend authentication, pilot identity, exclusive command ownership, lease expiry, end-to-end operator heartbeat and authorization for configuration/flight commands. The existing VPS link and browser presence indicators are *not* identity or authority proof.
2. **Validated FC configuration**: accurate parameter readback, fence content, pre-arm readiness, battery action thresholds and mode-specific fallback policy. No ASC-triggered RTL/LAND or Pixhawk parameter writes were introduced.
3. **Sensor validation**: actual ESC capability and motor fault thresholds, calibrated optical-flow/range/depth, compass status and estimator fallback, device-level power diagnostics.
4. **Mission and landing**: waypoint timing/timeout modeling, mission content verification, verified LANDING_TARGET transmission and AprilTag control effectiveness, RTL energy/clearance calculations.
5. **Delivery hardware**: payload latch/weight/release proof, rear camera and parachute controller, motor-stop coordination.
6. **Physical testing**: no live Jetson/Pixhawk session, ArduPilot SITL flight scenario, HIL, field test or certification was performed in this package.

## Deployment sequence

1. Back up the deployed Jetson code, VPS/static console and **flight-controller parameters**. Compare the included source with your deployed revisions. Do not overwrite newer live changes.
2. Test in ArduPilot **SITL** using the console's actual joystick rate, and deliberately interrupt camera, MAVLink, VPS and GCS links. Confirm the previous version's command-expiry change independently. Do not rely on telemetry from the same Jetson to certify loss protection.
3. Install the updated Python `asc/` and `airsent_server.py` on a **development Jetson**, not the live aircraft. Use the existing Python environment and pymavlink serial reader. There must never be two competing readers of the Pixhawk serial port.
4. Deploy `failsafe.html`, `failsafe.css`, `failsafe-auto.js`, and `asc-check-catalog.js` to the **same VPS static document root** as the rest of the console. Keep `failsafe-bridge.js` and `console-config.js` from the complete project. Clear cached JS/CSS if the browser serves old files.
5. Verify the raw `/telem` JSON includes `asc.version=1`, `asc.count=64`, increasing `asc.sequence`, per-source `sensor_age_s`, and an accurate `telemetry_age` from the VPS. Check the dropdown both when live and after a deliberate disconnect.
6. Validate on an unpowered-prop bench rig / HIL with engineering oversight before any flight. Review the existing GUIDED velocity timeout and flight-controller failsafe parameters on the exact target firmware.

### Safety boundary

All new work is **observational**. The browser ASC button, status rows, pre-arm alert, fence breach, and ESC telemetry **do not execute flight-control commands**. Existing local card activation buttons and policy editors remain *local-only simulation*, not actual flight-controller configuration. If critical safety decisions depend on these checks, a separately engineered and independently validated onboard supervisor is needed.
