"""One-second, observational safety/health evaluator.

This module deliberately has no pymavlink, network or flight-control imports.
Missing/expired evidence is UNKNOWN or STALE, never OK. Thresholds below are
operational indicators, NOT certified vehicle failsafe setpoints.
"""
from __future__ import annotations
import json
import math
import os
import threading
import time
from pathlib import Path

GROUPS = [
    'GPS / NAVIGATION', 'IMU / FLIGHT', '5G LINK', 'COMPASS', 'POWER',
    'FRONT CAMERA', 'RC LOSS', 'VIBRATION', 'BACK CAMERA', 'PARACHUTE',
    'RETURN TO HOME', 'MOTORS',
]

# Additional check coverage deliberately includes uninstrumented items; this
# is a manifest of what is expected, not a claim about connected hardware.
CHECKS = [
    ('fc_connection','Flight controller link',1),
    ('fc_heartbeat','Flight controller heartbeat',1),
    ('attitude_fresh','Attitude measurement freshness',1),
    ('ekf_status','EKF reported state',0),
    ('gps_fresh','GPS measurement freshness',0),
    ('gps_fix','GNSS fix type',0),
    ('gps_satellites','GNSS satellite count',0),
    ('gps_hdop','GNSS HDOP reporting',0),
    ('position_fresh','Position measurement freshness',0),
    ('rc_fresh','RC receiver evidence age',6),
    ('rc_rssi','RC reported RSSI validity',6),
    ('battery_fresh','Battery telemetry freshness',4),
    ('battery_remaining','Battery percent validity',4),
    ('battery_voltage','Battery voltage validity',4),
    ('jetson_temperature','Jetson temperature',4),
    ('jetson_cpu','Jetson CPU pressure',4),
    ('jetson_gpu','Jetson GPU pressure',4),
    ('jetson_ram','Jetson RAM pressure',4),
    ('jetson_disk','Jetson disk capacity',4),
    ('jetson_stats_fresh','Jetson resource sample freshness',4),
    ('range_fresh','Rangefinder acquisition freshness',1),
    ('range_valid','Rangefinder measurement validity',1),
    ('flow_fresh','Optical-flow acquisition freshness',1),
    ('flow_quality','Optical-flow reported quality',1),
    ('vibration_fresh','Vibration sample freshness',7),
    ('front_frame_fresh','Front camera frame freshness',5),
    ('down_frame_fresh','Down camera frame freshness',5),
    ('apriltag_fresh','AprilTag detector update freshness',5),
    ('apriltag_target','AprilTag target present during LAND',5),
    ('depth_fresh','Depth/proximity processing freshness',5),
    ('command_fresh','Remote velocity command freshness',2),
    ('vps_uplink','Jetson-to-VPS telemetry uplink',2),
    ('mission_state','Autonomous mission progress',1),
    ('operator_lease','Authenticated operator control lease',2),
    ('clock_sync','Cross-device timestamp synchronization',2),
    ('fc_prearm','FC pre-arm readback',1),
    ('fence_status','Geofence onboard status',0),
    ('compass_calibration','Compass calibration readback',3),
    ('camera_obstacle_coverage','Verified obstacle field of view',5),
    ('rear_camera','Rear-facing camera frames',8),
    ('parachute_controller','Parachute controller readiness',9),
    ('rtl_home','Verified home position and RTL clearance',10),
    ('esc_telemetry','Independent ESC/motor feedback',11),
    ('payload_latch','Payload latch / release telemetry',11),
    ('log_health','Persistent flight-log write validation',1),
    ('mission_current','Current mission waypoint telemetry',1),
    ('mission_total','Mission item count telemetry',1),
    ('mission_reached','Mission waypoint reached event',1),
    ('fence_breach','Reported onboard fence breach',0),
    ('home_position','Onboard home-position telemetry',10),
    ('esc_rpm','ESC RPM telemetry presence',11),
    ('battery_cells','Battery cell-voltage telemetry',4),
    ('prearm_alert','Reported pre-arm failure',1),
    ('landed_state','Autopilot landed-state telemetry',1),
    ('ekf_variance','EKF reported variance telemetry',1),
    ('asc_event_storage','ASC event-store availability',1),
    ('vps_cmd_transport','Jetson-to-VPS command transport',2),
    ('worker_mavlink','MAVLink reader thread liveness',1),
    ('worker_velocity','Velocity sender thread liveness',1),
    ('worker_thermal','Thermal monitor thread liveness',4),
    ('worker_front_capture','Front camera capture thread liveness',5),
    ('worker_down_capture','Down camera capture thread liveness',5),
    ('worker_front_rtmp','Front camera RTMP thread liveness',5),
    ('worker_down_rtmp','Down camera RTMP thread liveness',5),
]
CHECK_INDEX = {key: (title, group) for key, title, group in CHECKS}


