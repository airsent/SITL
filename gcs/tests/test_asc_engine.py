import unittest
from asc.engine import ASCEngine, check_snapshot, CHECKS, GROUPS


def base():
    return {
        'pixhawk_connected':True,'armed':True,'flight_mode':'GUIDED',
        'fix_type':'3D FIX','sats':12,'hdop':0.8,'ekf_healthy':True,
        'voltage':22.1,'battery':67,'rssi':92,'jetson_temp':52.1,
        'cpu':34,'gpu':30,'ram':40,'disk_used_percent':30,
        'rangefinder':1.7,'of_quality':205,'apriltag_detector_available':True,
        'front_cam_active':True,'down_cam_active':True,
        'vps_telem_connected':True,
        'sensor_age_s':{x:0.2 for x in ('heartbeat','attitude','position','gps','ekf','rc','power','rangefinder','of','vib','front_frame','down_frame','depth','velocity_cmd','apriltag','system_stats')},
    }


def byid(snapshot):
    return {x['id']:x for x in check_snapshot(snapshot)}


class EvaluationTests(unittest.TestCase):
    def test_catalog_unique_and_grouped(self):
        self.assertEqual(len(CHECKS),len(set(c[0] for c in CHECKS)))
        self.assertEqual(len(GROUPS),12)
        self.assertTrue(all(0<=c[2]<12 for c in CHECKS))

    def test_all_missing_is_not_green(self):
        result=byid({})
        self.assertNotIn('OK',{result['fc_heartbeat']['status'],result['range_fresh']['status'],result['gps_fresh']['status']})
        self.assertEqual(result['esc_telemetry']['status'],'UNKNOWN')
        self.assertEqual(result['parachute_controller']['status'],'UNKNOWN')

    def test_fresh_real_fields_reported(self):
        result=byid(base())
        self.assertEqual(result['gps_fresh']['status'],'OK')
        self.assertEqual(result['down_frame_fresh']['status'],'OK')
        self.assertEqual(result['command_fresh']['status'],'OK')
        self.assertEqual(result['operator_lease']['status'],'UNKNOWN')
        self.assertEqual(result['esc_telemetry']['status'],'UNKNOWN')

    def test_range_is_independent_of_optical_flow(self):
        s=base();s['sensor_age_s']['of']=6
        result=byid(s)
        self.assertEqual(result['flow_fresh']['status'],'STALE')
        self.assertEqual(result['range_fresh']['status'],'OK')
        self.assertEqual(result['range_valid']['status'],'OK')

    def test_stale_is_not_unknown_or_healthy(self):
        s=base();s['sensor_age_s']['gps']=10;s['sensor_age_s']['down_frame']=7
        r=byid(s)
        self.assertEqual(r['gps_fresh']['status'],'STALE')
        self.assertEqual(r['down_frame_fresh']['status'],'STALE')
        self.assertEqual(r['gps_fix']['status'],'UNKNOWN')

    def test_range_zero_is_not_touchdown(self):
        s=base();s['rangefinder']=0
        self.assertEqual(byid(s)['range_valid']['status'],'UNKNOWN')

    def test_guided_command_expires(self):
        s=base();s['sensor_age_s']['velocity_cmd']=2.2
        self.assertEqual(byid(s)['command_fresh']['status'],'STALE')
        s['flight_mode']='RTL'
        self.assertEqual(byid(s)['command_fresh']['status'],'NOT_APPLICABLE')

    def test_landing_phase_application(self):
        s=base();r=byid(s)
        self.assertEqual(r['apriltag_fresh']['status'],'NOT_APPLICABLE')
        s['flight_mode']='LAND';s['apriltag']={'detected':False}
        r=byid(s)
        self.assertEqual(r['apriltag_target']['status'],'WARNING')
        s['apriltag']={'detected':True}
        self.assertEqual(byid(s)['apriltag_target']['status'],'OK')

    def test_no_false_healthy_on_battery_unavailable(self):
        s=base();s['battery']=-1;s['voltage']=0
        r=byid(s)
        self.assertEqual(r['battery_remaining']['status'],'UNKNOWN')
        self.assertEqual(r['battery_voltage']['status'],'UNKNOWN')

    def test_false_or_missing_ekf(self):
        s=base();s['ekf_healthy']=None
        self.assertEqual(byid(s)['ekf_status']['status'],'UNKNOWN')
        s['ekf_healthy']=False
        self.assertEqual(byid(s)['ekf_status']['status'],'WARNING')

    def test_engine_one_second_tick_and_transitions(self):
        now=[100.0]
        eng=ASCEngine(interval=1.0,clock=lambda:now[0])
        a=eng.tick(base())
        self.assertEqual(a['count'],len(CHECKS))
        self.assertEqual(a['mode'],'MONITOR_ONLY')
        self.assertEqual(len(a['groups']),12)
        self.assertIs(eng.tick({}),a)
        now[0]+=1.1
        b=eng.tick({})
        self.assertEqual(b['sequence'],2)
        self.assertTrue(any(t['id']=='fc_heartbeat' for t in b['recent_transitions']))

    def test_reports_critical_fc_disconnect(self):
        s=base();s['pixhawk_connected']=False;s['sensor_age_s']['heartbeat']=8
        e=ASCEngine().tick(s)
        self.assertTrue(e['counts']['CRITICAL']>=1)
        self.assertEqual(e['groups'][1]['status'],'CRITICAL')


if __name__=='__main__':unittest.main()
