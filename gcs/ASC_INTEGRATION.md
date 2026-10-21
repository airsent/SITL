> **ASC v2 note:** Read `ASC_V2_START_HERE.md` first. The current package has 64 defined checks and a compact CHECKS dropdown on `failsafe.html`; v1 counts/screenshots in this document may be outdated.

# AirSent Automatic Safety Check (ASC) — Integrated v1

**Status:** Prototype, monitoring-only. **Not flight-tested, flight-certified, or a replacement for verified ArduPilot/Pixhawk protections.** This is an implementation in the existing Flight Console / `failsafe.html`, NOT a separate ASC page.

## 1. What is implemented

- A Python 1 Hz ASC evaluation engine in `asc/engine.py`, invoked by the **existing** Jetson `airsent_server.py`; **no second Pixhawk serial/MAVLink reader**.
- **45 explicit check definitions** across the existing 12 failsafe groups. The engine reports `OK`, `WARNING`, `CRITICAL`, `STALE`, `UNKNOWN`, and `NOT_APPLICABLE` for each check. Some check definitions are integration placeholders and **never report OK** without their own verified source.
- Real acquisition timestamps, captured at source for FC heartbeat/attitude/position/GPS/EKF/RC/power, rangefinder, optical flow, vibration, OAK-D frames, down-camera frames, AprilTag detection, depth, velocity commands, Jetson stats.
- Jetson resource estimates (CPU/GPU/RAM, thermal, disk), and status of Jetson→VPS telemetry transport.
- Existing ASC bar `#fsAutoToggle`, `#fsFaultCount`, `#fsAutoSummary` is retained **on the existing `failsafe.html` page**. New *Check Details* overlay is on that SAME page, with filtering across individual checks.
- Failsafe page opens the existing `/telem` browser feed itself. **The dashboard no longer has to be open in another tab.** A relay's re-broadcast of cached data is judged by VPS `telemetry_age`, not fresh browser arrival time.
- ASC monitoring is always active on the Jetson regardless of the browser switch. The ASC toggle controls the **browser display only**; it does not enable or disable actual aircraft protections. The UI auto-opens its ASC display when fresh telemetry explicitly reports **armed=true**; armed is **not** equated with airborne.
- Added source-age guard to `velocity_sender`: old GUIDED velocity commands are no longer re-emitted as though new. **THIS CHANGES FLIGHT-CONTROL BEHAVIOR. Validate ArduPilot's timeout behavior in SITL/HIL with a safety pilot before deployment.** Default maximum last-command age: `AIRSENT_VELOCITY_CMD_TIMEOUT_S=1.0` second. This is not an operator-authentication system or an FC failsafe.
- Removed misleading `ekf_healthy=True` initial value; stale rangefinder/flow readings become `null` rather than invented zero; rangefinder staleness is independent of optical flow. Unknown RC RSSI/GPS quality codes become null; Jetson thermal input missing is not read as 0°C. `telemetry.js` tolerates a `null` LiDAR reading without a `.toFixed()` exception.
- Optional JSONL event log of **status transitions** when `ASC_EVENT_JSONL=/path/to/asc-events.jsonl` is set. No telemetry dump by default; manage file permissions and retention before use.

## 2. Check interpretation

- `OK` = that specific measurement or freshness criterion passed; **never** proof an FC failsafe or actuator is configured, independently calibrated or operational.
- `WARNING` = degraded measurement, observed software concern or heuristic threshold.
- `CRITICAL` = high-priority diagnostic issue (e.g., confirmed FC disconnection); **not** a command to land, RTL, or deploy a parachute.
- `STALE` = last source sample exceeded its documented age limit. Repeated relay packets do not reset the age.
- `UNKNOWN` = missing, not instrumented, invalid, or not verified. Unknown does not equal healthy.
- `NOT_APPLICABLE` = gated by flight phase/mode; e.g., AprilTag target acquisition outside LAND.
- `FAULTS` on the ASC bar counts `CRITICAL` checks while ASC display is ON and telemetry is fresh; when data are unavailable, it shows `—`, not a misleading `0`. Warnings and unknowns remain visible in the bar and detail overlay.

### Known unimplemented / unverified checks

The included check catalog intentionally keeps these **UNKNOWN** until new integration and evidence exist: operator control lease and heartbeat, mission progression, parameter/pre-arm/fence readback, compass calibration, actual motor/ESC telemetry, rear camera, parachute release controller/interlocks/feedback, RTL home/clearance validation, flight-log write integrity, obstacle coverage calibration, sensor cross-device clock sync, payload-latch feedback. Even an `OK` frame check does not prove mission readiness.

Other features from the earlier proposed 72-feature wishlist (e.g. payload release and delivery proof, full mission execution tracking, storage read/write integrity, redundant power testing) require separate hardware, MAVLink messages, service APIs or trained/tested models. **They are not silently claimed as complete by this v1.**

## 3. Key files / integration points

