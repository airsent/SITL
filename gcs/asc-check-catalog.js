/* Generated from asc/engine.py. */
window.AirsentASCCheckCatalog = {
 "checks": [
  {
   "id": "fc_connection",
   "name": "Flight controller link",
   "group": 1
  },
  {
   "id": "fc_heartbeat",
   "name": "Flight controller heartbeat",
   "group": 1
  },
  {
   "id": "attitude_fresh",
   "name": "Attitude measurement freshness",
   "group": 1
  },
  {
   "id": "ekf_status",
   "name": "EKF reported state",
   "group": 0
  },
  {
   "id": "gps_fresh",
   "name": "GPS measurement freshness",
   "group": 0
  },
  {
   "id": "gps_fix",
   "name": "GNSS fix type",
   "group": 0
  },
  {
   "id": "gps_satellites",
   "name": "GNSS satellite count",
   "group": 0
  },
  {
   "id": "gps_hdop",
   "name": "GNSS HDOP reporting",
   "group": 0
  },
  {
   "id": "position_fresh",
   "name": "Position measurement freshness",
   "group": 0
  },
  {
   "id": "rc_fresh",
   "name": "RC receiver evidence age",
   "group": 6
  },
  {
   "id": "rc_rssi",
   "name": "RC reported RSSI validity",
   "group": 6
  },
  {
   "id": "battery_fresh",
   "name": "Battery telemetry freshness",
   "group": 4
  },
  {
   "id": "battery_remaining",
   "name": "Battery percent validity",
   "group": 4
  },
  {
   "id": "battery_voltage",
   "name": "Battery voltage validity",
   "group": 4
  },
  {
   "id": "jetson_temperature",
   "name": "Jetson temperature",
   "group": 4
  },
  {
   "id": "jetson_cpu",
   "name": "Jetson CPU pressure",
   "group": 4
  },
  {
   "id": "jetson_gpu",
   "name": "Jetson GPU pressure",
   "group": 4
  },
  {
   "id": "jetson_ram",
   "name": "Jetson RAM pressure",
   "group": 4
  },
  {
   "id": "jetson_disk",
   "name": "Jetson disk capacity",
   "group": 4
  },
  {
   "id": "jetson_stats_fresh",
   "name": "Jetson resource sample freshness",
   "group": 4
  },
  {
   "id": "range_fresh",
   "name": "Rangefinder acquisition freshness",
   "group": 1
  },
  {
   "id": "range_valid",
   "name": "Rangefinder measurement validity",
   "group": 1
  },
  {
   "id": "flow_fresh",
   "name": "Optical-flow acquisition freshness",
   "group": 1
  },
  {
   "id": "flow_quality",
   "name": "Optical-flow reported quality",
   "group": 1
  },
  {
   "id": "vibration_fresh",
   "name": "Vibration sample freshness",
   "group": 7
  },
  {
   "id": "front_frame_fresh",
   "name": "Front camera frame freshness",
   "group": 5
  },
  {
   "id": "down_frame_fresh",
   "name": "Down camera frame freshness",
   "group": 5
  },
  {
   "id": "apriltag_fresh",
   "name": "AprilTag detector update freshness",
   "group": 5
  },
  {
   "id": "apriltag_target",
   "name": "AprilTag target present during LAND",
   "group": 5
  },
  {
   "id": "depth_fresh",
   "name": "Depth/proximity processing freshness",
   "group": 5
  },
  {
   "id": "command_fresh",
   "name": "Remote velocity command freshness",
   "group": 2
  },
  {
   "id": "vps_uplink",
   "name": "Jetson-to-VPS telemetry uplink",
   "group": 2
  },
  {
   "id": "mission_state",
   "name": "Autonomous mission progress",
   "group": 1
  },
  {
   "id": "operator_lease",
   "name": "Authenticated operator control lease",
   "group": 2
  },
  {
   "id": "clock_sync",
   "name": "Cross-device timestamp synchronization",
   "group": 2
  },
  {
   "id": "fc_prearm",
   "name": "FC pre-arm readback",
   "group": 1
  },
  {
   "id": "fence_status",
   "name": "Geofence onboard status",
   "group": 0
  },
  {
   "id": "compass_calibration",
   "name": "Compass calibration readback",
   "group": 3
  },
  {
   "id": "camera_obstacle_coverage",
   "name": "Verified obstacle field of view",
   "group": 5
  },
  {
   "id": "rear_camera",
   "name": "Rear-facing camera frames",
   "group": 8
  },
  {
   "id": "parachute_controller",
   "name": "Parachute controller readiness",
   "group": 9
  },
  {
   "id": "rtl_home",
   "name": "Verified home position and RTL clearance",
   "group": 10
  },
  {
   "id": "esc_telemetry",
   "name": "Independent ESC/motor feedback",
   "group": 11
  },
  {
   "id": "payload_latch",
   "name": "Payload latch / release telemetry",
   "group": 11
  },
  {
   "id": "log_health",
   "name": "Persistent flight-log write validation",
   "group": 1
  },
  {
   "id": "mission_current",
   "name": "Current mission waypoint telemetry",
   "group": 1
  },
  {
   "id": "mission_total",
   "name": "Mission item count telemetry",
   "group": 1
  },
  {
   "id": "mission_reached",
   "name": "Mission waypoint reached event",
   "group": 1
  },
  {
   "id": "fence_breach",
   "name": "Reported onboard fence breach",
   "group": 0
  },
  {
   "id": "home_position",
   "name": "Onboard home-position telemetry",
   "group": 10
  },
  {
   "id": "esc_rpm",
   "name": "ESC RPM telemetry presence",
   "group": 11
  },
  {
   "id": "battery_cells",
   "name": "Battery cell-voltage telemetry",
   "group": 4
  },
  {
   "id": "prearm_alert",
   "name": "Reported pre-arm failure",
   "group": 1
  },
  {
   "id": "landed_state",
   "name": "Autopilot landed-state telemetry",
   "group": 1
  },
  {
   "id": "ekf_variance",
   "name": "EKF reported variance telemetry",
   "group": 1
  },
  {
   "id": "asc_event_storage",
   "name": "ASC event-store availability",
   "group": 1
  },
  {
   "id": "vps_cmd_transport",
   "name": "Jetson-to-VPS command transport",
   "group": 2
  },
  {
   "id": "worker_mavlink",
   "name": "MAVLink reader thread liveness",
   "group": 1
  },
  {
   "id": "worker_velocity",
   "name": "Velocity sender thread liveness",
   "group": 1
  },
  {
   "id": "worker_thermal",
   "name": "Thermal monitor thread liveness",
   "group": 4
  },
  {
   "id": "worker_front_capture",
   "name": "Front camera capture thread liveness",
   "group": 5
  },
  {
   "id": "worker_down_capture",
   "name": "Down camera capture thread liveness",
   "group": 5
  },
  {
   "id": "worker_front_rtmp",
   "name": "Front camera RTMP thread liveness",
   "group": 5
  },
  {
   "id": "worker_down_rtmp",
   "name": "Down camera RTMP thread liveness",
   "group": 5
  }
 ],
 "groups": [
  "GPS / NAVIGATION",
  "IMU / FLIGHT",
  "5G LINK",
  "COMPASS",
  "POWER",
  "FRONT CAMERA",
  "RC LOSS",
  "VIBRATION",
  "BACK CAMERA",
  "PARACHUTE",
  "RETURN TO HOME",
  "MOTORS"
 ]
};
