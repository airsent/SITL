#!/usr/bin/env python3
"""
Airsent SITL — WASD teleop + live map (self-contained cockpit for ArduCopter).

Fly the simulated drone with the keyboard AND watch it move on a built-in
top-down map (flight trail + heading + home), all in one window. Speaks
ArduCopter GUIDED-mode MAVLink — the same control law the real Airsent stack
uses. Connects DIRECTLY to SITL as the single client (the reliable path); no
MAVProxy, no fanout, no extra GUI deps.

Run (after ./run.sh):
  python teleop.py                     # connects tcp:127.0.0.1:5760
  python teleop.py udpin:127.0.0.1:14551   # or via fanout.py, if you're sharing the sim

Keys:
  MOVE   W / S  forward/back     A / D  left/right
  CLIMB  Space  up               Shift  down
  YAW    Q  left                 E  right
  FLIGHT G guided · Enter arm · T takeoff · L land · R RTL · Backspace disarm
  MAP    M basemap on/off · B satellite/street · [ ] zoom out/in
  ESC / close = quit (stops motion; does NOT disarm in the air)

The map draws a real basemap (Esri satellite by default, OpenStreetMap street via
B) under the flight trail — keyless tile services, cached to ./.tilecache/. Offline
or with M off it falls back to the plain metre grid.

To fly: G (guided) → Enter (ARM) → T (takeoff) → then WASD. Each step needs the
previous one to have taken — the terminal "→ …" lines only echo the keypress, so
trust the on-screen readout: the `mode` field must read GUIDED and `ARMED` must be
green before takeoff climbs. The bottom status line shows the vehicle's own replies
(e.g. "ARM: DENIED", "PreArm: …") so a rejected command is never silent.

ArduCopter blocks ARM for ~20-40s after SITL boot (EKF/GPS settle). If Enter
does nothing, wait and press it again.
"""
import os, sys, time, math, threading
from pymavlink import mavutil

CONN        = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5760"
MOVE        = 3.0     # m/s horizontal
CLIMB       = 1.5     # m/s vertical
YAW         = 0.5     # rad/s
TAKEOFF_ALT = 5.0     # m
SELFTEST    = bool(os.environ.get("TELEOP_SELFTEST"))   # headless data-pipeline check

# ── MAVLink link ─────────────────────────────────────────────────────────────
print(f"[teleop] connecting {CONN} … (run ./run.sh first)")
m = mavutil.mavlink_connection(CONN, source_system=252)
if m.wait_heartbeat(timeout=30) is None:
    sys.exit("[teleop] no heartbeat — is SITL (./run.sh) running?")
print(f"[teleop] linked — system {m.target_system}")
m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)

send_lock = threading.Lock()
telem = {"mode": "?", "armed": False, "alt": 0.0, "spd": 0.0, "yaw": 0.0,
         "sats": 0, "lat": None, "lon": None, "msg": "", "msg_err": False}
home = {"lat": None, "lon": None}
MODE_MAP = {0:'STABILIZE',1:'ACRO',2:'ALTHOLD',3:'AUTO',4:'GUIDED',5:'LOITER',
            6:'RTL',9:'LAND',16:'POSHOLD'}
# Command-ack readout: turn silent rejections (unarmed takeoff, pre-arm fails) visible.
ACK_CMDS    = {400:'ARM', 22:'TAKEOFF', 176:'SET_MODE', 21:'LAND'}
ACK_RESULTS = {0:'ACCEPTED', 1:'TEMP_REJECTED', 2:'DENIED', 3:'UNSUPPORTED',
               4:'FAILED', 5:'IN_PROGRESS'}

