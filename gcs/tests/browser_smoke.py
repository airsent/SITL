"""Optional mock-only DOM smoke test. Requires playwright and local Chromium."""
from pathlib import Path
from asc.engine import ASCEngine
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

ROOT=Path(__file__).parents[1]

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1440,'height':900})
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        soup=BeautifulSoup((ROOT/'failsafe.html').read_text(),'html.parser')
        for tag in soup.find_all(['script','link']):tag.decompose()
        page.set_content(str(soup),wait_until='domcontentloaded')
        page.add_style_tag(content=(ROOT/'failsafe.css').read_text())
        for name in ('failsafe-data.js','failsafe.js','failsafe-planning.js',
                     'console-select.js','asc-lock.js','asc-check-catalog.js','failsafe-monitor.js','failsafe-auto.js'):
            page.add_script_tag(content=(ROOT/name).read_text())
        snap={'pixhawk_connected':True,'armed':True,'flight_mode':'GUIDED','battery':60,'voltage':22.3,
              'fix_type':'3D FIX'}
        snap['asc']=ASCEngine().tick({'pixhawk_connected':True,'armed':True,'flight_mode':'GUIDED',
             'sensor_age_s':{'heartbeat':0.2,'gps':0.2}})
        page.evaluate("""(d)=>window.dispatchEvent(new CustomEvent('airsent-review-frame',{
            detail:{source:'telemetry',receivedAt:Date.now()-100,sourceAgeS:0.1,values:d,asc:d.asc}
        }))""",snap)
        assert 'CHECKS' in page.locator('#fsAutoSummary').inner_text(),page.locator('#fsAutoSummary').inner_text()
        assert page.locator('#fsAutoToggle').inner_text()=='ON'
        page.locator('#fsAscOpen').click()
        assert page.locator('.fs-asc-check-row').count()==len(snap['asc']['checks'])
        page.screenshot(path=str(ROOT.parent/'AirSent_ASC_Browser_Preview.png'),full_page=True)
        page.evaluate("""()=>window.dispatchEvent(new CustomEvent('airsent-review-frame',{
            detail:{source:'telemetry',receivedAt:Date.now()-9000,sourceAgeS:9,values:{},asc:null}
        }))""")
        assert 'NO LIVE DATA' in page.locator('#fsAutoSummary').inner_text()
        page.locator('#fsAscSearch').fill('ESC')
        assert page.locator('.fs-asc-check-row').count()>=1
        assert not errors,errors
        print('PASS: existing failsafe page; complete check dropdown; stale UI; no JS errors')
        browser.close()

if __name__=='__main__':main()
