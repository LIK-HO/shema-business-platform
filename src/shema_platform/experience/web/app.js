(()=>{'use strict';
const S={
  token:null,
  surface:new URLSearchParams(location.search).get('surface')==='max'?'max':'web',
  route:location.hash.slice(1)||'request',
  caps:{},
  notes:[],
  selected:null,
  pendingId:'',
  pendingQueue:[],
  online:navigator.onLine,
  evidenceIds:[],
  identityRef:'',
  lastActionId:'',
  ct:'check',
  preferences:{
    requests:{query:'',severity:'ALL',sort:'newest',view:'list'},
    search:{region:'Москва',industries:'',limit:30}
  }
};
const $=(s,r=document)=>r.querySelector(s);
const view=$('#view'),title=$('#title'),surface=$('#surface'),corr=$('#corr'),count=$('#nav-count'),countHeader=$('#nav-count-header');
const MAX_PENDING = 8;
const MAX_PENDING_BYTES=65536;
const MAX_PENDING_ATTEMPTS=3;
const MAX_PENDING_AGE_MS=86400000;

const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key=()=>crypto&&crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random();

function badge(value){
  const x=String(value||'').toLowerCase();
  let cls='neutral';
  if(['accepted','projected','verified','normal','pass','ready','active','sent','completed','online','fresh','match'].includes(x))cls='ok';
  if(['attention','warn','pending','stale','review','offline','unknown','not_checked','unavailable','searching'].includes(x))cls='warn';
  if(['blocking','conflicting','fail','failed','rejected','quarantined_spam','expired','reconciliation_required'].includes(x))cls='bad';
  return '<span class="status '+cls+'">'+esc(value)+'</span>';
}
function stateBadge(value){return badge(String(value||'unknown').toUpperCase())}
function toast(message){
  const node=document.createElement('div');node.className='toast';node.textContent=message;
  $('#toast').appendChild(node);setTimeout(()=>node.remove(),3500);
}
function updateOfflineState(){
  S.online=navigator.onLine;
  document.body.classList.toggle('offline',!S.online);
  const node=$('#network-state');
  if(node)node.innerHTML=badge(S.online?'online':'offline')+(S.pendingQueue.length?' <span class="muted">· ожидает '+S.pendingQueue.length+'</span>':'');
}
function queueMutation(path,opt){
  const headers=Object.assign({},opt.headers||{});
  const auth=Object.keys(headers).find(k=>k.toLowerCase()==='authorization');
  const idem=Object.keys(headers).find(k=>k.toLowerCase()==='idempotency-key');
  const body=typeof opt.body==='string'?opt.body:'';
  if(auth||!idem||path!=='/v1/public/intake'||body.length>MAX_PENDING_BYTES||S.pendingQueue.length>=MAX_PENDING)return null;
  const item={id:key(),path,method:opt.method||'POST',headers,body,createdAt:Date.now(),attempts:0};
  S.pendingQueue.push(item);updateOfflineState();return item;
}
async function api(path,opt={},policy={}){
  const headers=Object.assign({'Accept':'application/json'},opt.headers||{});
  if(S.token)headers.Authorization='Bearer '+S.token;
  const request=Object.assign({},opt,{headers});
  if(policy.queueOffline&&!navigator.onLine){
    const queued=queueMutation(path,request);
    if(queued){const err=new Error('Офлайн: запрос поставлен в ожидающую очередь');err.queued=true;throw err;}
  }
  try{
    const response=await fetch(path,request);
    const correlation=response.headers.get('X-Correlation-Id');if(correlation)corr.textContent='correlation: '+correlation;
    const contentType=response.headers.get('content-type')||'';
    const body=contentType.includes('json')?await response.json():await response.text();
    if(!response.ok){const err=new Error(body&&body.message?body.message:'HTTP '+response.status);err.status=response.status;throw err;}
    return body;
  }catch(err){
    if(policy.queueOffline&&!err.status){
      const queued=queueMutation(path,request);
      if(queued){const retry=new Error('Офлайн: запрос поставлен в ожидающую очередь');retry.queued=true;throw retry;}
    }
    throw err;
  }
}
async function flushPending(){
  if(!navigator.onLine||!S.pendingQueue.length)return;
  const now=Date.now(),next=[];
  for(const item of S.pendingQueue){
    if(now-item.createdAt>MAX_PENDING_AGE_MS||item.attempts>=MAX_PENDING_ATTEMPTS){toast('Ожидающий запрос истёк. Отправьте его заново.');continue;}
    item.attempts+=1;
    try{await api(item.path,{method:item.method,headers:item.headers,body:item.body},{queueOffline:false});toast('Ожидающий запрос доставлен.');}
    catch(err){
      if(err.status===409||err.status===412){toast('Конфликт заявки. Требуется явная повторная отправка.');continue;}
      if(item.attempts<MAX_PENDING_ATTEMPTS)next.push(item);
    }
  }
  S.pendingQueue=next;updateOfflineState();
}
function setSurfaceMode(publicMode){
  document.body.classList.toggle('public-mode',publicMode);
  document.body.classList.toggle('operator-mode',!publicMode);
  if(publicMode){S.token=null;S.caps={};}
}
function setHeader(mode,pageTitle){
  surface.textContent=mode;title.textContent=pageTitle;
  document.querySelectorAll('nav button').forEach(button=>button.classList.toggle('active',button.dataset.route===S.route));
}
async function loadCapabilities(){
  if(!S.token){S.caps={};$('#session').textContent='Гость';$('#notifications').hidden=true;return false;}
  try{
    const response=await api('/v1/operator/capabilities');
    S.caps=response.capabilities||{};
    $('#session').textContent=response.actorId||'Оператор';
    document.querySelectorAll('[data-capability]').forEach(node=>node.classList.toggle('hidden',S.caps[node.dataset.capability]!==true));
    $('#notifications').hidden=!S.caps.notifications;
    return true;
  }catch{
    S.token=null;S.caps={};$('#session').textContent='Нет доступа';return false;
  }
}
async function loadNotifications(){
  if(!S.token||!S.caps.notifications){S.notes=[];count.textContent='0';countHeader.textContent='0';return;}
  try{
    const response=await api('/v1/operator/notifications?limit=50');
    S.notes=response.notifications||[];
    count.textContent=S.notes.length;countHeader.textContent=S.notes.length;
  }catch{S.notes=[];count.textContent='0';countHeader.textContent='0';}
}
function notificationText(note){
  const p=note.payload||{};
  return (p.serviceType||'Новая заявка')+' · '+(p.location||'локация не указана');
}
function selectNote(note){S.selected=note;S.pendingId=String((note.payload||{}).inn||'');}
function noteCard(note){
  const p=note.payload||{};
  return '<article class="item'+(S.selected&&S.selected.eventId===note.eventId?' selected':'')+'">'+
    '<div class="split"><div><div class="eyebrow">'+esc(note.eventType)+'</div><b>'+esc(p.serviceType||'Новая заявка')+'</b><div class="muted">'+esc(p.location||'—')+' · '+esc(p.contactName||'—')+'</div></div>'+badge(note.severity)+'</div>'+
    '<div class="kv"><b>Состояние</b><span>'+stateBadge(p.preflightDecision||note.severity)+'</span></div>'+
    '<div class="toolbar start"><button class="secondary" data-open-note="'+esc(note.eventId)+'">Открыть</button></div>'+
  '</article>';
}
function pub(){
  setSurfaceMode(true);
  setHeader(S.surface==='max'?'MAX MINI-APP / PUBLIC':'PUBLIC / WEB','Заявка на услугу');
  view.innerHTML='<div class="grid">'+
    '<section class="hero"><div class="eyebrow">PUBLIC CLIENT</div><h2>'+(S.surface==='max'?'Заявка из MAX через ту же Web-поверхность':'Услуги грузчиков, такелажа и линейного персонала через единый рабочий контур')+'</h2><p>Сайт и MAX используют тот же canonical API. Публичная форма создаёт только заявку-наблюдение и не создаёт живой заказ напрямую.</p><div class="toolbar start">'+badge('Москва')+' '+badge('server-authoritative')+'</div></section>'+
    '<section class="grid cols3"><div class="card"><div class="eyebrow">НА ОБЪЕКТ</div><h3>Погрузка и разгрузка</h3><p class="muted">Офисы, магазины, мероприятия, объекты и складские задачи.</p></div><div class="card"><div class="eyebrow">СЛОЖНЫЕ РАБОТЫ</div><h3>Такелаж и подъём</h3><p class="muted">Тяжёлые/крупногабаритные грузы и подъём материалов.</p></div><div class="card"><div class="eyebrow">РЕСУРС</div><h3>Линейный персонал</h3><p class="muted">Разнорабочие и рабочие смены под конкретную потребность.</p></div></section>'+
    '<section class="card"><div class="eyebrow">REQUEST INTAKE</div><h2>Запрос</h2><form id="pf" class="form cols"><label>Услуга<input name="serviceType" required maxlength="120"></label><label>Локация<input name="location" required maxlength="240"></label><label>Дата / период<input name="preferredDateOrPeriod" required maxlength="120"></label><label>Контактное лицо<input name="contactName" required maxlength="200"></label><label class="full">Описание<textarea name="workOrCargoDescription" required maxlength="4000"></textarea></label><label>Контакт<input name="contactChannel" required maxlength="240"></label><label>Объём / вес<input name="approximateVolumeOrWeight" maxlength="500"></label><label>Ограничения по доступу<input name="accessOrLiftingConstraints" maxlength="1000"></label><label>Компания<input name="companyName" maxlength="300"></label><label>ИНН<input name="inn" maxlength="12"></label><label>ОГРН / ОГРНИП<input name="ogrnOrOgrnip" maxlength="15"></label><label class="full">Комментарий<textarea name="comments" maxlength="2000"></textarea></label><input type="hidden" name="entrySurface" value="'+(S.surface==='max'?'max_mini_app':'public_web')+'"><div class="full muted">UTM/referrer/correlation/requestId сохраняются сервером. Текст клиента — untrusted data.</div><div class="full actions"><button class="primary">Отправить запрос</button></div></form><div id="pres"></div></section>'+
  '</div>';
  $('#pf').onsubmit=submitPublic;
}
async function submitPublic(event){
  event.preventDefault();const form=event.currentTarget,node=$('#pres');
  const data=Object.fromEntries(new FormData(form).entries()),params=new URLSearchParams(location.search);
  data.utmSource=params.get('utm_source');data.utmMedium=params.get('utm_medium');data.utmCampaign=params.get('utm_campaign');data.referrer=document.referrer||null;
  const headers={'Content-Type':'application/json','Idempotency-Key':key(),'Origin':location.origin};
  if(window.SHEMA_BOT_CHALLENGE_TOKEN)headers['X-Bot-Challenge']=window.SHEMA_BOT_CHALLENGE_TOKEN;
  try{
    const response=await api('/v1/public/intake',{method:'POST',headers,body:JSON.stringify(data)},{queueOffline:true});
    node.innerHTML='<div class="success"><b>Запрос принят.</b><div class="kv"><b>requestId</b><span>'+esc(response.requestId)+'</span></div><div class="kv"><b>correlation</b><span>'+esc(response.correlationId)+'</span></div><div>'+badge(response.status)+' · '+badge(response.preflightDecision)+'</div><div class="muted">Источник: '+esc(data.entrySurface)+' · '+esc(data.utmSource||'direct')+'</div></div>';
    form.reset();
  }catch(err){
    node.innerHTML='<div class="'+(err.queued?'success':'error')+'">'+(err.queued?'<b>Нет связи.</b> Запрос поставлен в ожидающую очередь и повторится после восстановления сети с тем же Idempotency-Key.':('Запрос не принят: '+esc(err.message)))+'</div>';
  }
}
function requireOperator(){
  if(S.token)return true;
  view.innerHTML='<div class="card empty">Нужна аутентификация оператора.</div>';openAuth();return false;
}
function renderWorkSummary(){
  const note=S.selected;
  if(!note)return '<div class="empty">Выберите заявку из очереди, чтобы открыть полный причинно-следственный контекст.</div>';
  const p=note.payload||{};
  return '<div class="details-grid"><section class="card"><div class="eyebrow">КРАТКО</div><h2>'+esc(p.serviceType||'Заявка')+'</h2><div class="kv"><b>Локация</b><span>'+esc(p.location||'—')+'</span></div><div class="kv"><b>Дата / период</b><span>'+esc(p.preferredDateOrPeriod||'—')+'</span></div><div class="kv"><b>Контакт</b><span>'+esc(p.contactName||'—')+' · '+esc(p.contactChannel||'—')+'</span></div><div class="kv"><b>Описание</b><span>'+esc(p.workOrCargoDescription||'—')+'</span></div></section><aside class="card sticky-card"><div class="eyebrow">СОСТОЯНИЕ</div><div class="kv"><b>Preflight</b><span>'+badge(p.preflightDecision||'unknown')+'</span></div><div class="kv"><b>Identity</b><span>'+badge(p.identityMatch||'not_checked')+'</span></div><div class="kv"><b>Источник</b><span>'+esc(p.entrySurface||'—')+'</span></div><div class="kv"><b>UTM</b><span>'+esc([p.utmSource,p.utmMedium,p.utmCampaign].filter(Boolean).join(' / ')||'direct')+'</span></div><div class="kv"><b>Correlation</b><code>'+esc(note.correlationId||'—')+'</code></div></aside></div>';
}
function workbench(){
  setHeader('OPERATOR / WORKBENCH','Рабочий стол');
  view.innerHTML='<section class="grid">'+
    '<div class="grid cols3"><div class="card"><div class="eyebrow">ВХОДЯЩИЕ</div><div class="kpi">'+S.notes.length+'</div><div class="muted">уведомлений из server queue</div></div><div class="card"><div class="eyebrow">КОНТРАГЕНТ</div><div class="kpi">'+(S.selected?'Выбран':'Поиск')+'</div><div class="muted">identity → evidence</div></div><div class="card"><div class="eyebrow">КОММУНИКАЦИЯ</div><div class="kpi">'+(S.lastActionId?'Подготовлена':'Не подготовлена')+'</div><div class="muted">action → outcome</div></div></div>'+
    '<div class="card"><div class="split"><div><div class="eyebrow">TODAY QUEUE</div><h2>Рабочая очередь</h2></div><div class="segmented"><button class="active" disabled>Список</button><button disabled>Kanban</button></div></div><div class="list">'+(S.notes.slice(0,10).map(noteCard).join('')||'<div class="empty">Очередь пуста.</div>')+'</div></div>'+
    '<div class="card"><div class="eyebrow">CONTEXT</div>'+renderWorkSummary()+'</div>'+
  '</section>';
  bindNoteButtons();
}
function requests(){
  setHeader('OPERATOR / REQUESTS','Новые заявки');
  const pref=S.preferences.requests;
  let items=S.notes.filter(note=>{const q=pref.query.trim().toLowerCase();const p=note.payload||{};const text=(note.eventType+' '+notificationText(note)).toLowerCase();return (!q||text.includes(q))&&(pref.severity==='ALL'||note.severity===pref.severity);});
  items.sort((a,b)=>pref.sort==='oldest'?String(a.createdAt).localeCompare(String(b.createdAt)):String(b.createdAt).localeCompare(String(a.createdAt)));
  view.innerHTML='<section class="card"><div class="split"><div><div class="eyebrow">INBOX</div><h2>Новые заявки</h2><div class="muted">Серверное состояние; личные фильтры действуют только в памяти страницы.</div></div><div class="toolbar"><button class="ghost" id="notif-open">Уведомления</button><button class="primary" id="requests-refresh">Обновить</button></div></div><div class="toolbar start" style="margin-top:14px"><label style="min-width:240px">Фильтр<input id="rq" value="'+esc(pref.query)+'" placeholder="услуга, компания, локация"></label><label style="min-width:180px">Состояние<select id="rsev"><option>ALL</option><option>LOW</option><option>INFO</option><option>ATTENTION</option><option>HIGH</option><option>CRITICAL</option></select></label><label style="min-width:160px">Сортировка<select id="rsort"><option value="newest">Новые</option><option value="oldest">Старые</option></select></label></div><div id="request-list" class="list" style="margin-top:14px">'+(items.map(noteCard).join('')||'<div class="empty">Подходящих заявок нет.</div>')+'</div></section>';
  $('#rsev').value=pref.severity;$('#rsort').value=pref.sort;
  $('#rq').oninput=e=>{pref.query=e.target.value;renderRequestsList(items)};$('#rsev').onchange=e=>{pref.severity=e.target.value;requests();};$('#rsort').onchange=e=>{pref.sort=e.target.value;requests();};
  $('#requests-refresh').onclick=async()=>{await loadNotifications();requests();};$('#notif-open').onclick=showNotifications;bindNoteButtons();
}
function renderRequestsList(){requests();}
function bindNoteButtons(){
  view.querySelectorAll('[data-open-note]').forEach(button=>button.onclick=()=>{
    const note=S.notes.find(item=>item.eventId===button.dataset.openNote);if(note)selectNote(note);
    location.hash='dossier';
  });
}
function clients(){
  setHeader('OPERATOR / CLIENTS','Клиенты');
  view.innerHTML='<section class="grid cols2"><div class="card"><div class="eyebrow">CLIENT CONTEXT</div><h2>Контекст клиента</h2><p class="muted">Здесь не создаётся отдельное хранилище клиентов. Контекст собирается из canonical request, identity/evidence и связанных действий.</p>'+(S.selected?'<div class="kv"><b>Заявка</b><span>'+esc(S.selected.requestId||S.selected.eventId)+'</span></div><div class="kv"><b>Компания</b><span>'+esc((S.selected.payload||{}).companyName||'—')+'</span></div><div class="kv"><b>ИНН</b><span>'+esc((S.selected.payload||{}).inn||'—')+'</span></div><div class="toolbar start"><button class="primary" id="client-dossier">Открыть карточку</button></div>':'<div class="empty">Выберите заявку или выполните поиск, чтобы открыть клиентский контекст.</div>')+'</div><div class="card"><div class="eyebrow">WORK QUEUE</div><h2>Быстрые переходы</h2><div class="related"><button class="secondary" data-go="requests">Новые заявки</button><button class="secondary" data-go="search">Поиск клиентов</button><button class="secondary" data-go="counterparties">Контрагенты</button></div><div class="callout">Verified client status не создаётся UI самостоятельно: серверный контекст остаётся единственным источником.</div></div></section>';
  if(S.selected)$('#client-dossier').onclick=()=>location.hash='dossier';
  view.querySelectorAll('[data-go]').forEach(button=>button.onclick=()=>location.hash=button.dataset.go);
}
function globalIdentifier(query){
  const value=query.trim();
  if(!/^\d{10,15}$/.test(value))return null;
  if(value.length<=12)return {type:'INN',value};
  return {type:value.length===13?'OGRN':'OGRNIP',value};
}
function searchView(prefill=''){
  setHeader('OPERATOR / SEARCH','Поиск');
  const pref=S.preferences.search;
  const initialQuery=prefill||pref.query;
  view.innerHTML='<section class="grid cols2"><div class="card"><div class="eyebrow">CANONICAL SEARCH</div><h2>Поиск клиентов и контрагентов</h2><p class="muted">Точное значение ИНН/ОГРН/ОГРНИП переключает этот же поиск в режим проверки контрагента. AI до детерминированной проверки не вызывается.</p><form id="sf" class="form"><label>Запрос / идентификатор<input name="query" value="'+esc(initialQuery)+'" placeholder="ИНН, ОГРН, компания, услуга"></label><label>Регион<input name="region" value="'+esc(pref.region)+'"></label><label>Отрасли<input name="industries" value="'+esc(pref.industries)+'" placeholder="офисы, мероприятия, небольшие склады"></label><label>Лимит<input name="limit" type="number" min="1" max="500" value="'+esc(pref.limit)+'"></label><div class="actions"><button class="primary">Искать</button></div></form><div class="callout">NOT_SEARCHED ≠ NOT_FOUND · SOURCE_UNAVAILABLE ≠ CHANGED · BUDGET_LIMITED остаётся видимым.</div></div><div class="card"><div class="eyebrow">RESULTS</div><div id="sr" class="empty">Запустите поиск.</div></div></section>';
  $('#sf').onsubmit=doSearch;
}
async function doSearch(event){
  event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget).entries()),output=$('#sr');
  const exact=globalIdentifier(String(data.query||''));
  if(exact){S.pendingId=exact.value;S.ct='check';S.pendingIdentifierType=exact.type;location.hash='counterparties';return;}
  const pref=S.preferences.search;pref.region=data.region;pref.industries=data.industries;pref.limit=Number(data.limit);
  output.innerHTML='<div class="muted">Ищем…</div>';
  try{
    const response=await api('/v1/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({region:data.region,industries:String(data.industries).split(',').map(x=>x.trim()).filter(Boolean),limit:Number(data.limit),selectionLevel:'candidate'})});
    const attempts=(response.sourceAttempts||[]).map(item=>'<div class="item"><div class="split"><b>'+esc(item.sourceId)+'</b>'+stateBadge(item.status)+'</div><div class="muted">'+esc(item.sourceClass)+' · '+esc(item.errorCode||'')+'</div></div>').join('');
    output.innerHTML='<div class="toolbar start">'+stateBadge(response.completeness)+' '+badge(response.planVersion)+'</div>'+
      ((response.results||[]).map(item=>'<article class="item"><div class="split"><b>'+esc(item.name)+'</b>'+badge(item.selectionLevel)+'</div><div class="kv"><b>ИНН</b><span>'+esc(item.taxId||'—')+'</span></div><div class="kv"><b>Источник</b><code>'+esc(item.sourceRef||'—')+'</code></div><div class="toolbar start"><button class="secondary result-check" data-id="'+esc(item.taxId||'')+'">Проверить контрагента</button></div></article>').join('')||'<div class="empty">Результатов нет. '+esc(response.completeness)+'</div>')+
      (attempts?'<details style="margin-top:12px"><summary>Источники и полнота</summary><div class="list" style="margin-top:8px">'+attempts+'</div></details>':'');
    output.querySelectorAll('.result-check').forEach(button=>button.onclick=()=>{S.pendingId=button.dataset.id;S.pendingIdentifierType='INN';location.hash='counterparties';});
  }catch(err){output.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
function counterparties(){
  setHeader('OPERATOR / COUNTERPARTY','Контрагенты');
  view.innerHTML='<section class="card"><div class="split"><div><div class="eyebrow">COUNTERPARTY WORKSPACE</div><h2>Контрагенты</h2><div class="muted">Проверка, мониторинг и избранные — отдельные режимы.</div></div><div class="segmented"><button data-tab="check">Проверка</button><button data-tab="monitor">Мониторинг</button><button data-tab="favorites">Избранные</button></div></div><div id="cp" style="margin-top:16px"></div></section>';
  view.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{S.ct=button.dataset.tab;counterparties();});
  renderCp(S.ct||'check');
}
async function renderCp(tab){
  const node=$('#cp');
  view.querySelectorAll('[data-tab]').forEach(button=>button.classList.toggle('active',button.dataset.tab===tab));
  if(tab==='check'){
    node.innerHTML='<form id="cf" class="form cols"><label>Тип<select name="identifierType"><option>INN</option><option>OGRN</option><option>OGRNIP</option></select></label><label>Идентификатор<input name="identifier" required value="'+esc(S.pendingId)+'"></label><div class="full actions"><button class="primary">Проверить</button></div></form><div id="cr"></div>';
    if(S.pendingIdentifierType)$('#cf [name="identifierType"]').value=S.pendingIdentifierType;
    $('#cf').onsubmit=doCheck;return;
  }
  if(!S.caps.counterpartyWorkspace){node.innerHTML='<div class="empty">Workspace не скомпонован сервером.</div>';return;}
  try{
    const response=await api(tab==='monitor'?'/v1/intelligence/counterparties/monitoring':'/v1/intelligence/counterparties/favorites');
    const items=tab==='monitor'?(response.monitors||[]):(response.favorites||[]);
    node.innerHTML=items.length?'<div class="table"><table><thead><tr><th>Идентификатор</th><th>Состояние</th><th>Дата</th></tr></thead><tbody>'+items.map(item=>'<tr><td>'+esc(item.identifier)+'<div class="muted">'+esc(item.identifierType)+'</div></td><td>'+badge(item.status)+'</td><td>'+esc(item.nextCheckAt||item.createdAt||'—')+'</td></tr>').join('')+'</tbody></table></div>':'<div class="empty">Список пуст.</div>';
  }catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
async function doCheck(event){
  event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget).entries()),node=$('#cr');
  node.innerHTML='<div class="muted">Проверяем authoritative source…</div>';
  try{
    const response=await api('/v1/intelligence/counterparty-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    S.pendingId='';S.pendingIdentifierType=null;S.identityRef=response.identityRef||response.subjectRef;S.evidenceIds=response.evidenceIds||[];
    node.innerHTML='<div class="details-grid"><section class="card"><div class="eyebrow">КРАТКО</div><h3>'+esc(response.identityRef||response.subjectRef)+'</h3><p>'+esc(response.operatorBrief||'—')+'</p><div class="toolbar start">'+badge(response.freshness)+' '+badge(response.identityState||'unknown')+'</div></section><section class="card"><div class="eyebrow">ОСНОВАНИЯ</div><code>'+esc((response.evidenceIds||[]).join('\n'))+'</code>'+(response.contradictions&&response.contradictions.length?'<div class="error"><b>Противоречия</b></div>':'')+'</section></div>';
  }catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
function research(){
  setHeader('OPERATOR / RESEARCH','Разведка');
  const seed=S.identityRef||S.pendingId||((S.selected||{}).payload||{}).inn||'';
  view.innerHTML='<section class="grid cols2"><div class="card"><div class="eyebrow">EVIDENCE WORKSPACE</div><h2>Глубокая разведка</h2><p class="muted">Сначала детерминированная идентичность, затем выбранная глубина исследования.</p><form id="research-form" class="form"><label>SubjectRef<input name="subjectRef" value="'+esc(seed)+'" required></label><label>Тип компании<input name="companyType" value="organization" required></label><label>Глубина<select name="depth"><option>R1_IDENTITY</option><option selected>R2_CONTEXT</option><option>R3_DEEP</option><option>R4_INVESTIGATIVE</option></select></label><label>Запрос<textarea name="query" required>Проверить актуальный открытый контекст, связи и источники по контрагенту.</textarea></label><div class="actions"><button class="primary">Получить evidence</button></div></form><div class="callout">AI не подменяет реестр: вывод строится вокруг evidence/provenance.</div></div><div class="card"><div class="eyebrow">EVIDENCE</div><div id="research-result" class="empty">Пока нет результатов.</div></div></section>';
  $('#research-form').onsubmit=submitResearch;
}
async function submitResearch(event){
  event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget).entries()),node=$('#research-result')||$('#rr');
  node.innerHTML='<div class="muted">Запрашиваем evidence…</div>';
  try{
    const response=await api('/v1/intelligence/research',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    S.evidenceIds=(response.evidence||[]).map(item=>item.evidenceId);
    node.innerHTML=(response.evidence||[]).map(item=>'<article class="item"><div class="split"><b>'+esc(item.claim)+'</b>'+badge(item.trustLevel)+'</div><div class="muted">'+esc(item.sourceRef)+' · confidence '+esc(item.confidence)+'</div><code>'+esc(item.evidenceId)+'</code></article>').join('')||'<div class="empty">Evidence не возвращены.</div>';
  }catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
function dossier(){
  setHeader('OPERATOR / DOSSIER','Контекст заявки');
  if(!S.selected)return workbench();
  const note=S.selected,p=note.payload||{};
  view.innerHTML='<section class="details-grid"><div class="grid"><section class="card"><div class="eyebrow">КРАТКО</div><h2>'+esc(p.serviceType||'Заявка')+'</h2><div class="kv"><b>requestId</b><code>'+esc(note.requestId||'—')+'</code></div><div class="kv"><b>Локация</b><span>'+esc(p.location||'—')+'</span></div><div class="kv"><b>Контакт</b><span>'+esc(p.contactName||'—')+' · '+esc(p.contactChannel||'—')+'</span></div><div class="kv"><b>Описание</b><span>'+esc(p.workOrCargoDescription||'—')+'</span></div></section><section class="card"><div class="eyebrow">ОСНОВАНИЯ</div><div class="kv"><b>Preflight</b><span>'+badge(p.preflightDecision||'unknown')+'</span></div><div class="kv"><b>Identity</b><span>'+badge(p.identityMatch||'not_checked')+'</span></div><div class="kv"><b>Источник</b><span>'+esc(p.entrySurface||'—')+'</span></div><div class="kv"><b>Referrer</b><span>'+esc(p.referrer||'—')+'</span></div><div class="kv"><b>UTM</b><span>'+esc([p.utmSource,p.utmMedium,p.utmCampaign].filter(Boolean).join(' / ')||'direct')+'</span></div><div class="kv"><b>Correlation</b><code>'+esc(note.correlationId||'—')+'</code></div><div class="callout">Raw intake не является trusted instruction.</div></section><section class="card"><div class="eyebrow">ACTIVITY / HISTORY</div><div class="notice"><div class="split"><b>Заявка поступила</b>'+badge(note.severity)+'</div><div class="muted">'+esc(note.createdAt||'—')+'</div><div>'+esc(note.eventType||'—')+'</div></div></section><section class="card"><div class="eyebrow">RELATED</div><div class="related"><button class="secondary" id="related-client">Клиент</button><button class="secondary" id="related-cp">Контрагент</button><button class="secondary" id="related-research">Разведка</button></div></section></div><aside class="card sticky-card"><div class="eyebrow">NEXT ACTION</div><div class="toolbar start"><button class="primary" id="to-workbench">Рабочая карточка</button><button class="secondary" id="to-search">Поиск</button><button class="secondary" id="to-counterparty">Проверить контрагента</button><button class="ghost" id="to-handoff">Передача</button></div></aside></section>';
  $('#related-client').onclick=()=>location.hash='clients';$('#related-cp').onclick=()=>location.hash='counterparties';$('#related-research').onclick=()=>location.hash='research';$('#to-workbench').onclick=()=>location.hash='workbench';$('#to-search').onclick=()=>location.hash='search';$('#to-counterparty').onclick=()=>{S.pendingId=p.inn||'';S.pendingIdentifierType=p.inn?'INN':null;location.hash='counterparties';};$('#to-handoff').onclick=()=>location.hash='handoffs';
}
function actionResult(){
  const actionId=S.lastActionId||'';
  return actionId?'<div class="success">Canonical action: <code>'+esc(actionId)+'</code></div>':'<div class="empty">Action ещё не создан.</div>';
}
function workbenchDetail(){
  if(!S.selected)return;
  // kept as a named transition point for old deep links; execution lives in the same canonical workbench.
}
function fullWorkbench(){
  setHeader('OPERATOR / WORKBENCH','Рабочая карточка');
  if(!S.selected){return workbench();}
  const p=S.selected.payload||{},seed=S.identityRef||p.inn||S.selected.requestId||'';
  view.innerHTML='<section class="grid cols2"><section class="card"><div class="eyebrow">EVIDENCE</div><h2>Разведка</h2><form id="rf" class="form"><label>SubjectRef<input name="subjectRef" value="'+esc(seed)+'" required></label><label>Тип компании<input name="companyType" value="organization" required></label><label>Глубина<select name="depth"><option>R1_IDENTITY</option><option>R2_CONTEXT</option><option>R3_DEEP</option><option>R4_INVESTIGATIVE</option></select></label><label>Запрос<textarea name="query" required>Проверить контекст, связи и актуальные открытые источники по контрагенту.</textarea></label><div class="actions"><button class="primary">Получить evidence</button></div></form><div id="rr"></div></section><section class="card"><div class="eyebrow">QUALIFICATION</div><h2>Квалификация</h2><form id="qf" class="form"><label>CandidateRef<input name="candidateRef" value="'+esc(seed)+'" required></label><label><span><input name="serviceFit" type="checkbox" checked> Соответствует услуге</span></label><label><span><input name="economicFit" type="checkbox"> Экономическая пригодность подтверждена</span></label><div class="actions"><button class="primary">Оценить</button></div></form><div id="qr"></div></section><section class="card"><div class="eyebrow">CONTACT PREPARATION</div><h2>Подготовка контакта</h2><form id="af" class="form"><label>Identity ID<input name="identityId" value="'+esc(S.identityRef||'')+'" required></label><label>ContactRef<input name="contactRef" value="'+esc(p.contactChannel||'')+'" required></label><label>Канал<input name="channel" value="telegram" required></label><label>Evidence IDs<input name="evidenceRefs" value="'+esc((S.evidenceIds||[]).join(', '))+'" required></label><div class="actions"><button class="primary">Создать action</button></div></form><div id="ar">'+actionResult()+'</div><div id="sendbox"></div></section><section class="card"><div class="eyebrow">RESULT</div><h2>Заказ и экономика</h2><form id="of" class="form"><label>Action ID<input name="actionId" value="'+esc(S.lastActionId)+'" required></label><label>Описание строки<input name="description" value="'+esc(p.serviceType||'Услуга')+'" required></label><label>Количество<input name="quantity" value="1" required></label><label>Цена<input name="amount" placeholder="0" required></label><label>Валюта<input name="currency" value="RUB" maxlength="3" required></label><div class="actions"><button class="primary">Создать order draft</button></div></form><div id="or"></div><form id="ef" class="form"><label>EntityRef<input name="entityRef" value="'+esc(S.identityRef||seed)+'" required></label><div class="actions"><button class="ghost">Загрузить economics</button></div></form><div id="er"></div></section></section>';
  $('#rf').onsubmit=submitResearchWorkbench;$('#qf').onsubmit=submitQualification;$('#af').onsubmit=submitAction;$('#of').onsubmit=submitOrder;$('#ef').onsubmit=loadEconomics;
}
async function submitResearchWorkbench(event){
  event.preventDefault();
  const data=Object.fromEntries(new FormData(event.currentTarget).entries()),node=$('#rr');
  node.innerHTML='<div class="muted">Запрашиваем evidence…</div>';
  try{
    const response=await api('/v1/intelligence/research',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(data)});
    S.evidenceIds=(response.evidence||[]).map(item=>item.evidenceId);
    node.innerHTML=(response.evidence||[]).map(item=>'<article class="item"><div class="split"><b>'+esc(item.claim)+'</b>'+badge(item.trustLevel)+'</div><div class="muted">'+esc(item.sourceRef)+' · confidence '+esc(item.confidence)+'</div><code>'+esc(item.evidenceId)+'</code></article>').join('')||'<div class="empty">Evidence не возвращены.</div>';
  }catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
async function submitQualification(event){
  event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget).entries()),node=$('#qr');node.innerHTML='<div class="muted">Проверяем…</div>';
  try{const response=await api('/v1/discovery/evaluate',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify({candidateRef:data.candidateRef,serviceFit:data.serviceFit==='on',economicFit:data.economicFit==='on'})});node.innerHTML='<div class="callout">'+badge(response.qualification)+'<div>'+esc((response.reasons||[]).join(' · '))+'</div></div>';}catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
async function submitAction(event){
  event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget).entries()),refs=String(data.evidenceRefs).split(',').map(x=>x.trim()).filter(Boolean),node=$('#ar');
  if(!refs.length){node.innerHTML='<div class="error">Нужен минимум один evidenceRef.</div>';return;}
  try{const response=await api('/v1/commercial-actions',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify({identityId:data.identityId,contactRef:data.contactRef,channel:data.channel,evidenceRefs:refs})});S.lastActionId=response.actionId;node.innerHTML='<div class="success">action '+esc(response.actionId)+' · '+badge(response.status)+'</div>';showSendBox();}catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