def reader():
    while True:
        msg = m.recv_match(blocking=True, timeout=2)
        if not msg:
            continue
        t = msg.get_type()
        if t == 'HEARTBEAT':
            telem["armed"] = bool(msg.base_mode & 128)
            telem["mode"]  = MODE_MAP.get(msg.custom_mode, str(msg.custom_mode))
        elif t == 'GLOBAL_POSITION_INT':
            telem["alt"] = msg.relative_alt / 1000.0
            lat, lon = msg.lat / 1e7, msg.lon / 1e7
            telem["lat"], telem["lon"] = lat, lon
            if home["lat"] is None and (lat != 0.0 or lon != 0.0):
                home["lat"], home["lon"] = lat, lon
        elif t == 'VFR_HUD':
            telem["spd"] = msg.groundspeed
        elif t == 'ATTITUDE':
            telem["yaw"] = (math.degrees(msg.yaw) + 360) % 360
        elif t == 'GPS_RAW_INT':
            telem["sats"] = msg.satellites_visible
        elif t == 'STATUSTEXT':                       # vehicle's own messages ("PreArm: …")
            txt = msg.text.decode(errors='ignore') if isinstance(msg.text, bytes) else msg.text
            telem["msg"] = txt.strip()
            telem["msg_err"] = getattr(msg, "severity", 6) <= 4
            print(f"[ac] {telem['msg']}")
        elif t == 'COMMAND_ACK':                      # did the last command take?
            cn = ACK_CMDS.get(msg.command, str(msg.command))
            rn = ACK_RESULTS.get(msg.result, str(msg.result))
            telem["msg"] = f"{cn}: {rn}"
            telem["msg_err"] = msg.result != 0
            print(f"[ack] {telem['msg']}")

threading.Thread(target=reader, daemon=True).start()

def _cmd(cmd, *params):
    p = list(params) + [0.0] * (7 - len(params))
    with send_lock:
        m.mav.command_long_send(m.target_system, m.target_component, cmd, 0, *p)

def set_mode(num):  _cmd(mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                         mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, num)
def arm(v=1):       _cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, v)
def takeoff(alt):   _cmd(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0,0,0,0,0,0, alt)

_TYPEMASK = (mavutil.mavlink.POSITION_TARGET_TYPEMASK_X_IGNORE |
             mavutil.mavlink.POSITION_TARGET_TYPEMASK_Y_IGNORE |
             mavutil.mavlink.POSITION_TARGET_TYPEMASK_Z_IGNORE |
             mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE |
             mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE |
             mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE |
             mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE)
def velocity(vx, vy, vz, yr):
    with send_lock:
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED, _TYPEMASK,
            0,0,0, vx,vy,vz, 0,0,0, 0, yr)

def local_ne(lat, lon):
    """Metres north/east of home (local-tangent equirectangular)."""
    if home["lat"] is None or lat is None:
        return None
    n = (lat - home["lat"]) * 111320.0
    e = (lon - home["lon"]) * 111320.0 * math.cos(math.radians(home["lat"]))
    return n, e

# ── Headless self-test (verifies the telemetry + map math, no display) ───────
if SELFTEST:
    print("[selftest] sampling 6s …")
    t0 = time.time()
    while time.time() - t0 < 6:
        time.sleep(0.5)
    ne = local_ne(telem["lat"], telem["lon"])
    print(f"[selftest] mode={telem['mode']} armed={telem['armed']} alt={telem['alt']:.2f} "
          f"yaw={telem['yaw']:.0f} sats={telem['sats']}")
    print(f"[selftest] lat={telem['lat']} lon={telem['lon']} home={home['lat']},{home['lon']}")
    print(f"[selftest] local N/E from home = {ne}")
    ok = telem["lat"] is not None and telem["mode"] != "?" and ne is not None
    print("[selftest]", "DATA PIPELINE OK ✅" if ok else "FAIL ✗")
    # basemap tile reachability (non-fatal — network may be absent)
    if telem["lat"] is not None:
        import urllib.request
        n = 2 ** 17
        xf = (telem["lon"] + 180.0) / 360.0 * n
        yf = (1.0 - math.asinh(math.tan(math.radians(telem["lat"]))) / math.pi) / 2.0 * n
        url = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
               f"World_Imagery/MapServer/tile/17/{int(yf)}/{int(xf)}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Airsent-SITL/1.0 (dev)"})
            data = urllib.request.urlopen(req, timeout=10).read()
            print(f"[selftest] basemap tile z17/{int(xf)}/{int(yf)} = {len(data)}B",
                  "TILE API OK ✅" if len(data) > 1000 else "TILE API WARN")
        except Exception as ex:
            print(f"[selftest] basemap tile fetch failed (non-fatal): {ex}")
    sys.exit(0 if ok else 1)

