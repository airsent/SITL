# Airsent SITL

A one-command, **shareable** Software-In-The-Loop (SITL) rig for the Airsent drone.
Clone it, run one script, and fly a **simulated ArduCopter** on your own machine — no
hardware needed. It bundles two ways to fly the same sim:

1. **The real Airsent GCS console** driving the sim (`./demo.sh`) — the actual dashboard
   commanding a simulated Pixhawk: arm → takeoff → fly → land.
2. **A standalone keyboard flyer** with a live map (`python teleop.py`) — WASD control in
   a single window, no browser.

Same recipe on every machine, in git — the substrate we develop and test against before
touching real hardware.

**The flight stack is [ArduCopter](https://ardupilot.org/copter/) — Airsent's production
autopilot.** The Pixhawk 6 runs ArduCopter and the GCS + Jetson server speak ArduCopter
MAVLink (GUIDED, `NAV_TAKEOFF`, ArduPilot params), so ArduCopter SITL exercises the *real*
command/telemetry code. The sim wraps the maintained
[`radarku/ardupilot-sitl`](https://hub.docker.com/r/radarku/ardupilot-sitl) image.

> PX4 SITL is kept under [`px4/`](px4/) as a **reference** substrate only — it does not
> match the real command layer.

## What's in here

| Path | What it is |
|---|---|
| `run.sh` · `docker-compose.yml` | Bring up ArduCopter SITL on `tcp:127.0.0.1:5760`. |
| `demo.sh` | One-command **dashboard-over-SITL** demo (uses the bundled console). |
| `teleop.py` | Standalone WASD flyer + live map (connects straight to SITL). |
| `fanout.py` | Optional: rebroadcast the single-client SITL link to two consumers. |
| `gcs/` | The **Airsent GCS console** (browser dashboard + `airsent_server.py`), the SITL-integration snapshot the demo serves. |

> **`gcs/` is the console's source of truth.** It began as a snapshot of
> `Airsent-FlightConsole` (`sitl-integration`), but the dashboard↔SITL work — Phase A's
> `_LOCAL_DEV` endpoint seam, Phase A.5's sensor-health / system-status / STATUSTEXT
> forwarding — all landed here, leaving that branch 112 lines behind and never pushed.
> Rather than keep two copies drifting, this repo is now canonical for the console:
> develop here, and treat `Airsent-FlightConsole`'s `sitl-integration` branch as retired
> (2026-09-07).

---

## Prerequisites (one-time)

1. **Docker Desktop** — https://www.docker.com/products/docker-desktop/
   (macOS: `brew install --cask docker`, launch once).
2. **Python 3** with the host tooling: `pip install -r requirements.txt`.

---

## Quick start

```bash
git clone https://github.com/airsent/SITL.git airsent-sitl
cd airsent-sitl
pip install -r requirements.txt

./run.sh            # terminal 1 — ArduCopter SITL on tcp:127.0.0.1:5760
```

First `./run.sh` pulls the image (~1.25 GB, once). Custom home: `LAT=.. LON=.. ./run.sh`
(default = ASU Tempe). Then, in terminal 2, pick one of the two ways to fly:

```bash
./demo.sh           # A) the real Airsent dashboard flies the sim (opens in a browser)
python teleop.py    # B) standalone WASD flyer with a live map
```

---

## A) Dashboard demo — `./demo.sh`

Brings up a **clean** SITL, starts the bundled console server in `--sim` mode, serves the
browser console, and opens it. Everything it needs is in this repo.

In the pilot console that opens:

1. Wait for the top badge to read **● TELEM: PIXHAWK** (green).
2. Click **▲ Takeoff** → confirm the slide (arms → GUIDED → climbs to the set altitude).
3. Once it's hovering, click **Manual** to take the sticks.
4. Fly: `W A S D` move · `Space`/`Shift` up/down · `Q`/`E` yaw.
5. Click **▼ Land** (⌂ RTH = return to launch).

> Take off **before** switching to Manual — Manual streams a velocity setpoint that would
> otherwise override the takeoff climb. (This was a real bug SITL caught before flight.)

**What actually reflects the sim:** only the **pilot** console commands and reads the local
SITL; `dashboard` shows it live too. `preflight`/`logs` read local sim telemetry (read-only).
`health`/`sensor-status` use the page origin's `/telem`, which the local demo server doesn't
serve, so they read OFFLINE here. `failsafe` (from upstream FlightConsole) is a browser-local
policy page and never writes to the aircraft. `mission`/`parameters`/`actuators` have no backend.

**`--relay` note:** upstream moved the VPS relays behind an SSH tunnel (see `gcs/DROPLET_SETUP.md`);
the old public relay ports are closed. To relay the sim, open the tunnel and set
`VPS_TELEM_URL` / `VPS_CMD_URL` before `--sim --relay`. Keep the flying demo on the pilot
page.

Options: `NO_RESTART=1 ./demo.sh` (reuse a clean running SITL, faster) · `DEMO_OPEN=0 ./demo.sh`
(print the URL instead of auto-opening).

---

## B) Standalone flyer — `teleop.py`

A self-contained cockpit: keyboard control **and** a top-down map (flight trail + heading +
home) in one window. Connects directly to SITL — no browser, no server.

```
python teleop.py                        # tcp:127.0.0.1:5760 (default)
```

| | Keys |
|---|---|
| **Move** | `W`/`S` fwd·back · `A`/`D` left·right |
| **Climb** | `Space` up · `Shift` down |
| **Yaw** | `Q` left · `E` right |
| **Flight** | `G` guided · `Enter` arm · `T` takeoff · `L` land · `R` RTL · `Backspace` disarm |
| **Map** | `M` basemap on/off · `B` satellite↔street · `[` `]` zoom out/in |

Typical: **G → Enter → T**, then fly. The map shows the drone (orange, pointed at its
heading), a blue trail, an auto-scaling metre grid, and live altitude — over a **real
basemap** so you can see the drone against actual ground.

### Basemap

Real slippy tiles under the flight trail — **Esri World Imagery (satellite)** by default,
**OpenStreetMap (street)** via `B`. Both are **keyless** (no token to hand the team),
fetched on a background thread and cached to `./.tilecache/` (git-ignored), so a second
flight over the same area is instant and offline-capable. Zoom auto-fits the flight; `[` /
`]` nudge it. `M` drops back to the plain metre grid (also the automatic fallback when a
tile can't be fetched). Tiles are © Esri / © OpenStreetMap under their respective terms.

> ⚠️ **Arming:** ArduCopter blocks ARM for **~20–40 s after boot** while EKF/GPS settle.
> If `Enter` seems to do nothing, wait and press again.

> **Verified 2026-07-09 (Apple Silicon):** direct GUIDED arm → `NAV_TAKEOFF` → velocity
> teleop → LAND, and the live-map data pipeline, end to end.

---

## Attach another GCS (optional) — `fanout.py`

SITL's `:5760` is a **single-client** MAVLink TCP server, so only one tool can connect at a
time. To share the sim with a second tool (e.g. QGroundControl), run the fan-out — it reads
`:5760` once and rebroadcasts over UDP:

```bash
python fanout.py            # tcp:5760 -> udp 14650 & 14551
python teleop.py udpin:127.0.0.1:14551
# QGC: add a UDP link on 14650
```

---

## Caveats

- **Single-client TCP:** keep **one** client on `:5760` (the dashboard demo *or* teleop *or*
  fanout — not several). Killing a client can wedge SITL's listener — if a fresh client
  won't get a heartbeat, `docker restart airsent-sitl` and reconnect. (`demo.sh` does the
  clean restart for you.)
- **amd64 image** runs under emulation on Apple Silicon (~0.93× real-time — fine).
- **No Gazebo needed:** ArduCopter SITL has a built-in physics model.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Docker daemon not reachable` | Launch Docker Desktop. |
| Won't ARM | Wait ~30 s after boot (EKF/GPS settle), retry. |
| teleop/demo: `no heartbeat` | SITL not up, or its listener wedged — `docker restart airsent-sitl`. |
| Port 5760 in use | `docker ps` → `docker rm -f <name>`, or another client already holds it. |
| demo: `didn't open :8767` | Check the server log path printed by `demo.sh`. |

---

## For the team

Clone, `pip install -r requirements.txt`, `./run.sh`, then `./demo.sh` (dashboard) or
`python teleop.py` (standalone) — same on every machine. ArduCopter is the default because
it's what actually flies; `px4/` stays as reference only.