function showSendBox(){
  const node=$('#sendbox');if(!node)return;node.innerHTML='<form id="sendf" class="form"><label>Сообщение<textarea name="body" required>Добрый день! Уточняю возможность выполнения работ по заявке.</textarea></label><div class="actions"><button class="secondary">Отправить через canonical action API</button></div></form>';$('#sendf').onsubmit=sendAction;
}
async function sendAction(event){
  event.preventDefault();const body=new FormData(event.currentTarget).get('body'),node=$('#sendbox');
  if(!S.lastActionId){node.innerHTML='<div class="error">Сначала создайте action.</div>';return;}
  try{const response=await api('/v1/commercial-actions/'+encodeURIComponent(S.lastActionId)+'/send',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify({body})});node.innerHTML='<div class="success">Коммуникация: '+esc(response.externalMessageId||response.actionId)+' · accepted='+esc(response.accepted)+'</div>';}catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
async function submitOrder(event){
  event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget).entries()),node=$('#or');const line={lineId:'web-line-'+Date.now(),description:data.description,quantity:data.quantity,unitPrice:{amount:data.amount,currency:String(data.currency).toUpperCase()}};
  try{const response=await api('/v1/orders',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify({actionId:data.actionId,lines:[line]})});node.innerHTML='<div class="success">order '+esc(response.orderId)+' · '+badge(response.status)+'</div>';$('#ef [name="entityRef"]').value=response.identityId||$('#ef [name="entityRef"]').value;}catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