# ── pygame cockpit (instruments + live map) ──────────────────────────────────
import pygame
pygame.init()
W, H = 940, 560
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Airsent SITL — Teleop + Map")
font  = pygame.font.SysFont("Menlo", 15)
big   = pygame.font.SysFont("Menlo", 21, bold=True)
small = pygame.font.SysFont("Menlo", 12)
clock = pygame.time.Clock()
BG=(10,14,21); PANEL=(15,20,28); FG=(232,237,242); DIM=(120,140,160)
OK=(34,197,94); WARN=(245,158,11); TRAIL=(56,189,248); GRID=(30,40,52); DRONE=(245,158,11)

# Map viewport (right side)
MX, MY, MS = 312, 12, 536          # origin x,y and square size
last_vel = (0.0, 0.0, 0.0, 0.0)
trail = []                          # list of (north, east) metres

# ── Basemap tiles (real map imagery under the instrument map) ─────────────────
# Slippy web-mercator tiles from keyless services, cached to disk. Fetched on a
# background thread so the render loop never blocks on the network; the map
# degrades gracefully to the plain grid when offline or with the basemap off.
import queue, urllib.request

TILE = 256
UA = "Airsent-SITL/1.0 (dev tool; github.com/IshaanMarwaha/SITL-Airsent)"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tilecache")
SOURCES = [
    {"name": "satellite", "attr": "© Esri", "ext": "jpg",
     "url": lambda z, x, y: f"https://server.arcgisonline.com/ArcGIS/rest/services/"
                            f"World_Imagery/MapServer/tile/{z}/{y}/{x}"},
    {"name": "street", "attr": "© OpenStreetMap", "ext": "png",
     "url": lambda z, x, y: f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"},
]
mapview = {"on": True, "src": 0, "zoff": 0, "z": None}   # runtime basemap state

_tiles_mem = {}          # (src,z,x,y) -> pygame.Surface
_tiles_pending = set()   # in-flight fetches
_tiles_failed = {}       # key -> last-attempt time (retry cooldown)
_fetch_q = queue.Queue()

def _tile_path(src, z, x, y):
    s = SOURCES[src]
    return os.path.join(CACHE_DIR, s["name"], str(z), str(x), f"{y}.{s['ext']}")

def _fetch_worker():
    while True:
        key = _fetch_q.get()
        src, z, x, y = key
        try:
            req = urllib.request.Request(SOURCES[src]["url"](z, x, y),
                                         headers={"User-Agent": UA})
            data = urllib.request.urlopen(req, timeout=10).read()
            p = _tile_path(src, z, x, y)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p + ".part", "wb") as f:
                f.write(data)
            os.replace(p + ".part", p)          # atomic: readers never see a partial
        except Exception:
            _tiles_failed[key] = time.time()
        finally:
            _tiles_pending.discard(key)

def get_tile(src, z, x, y):
    """Surface if cached, else kick off a background fetch and return None."""
    key = (src, z, x, y)
    s = _tiles_mem.get(key)
    if s is not None:
        return s
    p = _tile_path(src, z, x, y)
    if os.path.exists(p):
        try:
            surf = pygame.image.load(p).convert()   # main thread only (convert)
            _tiles_mem[key] = surf
            return surf
        except Exception:
            try: os.remove(p)
            except OSError: pass
    if key in _tiles_pending:
        return None
    last = _tiles_failed.get(key)
    if last is not None and time.time() - last < 30:
        return None                                 # cool down after a failure
    _tiles_pending.add(key)
    _fetch_q.put(key)
    return None

def latlon_to_world(lat, lon, z):
    """Lat/lon -> global web-mercator pixel at zoom z (256-px tiles)."""
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n * TILE
    lr = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lr)) / math.pi) / 2.0 * n * TILE
    return x, y

def ground_res(lat, z):
    """Metres per pixel at this latitude/zoom (web-mercator)."""
    return 156543.03392804097 * math.cos(math.radians(lat)) / (2 ** z)

def nice_step(extent):
    for s in (5, 10, 25, 50, 100, 250, 500, 1000):
        if extent / s <= 6:
            return s
    return 2000

