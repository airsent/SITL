"""Static regression tests: no Jetson/hardware dependencies required."""
import unittest
from pathlib import Path
P=Path(__file__).parents[1]

class IntegrationTests(unittest.TestCase):
    def test_same_html_page(self):
        page=(P/'failsafe.html').read_text()
        self.assertIn('id="fsAutoToggle"',page)
        self.assertIn('id="fsFaultCount"',page)
        self.assertIn('id="fsAscDetails"',page)
        self.assertIn('id="fsGroups"',page)
        self.assertIn('console-config.js',page)

    def test_stale_relay_source_age(self):
        server=(P/'telemetry_server.py').read_text()
        bridge=(P/'failsafe-bridge.js').read_text()
        self.assertIn('telemetry_age',server)
        self.assertIn('sourceAge*1000',bridge)
        self.assertIn("new WebSocket(wsUrl())",bridge)

    def test_no_independent_mavlink_reader_in_asc(self):
        src=(P/'asc'/'engine.py').read_text()
        self.assertNotIn('import pymavlink',src)
        self.assertNotIn('set_position_target',src)
        self.assertIn('asc_engine.tick(payload)',(P/'airsent_server.py').read_text())

    def test_no_fake_zero_range_when_flow_fails(self):
        src=(P/'airsent_server.py').read_text()
        self.assertNotIn('or of_offline)',src)
        self.assertIn("payload['rangefinder'] = None",src)

if __name__=='__main__':unittest.main()