async function loadEconomics(event){
  event.preventDefault();const ref=new FormData(event.currentTarget).get('entityRef'),node=$('#er');node.innerHTML='<div class="muted">Загружаем economics…</div>';
  try{const response=await api('/v1/economics/'+encodeURIComponent(ref));node.innerHTML=(response.entries||[]).map(item=>'<div class="kv"><b>'+esc(item.label||item.kind)+'</b><span>'+esc(item.amount&&item.amount.amount||'—')+' '+esc(item.amount&&item.amount.currency||'')+'</span></div>').join('')||'<div class="empty">Данных нет.</div>';}catch(err){node.innerHTML='<div class="error">'+esc(err.message)+'</div>';}
}
function handoffs(){
  setHeader('OPERATOR / HANDOFF','Передача');
  const note=S.selected,p=note?note.payload||{}:{};
  view.innerHTML='<section class="grid cols2"><div class="card"><div class="eyebrow">BUSINESS PLANE HANDOFF</div><h2>Подготовка передачи</h2><p class="muted">Phase 6 не создаёт второй live business plane. Реальная запись в Bitrix24 будет разрешена только через отдельный provider/integration boundary.</p><div class="kv"><b>Состояние</b><span>'+badge('PREPARED')+'</span></div><div class="kv"><b>Identity</b><span>'+esc(S.identityRef||p.inn||'не определена')+'</span></div><div class="kv"><b>Request</b><span>'+esc(note&&note.requestId||'—')+'</span></div><div class="callout">Execution endpoint не скомпонован в текущем runtime: UI не имитирует ACK, externalEntityRef или успешную передачу.</div></div><div class="card"><div class="eyebrow">RECONCILIATION</div><h2>Безопасность передачи</h2><div class="list"><div class="item">'+stateBadge('ACKNOWLEDGED')+' Только после подтверждения внешней системы.</div><div class="item">'+stateBadge('SENT_UNKNOWN')+' Не повторять запись вслепую; сначала reconciliation.</div><div class="item">'+stateBadge('RECONCILIATION_REQUIRED')+' Несовпадение — ручная сверка, без purge.</div><div class="item">'+stateBadge('HANDOFF_FAILED')+' История Shema сохраняется.</div></div><div class="toolbar start"><button class="secondary" id="handoff-back">Назад к карточке</button></div></div></section>';
  $('#handoff-back').onclick=()=>location.hash='dossier';
}
const REPEAT_ORDER_API='/v1/operator/repeat-orders';
function repeat(){
  setHeader('OPERATOR / CONTINUITY','Повторные заказы');
  if(!S.caps.repeatOrders){view.innerHTML='<div class="card"><div class="eyebrow">REPEAT ORDERS & BUSINESS CONTINUITY</div><h2>Контур подготовлен, но не активирован</h2><div class="callout">Сервер не рекламирует <code>repeatOrders</code>, поэтому UI не создаёт фиктивные планы. Для активации требуется реальный server-side revalidator.</div></div>';return;}
  view.innerHTML='<div class="card"><div class="eyebrow">PLAN</div><h2>Повторные заказы</h2><p class="muted">Операции делегированы существующему RepeatOrderService и защищены Idempotency-Key.</p><div class="callout">Список текущих планов не добавляется без canonical read endpoint: UI не создаёт локальную копию бизнес-состояния.</div></div>';
}
function system(){return control();}
function control(){
  setHeader('OPERATOR / CONTROL PLANE','Контроль');
  view.innerHTML='<section class="grid cols2"><div class="card"><div class="eyebrow">READINESS</div><h2>Готовность</h2><div id="health" class="muted">Проверяем…</div></div><div class="card"><div class="eyebrow">DIAGNOSTICS</div><h2>Диагностика</h2><div id="diag" class="muted">Проверяем…</div></div></section>';
  fetch('/health/ready').then(response=>response.json()).then(data=>$('#health').innerHTML=badge(data.ready?'READY':'BLOCKING')).catch(()=>$('#health').textContent='health unavailable');
  if(!S.caps.diagnostics){$('#diag').textContent='Не разрешено или не скомпоновано';return;}
  api('/v1/diagnostics').then(data=>$('#diag').innerHTML=(data.checks||[]).map(item=>'<div class="kv"><b>'+esc(item.checkId)+'</b><span>'+badge(item.status)+' '+esc(item.message||'')+'</span></div>').join('')).catch(err=>$('#diag').innerHTML='<div class="error">'+esc(err.message)+'</div>');
}
function showNotifications(){
  if(!S.caps.notifications)return;
  let dialog=document.querySelector('#notification-dialog');
  if(!dialog){dialog=document.createElement('dialog');dialog.id='notification-dialog';document.body.appendChild(dialog);}
  dialog.innerHTML='<form method="dialog"><div class="split"><div><div class="eyebrow">NOTIFICATION CENTER</div><h2>Уведомления</h2></div><button class="ghost">Закрыть</button></div><div class="notification-center">'+(S.notes.length?S.notes.map(item=>'<div class="notice"><div class="split"><b>'+esc(notificationText(item))+'</b>'+badge(item.severity)+'</div><div class="muted">'+esc(item.createdAt||'—')+' · '+esc(item.requestId||'')+'</div><button class="secondary notice-open" data-id="'+esc(item.eventId)+'">Открыть</button></div>').join(''):'<div class="empty">Новых уведомлений нет.</div>')+'</div></form>';
  dialog.querySelectorAll('.notice-open').forEach(button=>button.onclick=()=>{const note=S.notes.find(item=>item.eventId===button.dataset.id);if(note)selectNote(note);dialog.close();location.hash='dossier';});
  dialog.showModal();
}
function openAuth(){$('#auth-error').classList.add('hidden');$('#token').value='';$('#auth').showModal();}
async function handleAuth(event){
  event.preventDefault();S.token=$('#token').value.trim();const ok=await loadCapabilities();
  if(!ok||!S.token){S.token=null;$('#auth-error').textContent='Сервер не подтвердил сессию';$('#auth-error').classList.remove('hidden');return;}
  $('#auth').close();await loadNotifications();if(!location.hash)location.hash='requests';await route();
}
async function route(){
  S.route=location.hash.slice(1)||'request';
  if(S.route==='request')return pub();
  setSurfaceMode(false);
  document.querySelectorAll('nav button').forEach(button=>button.classList.toggle('active',button.dataset.route===S.route));
  if(!requireOperator())return;
  await loadCapabilities();await loadNotifications();
  if(S.route==='workbench')return workbench();
  if(S.route==='clients')return clients();
  if(S.route==='requests')return requests();
  if(S.route==='search')return searchView();
  if(S.route==='counterparties')return counterparties();
  if(S.route==='research')return research();
  if(S.route==='repeat')return repeat();
  if(S.route==='handoffs')return handoffs();
  if(S.route==='control'||S.route==='system')return system();
  if(S.route==='dossier')return dossier();
  if(S.route==='operator')return fullWorkbench();
  return workbench();
}
document.querySelectorAll('nav button').forEach(button=>button.onclick=()=>{if(!S.token)return openAuth();location.hash=button.dataset.route;});
$('#login').onclick=openAuth;$('#auth-form').onsubmit=handleAuth;$('#refresh').onclick=route;$('#notifications').onclick=showNotifications;$('#global-search').onsubmit=event=>{event.preventDefault();const query=$('#global-query').value.trim();const exact=globalIdentifier(query);if(exact){S.pendingId=exact.value;S.pendingIdentifierType=exact.type;location.hash='counterparties';}else{S.preferences.search.query=query;location.hash='search';}};
$('#menu-toggle')?.addEventListener('click',()=>document.querySelector('.side')?.classList.toggle('menu-open'));
window.addEventListener('hashchange',route);
window.addEventListener('online',()=>{updateOfflineState();flushPending();});
window.addEventListener('offline',()=>{updateOfflineState();toast('Соединение потеряно. Доступна безопасная офлайн-очередь публичных заявок.');});
function registerPwa(){
  if(!('serviceWorker' in navigator))return;
  navigator.serviceWorker.register('/sw.js',{scope:'/'}).then(reg=>{
    reg.addEventListener('updatefound',()=>{
      const worker=reg.installing;if(!worker)return;
      worker.addEventListener('statechange',()=>{
        if(worker.state==='installed'&&navigator.serviceWorker.controller){
          const node=document.createElement('div');node.className='update-banner';node.innerHTML='<span>Доступно обновление.</span><button class="primary">Обновить</button>';
          node.querySelector('button').onclick=()=>{worker.postMessage({type:'SKIP_WAITING'});node.remove();};
          document.body.appendChild(node);
        }
      });
    });
  }).catch(()=>{});
}
registerPwa();updateOfflineState();route();
})();