def _num(v):
    return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)


def _result(check_id, state, reason, value=None):
    title, group = CHECK_INDEX[check_id]
    obj = {'id': check_id, 'name': title, 'group': group, 'status': state, 'reason': reason}
    if value is not None and (isinstance(value, (bool, str)) or _num(value)):
        obj['value'] = value
    return obj


def check_snapshot(s: dict) -> list[dict]:
    """Evaluate one Jetson-produced snapshot with source-age values in seconds.

    Input can be unit-tested without running the Jetson stack. No writes/flight commands.
    """
    if not isinstance(s, dict):
        s = {}
    age = s.get('sensor_age_s') if isinstance(s.get('sensor_age_s'), dict) else {}
    out = {key: _result(key,'UNKNOWN','No verified telemetry / integration available') for key in CHECK_INDEX}

    def put(key, state, msg, val=None):
        out[key] = _result(key, state, msg, val)

    def agecheck(key, source, limit=3.0, applicable=True):
        if not applicable:
            put(key,'NOT_APPLICABLE','Not required for the current flight phase')
            return False
        v = age.get(source)
        if not _num(v) or v < 0:
            put(key,'UNKNOWN','No acquisition timestamp for '+source)
            return False
        if v > limit:
            put(key,'STALE',f'{source} sample age {v:.1f}s > {limit:.1f}s',round(v,2))
            return False
        put(key,'OK',f'{source} sample age {v:.1f}s',round(v,2))
        return True

    armed = s.get('armed') is True
    mode = str(s.get('flight_mode') or 'UNKNOWN').upper()
    connected = s.get('pixhawk_connected')
    if connected is True:
        put('fc_connection','OK','MAVLink connection handle present (not proof of fresh data)')
    elif connected is False:
        put('fc_connection','CRITICAL','MAVLink connection unavailable')
    agecheck('fc_heartbeat','heartbeat',3)
    agecheck('attitude_fresh','attitude',3)
    agecheck('position_fresh','position',3)
    if agecheck('gps_fresh','gps',4):
        fix = s.get('fix_type')
        if not isinstance(fix,str) or not fix:
            put('gps_fix','UNKNOWN','No GNSS fix classification')
        elif fix in ('NO FIX','2D FIX'):
            put('gps_fix','WARNING','GNSS has no confirmed 3D fix',fix)
        else:
            put('gps_fix','OK','Reported GNSS fix; position integrity separately unverified',fix)
        sats = s.get('sats')
        if _num(sats):
            put('gps_satellites','OK' if sats >= 6 else 'WARNING','Satellite count is informational, not position integrity',sats)
        hdop = s.get('hdop')
        if _num(hdop) and 0 <= hdop < 99:
            put('gps_hdop','OK','HDOP reported; no vehicle-calibrated safety threshold',hdop)
    if agecheck('ekf_status','ekf',4):
        flag = s.get('ekf_healthy')
        if flag is True: put('ekf_status','OK','Reported EKF_STATUS_REPORT flag (partial estimator evidence)')
        elif flag is False: put('ekf_status','WARNING','EKF flags not fully satisfied; inspect FC telemetry')
        else: put('ekf_status','UNKNOWN','EKF flag unavailable')
    if agecheck('rc_fresh','rc',4):
        rssi = s.get('rssi')
        if _num(rssi) and 0 <= rssi <= 100:
            put('rc_rssi','OK','Reported RSSI; thresholds and units unverified',rssi)
        else:
            put('rc_rssi','UNKNOWN','RC RSSI missing or invalid')
    if agecheck('battery_fresh','power',5):
        battery = s.get('battery')
        if _num(battery) and 0 <= battery <= 100:
            put('battery_remaining','OK','Battery estimate present; low/critical thresholds unverified',battery)
        elif battery == -1:
            put('battery_remaining','UNKNOWN','Flight controller reports battery percentage unavailable')
        else:
            put('battery_remaining','UNKNOWN','Battery percentage unavailable')
        volts = s.get('voltage')
        if _num(volts) and volts > 0:
            put('battery_voltage','OK','Battery voltage present; pack thresholds unverified',volts)
        else:
            put('battery_voltage','UNKNOWN','Battery voltage absent or invalid')

    stats_fresh = agecheck('jetson_stats_fresh','system_stats',12)
    for key, name, warn, critical in (
        ('jetson_temperature','jetson_temp',75,85),
        ('jetson_cpu','cpu',90,99), ('jetson_gpu','gpu',95,100),
        ('jetson_ram','ram',90,98), ('jetson_disk','disk_used_percent',90,98),
    ):
        v = s.get(name)
        if stats_fresh and _num(v) and v >= 0:
            state = 'CRITICAL' if v >= critical else 'WARNING' if v >= warn else 'OK'
            put(key,state,'Companion resource indicator; review thresholds for this hardware',round(v,2))

    disk = s.get('disk_used_percent')
    if _num(disk) and disk >= 0:
        put('jetson_disk','CRITICAL' if disk>=98 else 'WARNING' if disk>=90 else 'OK',
            'Companion disk usage indicator; verify allocation and write permissions',round(disk,2))
    if agecheck('range_fresh','rangefinder',3):
        dist = s.get('rangefinder')
        if _num(dist) and dist > 0:
            put('range_valid','OK','Positive reading; calibrated min/max limits not provided',dist)
        else:
            put('range_valid','UNKNOWN','No valid positive distance; zero is NOT ground contact')
    if agecheck('flow_fresh','of',3):
        quality = s.get('of_quality')
        if _num(quality) and 0 <= quality <= 255:
            put('flow_quality','OK','Reported flow quality; active EKF usage/limit unverified',quality)
    agecheck('vibration_fresh','vib',4)
    agecheck('front_frame_fresh','front_frame',3)
    agecheck('down_frame_fresh','down_frame',3)
    detector_ready = s.get('apriltag_detector_available')
    if detector_ready is False:
        put('apriltag_fresh','UNKNOWN','AprilTag detector package not available')
    elif agecheck('apriltag_fresh','apriltag',4,applicable=mode=='LAND'):
        target = s.get('apriltag')
        if isinstance(target,dict) and target.get('detected') is True:
            put('apriltag_target','OK','Tag detected; FC LANDING_TARGET guidance is NOT verified')
        else:
            put('apriltag_target','WARNING','No tag detected in LAND; precision landing requirement unverified')
    if mode != 'LAND':
        put('apriltag_target','NOT_APPLICABLE','Landing-target check only applies in LAND mode')
    agecheck('depth_fresh','depth',4)
    if mode == 'GUIDED' and armed:
        agecheck('command_fresh','velocity_cmd',1.0)
    else:
        put('command_fresh','NOT_APPLICABLE','No armed GUIDED velocity session reported')
    connected_uplink = s.get('vps_telem_connected')
    if connected_uplink is True: put('vps_uplink','OK','Jetson-to-VPS telemetry WebSocket connected')
    elif connected_uplink is False: put('vps_uplink','WARNING','Jetson-to-VPS telemetry WebSocket disconnected')
    # Information-only MAVLink evidence. Presence never implies that the
    # related hardware or autonomous recovery policy has been verified.
    if agecheck('mission_current','mission_current',6,applicable=mode=='AUTO'):
        seq=s.get('mission_seq')
        put('mission_current','OK' if isinstance(seq,int) and seq>=0 else 'UNKNOWN',
            'FC reports current mission item; mission progress is NOT independently verified',seq)
        if isinstance(seq,int) and seq>=0:
            put('mission_state','OK','FC mission index reported; no waypoint timeout or destination validation',seq)
    if agecheck('mission_total','mission_count',30,applicable=mode=='AUTO'):
        count=s.get('mission_count')
        put('mission_total','OK' if isinstance(count,int) and count>=0 else 'UNKNOWN',
            'FC mission item count; uploaded mission content NOT independently verified',count)
    # A reached event is occasional, not a continuous sensor; its absence
    # is not evidence of failure or successful progress.
    reached=s.get('mission_reached')
    if mode!='AUTO':
        put('mission_reached','NOT_APPLICABLE','Mission progress applies to AUTO mode')
    elif isinstance(reached,int) and reached>=0:
        put('mission_reached','OK','Most recent MISSION_ITEM_REACHED event; no progress guarantee',reached)
    else:
        put('mission_reached','UNKNOWN','No mission item reached event has been observed')
    if agecheck('fence_breach','fence',10):
        breached=s.get('fence_breached')
        if breached is True:
            put('fence_breach','CRITICAL','Pixhawk reported FENCE_STATUS breached')
            put('fence_status','CRITICAL','Onboard fence breach reported; action not validated')
        elif breached is False:
            put('fence_breach','OK','No breach in latest FENCE_STATUS; fence configuration unverified')
            # Fence status never goes OK without verifying enabled parameters.
            put('fence_status','UNKNOWN','No reported breach; uploaded fence/configuration not verified')
    if agecheck('home_position','home_position',30):
        lat,lon=s.get('home_lat'),s.get('home_lon')
        if _num(lat) and _num(lon) and abs(lat)<=90 and abs(lon)<=180 and (lat!=0 or lon!=0):
            put('home_position','OK','FC HOME_POSITION available; RTL energy and clearance still unknown')
    if agecheck('esc_rpm','esc',5):
        rpms=s.get('esc_rpm')
        if isinstance(rpms,list) and any(_num(r) and r>=0 for r in rpms):
            put('esc_rpm','OK','ESC reports RPM samples; stall/health thresholds NOT calibrated')
            put('esc_telemetry','OK','ESC RPM telemetry received; does not prove motor health')
    if agecheck('battery_cells','battery_status',10):
        cells=s.get('battery_cell_mv')
        if isinstance(cells,list) and cells and all(isinstance(x,int) and x>0 for x in cells):
            put('battery_cells','OK','Battery cell voltages reported; pack calibration unverified')
    alert=s.get('last_prearm_alert')
    alert_age=age.get('prearm_alert')
    if isinstance(alert,str) and alert and _num(alert_age) and alert_age<120:
        put('prearm_alert','WARNING','FC recently reported pre-arm issue: '+alert[:100])
        put('fc_prearm','WARNING','Recent FC PreArm diagnostic; no parameter readback')
    if agecheck('landed_state','landed_state',8):
        landed=s.get('landed_state')
        if isinstance(landed,int) and 1<=landed<=4:
            put('landed_state','OK','FC EXTENDED_SYS_STATE landed state received',landed)
    if agecheck('ekf_variance','ekf',4):
        variance=s.get('ekf_velocity_variance')
        if _num(variance) and variance>=0:
            put('ekf_variance','OK','EKF variance observed; limits require vehicle-specific validation',round(variance,4))
    if s.get('asc_store_ready') is True:
        put('asc_event_storage','OK','ASC SQLite event store initialized (write errors reported separately)')
    elif s.get('asc_store_ready') is False:
        put('asc_event_storage','WARNING','ASC SQLite event store unavailable; telemetry still running')
    cmd_connected=s.get('vps_cmd_connected')
    if cmd_connected is True:
        put('vps_cmd_transport','OK','Jetson command relay transport connected; operator authorization NOT verified')
    elif cmd_connected is False:
        put('vps_cmd_transport','WARNING','Jetson command relay transport disconnected; onboard protection required')
    # .is_alive verifies process thread existence only, not forward progress.
    worker_states=s.get('worker_threads')
    if isinstance(worker_states,dict):
        for worker in ('mavlink','velocity','thermal','front_capture','down_capture','front_rtmp','down_rtmp'):
            live=worker_states.get(worker)
            if live is True:
                put('worker_'+worker,'OK','Python worker thread alive; functional progress checked separately')
            elif live is False:
                severity='CRITICAL' if worker in ('mavlink','velocity') else 'WARNING'
                put('worker_'+worker,severity,'Python worker thread exited unexpectedly')
    # Do not infer operator presence from the VPS connection.
    return [out[k] for k in CHECK_INDEX]