| File | Role |
| --- | --- |
| `asc/engine.py` | Pure Python one-second check registry, status and transition engine. No MAVLink writes. |
| `airsent_server.py` | Creates source timestamps, builds ASC payload, optional event logging, command-age guard. Uses existing MAVLink reader. |
| `failsafe.html` | Existing page, ASC bar unchanged in location; adds inline overlay. |
| `failsafe-auto.js` | Existing ASC switch, count, summary and per-check overlay. |
| `failsafe-monitor.js` | Renders backend ASC groups on 12 existing failsafe cards. |
| `failsafe-bridge.js` | Direct read-only `/telem` WebSocket; respects upstream age. |
| `failsafe.css` | New overlay CSS; current layout preserved. |
| `telemetry.js` | Null-safe LiDAR/RSSI/EKF rendering on dashboard. |
| `telemetry_server.py` | **Unchanged.** Existing VPS `telemetry_age` is used by browser. |
| `tests/test_asc_engine.py` and `tests/test_integration_source.py` | Hardware-independent automated tests. |
| `tests/browser_smoke.py` | Optional DOM/JavaScript UI smoke with synthetic ASC data. |

## 4. Deployment plan (do not skip validation)

1. **Backup** your live VPS, Jetson source, systemd units, Nginx config, flight-controller parameters and firmware/mission data. Make a rollback commit/tag. Do not deploy during operations.
2. **Review diff first:** `airsent_server.py`, `telemetry.js`, new ASC files, and especially `velocity_sender`. Confirm the running project versions match the supplied original ZIP and supplied failsafe files; reconcile any newer live changes instead of blindly overwriting.
3. **SITL**: test GUIDED setpoints at the actual console input rate; pause and disconnect operator feed; verify ArduPilot stops previous motion as expected after source commands stop, and test loss of telemetry, Jetson reboot, FC reconnect, and re-arm. Validate FC-level loss handling independently. **Do not flight-test first.**
4. On a development Jetson with compatible dependencies, copy `asc/` plus updated `airsent_server.py` to the same directory. Keep existing dependencies (`depthai`, OpenCV, `pymavlink`, `websockets`, `numpy`, optional `pupil_apriltags`) as the baseline application requires. Do NOT start a second MAVLink process.
5. On a development VPS, publish the updated static files `failsafe.html`, `failsafe.css`, `failsafe-auto.js`, `failsafe-monitor.js`, `failsafe-bridge.js`, `telemetry.js` and confirm `console-config.js` exposes `airsentApiUrl('/telem',true)`. Existing relay service and `/telem` Nginx WebSocket route are reused. There is **no new API service/port**.
6. Run automated tests in the updated directory: `python -m unittest discover -s tests -v`; `python -m compileall -q asc airsent_server.py`; `node --check failsafe-auto.js` etc. Optional browser smoke: `PYTHONPATH=. python tests/browser_smoke.py` (Playwright + Chromium).
7. For integration test, watch a raw `/telem` JSON message for `asc.version=1`, `asc.sequence` increasing approximately once/second, `asc.count=45`, and realistic `sensor_age_s` values. Temporarily interrupt a source and confirm `STALE`/`UNKNOWN`, not fake `OK`. Check source disconnect and restore. **No aircraft commands are sent by ASC.**
8. Before supervised live deployment, use an engineering review to sign off actual thresholds, whether the velocity-age guard should be enabled for the flight configuration, network-loss policy, flight phases, operator-lease security and Pixhawk parameter readback. Controlled bench/HIL validation with props removed before any supervised flight.

## 5. Practical rollout in four follow-up tasks

**Task A — Telemetry/ASC contract and SITL:** Validate source ages, mode transitions, FC message rates, velocity timeout and link-loss behavior on ArduPilot SITL. Owner: flight-control/backend.

**Task B — Sensor-specific completion:** Instrument active EKF source/quality, calibrated LiDAR limits, ESC current/RPM telemetry if hardware supports it, 5G/operator lease, authentic camera frame timestamps and logging errors. Owner: perception/Jetson.

**Task C — Mission/precision landing and FC readback:** Read actual MAVLink parameters/pre-arm/fence, mission state/progress, landing target frames/guidance, RTL/home viability. Owner: autonomy/FC.

**Task D — Review and validation:** HIL/propless bench fault injection, realistic network impairments, camera freeze, Jetson restart, energy model calibration, incident reports and approval gates; build a separate, tightly tested response supervisor only if later authorized. Owner: systems safety.

## 6. Strict boundaries

- The 12 tile Activate/Deactivate controls, battery/RTL response drafts, and browser password remain **local-only planning UI**. They DO NOT turn on/off onboard protection or update Pixhawk parameters. Do not interpret the local `ACTIVE` appearance as a configured FC state.
- Parachute and motor-stop sequencing are NOT implemented and must not be connected to ASC/browser buttons without independent, qualified hardware and a validated, fail-safe supervisory design.
- The ASC system does not have direct remote command authentication, operator lease, authoritative RC loss, verified return-home energy/terrain clearance, or certification evidence. Those limitations block production autonomy decisions.
- The optional velocity transport guard is **a change to the existing command path** but is not executed by ASC alerts. Observe documented regression-test gates before use on a real aircraft.
