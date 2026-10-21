/* ASC direct telemetry bridge — existing failsafe.html, no dashboard tab required.
 * Read-only. No command socket is opened by this module.
 * 'receivedAt' is backdated with VPS source age, NOT browser arrival time.
 */
(()=>{'use strict';
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('airsent-failsafe-trial-v1'):null;
 // SITL: on localhost read the local sim server directly (same seam as dashboard/pilot).
 const _LOCAL_DEV = location.hostname==='localhost' || location.hostname==='127.0.0.1';
 const wsUrl=()=>_LOCAL_DEV ? `ws://${location.hostname}:8765`
   :typeof window.airsentApiUrl==='function'
   ?window.airsentApiUrl('/telem',true)
   :(location.protocol==='https:'?'wss://':'ws://')+location.host+'/telem';
 let latest=null,socket=null,retry=null,stopped=false,everConnected=false;
 function emit(frame){latest=frame;window.dispatchEvent(new CustomEvent('airsent-review-frame',{detail:frame}));}
 function fromWire(data){
   if(!data||typeof data!=='object'||Array.isArray(data))return;
   // VPS continues rebroadcasting the last received Jetson message after disconnect.
   // telemetry_age measures original source freshness; never reset it on receipt.
   const sourceAge=typeof data.telemetry_age==='number'&&Number.isFinite(data.telemetry_age)
     ?Math.max(0,data.telemetry_age)
     // SITL: read straight from the local server (no relay), so receipt time is source time.
     :(_LOCAL_DEV?0:null);
   const recv=Date.now();
   const age=sourceAge===null?null:sourceAge*1000;
   const frame={type:'review-frame',version:2,source:'telemetry',
     receivedAt:age===null?0:recv-age,sourceAgeS:sourceAge,
     values:data,asc:data.asc&&typeof data.asc==='object'?data.asc:null};
   emit(frame);
 }
 function connect(){
   if(stopped)return;
   try{
     socket=new WebSocket(wsUrl());
     socket.onopen=()=>{everConnected=true;};
     socket.onmessage=event=>{
       try{fromWire(JSON.parse(event.data))}catch(e){console.warn('ASC invalid telemetry frame',e)}
     };
     socket.onclose=()=>{if(!stopped){emit({...latest,type:'review-frame',version:2,source:'telemetry',receivedAt:0,sourceAgeS:null,asc:null,values:{}});retry=setTimeout(connect,3000)}};
     socket.onerror=()=>socket.close();
   }catch(e){console.warn('ASC telemetry socket',e);retry=setTimeout(connect,3000)}
 }
 // Legacy compatibility for dashboard sharing/demo. Real live telemetry always
 // comes from /telem directly on the failsafe page, not another browser tab.
 function publish(data,source){
   if(!data||typeof data!=='object'||!['demo','telemetry'].includes(source))return;
   if(source==='telemetry')return; // direct source is authoritative
   const frame={type:'review-frame',version:2,source:'demo',receivedAt:Date.now(),
     sourceAgeS:0,values:data,asc:null};
   channel?.postMessage(frame);
 }
 if(channel)channel.onmessage=e=>{
   const m=e.data;
   if(m?.type==='request-review-frame'){if(latest)channel.postMessage(latest);return}
   if(m?.type==='review-frame'&&m.source==='demo'&&!everConnected&&
       Number.isFinite(m.receivedAt)&&Date.now()-m.receivedAt<4000)emit(m);
 };
 window.AirsentReviewBridge={publish,request:()=>channel?.postMessage({type:'request-review-frame'})};
 addEventListener('pagehide',()=>{stopped=true;clearTimeout(retry);socket?.close();channel?.close()},{once:true});
 connect();
})();