class ASCEngine:
    """Caches 1 Hz evaluations and optionally records transitions in JSONL."""
    def __init__(self, interval=1.0, event_path=None, clock=None, sqlite_path=None):
        self.interval = float(interval)
        self.clock = clock or time.monotonic
        self.event_path = Path(event_path) if event_path else None
        self.sqlite_path = Path(sqlite_path) if sqlite_path else None
        self._event_store = None
        self.store_ready = False
        if self.sqlite_path:
            try:
                from .store import ASCEventStore
                self._event_store = ASCEventStore(self.sqlite_path)
                self.store_ready = True
            except (OSError, ValueError):
                self.store_ready = False
        self._lock = threading.Lock()
        self._previous = {}
        self._last_run = None
        self._seq = 0
        self._snapshot = None

    def tick(self, snapshot):
        with self._lock:
            now = self.clock()
            if self._snapshot is not None and self._last_run is not None and now - self._last_run < self.interval:
                return self._snapshot
            self._last_run = now
            self._seq += 1
            snapshot = dict(snapshot) if isinstance(snapshot,dict) else {}
            snapshot['asc_store_ready'] = self.store_ready if self.sqlite_path else None
            checks = check_snapshot(snapshot)
            transitions=[]
            for item in checks:
                old=self._previous.get(item['id'])
                if (old is not None and old != item['status']) or \
                   (old is None and item['status'] in ('WARNING','CRITICAL','STALE')):
                    transitions.append({'id':item['id'],'before':old or 'INITIAL',
                                        'after':item['status'],'reason':item['reason']})
                self._previous[item['id']]=item['status']
            if self._event_store and transitions:
                try:
                    self._event_store.write_transitions(self._seq, transitions)
                    self.store_ready = True
                except (OSError, ValueError):
                    self.store_ready = False
            if self.event_path and transitions:
                try:
                    self.event_path.parent.mkdir(parents=True,exist_ok=True)
                    with self.event_path.open('a',encoding='utf-8') as f:
                        for t in transitions:
                            f.write(json.dumps({'ts':time.time(),'seq':self._seq,**t})+'\n')
                except OSError:
                    pass  # telemetry must not die if storage is full/unwritable
            counts = {status:sum(1 for c in checks if c['status']==status)
                      for status in ('OK','WARNING','CRITICAL','UNKNOWN','STALE','NOT_APPLICABLE')}
            groups=[]
            for idx, name in enumerate(GROUPS):
                subset=[c for c in checks if c['group']==idx and c['status']!='NOT_APPLICABLE']
                statuses={c['status'] for c in subset}
                if 'CRITICAL' in statuses: state='CRITICAL'
                elif 'WARNING' in statuses: state='WARNING'
                elif 'STALE' in statuses: state='STALE'
                elif 'UNKNOWN' in statuses or not subset: state='UNKNOWN'
                else: state='OK'
                groups.append({'id':idx,'name':name,'status':state})
            self._snapshot={'version':1,'mode':'MONITOR_ONLY','interval_s':self.interval,
                'sequence':self._seq,'timestamp_ms':round(time.time()*1000),
                'count':len(checks),'counts':counts,'groups':groups,
                'checks':checks,'recent_transitions':transitions,
                'event_storage':('SQLITE_READY' if self.store_ready else 'UNAVAILABLE') if self.sqlite_path else 'NOT_CONFIGURED',
                'note':'Monitoring only. No aircraft parameter/command writes. UNKNOWN is not healthy.'}
            return self._snapshot