def draw_instruments():
    y = [16]
    def line(txt, col=FG, f=font, dy=22):
        screen.blit(f.render(txt, True, col), (16, y[0])); y[0] += dy
    line("AIRSENT SITL", OK, big, 30)
    line("teleop + map", DIM, small, 22)
    armed = telem["armed"]
    line(f"mode  {telem['mode']:<9}", FG)
    line(("ARMED" if armed else "disarmed"), OK if armed else DIM)
    line(f"alt   {telem['alt']:6.2f} m", FG)
    line(f"spd   {telem['spd']:5.1f} m/s")
    line(f"yaw   {telem['yaw']:5.0f}°")
    line(f"sats  {telem['sats']}")
    vx, vy, vz, yr = last_vel
    y[0] += 6
    line("cmd", DIM, small, 16)
    line(f"vx{vx:+.1f} vy{vy:+.1f}", WARN if any((vx,vy,vz,yr)) else DIM, font, 20)
    line(f"vz{vz:+.1f} yaw{yr:+.2f}", WARN if any((vx,vy,vz,yr)) else DIM, font, 26)
    for t in ("W/S fwd·back  A/D l·r","Space/Shift up·down","Q/E yaw",
              "G guided  Enter arm","T takeoff  L land","R rtl  ⌫ disarm  Esc quit",
              "─ map ─","M base  B layer  [ ] zoom"):
        line(t, DIM, small, 17)

