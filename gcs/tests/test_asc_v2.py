"""ASC v2 evidence, persistence and catalog regression tests (no flight hardware)."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from asc.engine import ASCEngine, CHECKS, GROUPS, check_snapshot
from asc.store import ASCEventStore
ROOT=Path(__file__).parents[1]


def checked(data):
    return {c['id']:c for c in check_snapshot(data)}

class NewMAVLinkEvidenceTests(unittest.TestCase):
    def test_fence_breach_requires_reported_flag_and_age(self):
        s={'sensor_age_s':{'fence':.1},'fence_breached':True}
        result=checked(s)
        self.assertEqual(result['fence_breach']['status'],'CRITICAL')
        self.assertEqual(result['fence_status']['status'],'CRITICAL')
        s['fence_breached']=False
        result=checked(s)
        self.assertEqual(result['fence_breach']['status'],'OK')
        self.assertEqual(result['fence_status']['status'],'UNKNOWN')
        s['sensor_age_s']['fence']=99
        self.assertEqual(checked(s)['fence_breach']['status'],'STALE')

    def test_home_position_does_not_prove_rtl_safety(self):
        s={'home_lat':33.4,'home_lon':-111.9,'sensor_age_s':{'home_position':.2}}
        result=checked(s)
        self.assertEqual(result['home_position']['status'],'OK')
        self.assertEqual(result['rtl_home']['status'],'UNKNOWN')

    def test_esc_presence_does_not_prove_motor_health(self):
        s={'esc_rpm':[950,0,965,971],'sensor_age_s':{'esc':.3}}
        result=checked(s)
        self.assertEqual(result['esc_rpm']['status'],'OK')
        self.assertIn('does not prove',result['esc_telemetry']['reason'])
        s['sensor_age_s']['esc']=9
        self.assertEqual(checked(s)['esc_rpm']['status'],'STALE')

    def test_mission_requires_auto_and_fresh_update(self):
        s={'flight_mode':'AUTO','mission_seq':2,'mission_count':8,'sensor_age_s':{'mission_current':.2,'mission_count':.3}}
        result=checked(s)
        self.assertEqual(result['mission_current']['status'],'OK')
        self.assertEqual(result['mission_total']['status'],'OK')
        self.assertEqual(result['mission_reached']['status'],'UNKNOWN')
        s['flight_mode']='GUIDED'
        self.assertEqual(checked(s)['mission_current']['status'],'NOT_APPLICABLE')

    def test_prearm_alert_is_warning_not_arm_permission(self):
        s={'last_prearm_alert':'PreArm: Compass not calibrated','sensor_age_s':{'prearm_alert':.5}}
        result=checked(s)
        self.assertEqual(result['fc_prearm']['status'],'WARNING')
        s['sensor_age_s']['prearm_alert']=400
        self.assertEqual(checked(s)['fc_prearm']['status'],'UNKNOWN')

    def test_transport_and_workers_dont_claim_operator_presence(self):
        s={'vps_cmd_connected':True,'worker_threads':{'mavlink':True,'velocity':False,'down_capture':False}}
        result=checked(s)
        self.assertEqual(result['vps_cmd_transport']['status'],'OK')
        self.assertEqual(result['operator_lease']['status'],'UNKNOWN')
        self.assertEqual(result['worker_mavlink']['status'],'OK')
        self.assertEqual(result['worker_velocity']['status'],'CRITICAL')
        self.assertEqual(result['worker_down_capture']['status'],'WARNING')

    def test_catalog_includes_every_check(self):
        js=(ROOT/'asc-check-catalog.js').read_text()
        catalog=json.loads(js[js.index('{'):js.rindex('}')+1])
        self.assertEqual(len(catalog['checks']),len(CHECKS))
        self.assertEqual(catalog['groups'],GROUPS)
        self.assertEqual([x['id'] for x in catalog['checks']],[x[0] for x in CHECKS])

class StorageTests(unittest.TestCase):
    def test_sqlite_events_and_one_hz_engine(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'asc.sqlite'
            time=[300.0]
            engine=ASCEngine(interval=1.0, clock=lambda:time[0], sqlite_path=path)
            first=engine.tick({'pixhawk_connected':True})
            self.assertEqual(first['event_storage'],'SQLITE_READY')
            self.assertTrue(path.is_file())
            self.assertEqual(ASCEventStore(path).recent(),[])
            time[0]+=1.1
            second=engine.tick({'pixhawk_connected':False})
            self.assertEqual(second['sequence'],2)
            saved=ASCEventStore(path).recent()
            self.assertTrue(any(row['check_id']=='fc_connection' and row['after']=='CRITICAL' for row in saved))

    def test_store_keeps_bounded_history(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'history.sqlite'
            store=ASCEventStore(path,max_events=100)
            for i in range(106):
                store.write_transitions(i,[{'id':'heartbeat','before':'OK','after':'STALE','reason':'test'}])
            self.assertEqual(len(store.recent(500)),100)

if __name__=='__main__':unittest.main()
