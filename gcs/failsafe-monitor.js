/* Map ASC backend evidence to the EXISTING twelve failsafe cards.
 * Status is diagnostic evidence, not FC failsafe-parameter confirmation.
 */
(()=>{'use strict';
 let frame=null,selected=1;const $=id=>document.getElementById(id);
 const num=v=>typeof v==='number'&&Number.isFinite(v);
 const fresh=()=>frame?.source==='telemetry'&&Number.isFinite(frame.receivedAt)&&
   Date.now()-frame.receivedAt>=0&&Date.now()-frame.receivedAt<=3500&&
   frame.asc?.mode==='MONITOR_ONLY';
 function draw(){
   if(!$('fsSource'))return;
   const age=frame?.receivedAt?Math.max(0,Date.now()-frame.receivedAt):Infinity;
   const ok=fresh(),asc=ok?frame.asc:null;
   const states={OK:'healthy',WARNING:'warning',CRITICAL:'fault',UNKNOWN:'unknown',STALE:'warning',NOT_APPLICABLE:'unknown'};
   for(const tile of document.querySelectorAll('.fs-square-tile')){
     const indicator=tile.querySelector('.fs-status-light');if(!indicator)continue;
     const group=asc?.groups?.find(x=>x.id===Number(tile.dataset.system));
     const status=group?.status||'UNKNOWN';
     indicator.dataset.state=states[status]||'unknown';
     indicator.title=group?`${status} — ASC observation only; failsafe configuration not verified`:'Backend missing/stale — status unknown; not healthy';
     indicator.setAttribute('aria-label',indicator.title);
   }
   $('fsClock').textContent=new Date().toLocaleTimeString('en-GB');
   $('fsUpdated').textContent=frame?.receivedAt?new Date(frame.receivedAt).toLocaleTimeString('en-GB'):'--:--:--';
   const v=ok?frame.values:null;
   let observation='Backend data is missing, stale, or does not verify an onboard response.';
   if(v){
     const ids={12:['range_fresh','range_valid'],13:['jetson_temperature'],14:['flow_fresh','flow_quality'],15:['down_frame_fresh','apriltag_fresh']};
     const cids=ids[selected];
     if(cids)observation=cids.map(id=>asc.checks.find(c=>c.id===id)).filter(Boolean)
        .map(c=>`${c.name}: ${c.status} — ${c.reason}`).join(' | ')||observation;
   }
   $('fsObservation').textContent=observation;
   $('fsSource').textContent=ok?'ASC / LIVE':frame?.source==='demo'?'DEMO':'ASC / STALE';
   $('fsVehicleState').textContent=!ok?'STALE':v.pixhawk_connected===false?'FC OFFLINE':'UNVERIFIED';
   $('fsVehicleState').dataset.severity=!ok?'warning':v.pixhawk_connected===false?'fault':'unknown';
   $('fsVoltage').textContent=v&&num(v.voltage)&&v.voltage>0?v.voltage.toFixed(1)+' V':'—';
   $('fsGps').textContent=v&&typeof v.fix_type==='string'?v.fix_type:'—';
   $('fsAge').textContent=Number.isFinite(age)?(age/1000).toFixed(1)+' s'+(!ok?' · STALE':''):'—';
 }
 addEventListener('airsent-review-selection',e=>{selected=e.detail.id;draw()});
 addEventListener('airsent-review-frame',e=>{frame=e.detail;draw()});
 addEventListener('DOMContentLoaded',()=>{draw();setInterval(draw,500)});
})();
