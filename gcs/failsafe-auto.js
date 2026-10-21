/* ASC v2: concise existing top bar + complete component dropdown.
 * Read-only console; monitoring continues on Jetson when this display is OFF.
 */
(()=>{'use strict';
 const byId=id=>document.getElementById(id);
 const button=byId('fsAutoToggle'), summary=byId('fsAutoSummary'), details=byId('fsAscDetails');
 const open=byId('fsAscOpen'), close=byId('fsAscClose'), list=byId('fsAscCheckList');
 const filter=byId('fsAscFilter'),group=byId('fsAscGroup'),search=byId('fsAscSearch');
 const count=byId('fsFaultCount'),catalog=window.AirsentASCCheckCatalog||{checks:[],groups:[]};
 let enabled=false,frame=null,wasArmed=false,lastRenderKey='';
 const isFresh=()=>frame?.source==='telemetry'&&Number.isFinite(frame.receivedAt)&&
    Date.now()-frame.receivedAt>=0&&Date.now()-frame.receivedAt<=3500&&
    frame.asc?.version===1&&frame.asc?.mode==='MONITOR_ONLY';
 const asc=()=>isFresh()?frame.asc:null;
 function setEnabled(v){enabled=Boolean(v);button.setAttribute('aria-checked',String(enabled));button.textContent=enabled?'ON':'OFF';draw()}
 function setOpen(v){details.hidden=!v;open.setAttribute('aria-expanded',String(v));open.classList.toggle('fs-asc-open-active',v);if(v)renderChecks()}
 function make(t,cls,text){const n=document.createElement(t);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
 function renderChecks(){
   const a=asc(),rows=(a?.checks?.length?a.checks:catalog.checks.map(c=>({...c,status:'UNKNOWN',reason:'Live telemetry unavailable'})));
   const chosenGroup=group.value,chosenStatus=filter.value,q=search.value.trim().toLowerCase();
   const filtered=rows.filter(c=>(chosenGroup==='all'||String(c.group)===chosenGroup)&&
     (chosenStatus==='all'||c.status===chosenStatus)&&(!q||`${c.name} ${c.id} ${c.reason||''}`.toLowerCase().includes(q)))
     .sort((a,b)=>Number(a.group)-Number(b.group)||a.name.localeCompare(b.name));
   byId('fsAscTotal').textContent=`${rows.length}`;
   byId('fsAscConnection').textContent=a?'LIVE · 1 SECOND CYCLE':'NO FRESH BACKEND DATA · ALL UNVERIFIED';
   list.replaceChildren();
   if(!filtered.length){list.append(make('p','fs-asc-empty','No checks match these filters.'));return}
   let lastGroup=null;
   for(const c of filtered){
     if(c.group!==lastGroup){lastGroup=c.group;list.append(make('div','fs-asc-group-label',catalog.groups[c.group]||'OTHER SYSTEMS'))}
     const row=make('div','fs-asc-check-row');
     const state=make('b','fs-asc-state',c.status||'UNKNOWN');state.dataset.status=c.status||'UNKNOWN';
     const title=make('span','fs-asc-check-name',c.name);
     const why=make('small','fs-asc-check-reason',c.reason||'No verified data received');
     row.append(state,title,why);list.append(row);
   }
 }
 function draw(){
   const a=asc(),n=a?.counts||{},faults=n.CRITICAL||0;
   count.textContent=a?String(faults):'—';
   count.title='Critical ASC observations; not configured aircraft failsafe actions';
   count.parentElement.classList.toggle('fs-multiple-faults',Boolean(a)&&faults>1);
   const bar=document.querySelector('.fs-auto-bar');
   bar.classList.toggle('fs-asc-on',enabled);bar.classList.toggle('fs-asc-emergency',enabled&&faults>0);
   summary.dataset.fault=String(enabled&&faults>0);
   summary.textContent=!enabled?'12 SYSTEM CHECKS · OFF'
     :!a?'ASC · NO LIVE DATA'
     :`${a.count} CHECKS · ${n.WARNING||0} WARNINGS · ${(n.UNKNOWN||0)+(n.STALE||0)} UNVERIFIED`;
   for(const card of document.querySelectorAll('.fs-square-tile')){
      const status=enabled&&a?.groups?.find(g=>g.id===Number(card.dataset.system))?.status;
      card.classList.toggle('fs-monitor-on',enabled);
      card.classList.toggle('fs-emergency',status==='CRITICAL');
      card.classList.toggle('fs-card-caution',status==='WARNING'||status==='STALE');
   }
   if(!details.hidden){
     const key=[a?.sequence??'none',Boolean(a),group.value,filter.value,search.value].join('|');
     if(key!==lastRenderKey){lastRenderKey=key;renderChecks()}
   }
 }
 for(let i=0;i<catalog.groups.length;i++)group.add(new Option(catalog.groups[i],String(i)));
 button.addEventListener('click',()=>{
    const toggle=()=>setEnabled(!enabled);
    if(window.AirsentASCLock?.request)window.AirsentASCLock.request(toggle);else toggle();
 });
 open.addEventListener('click',()=>setOpen(details.hidden));
 close.addEventListener('click',()=>setOpen(false));
 filter.addEventListener('change',()=>{lastRenderKey='';renderChecks()});
 group.addEventListener('change',()=>{lastRenderKey='';renderChecks()});
 search.addEventListener('input',()=>{lastRenderKey='';renderChecks()});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!details.hidden)setOpen(false)});
 document.addEventListener('pointerdown',e=>{if(!details.hidden&&!details.contains(e.target)&&!open.contains(e.target))setOpen(false)});
 addEventListener('airsent-review-frame',event=>{
   frame=event.detail;
   const armed=isFresh()&&frame.values?.armed===true;
   if(armed&&!wasArmed)setEnabled(true);
   wasArmed=armed;
   draw();
 });
 setInterval(draw,1000);draw();
})();
