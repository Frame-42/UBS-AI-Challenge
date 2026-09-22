// Local collector-triage UI. All risk calculations belong to risk_framework.
const icons = {
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  'chevron-left': '<path d="m15 6-6 6 6 6"/>',
  'chevron-right': '<path d="m9 6 6 6-6 6"/>',
  'arrow-right': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  'arrow-up-right': '<path d="M6 18 18 6M6 6h12v12"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  sliders: '<path d="M4 7h7m4 0h5M4 17h3m4 0h9"/><circle cx="13" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  sort: '<path d="M8 4v16m-3-3 3 3 3-3M16 20V4m-3 3 3-3 3 3"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
};
function icon(name) { return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.info}</svg>`; }
function hydrateIcons(root = document) { root.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); }); }
const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {cybersecurity:'Cyber',reputational:'Reputation',fraud:'Fraud',financial:'Financial',sanctions:'Sanctions'};
let vendors=[], riskDimensions=[], defaultWeights={}, payload=null;
const state={query:'',category:'all',region:'all',risk:'all',page:1,sort:'desc',sortKey:'weighted',weights:{},live:true,selected:null};
const pageSize=8;
const refreshIntervalMs=30000;
const weightDebounceMs=120;
const weightId=key=>"weight-"+encodeURIComponent(key);
const sourceId=key=>"source-"+encodeURIComponent(key);
const scoreText=value=>Number.isFinite(value)?Number(value.toFixed(1)).toString():'—';
const percent=value=>`${Number((value*100).toFixed(1))}%`;
const dateText=value=>value?new Date(value).toLocaleString('en-GB',{timeZone:'UTC',dateStyle:'medium',timeStyle:'short'})+' UTC':'Unavailable';
const weightedScore=v=>v.overall.score;
const subscore=(v,key)=>v.categories[key]?.score??null;
const tone=level=>['HIGH','CRITICAL'].includes(level)?'high':['MODERATE','GUARDED'].includes(level)?'moderate':level==='LOW'?'low':'unavailable';
const riskName=level=>level?level.charAt(0)+level.slice(1).toLowerCase():'Unscored';
function badge(level){return `<span class="status-badge ${tone(level)}"><i class="dot ${tone(level)}"></i>${escapeHTML(riskName(level))}</span>`;}
function sourceLink(source){
  let url;try{url=new URL(source.url);}catch{return escapeHTML(source.name||'Source');}
  if(!['https:','http:'].includes(url.protocol))return escapeHTML(source.name||'Source');
  return `<a href="${escapeHTML(url.href)}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.name||url.hostname)} ${icon('arrow-up-right')}</a>`;
}
function citation(source){return `<div class="citation">${sourceLink(source)}<small>${escapeHTML(source.publisher||'')} · Retrieved ${dateText(source.retrieved_at)}${source.published_at?' · Published '+dateText(source.published_at):''}${source.accessed_via?' · Via '+escapeHTML(source.accessed_via):''}${source.license?' · '+escapeHTML(source.license):''}</small></div>`;}
// Weight controls rebalance display preferences; the server normalizes scoring weights.
function renderWeights(){
  riskDimensions.forEach(d=>{
    const input=document.getElementById(weightId(d.key)),number=document.getElementById(weightId(d.key)+"-number");
    input.value=state.weights[d.key];input.style.setProperty('--range-progress',input.value+'%');
    input.setAttribute('aria-valuetext',`${input.value}% of requested weight`);
    if(number!==document.activeElement)number.value=state.weights[d.key];
  });
  const custom=riskDimensions.some(d=>state.weights[d.key]!==defaultWeights[d.key]);
  $('#weights-custom').hidden=!custom;$('#weights-button').classList.toggle('is-custom',custom);
  $('#weight-formula').textContent='Weights are renormalized over categories with scores. Unavailable categories reduce coverage.';
}
function rebalanceWeights(key,value){
  if(riskDimensions.length===1){state.weights[key]=100;return;}
  const units=Math.max(0,Math.min(1000,Math.round(value*10))),remaining=1000-units;
  const others=riskDimensions.map(d=>d.key).filter(k=>k!==key);
  const total=others.reduce((s,k)=>s+state.weights[k],0);
  let used=0;
  others.forEach((k,i)=>{const next=i===others.length-1?remaining-used:Math.min(remaining-used,Math.round(remaining*(total?state.weights[k]/total:1/others.length)));state.weights[k]=next/10;used+=next;});
  state.weights[key]=units/10;
}
let weightTimer;
function updateWeights(){renderWeights();state.page=1;setPending(true);clearTimeout(weightTimer);weightTimer=setTimeout(()=>loadDashboard(),weightDebounceMs);positionWeights();}
function setupControls(){
  riskDimensions=Object.keys(payload.scoreboard.normalized_weights).map(key=>({key,label:labels[key]||key}));
  defaultWeights={...payload.dashboard.default_weights};
  const total=Object.values(defaultWeights).reduce((s,v)=>s+v,0);
  let used=0;riskDimensions.forEach((d,i)=>{const units=i===riskDimensions.length-1?1000-used:Math.min(1000-used,Math.round((defaultWeights[d.key]||0)/total*1000));defaultWeights[d.key]=units/10;used+=units;});
  state.weights={...defaultWeights};
  $('#weight-controls').innerHTML=riskDimensions.map(d=>`<div class="weight-control"><div class="weight-label-row"><label for="${weightId(d.key)}">${escapeHTML(d.label)}</label><span class="weight-number-wrap"><input type="number" id="${weightId(d.key)}-number" data-weight-number="${escapeHTML(d.key)}" min="0" max="100" step="0.1" inputmode="decimal" aria-label="${escapeHTML(d.label)} weight, percent"><span>%</span></span></div><input type="range" id="${weightId(d.key)}" data-weight="${escapeHTML(d.key)}" min="0" max="100" step="0.1"></div>`).join('');
  $('#table-head').innerHTML=`<tr><th scope="col" class="vendor-column">Vendor</th><th scope="col"><button data-sort="weighted">Weighted score${icon('sort')}</button></th>${riskDimensions.map(d=>`<th scope="col"><button data-sort="${escapeHTML(d.key)}">${escapeHTML(d.label)}${icon('sort')}</button></th>`).join('')}<th scope="col">Status</th></tr>`;
  $('#risk-tabs').innerHTML=[['all','All vendors'],...payload.scoreboard.config.risk_levels.map(r=>[r.label,riskName(r.label)]),['unscored','Unscored']].map(([key,label])=>`<button data-risk="${escapeHTML(key)}">${escapeHTML(label)} <span>0</span></button>`).join('');
  $('#weights-button').disabled=false;renderWeights();
}
// Render server-provided scores and original evidence; never calculate risk in the browser.
function renderMetrics(){
  const scored=vendors.filter(v=>weightedScore(v)!==null);
  const average=scored.length?scored.reduce((sum,v)=>sum+weightedScore(v),0)/scored.length:null;
  const cards=[['Monitored vendors',vendors.length,`${scored.length} scored · ${vendors.length-scored.length} unscored`],['Elevated risk',vendors.filter(v=>tone(v.overall.risk_level)==='high').length,'High & critical'],['Average weighted score',scoreText(average),'Scored vendors only'],['Collected findings',vendors.reduce((s,v)=>s+(v.evidence.report?.signals.length||0),0),'Latest saved reports']];
  $('#metrics').innerHTML=cards.map(([label,value,foot])=>`<div class="metric-card"><div class="metric-label">${label}</div><div class="metric-reading"><div class="metric-number">${value}</div><div class="metric-bottom">${foot}</div></div></div>`).join('');
}
function riskMatches(v,risk){return risk==='all'||(risk==='unscored'?v.overall.score===null:v.overall.risk_level===risk);}
function filteredVendors(){
  const result=vendors.filter(v=>`${v.name} ${(v.evidence.company.aliases||[]).join(' ')} ${v.country} ${v.evidence.company.domain||''}`.toLowerCase().includes(state.query.toLowerCase())&&(state.category==='all'||(state.category==='scored')===(weightedScore(v)!==null))&&(state.region==='all'||v.country===state.region)&&riskMatches(v,state.risk));
  const value=v=>state.sortKey==='weighted'?weightedScore(v):subscore(v,state.sortKey);
  return result.sort((a,b)=>{const x=value(a),y=value(b);return x===null?(y===null?a.id.localeCompare(b.id):1):y===null?-1:(state.sort==='desc'?y-x:x-y)||a.id.localeCompare(b.id);});
}
function renderTable(){
  const result=filteredVendors(),pages=Math.max(1,Math.ceil(result.length/pageSize));state.page=Math.min(state.page,pages);const offset=(state.page-1)*pageSize;
  $('#vendor-total').textContent=vendors.length;
  document.querySelectorAll('[data-risk]').forEach(b=>{b.classList.toggle('active',b.dataset.risk===state.risk);b.setAttribute('aria-pressed',String(b.dataset.risk===state.risk));b.querySelector('span').textContent=vendors.filter(v=>riskMatches(v,b.dataset.risk)).length;});
  document.querySelectorAll('[data-sort]').forEach(b=>b.closest('th').setAttribute('aria-sort',b.dataset.sort===state.sortKey?(state.sort==='desc'?'descending':'ascending'):'none'));
  $('#vendor-rows').innerHTML=result.length?result.slice(offset,offset+pageSize).map(v=>`<tr data-vendor-row="${escapeHTML(v.id)}"><td><button class="vendor-cell" data-open="${escapeHTML(v.id)}"><span class="vendor-logo">${escapeHTML(v.name.slice(0,2).toUpperCase())}</span><span><strong>${escapeHTML(v.name)}</strong><small>${escapeHTML(v.evidence.company.domain||v.country||'Country unavailable')}</small></span></button></td><td><div class="score-cell risk-${tone(v.overall.risk_level)}"><span class="score-track" aria-hidden="true"><i style="width:${weightedScore(v)??0}%"></i></span><span class="score-value">${scoreText(weightedScore(v))}</span></div><small class="coverage">${percent(v.overall.coverage)} coverage</small></td>${riskDimensions.map(d=>`<td><button class="table-subscore risk-${tone(v.categories[d.key].risk_level)}" data-vendor-source="${escapeHTML(v.id)}" data-dimension="${escapeHTML(d.key)}" aria-label="${escapeHTML(v.name)} ${escapeHTML(d.label)} ${scoreText(subscore(v,d.key))}. View evidence."><span class="subscore-track" aria-hidden="true"><i style="width:${subscore(v,d.key)??0}%"></i></span><span class="subscore-value">${scoreText(subscore(v,d.key))}</span>${icon('arrow-up-right')}</button></td>`).join('')}<td>${badge(v.overall.risk_level)}</td></tr>`).join(''):`<tr><td colspan="${riskDimensions.length+3}"><div class="empty-state"><strong>No vendors found</strong><p>Adjust the search or filters.</p><button class="text-button" id="empty-reset">Clear filters</button></div></td></tr>`;
  $('#table-count').textContent=result.length?`Showing ${offset+1}–${Math.min(offset+pageSize,result.length)} of ${result.length} vendors`:'0 vendors';$('#page-label').textContent=`${state.page} / ${pages}`;$('#prev-page').disabled=state.page===1;$('#next-page').disabled=state.page===pages;
}
function sourceMarkup(v){return riskDimensions.map(d=>{
  const findings=(v.evidence.report?.signals||[]).filter(s=>s.category===d.key);
  return `<details class="source-record" id="${sourceId(d.key)}"><summary><span class="source-heading"><span><span class="source-category">${escapeHTML(d.label)}</span><strong>${findings.length} sourced findings</strong></span>${icon('chevron-down')}</span></summary><div class="source-excerpt">${findings.length?findings.map(s=>`<article class="finding"><strong>${escapeHTML(s.title)}</strong><small>${escapeHTML(s.severity)} · ${escapeHTML(s.collector)}${s.observed_at?' · Observed '+escapeHTML(s.observed_at):''}</small><p>${escapeHTML(s.summary)}</p>${s.sources.map(citation).join('')}</article>`).join(''):'<p>No sourced findings in the latest report. No score is assigned.</p>'}</div></details>`;
}).join('');}
function renderDetail(){
  const v=vendors.find(v=>v.id===state.selected);if(!v)return;
  const report=v.evidence.report,findings=report?.signals||[],overall=v.overall;
  $('#vendor-detail').innerHTML=`<div class="detail-topbar"><span>VENDOR ASSESSMENT</span><button class="icon-button" id="close-detail" aria-label="Close vendor assessment">${icon('x')}</button></div><div class="detail-body"><div class="detail-identity"><div><h2 id="detail-name">${escapeHTML(v.name)}</h2><p>${escapeHTML(v.evidence.company.domain||'')}</p></div></div><div class="detail-meta">${escapeHTML(v.country||'Country unavailable')}</div><div class="evidence-meta"><span>${findings.length} sourced findings</span><span>Collected ${dateText(v.evidence.generated_at)}</span></div><section class="detail-score-card"><div class="detail-score-top"><span>Weighted risk score</span>${badge(overall.risk_level)}</div><div class="detail-score-main"><div class="detail-score-number risk-${tone(overall.risk_level)}">${scoreText(overall.score)}<small>/ 100</small></div><div class="detail-score-trend">${percent(overall.coverage)}<small>weighted coverage</small></div></div></section><p class="detail-summary">${overall.score===null?'No eligible scores under the current weights.':`Score based on ${Object.keys(overall.effective_weights).map(k=>escapeHTML(labels[k]||k)).join(', ')}. Available weights are renormalized.`} ${overall.missing_categories.length?'Missing: '+overall.missing_categories.map(k=>escapeHTML(labels[k]||k)).join(', ')+'.':''}</p><section class="detail-section"><h3>Risk dimensions</h3><div class="subscore-grid">${riskDimensions.map(d=>`<div class="subscore-card"><div class="subscore-label">${escapeHTML(d.label)}</div><div class="subscore-number risk-${tone(v.categories[d.key].risk_level)}">${scoreText(subscore(v,d.key))}<small>/ 100</small></div><small>Effective weight ${percent(overall.effective_weights[d.key]||0)}</small><button class="source-jump" data-source="${escapeHTML(d.key)}">View evidence ${icon('arrow-right')}</button></div>`).join('')}</div></section><section class="detail-section"><h3>Collected summary</h3><p class="detail-summary">${(report?.summary||[]).map(s=>`${escapeHTML(labels[s.category]||s.category)}: ${s.signals} finding${s.signals===1?'':'s'}, highest severity ${escapeHTML(s.max_severity)}.`).join(' ')||'No findings in the latest collection.'}</p></section><section class="detail-section"><h3>Sources & evidence</h3>${sourceMarkup(v)}</section><section class="detail-section"><h3>Collection checks</h3>${(report?.errors||[]).map(e=>`<p class="collection-error">${escapeHTML(e)}</p>`).join('')}<details class="source-record"><summary>Sources consulted · ${report?.sources_consulted.length||0}</summary><div class="source-excerpt">${(report?.sources_consulted||[]).map(c=>`<article class="finding"><strong>${escapeHTML(c.status)}</strong><p>${escapeHTML(c.detail||'')}</p>${citation(c.source)}</article>`).join('')||'<p>No source checks available.</p>'}</div></details><p class="subscore-note">${v.evidence.notes.map(escapeHTML).join(' ')}</p></section><div class="detail-footer">Collector scores support triage and analyst review. Report: ${escapeHTML(v.evidence.report_file||'Unavailable')}</div></div>`;
}
function refreshDetail(){
  if(!$('#vendor-dialog').open)return;
  if(!vendors.some(v=>v.id===state.selected)){$('#vendor-dialog').close();return;}
  const openIds=[...$('#vendor-detail').querySelectorAll('details[open][id]')].map(el=>el.id),scroll=$('#vendor-dialog').scrollTop,focused=document.activeElement;
  const focusId=focused.id,sourceKey=focused.dataset?.source;
  renderDetail();openIds.forEach(id=>{const el=document.getElementById(id);if(el)el.open=true;});$('#vendor-dialog').scrollTop=scroll;
  if(focusId)document.getElementById(focusId)?.focus({preventScroll:true});else if(sourceKey)document.querySelector(`[data-source="${CSS.escape(sourceKey)}"]`)?.focus({preventScroll:true});
}
let lastTrigger=null;
function openVendor(id,trigger){closeWeights(false);state.selected=id;lastTrigger=trigger||document.activeElement;renderDetail();if(!$('#vendor-dialog').open)$('#vendor-dialog').showModal();document.body.style.overflow='hidden';$('#vendor-dialog').scrollTop=0;$('#close-detail').focus();}
let toastTimer;
function toast(message){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').classList.add('visible');toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3500);}
function clearFilters(){state.query='';state.category='all';state.region='all';state.risk='all';state.page=1;$('#vendor-search').value='';$('#category-filter').value='all';$('#region-filter').value='all';renderTable();}
// Abort superseded requests and preserve the last valid view on refresh failure.
let requestId=0,controller,pending=false;
function setPending(value){pending=value;$('#export-button').disabled=value||!payload;$('#portfolio-content').setAttribute('aria-busy',String(value));}
async function loadDashboard(useDefaults=false){
  const id=++requestId;controller?.abort();controller=new AbortController();setPending(true);
  const requested=payload&&!useDefaults?{...state.weights}:null;
  try{
    const query=requested?'?weights='+encodeURIComponent(JSON.stringify(requested)):'';
    const response=await fetch('/api/dashboard'+query,{cache:'no-store',signal:controller.signal});
    const next=await response.json();
    // Removed/renamed categories can invalidate previously selected weights.
    if(response.status===400&&requested&&id===requestId){await loadDashboard(true);return;}
    if(!response.ok)throw new Error(next.error||'Unable to read collection');
    if(id!==requestId||requested&&JSON.stringify(requested)!==JSON.stringify(state.weights))return;
    if(next.score_basis!=='collector_heuristic')throw new Error('Unsupported assessment basis');
    const controlsChanged=useDefaults||!payload||JSON.stringify([
      Object.keys(payload.scoreboard.normalized_weights),payload.dashboard.default_weights,payload.scoreboard.config.risk_levels
    ])!==JSON.stringify([
      Object.keys(next.scoreboard.normalized_weights),next.dashboard.default_weights,next.scoreboard.config.risk_levels
    ]);
    payload=next;
    if(controlsChanged){
      setupControls();state.risk='all';state.sortKey='weighted';state.page=1;
      // Fetch the reset weights before rendering; controls and displayed scores must agree.
      if(requested){await loadDashboard();return;}
    }
    vendors=payload.scoreboard.records.map(v=>({...v,id:v.entity_id,name:v.entity_name,evidence:payload.evidence[v.entity_id],country:payload.evidence[v.entity_id].company.country||''}));
    const countries=[...new Set(vendors.map(v=>v.country).filter(Boolean))].sort();
    if(state.region!=='all'&&!countries.includes(state.region))state.region='all';
    $('#region-filter').innerHTML='<option value="all">All countries</option>'+countries.map(c=>`<option>${escapeHTML(c)}</option>`).join('');$('#region-filter').value=state.region;
    const focused=document.activeElement,focusKey=focused.dataset?.vendorSource,dimension=focused.dataset?.dimension,openKey=focused.dataset?.open;
    renderMetrics();renderTable();refreshDetail();
    if(!focused.isConnected){const selector=focusKey?`[data-vendor-source="${CSS.escape(focusKey)}"][data-dimension="${CSS.escape(dimension)}"]`:openKey?`[data-open="${CSS.escape(openKey)}"]`:null;if(selector)document.querySelector(selector)?.focus({preventScroll:true});}
    $('#data-status').hidden=true;
    const latest=vendors.map(v=>v.evidence.generated_at).filter(Boolean).sort((a,b)=>Date.parse(a)-Date.parse(b)).at(-1);
    $('#last-updated').textContent=`Latest collection ${dateText(latest)} · Checked ${new Date().toLocaleTimeString('en-GB')}`;
    setPending(false);
  }catch(error){if(error.name==='AbortError'||id!==requestId)return;$('#data-status').hidden=false;$('#data-status').textContent=(payload?'Refresh failed. Showing the last successful snapshot. ':'Unable to load vendor data. ')+error.message;setPending(false);$('#export-button').disabled=true;}
}
// Export all filtered rows, using the last successful response's weights.
function exportCSV(){
  if(pending||!payload)return;const list=filteredVendors(),weights=payload.scoreboard.normalized_weights;
  const rows=[['Vendor','Country','Score basis','Weighted score','Risk level','Coverage',...riskDimensions.map(d=>d.label+' score'),...riskDimensions.map(d=>d.label+' requested weight (%)'),'Collected at','Report file'],...list.map(v=>[v.name,v.country,payload.score_basis,weightedScore(v)??'',v.overall.risk_level||'Unscored',v.overall.coverage,...riskDimensions.map(d=>subscore(v,d.key)??''),...riskDimensions.map(d=>weights[d.key]*100),v.evidence.generated_at||'',v.evidence.report_file||''])];
  const csv=rows.map(row=>row.map(cell=>{let value=String(cell);if(/^[=+@-]/.test(value))value="'"+value;return '"'+value.replace(/"/g,'""')+'"';}).join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8;'}));const link=document.createElement('a');link.href=url;link.download=`vendor-risk-${new Date().toISOString().slice(0,10)}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast(`Exported ${list.length} vendors`);
}
function jumpSource(key){const record=document.getElementById(sourceId(key));if(record){record.open=true;record.scrollIntoView({block:'start'});record.querySelector('summary').focus({preventScroll:true});}}
document.addEventListener('click',event=>{
  const sort=event.target.closest('[data-sort]');if(sort){state.sort=state.sortKey===sort.dataset.sort&&state.sort==='desc'?'asc':'desc';state.sortKey=sort.dataset.sort;state.page=1;renderTable();return;}
  const vendorSource=event.target.closest('[data-vendor-source]');if(vendorSource){openVendor(vendorSource.dataset.vendorSource,vendorSource);jumpSource(vendorSource.dataset.dimension);return;}
  const source=event.target.closest('[data-source]');if(source){jumpSource(source.dataset.source);return;}
  const open=event.target.closest('[data-open]');if(open){openVendor(open.dataset.open,open);return;}
  const row=event.target.closest('[data-vendor-row]');if(row){openVendor(row.dataset.vendorRow,row.querySelector('[data-open]'));return;}
  const risk=event.target.closest('[data-risk]');if(risk){state.risk=risk.dataset.risk;state.page=1;renderTable();return;}
  if(event.target.closest('#close-detail'))$('#vendor-dialog').close();if(event.target.closest('#empty-reset'))clearFilters();
});
$('#weight-controls').addEventListener('input',event=>{const key=event.target.dataset.weight||event.target.dataset.weightNumber;if(!key||event.target.value===''||!Number.isFinite(event.target.valueAsNumber))return;const value=Math.max(0,Math.min(100,event.target.valueAsNumber));event.target.value=value;rebalanceWeights(key,value);updateWeights();});
$('#weight-controls').addEventListener('change',event=>{const key=event.target.dataset.weightNumber;if(key)event.target.value=state.weights[key];});
$('#vendor-search').addEventListener('input',e=>{state.query=e.target.value;state.page=1;renderTable();});
$('#category-filter').addEventListener('change',e=>{state.category=e.target.value;state.page=1;renderTable();});
$('#region-filter').addEventListener('change',e=>{state.region=e.target.value;state.page=1;renderTable();});
$('#prev-page').addEventListener('click',()=>{state.page--;renderTable();});$('#next-page').addEventListener('click',()=>{state.page++;renderTable();});
$('#reset-filters').addEventListener('click',clearFilters);$('#export-button').addEventListener('click',exportCSV);
$('#reset-weights').addEventListener('click',()=>{state.weights={...defaultWeights};updateWeights();});
$('#live-toggle').addEventListener('click',()=>{state.live=!state.live;$('#live-toggle').setAttribute('aria-pressed',String(state.live));$('#live-text').textContent=state.live?'Auto-refresh':'Paused';document.body.classList.toggle('refresh-paused',!state.live);if(state.live)loadDashboard();});
$('#vendor-dialog').addEventListener('close',()=>{state.selected=null;document.body.style.overflow='';if(lastTrigger?.isConnected)lastTrigger.focus();else $('#vendor-search').focus();});
$('#vendor-dialog').addEventListener('click',event=>{const dialog=event.currentTarget,r=dialog.getBoundingClientRect();if(event.target===dialog&&(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom))dialog.close();});
document.addEventListener('keydown',event=>{if(event.key==='/'&&!document.querySelector('dialog[open]')&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)){event.preventDefault();$('#vendor-search').focus();}});
const weightsDialog=$('#weights-popover');
const weightsButton=$('#weights-button');
const sheetMedia=matchMedia('(max-width: 560px)');
function positionWeights() {
  if(!weightsDialog.open||sheetMedia.matches)return;
  const anchor=weightsButton.getBoundingClientRect();
  const width=weightsDialog.offsetWidth,height=weightsDialog.offsetHeight;
  const below=anchor.bottom+8;
  const top=below+height<=innerHeight-12?below:Math.max(12,anchor.top-height-8);
  weightsDialog.style.left=Math.max(12,Math.min(anchor.right-width,document.documentElement.clientWidth-width-12))+'px';
  weightsDialog.style.top=top+'px';
}
function openWeights() {
  if(weightsDialog.open)return;
  weightsDialog.style.removeProperty('left');weightsDialog.style.removeProperty('top');
  if(sheetMedia.matches){weightsDialog.setAttribute('aria-modal','true');weightsDialog.showModal();document.body.style.overflow='hidden';}
  else {weightsDialog.removeAttribute('aria-modal');weightsDialog.show();}
  weightsButton.setAttribute('aria-expanded','true');
  positionWeights();
  document.querySelector('[data-weight]').focus({preventScroll:true});
}
function closeWeights(restoreFocus=true) {
  if(!weightsDialog.open)return;
  weightsDialog.close();
  weightsButton.setAttribute('aria-expanded','false');
  if(!$('#vendor-dialog').open)document.body.style.overflow='';
  if(restoreFocus)weightsButton.focus({preventScroll:true});
}
weightsButton.addEventListener('click',()=>weightsDialog.open?closeWeights():openWeights());
$('#close-weights').addEventListener('click',()=>closeWeights());
weightsDialog.addEventListener('cancel',event=>{event.preventDefault();closeWeights();});
document.addEventListener('pointerdown',event=>{
  if(!weightsDialog.open||weightsButton.contains(event.target))return;
  const rect=weightsDialog.getBoundingClientRect();
  if(!weightsDialog.contains(event.target)||(event.target===weightsDialog&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)))closeWeights(false);
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&weightsDialog.open){event.preventDefault();closeWeights();}
});
document.addEventListener('focusin',event=>{
  if(weightsDialog.open&&!sheetMedia.matches&&!weightsDialog.contains(event.target)&&!weightsButton.contains(event.target))closeWeights(false);
});
window.addEventListener('resize',positionWeights);
window.addEventListener('scroll',positionWeights,{passive:true});
sheetMedia.addEventListener('change',()=>{
  if(!weightsDialog.open)return;
  const focused=document.activeElement;
  closeWeights(false);openWeights();
  if(weightsDialog.contains(focused))focused.focus({preventScroll:true});
});
hydrateIcons();loadDashboard();
setInterval(()=>{if(state.live&&!document.hidden&&!pending)loadDashboard();},refreshIntervalMs);