def draw_map():
    pygame.draw.rect(screen, PANEL, (MX, MY, MS, MS))
    pygame.draw.rect(screen, GRID, (MX, MY, MS, MS), 1)
    cx, cy = MX + MS//2, MY + MS//2
    cur = local_ne(telem["lat"], telem["lon"])
    if cur is None or home["lat"] is None:
        screen.blit(font.render("acquiring GPS…", True, DIM), (cx-60, cy))
        return
    pts = trail + [cur]
    extent = max(15.0, max(max(abs(n), abs(e)) for n, e in pts) * 1.15)

    # Pick a discrete web-mercator zoom that fits the flight; hysteresis (0.6)
    # keeps it from flickering between levels while hovering near a boundary.
    zf = math.log2(156543.03392804097 * math.cos(math.radians(home["lat"]))
                   / (extent / (MS/2 - 16)))
    base = mapview["z"]
    if base is None or abs(zf - base) > 0.6:
        base = int(round(zf))
    mapview["z"] = base
    z = max(3, min(19, base + mapview["zoff"]))
    res = ground_res(home["lat"], z)                 # metres/pixel at this zoom
    hwx, hwy = latlon_to_world(home["lat"], home["lon"], z)  # home world px (map centre)

    def s_ne(n, e):                                  # local N/E metres -> screen px
        lat = home["lat"] + n / 111320.0
        lon = home["lon"] + e / (111320.0 * math.cos(math.radians(home["lat"])))
        wx, wy = latlon_to_world(lat, lon, z)
        return int(cx + (wx - hwx)), int(cy + (wy - hwy))

    screen.set_clip((MX, MY, MS, MS))                # keep map content inside its panel
    # basemap tiles under everything
    if mapview["on"]:
        nt = 2 ** z
        for tx in range(int((hwx + MX - cx) // TILE), int((hwx + MX + MS - cx) // TILE) + 1):
            for ty in range(int((hwy + MY - cy) // TILE), int((hwy + MY + MS - cy) // TILE) + 1):
                if not (0 <= tx < nt and 0 <= ty < nt):
                    continue
                surf = get_tile(mapview["src"], z, tx, ty)
                if surf is not None:
                    screen.blit(surf, (int(cx + tx*TILE - hwx), int(cy + ty*TILE - hwy)))
    # metre grid (scale reference), sized to the real ground resolution
    half_m = (MS/2) * res
    step = nice_step(half_m)
    r = 0.0
    while r <= half_m:
        rp = int(r / res)
        for rr in (rp, -rp):
            pygame.draw.line(screen, GRID, (cx+rr, MY), (cx+rr, MY+MS))
            pygame.draw.line(screen, GRID, (MX, cy+rr), (MX+MS, cy+rr))
        r += step
    # home marker
    hx, hy = s_ne(0, 0)
    pygame.draw.line(screen, DIM, (hx-5, hy), (hx+5, hy)); pygame.draw.line(screen, DIM, (hx, hy-5), (hx, hy+5))
    # trail
    if len(pts) > 1:
        pygame.draw.aalines(screen, TRAIL, False, [s_ne(n, e) for n, e in pts])
    # drone triangle, pointed at yaw
    dx, dy = s_ne(*cur)
    a = math.radians(telem["yaw"])
    tri = [(0,-11),(7,8),(-7,8)]
    rot = [(dx + vx*math.cos(a) - vy*math.sin(a), dy + vx*math.sin(a) + vy*math.cos(a)) for vx,vy in tri]
    pygame.draw.polygon(screen, DRONE, rot)
    screen.blit(small.render(f"{telem['alt']:.1f} m", True, FG), (dx+10, dy-6))
    screen.set_clip(None)
    # labels + attribution
    screen.blit(small.render(f"{step} m grid · z{z}", True, DIM), (MX+8, MY+MS-18))
    screen.blit(small.render("N↑", True, DIM), (cx-6, MY+6))
    lbl = SOURCES[mapview["src"]]["attr"] if mapview["on"] else "basemap off (M)"
    tw = small.render(lbl, True, DIM)
    screen.blit(tw, (MX + MS - tw.get_width() - 8, MY + MS - 18))

def vel_from_keys(k):
    vx = vy = vz = yr = 0.0
    if k[pygame.K_w]: vx += MOVE
    if k[pygame.K_s]: vx -= MOVE
    if k[pygame.K_d]: vy += MOVE
    if k[pygame.K_a]: vy -= MOVE
    if k[pygame.K_SPACE]: vz -= CLIMB
    if k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT]: vz += CLIMB
    if k[pygame.K_e]: yr += YAW
    if k[pygame.K_q]: yr -= YAW
    return vx, vy, vz, yr

for _ in range(3):                                   # background tile fetchers
    threading.Thread(target=_fetch_worker, daemon=True).start()

running = True
was_moving = False
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif ev.type == pygame.KEYDOWN:
            if   ev.key == pygame.K_ESCAPE:    running = False
            elif ev.key == pygame.K_g:         set_mode(4);  print("[teleop] → GUIDED")
            elif ev.key == pygame.K_RETURN:    arm(1);       print("[teleop] → ARM")
            elif ev.key == pygame.K_BACKSPACE: arm(0);       print("[teleop] → DISARM")
            elif ev.key == pygame.K_t:         takeoff(TAKEOFF_ALT); print(f"[teleop] → TAKEOFF {TAKEOFF_ALT}m")
            elif ev.key == pygame.K_l:         set_mode(9);  print("[teleop] → LAND")
            elif ev.key == pygame.K_r:         set_mode(6);  print("[teleop] → RTL")
            elif ev.key == pygame.K_m:         mapview["on"] = not mapview["on"]
            elif ev.key == pygame.K_b:         mapview["src"] = (mapview["src"] + 1) % len(SOURCES); print(f"[teleop] basemap → {SOURCES[mapview['src']]['name']}")
            elif ev.key == pygame.K_LEFTBRACKET:  mapview["zoff"] = max(-4, mapview["zoff"] - 1)
            elif ev.key == pygame.K_RIGHTBRACKET: mapview["zoff"] = min(4, mapview["zoff"] + 1)
    k = pygame.key.get_pressed()
    vx, vy, vz, yr = vel_from_keys(k)
    moving = any((vx, vy, vz, yr))
    if moving:
        velocity(vx, vy, vz, yr); last_vel = (vx, vy, vz, yr); was_moving = True
    elif was_moving:
        velocity(0, 0, 0, 0); last_vel = (0, 0, 0, 0); was_moving = False
    # accumulate trail
    cur = local_ne(telem["lat"], telem["lon"])
    if cur is not None and (not trail or math.hypot(cur[0]-trail[-1][0], cur[1]-trail[-1][1]) > 0.5):
        trail.append(cur)
        if len(trail) > 3000: trail.pop(0)
    screen.fill(BG)
    draw_instruments()
    draw_map()
    if telem["msg"]:                                  # latest vehicle message / command ack
        screen.blit(small.render(telem["msg"][:54], True, WARN if telem["msg_err"] else OK), (16, H-18))
    pygame.display.flip()
    clock.tick(15)

velocity(0, 0, 0, 0)
pygame.quit()
print("[teleop] bye")
