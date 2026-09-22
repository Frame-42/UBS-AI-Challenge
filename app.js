/* All vendor assessments and signals below are fictional prototype fixtures. */
const icons = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  building: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h1m4 0h1M9 11h1m4 0h1M9 15h1m4 0h1M10 21v-3h4v3"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  star: '<path d="m12 3 2.8 5.7 6.3.9-4.5 4.4 1.1 6.2-5.7-3-5.7 3 1.1-6.2-4.5-4.4 6.3-.9Z"/>',
  activity: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z"/><path d="M14 3v6h6M8 13h8m-8 4h5"/>',
  flask: '<path d="M9 3h6m-5 0v7L4 19a1.3 1.3 0 0 0 1 2h14a1.3 1.3 0 0 0 1-2l-6-9V3M7 15h10"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  'shield-alert': '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="M12 8v5m0 3h.01"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  'chevron-left': '<path d="m15 6-6 6 6 6"/>',
  'chevron-right': '<path d="m9 6 6 6-6 6"/>',
  'arrow-right': '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  'arrow-up-right': '<path d="M6 18 18 6M6 6h12v12"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  sliders: '<path d="M4 7h7m4 0h5M4 17h3m4 0h9"/><circle cx="13" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  sort: '<path d="M8 4v16m-3-3 3 3 3-3M16 20V4m-3 3 3-3 3 3"/>',
  sparkles: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/><path d="M20 2v4m-2-2h4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6h14M5 18h14"/>',
  chart: '<path d="M4 3v17h17M8 15v-4m5 4V6m5 9v-6"/>',
  'check-circle': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  layers: '<path d="m12 3 10 5-10 5L2 8Zm-10 9 10 5 10-5M2 16l10 5 10-5"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  alert: '<path d="m12 3 10 18H2Z"/><path d="M12 9v5m0 3h.01"/>',
};
function icon(name) { return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.info}</svg>`; }
function hydrateIcons(root = document) { root.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); }); }
const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const vendors = [
  {id:'aws',name:'Amazon Web Services',short:'AWS',category:'Cloud infrastructure',region:'Americas',country:'United States',score:24,history:[29,27,28,24,26,25,24],mark:'aws',service:'Global cloud hosting & storage',summary:'Cloud service availability remains steady across the simulated banking footprint. Strong financial resilience and established controls offset a moderate concentration of critical workloads. Continue monitoring regional redundancy and recovery readiness.',action:'Maintain routine monitoring and validate the next recovery exercise.'},
  {id:'microsoft',name:'Microsoft',short:'Microsoft',category:'Enterprise software',region:'Americas',country:'United States',score:18,history:[22,23,20,21,19,20,18],mark:'',service:'Productivity, identity & Azure services',summary:'The simulated assessment shows stable enterprise service delivery and a mature control environment. Identity services remain a critical dependency across the bank. Recent fictional control evidence indicates improving access governance.',action:'Review privileged access controls at the next quarterly assessment.'},
  {id:'nvidia',name:'NVIDIA',short:'NVIDIA',category:'Semiconductors',region:'Americas',country:'United States',score:64,history:[51,54,52,58,57,62,64],mark:'NV',service:'Accelerated computing & AI processors',summary:'A fictional export-control scenario raises geopolitical exposure for accelerator supply. Simulated demand pressure may extend procurement lead times for the bank’s AI infrastructure. Financial health remains resilient, while supply continuity needs closer review.',action:'Confirm regional delivery commitments and assess alternative compute capacity.'},
  {id:'tsmc',name:'TSMC',short:'TSMC',category:'Semiconductors',region:'Asia Pacific',country:'Taiwan',score:72,history:[59,62,61,66,68,67,72],mark:'tsmc',service:'Semiconductor manufacturing supply chain',summary:'Geographic concentration and a fictional shipping disruption drive an elevated simulated score. Indirect exposure through processor suppliers could affect hardware refresh plans across multiple regions. No actual disruption is being reported by this prototype.',action:'Map indirect dependencies and confirm inventory buffers with hardware suppliers.'},
  {id:'sap',name:'SAP',short:'SAP',category:'Enterprise software',region:'Europe',country:'Germany',score:21,history:[26,24,25,22,23,20,21],mark:'SAP',service:'Finance, procurement & enterprise systems',summary:'The fictional assessment indicates dependable application availability and a stable financial profile. A recent simulated controls review found no material gaps. Legacy integrations remain an area for periodic operational review.',action:'Continue scheduled controls reviews and track integration modernization.'},
  {id:'bloomberg',name:'Bloomberg',short:'Bloomberg',category:'Market data',region:'Americas',country:'United States',score:16,history:[19,18,20,17,18,16,16],mark:'B',service:'Market data, terminals & pricing feeds',summary:'Simulated pricing-feed delivery remains consistent across the trading day. Established operational controls support a low illustrative risk score. The bank should continue to test fallback data sources for critical valuation processes.',action:'Maintain routine monitoring and periodic market-data failover testing.'},
  {id:'visa',name:'Visa',short:'Visa',category:'Payments',region:'Americas',country:'United States',score:12,history:[18,16,17,15,14,13,12],mark:'VISA',service:'Global card network & settlement',summary:'A fictional resilience exercise shows robust transaction processing and settlement continuity. Financial and compliance indicators remain stable in this demo. Cross-border dependencies should remain part of regular scenario testing.',action:'Continue standard monitoring and scheduled payment-continuity exercises.'},
  {id:'infosys',name:'Infosys',short:'Infosys',category:'IT services',region:'Asia Pacific',country:'India',score:43,history:[36,38,37,42,40,41,43],mark:'infy',service:'Technology operations & transformation',summary:'A fictional staffing transition introduces moderate delivery exposure for a core transformation program. Service availability is stable, but simulated resource concentration warrants review. Cybersecurity and financial indicators show no significant movement.',action:'Review transition milestones and validate backup staffing for critical services.'},
  {id:'oracle',name:'Oracle',short:'Oracle',category:'Enterprise software',region:'Americas',country:'United States',score:47,history:[41,40,44,43,46,45,47],mark:'OR',service:'Database platforms & core applications',summary:'A fictional maintenance backlog raises operational exposure for database services. Simulated patch coverage is improving, though several critical applications depend on shared database infrastructure. Commercial concentration is also under review.',action:'Confirm patch milestones and review application recovery dependencies.'},
  {id:'lseg',name:'LSEG',short:'LSEG',category:'Market data',region:'Europe',country:'United Kingdom',score:33,history:[39,37,38,35,36,34,33],mark:'LSEG',service:'Financial data & trading infrastructure',summary:'Simulated risk has improved following a fictional data-quality review. A small number of feed reconciliation items remain open. Operational dependencies across trading and risk reporting support continued enhanced monitoring.',action:'Track the remaining feed-reconciliation items to closure.'},
  {id:'accenture',name:'Accenture',short:'Accenture',category:'IT services',region:'Europe',country:'Ireland',score:35,history:[31,30,33,32,36,34,35],mark:'>',service:'Consulting & managed technology services',summary:'The fictional assessment reflects moderate exposure from a broad outsourced service footprint. A simulated subcontractor review is in progress. Financial and delivery indicators remain stable, with concentration across transformation initiatives under observation.',action:'Complete the subcontractor review and confirm service ownership boundaries.'},
  {id:'swift',name:'Swift',short:'Swift',category:'Payments',region:'Europe',country:'Belgium',score:61,history:[51,53,52,57,56,59,61],mark:'swift',service:'Cross-border financial messaging',summary:'A fictional sanctions-policy change increases compliance complexity for cross-border messaging. The elevated demo score reflects bank-specific exposure and scenario assumptions. Messaging availability remains stable within the simulation.',action:'Validate corridor-specific controls and refresh the sanctions-response playbook.'},
];
vendors.forEach(v => {
  v.baseScore = v.score;
  v.subscores = Object.fromEntries(riskDimensions.map((dimension,i) => [dimension.key,vendorEvidence[v.id][i][0]]));
  v.sources = riskDimensions.map((dimension,i) => ({
    ...dimension,
    id:`${dimension.prefix}-${v.id.toUpperCase()}-202609-${String(i+1).padStart(2,'0')}`,
    title:vendorEvidence[v.id][i][1],
    excerpt:vendorEvidence[v.id][i][2],
    published:`2026-09-${21-i}`,
  }));
});
const startTime = Date.now();
let signals = [
  {vendor:'tsmc',severity:'high',title:'Supply-chain concentration flagged in regional review',source:'Supply chain · Demo scenario',time:startTime-2*60000,type:'globe'},
  {vendor:'nvidia',severity:'high',title:'New export-control scenario increases geographic exposure',source:'Geopolitical · Demo scenario',time:startTime-14*60000,type:'alert'},
  {vendor:'microsoft',severity:'low',title:'Access-control review completed with improved coverage',source:'Cybersecurity · Demo scenario',time:startTime-38*60000,type:'check-circle'},
  {vendor:'swift',severity:'moderate',title:'Cross-border compliance review requires follow-up',source:'Compliance · Demo scenario',time:startTime-56*60000,type:'file'},
  {vendor:'infosys',severity:'moderate',title:'Service transition milestones added to monitoring',source:'Operations · Demo scenario',time:startTime-94*60000,type:'layers'},
  {vendor:'visa',severity:'low',title:'Payment continuity exercise completed successfully',source:'Resilience · Demo scenario',time:startTime-130*60000,type:'shield'},
];
let watchlist;
try { const saved = JSON.parse(localStorage.getItem('vendor-risk-watchlist') ?? localStorage.getItem('vantage-watchlist')); watchlist = new Set(Array.isArray(saved) ? saved.filter(id => vendors.some(v => v.id === id)) : ['nvidia','tsmc','swift']); }
catch { watchlist = new Set(['nvidia','tsmc','swift']); }
const state = {view:'overview',query:'',category:'all',region:'all',risk:'all',page:1,sort:null,live:true,selected:null,updatedAt:startTime};
const pageSize = 8;
const riskLevel = score => score >= 60 ? 'high' : score >= 30 ? 'moderate' : 'low';
const riskName = score => ({high:'High risk',moderate:'Moderate',low:'Low risk'}[riskLevel(score)]);
const color = score => ({high:'#c76475',moderate:'#c4a063',low:'#72a590'}[riskLevel(score)]);
function logo(v) { return `<span class="vendor-logo ${v.id}" aria-hidden="true">${v.id === 'microsoft' ? '<i></i><i></i><i></i><i></i>' : escapeHTML(v.mark)}</span>`; }
function badge(score) { const r = riskLevel(score); return `<span class="status-badge ${r}"><i class="dot ${r}"></i>${riskName(score)}</span>`; }
function change(v) { return v.score - v.history[0]; }
function changeLabel(v) { const n = change(v); return n > 0 ? `+${n}` : String(n); }
function sparkline(values, stroke, width = 80, height = 28, fill = false) {
  const min = Math.min(...values)-3, max = Math.max(...values)+3;
  const points = values.map((v,i) => `${(i*(width-4)/(values.length-1)+2).toFixed(1)},${(height-3-(v-min)/(max-min)*(height-6)).toFixed(1)}`).join(' ');
  return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">${fill ? `<polygon points="2,${height} ${points} ${width-2},${height}" fill="${stroke}" opacity=".07"/>` : ''}<polyline points="${points}" fill="none" stroke="${stroke}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
function relativeTime(time) { const minutes = Math.max(0,Math.floor((Date.now()-time)/60000)); return minutes === 0 ? 'Just now' : minutes < 60 ? `${minutes}m ago` : `${Math.floor(minutes/60)}h ago`; }
function formatTime(time) { return new Date(time).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit',second:'2-digit'}); }
function renderMetrics() {
  const high = vendors.filter(v => v.score >= 60).length;
  const average = Math.round(vendors.reduce((sum,v) => sum+v.score,0)/vendors.length);
  const cards = [
    {label:'Monitored vendors',value:vendors.length,icon:'building',foot:'<strong>6 categories</strong><span>across 3 regions</span>',history:[5,5,6,6,8,8,10,10,12],color:'#aaadb8'},
    {label:'Elevated risk',value:high,icon:'shield-alert',foot:'<strong class="risk-text">Review recommended</strong>',history:[1,1,2,2,1,2,2,3,high],color:'#d98b99',class:'elevated'},
    {label:'Average risk score',value:average,unit:'/ 100',icon:'chart',foot:'<strong class="neutral-text">Higher score = higher risk</strong>',history:[45,46,44,41,42,40,39,38,average],color:'#9fb9ab'},
    {label:'Recent signals',value:signals.length,icon:'activity',foot:`<strong>${state.live?'Monitoring active':'Monitoring paused'}</strong><span>simulated feed</span>`,history:[1,2,2,3,3,4,4,5,signals.length],color:'#c8a5b0'},
  ];
  $('#metrics').innerHTML = cards.map(c => `<div class="metric-card ${c.class || ''}"><div class="metric-label">${c.label}<span>${icon(c.icon)}</span></div><div class="metric-number">${c.value}${c.unit ? `<small>${c.unit}</small>` : ''}</div><div class="metric-chart">${sparkline(c.history,c.color,85,30,true)}</div><div class="metric-bottom">${c.foot}</div></div>`).join('');
  $('#high-risk-count').textContent = `${high} vendors`;
  $('#insight-copy').innerHTML = `Your ${high} elevated-risk vendors account for <strong>${Math.round(high/vendors.length*100)}% of this portfolio.</strong> A closer look can help prioritize your next review.`;
  $('#region-bars').innerHTML = ['Americas','Europe','Asia Pacific'].map(region => { const count=vendors.filter(v=>v.region===region).length; return `<div><div class="region-top">${region}<strong>${count}</strong></div><div class="region-track"><i style="width:${count/vendors.length*100}%"></i></div><div class="region-sub">${Math.round(count/vendors.length*100)}% of portfolio</div></div>`; }).join('');
}
function baseVendors() { return vendors.filter(v => state.view !== 'watchlist' || watchlist.has(v.id)); }
function filteredVendors() {
  const result = baseVendors().filter(v => `${v.name} ${v.short} ${v.category} ${v.country}`.toLowerCase().includes(state.query.toLowerCase()) && (state.category==='all'||v.category===state.category) && (state.region==='all'||v.region===state.region) && (state.risk==='all'||riskLevel(v.score)===state.risk));
  if(state.sort) result.sort((a,b) => state.sort==='desc' ? b.score-a.score : a.score-b.score);
  return result;
}
function renderTable() {
  const result = filteredVendors(), pages = Math.max(1,Math.ceil(result.length/pageSize));
  state.page = Math.min(state.page,pages);
  const offset = (state.page-1)*pageSize;
  $('#vendor-total').textContent = baseVendors().length;
  document.querySelectorAll('[data-risk]').forEach(button => {
    button.classList.toggle('active',button.dataset.risk===state.risk);
    button.setAttribute('aria-pressed',String(button.dataset.risk===state.risk));
    button.querySelector('span').textContent = baseVendors().filter(v=>button.dataset.risk==='all'||riskLevel(v.score)===button.dataset.risk).length;
  });
  $('#score-sort').closest('th').setAttribute('aria-sort', state.sort==='asc'?'ascending':state.sort==='desc'?'descending':'none');
  $('#score-sort').setAttribute('aria-label',`Sort risk score ${state.sort==='desc'?'ascending':'descending'}`);
  $('#vendor-rows').innerHTML = result.length ? result.slice(offset,offset+pageSize).map(v => `<tr data-vendor-row="${v.id}"><td><button class="vendor-cell" data-open="${v.id}" aria-label="View ${v.name} risk assessment">${logo(v)}<span><strong>${v.name}</strong><small>${v.category}</small>${compactSubscores(v)}</span></button></td><td><div class="score-cell risk-${riskLevel(v.score)}"><span class="score-value">${v.score}</span><span class="score-track"><i style="width:${v.score}%"></i></span></div></td><td><div class="trend-cell">${sparkline(v.history,color(v.score))}<span class="trend-change ${change(v)>0?'risk-high':'risk-low'}" aria-label="${change(v)} points over seven days">${changeLabel(v)}</span></div></td><td>${badge(v.score)}</td><td><button class="star-button ${watchlist.has(v.id)?'watched':''}" data-watch="${v.id}" aria-pressed="${watchlist.has(v.id)}" aria-label="${watchlist.has(v.id)?'Remove':'Add'} ${v.name} ${watchlist.has(v.id)?'from':'to'} watchlist">${icon('star')}</button></td></tr>`).join('') : `<tr><td colspan="5"><div class="empty-state">${icon(state.view==='watchlist'?'star':'search')}<strong>${state.view==='watchlist'&&!watchlist.size?'Your watchlist starts here.':'No matching vendors'}</strong><p>${state.view==='watchlist'&&!watchlist.size?'Star a vendor in the portfolio to keep it close.':'Try another search or clear your filters.'}</p><button class="text-button" id="empty-reset">${state.view==='watchlist'&&!watchlist.size?'Explore vendors':'Clear filters'}${icon('arrow-right')}</button></div></td></tr>`;
  $('#table-count').textContent = result.length ? `Showing ${offset+1}–${Math.min(offset+pageSize,result.length)} of ${result.length} vendors` : '0 vendors';
  $('#page-label').textContent = `${state.page} / ${pages}`;
  $('#prev-page').disabled = state.page===1;
  $('#next-page').disabled = state.page===pages;
  $('#watch-count').textContent = watchlist.size;
}
function signalMarkup(signal, full = false) {
  const v=vendors.find(v=>v.id===signal.vendor);
  const body=`<span class="signal-symbol ${signal.severity}">${icon(signal.type)}</span><div class="signal-info"><div class="signal-meta"><strong>${v.short}</strong><time datetime="${new Date(signal.time).toISOString()}">${relativeTime(signal.time)}</time></div><p class="signal-title">${escapeHTML(signal.title)}</p><div class="signal-source"><i class="dot ${signal.severity}"></i>${escapeHTML(signal.source)}</div></div>`;
  return full ? `<div class="activity-row">${body}<button class="button button-secondary" data-open="${v.id}">View assessment${icon('arrow-up-right')}</button></div>` : `<button class="signal-item" data-open="${v.id}">${body}</button>`;
}
function renderSignals() {
  $('#latest-signals').innerHTML = signals.slice(0,4).map(s=>signalMarkup(s)).join('');
  if(state.view==='activity') $('#activity-content').innerHTML = `<div class="panel-heading"><div><h2>Every signal, in context <span class="number-pill">${signals.length}</span></h2><p>Fictional events across your vendor ecosystem · Newest first</p></div><span class="pulse-indicator"></span></div>${signals.map(s=>signalMarkup(s,true)).join('')}`;
}
function renderReports() {
  $('#reports-content').innerHTML = `<div class="panel-heading"><div><h2>From insight to action</h2><p>Download a snapshot of your simulated portfolio.</p></div></div><div class="report-intro"><span>${icon('file')}</span><div><h2>Your next review, a little easier.</h2><p>Export vendor scores, risk levels, seven-day changes, and geographic coverage. Every file is labeled as fictional demo data.</p></div></div>${[{title:'Complete vendor portfolio',description:`All ${vendors.length} vendors · Current risk scores and categories`,scope:'all'},{title:'Elevated-risk vendors',description:'Vendors with scores of 60 or above · Prioritize your review',scope:'high'},{title:'Your watchlist',description:`${watchlist.size} saved vendors · Your focused monitoring list`,scope:'watchlist'}].map(r=>`<div class="report-card"><div><strong>${r.title}</strong><p>${r.description}</p></div><button class="button button-secondary" data-export="${r.scope}">${icon('download')}Export CSV</button></div>`).join('')}`;
}
const viewInfo={overview:['Overview','A clearer view of vendor risk.','Your global ecosystem. Every signal. One place to stay ahead.'],vendors:['Vendor portfolio','Your ecosystem, in focus.','Explore every partner behind your global operations.'],watchlist:['Watchlist','Keep your priorities close.','A focused view of the vendors that matter most to you.'],activity:['Activity feed','Follow the signals.','The latest simulated changes across your vendor ecosystem.'],reports:['Reports & exports','Insights worth sharing.','Turn your vendor intelligence into a snapshot for your next review.']};
function navigate() {
  const candidate=location.hash.slice(1);
  if(candidate==='main') return;
  state.view=Object.hasOwn(viewInfo,candidate)?candidate:'overview';
  state.page=1;
  const [breadcrumb,title,description]=viewInfo[state.view];
  $('#breadcrumb-title').textContent=breadcrumb; $('#page-title').textContent=title; $('#page-description').textContent=description;
  document.querySelectorAll('[data-view]').forEach(link=>{ const active=link.dataset.view===state.view; link.classList.toggle('active',active); if(active) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current'); });
  const portfolio=['overview','vendors','watchlist'].includes(state.view);
  $('#overview-content').hidden=state.view!=='overview'; $('#portfolio-content').hidden=!portfolio; $('#bottom-content').hidden=state.view!=='overview';
  $('#right-column').hidden=state.view!=='overview'; $('#portfolio-content').style.gridTemplateColumns=state.view==='overview'?'':'minmax(0,1fr)';
  $('#activity-content').hidden=state.view!=='activity'; $('#reports-content').hidden=state.view!=='reports';
  renderTable(); renderSignals(); if(state.view==='reports')renderReports();
}
function detailChart(v) {
  const points=v.history.map((score,i)=>`${i*65},${100-score}`).join(' ');
  const stroke=color(v.score);
  return `<svg viewBox="0 0 390 105" preserveAspectRatio="none" role="img" aria-label="Illustrative seven-day scores: ${v.history.join(', ')}"><defs><linearGradient id="detail-gradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${stroke}" stop-opacity=".18"/><stop offset="100%" stop-color="${stroke}" stop-opacity="0"/></linearGradient></defs><path d="M0 20H390M0 50H390M0 80H390" stroke="#eee9ed" stroke-dasharray="3 4" fill="none"/><polygon points="0,105 ${points} 390,105" fill="url(#detail-gradient)"/><polyline points="${points}" stroke="${stroke}" fill="none" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/><circle cx="390" cy="${100-v.score}" r="3.5" fill="${stroke}" stroke="white" stroke-width="2"/></svg>`;
}
function renderDetail() {
  const v=vendors.find(v=>v.id===state.selected); if(!v)return;
  const related=signals.filter(s=>s.vendor===v.id).slice(0,3);
  $('#vendor-detail').innerHTML=`<div class="detail-topbar"><span>${icon('shield')}VENDOR ASSESSMENT <span class="demo-tag">SIMULATED</span></span><button class="icon-button" id="close-detail" aria-label="Close vendor assessment">${icon('x')}</button></div><div class="detail-body"><div class="detail-identity">${logo(v)}<div><h2 id="detail-name">${v.name}</h2><p>${v.service}</p></div></div><div class="detail-meta"><span>${icon('pin')}${v.country}</span><span>·</span><span>${v.category}</span></div><section class="detail-score-card" aria-label="Current risk score"><div class="detail-score-top"><span>Overall risk score</span>${badge(v.score)}</div><div class="detail-score-main"><div class="detail-score-number risk-${riskLevel(v.score)}" id="live-detail-score">${v.score}<small>/ 100</small></div><div class="detail-score-trend ${change(v)>0?'risk-high':'risk-low'}" id="live-detail-change">${changeLabel(v)} points<small>over the last 7 days</small></div></div><div class="detail-chart" id="live-detail-chart">${detailChart(v)}</div><div class="chart-axis"><span>6 days ago</span><span>Illustrative 7-day trend · 0–100 scale</span><span>Today</span></div></section><section class="detail-section"><h3>${icon('sparkles')}Live risk summary</h3><div class="detail-summary"><div class="summary-label"><span>ASSESSMENT BRIEF</span><span>SYNTHETIC</span></div><p>${v.summary}</p><p id="live-summary" style="margin-top:10px">Current simulated score: <strong>${v.score}/100</strong> · ${riskName(v.score).toLowerCase()}. Refreshed at ${formatTime(state.updatedAt)} UTC.</p></div></section><section class="detail-section"><h3>Risk subscores <span class="number-pill">0–100</span></h3><div id="live-factors">${factorMarkup(v)}</div></section><section class="detail-section"><h3>${icon('file')}Sources & evidence <span class="number-pill">3 reports</span></h3><div id="detail-sources">${sourceMarkup(v)}</div></section><section class="detail-section"><h3>${icon('activity')}Recent signals</h3><div id="detail-signals">${related.length?related.map(s=>signalMarkup(s)).join(''):'<p class="detail-summary">No new signals in this demo session. Routine monitoring remains active.</p>'}</div></section><section class="detail-section"><h3>${icon('check-circle')}Suggested next step</h3><p class="detail-summary">${v.action}</p></section><div class="detail-footer"><span>Fictional assessment for demonstration.<br>No external data or risk model connected.</span><button class="button button-secondary detail-watch" data-watch="${v.id}">${icon('star')}${watchlist.has(v.id)?'Remove from watchlist':'Add to watchlist'}</button></div></div>`;
}
function subscore(v,key) { return Math.max(0,Math.min(100,v.subscores[key]+v.score-v.baseScore)); }
function compactSubscores(v) {
  return `<span class="vendor-subscores">${riskDimensions.map(d=>`<span title="${d.label} risk: ${subscore(v,d.key)} out of 100">${d.key==='reputation'?'Rep.':d.label} <b class="risk-${riskLevel(subscore(v,d.key))}">${subscore(v,d.key)}</b></span>`).join('')}</span>`;
}
function factorMarkup(v) {
  return `<div class="subscore-grid">${riskDimensions.map(d=>{
    const score=subscore(v,d.key);
    return `<div class="subscore-card"><div class="subscore-label">${icon(d.icon)}${d.label}</div><div class="subscore-number risk-${riskLevel(score)}">${score}<small>/ 100</small></div><div class="factor-bar risk-${riskLevel(score)}"><span style="width:${score}%"></span></div><button class="source-jump" data-source="${d.key}" aria-label="View ${d.label.toLowerCase()} source for ${v.name}">View source ${icon('arrow-right')}</button></div>`;
  }).join('')}</div><p class="subscore-note">Higher means greater risk. Overall risk and subscores are independent demo values.</p>`;
}
function sourceMarkup(v) {
  return `<p class="source-disclaimer">All reports, publishers, and findings below are invented for this prototype.</p>${v.sources.map((source,i)=>`<details class="source-record" id="source-${source.key}"><summary><span class="source-heading"><span class="source-index">0${i+1}</span><span><span class="source-category">${source.label} <span class="fictional-label">FICTIONAL SOURCE</span></span><strong>${escapeHTML(source.title)}</strong><span class="source-byline">${source.publisher} · <time datetime="${source.published}">${new Date(source.published+'T00:00:00Z').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'})}</time></span></span>${icon('chevron-down')}</span></summary><div class="source-excerpt"><span class="source-document-id">Document ${source.id}</span><p>${escapeHTML(source.excerpt)}</p><span class="source-excerpt-note">Synthetic report excerpt · ${source.label.toLowerCase()} subscore evidence</span></div></details>`).join('')}`;
}
function refreshDetail() {
  if(!$('#vendor-dialog').open)return;
  const v=vendors.find(v=>v.id===state.selected);
  $('#live-detail-score').innerHTML=`${v.score}<small>/ 100</small>`;
  $('#live-detail-score').className=`detail-score-number risk-${riskLevel(v.score)}`;
  $('.detail-score-top .status-badge').outerHTML=badge(v.score);
  $('#live-detail-change').innerHTML=`${changeLabel(v)} points<small>over the last 7 days</small>`;
  $('#live-detail-change').className=`detail-score-trend ${change(v)>0?'risk-high':'risk-low'}`;
  $('#live-detail-chart').innerHTML=detailChart(v);
  $('#live-summary').innerHTML=`Current simulated score: <strong>${v.score}/100</strong> · ${riskName(v.score).toLowerCase()}. Refreshed at ${formatTime(state.updatedAt)} UTC.`;
  $('#live-factors').innerHTML=factorMarkup(v);
  const related=signals.filter(s=>s.vendor===v.id).slice(0,3);
  if(related.length)$('#detail-signals').innerHTML=related.map(s=>signalMarkup(s)).join('');
}
let lastTrigger=null;
function openVendor(id,trigger) { state.selected=id; lastTrigger=trigger || document.activeElement; renderDetail(); if(!$('#vendor-dialog').open)$('#vendor-dialog').showModal(); document.body.style.overflow='hidden'; $('#close-detail').focus(); }
let toastTimer;
function toast(message) { clearTimeout(toastTimer); $('#toast').textContent=message; $('#toast').classList.add('visible'); toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3500); }
function toggleWatch(id) {
  const wasWatched=watchlist.has(id),v=vendors.find(v=>v.id===id);
  if(wasWatched)watchlist.delete(id);else watchlist.add(id);
  let saved=true;try{localStorage.setItem('vendor-risk-watchlist',JSON.stringify([...watchlist]));}catch{saved=false;}
  renderTable(); if(state.view==='reports')renderReports();
  if($('#vendor-dialog').open) { const button=$('.detail-watch'); button.innerHTML=`${icon('star')}${watchlist.has(state.selected)?'Remove from watchlist':'Add to watchlist'}`; }
  toast(`${v.short} ${wasWatched?'removed from':'added to'} your watchlist${saved?'':'. Browser storage unavailable; saved for this session only.'}`);
}
function clearFilters() { state.query='';state.category='all';state.region='all';state.risk='all';state.page=1;state.sort=null;$('#vendor-search').value='';$('#category-filter').value='all';$('#region-filter').value='all';renderTable(); }
function reviewRisk() { clearFilters();state.risk='high';location.hash='vendors';navigate();$('#portfolio-title').scrollIntoView({block:'start',behavior:'smooth'}); }
function exportCSV(scope='current') {
  const list=scope==='all'?vendors:scope==='high'?vendors.filter(v=>v.score>=60):scope==='watchlist'?vendors.filter(v=>watchlist.has(v.id)):['activity','reports'].includes(state.view)?vendors:filteredVendors();
  if(!list.length){toast('No vendors to export. Adjust your filters or add to your watchlist.');return;}
  const timestamp=new Date().toISOString();
  const rows=[['Dataset','Vendor','Category','Region','Country','Risk score (0-100)','Risk level','Cyber subscore','Reputation subscore','Fraud subscore','7-day change','Watchlisted','Score updated at (UTC)','Exported at (UTC)'],...list.map(v=>['FICTIONAL DEMO DATA',v.name,v.category,v.region,v.country,v.score,riskName(v.score),subscore(v,'cyber'),subscore(v,'reputation'),subscore(v,'fraud'),change(v),watchlist.has(v.id)?'Yes':'No',new Date(state.updatedAt).toISOString(),timestamp])];
  const csv=rows.map(row=>row.map(cell=>`"${String(cell).replace(/"/g,'""')}"`).join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8;'}));
  const link=document.createElement('a');link.href=url;link.download=`vendor-risk-demo-${scope}-${timestamp.slice(0,10)}.csv`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast(`Exported ${list.length} vendors · Demo data snapshot`);
}
document.addEventListener('click',event=>{
  const source=event.target.closest('[data-source]');
  if(source){const record=$('#source-'+source.dataset.source);record.open=true;record.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});record.querySelector('summary').focus({preventScroll:true});return;}
  const open=event.target.closest('[data-open]');if(open){openVendor(open.dataset.open,open);return;}
  const watch=event.target.closest('[data-watch]');if(watch){toggleWatch(watch.dataset.watch);return;}
  const row=event.target.closest('[data-vendor-row]');if(row){openVendor(row.dataset.vendorRow,row.querySelector('[data-open]'));return;}
  const risk=event.target.closest('[data-risk]');if(risk){state.risk=risk.dataset.risk;state.page=1;renderTable();return;}
  const download=event.target.closest('[data-export]');if(download){exportCSV(download.dataset.export);return;}
  if(event.target.closest('#close-detail'))$('#vendor-dialog').close();
  if(event.target.closest('#empty-reset')){clearFilters();if(state.view==='watchlist'&&!watchlist.size)location.hash='vendors';}
});
$('#vendor-search').addEventListener('input',event=>{state.query=event.target.value;state.page=1;renderTable();});
$('#category-filter').addEventListener('change',event=>{state.category=event.target.value;state.page=1;renderTable();});
$('#region-filter').addEventListener('change',event=>{state.region=event.target.value;state.page=1;renderTable();});
$('#score-sort').addEventListener('click',()=>{state.sort=state.sort==='desc'?'asc':'desc';state.page=1;renderTable();});
$('#prev-page').addEventListener('click',()=>{state.page--;renderTable();});
$('#next-page').addEventListener('click',()=>{state.page++;renderTable();});
$('#reset-filters').addEventListener('click',clearFilters);
$('#review-risk').addEventListener('click',reviewRisk);$('#insight-review').addEventListener('click',reviewRisk);
$('#export-button').addEventListener('click',()=>exportCSV());
$('#notifications-button').addEventListener('click',()=>{location.hash='activity';});
$('#live-toggle').addEventListener('click',()=>{state.live=!state.live;$('#live-toggle').setAttribute('aria-pressed',String(state.live));$('#live-text').textContent=state.live?'Live demo':'Paused';document.body.classList.toggle('simulation-paused',!state.live);renderMetrics();toast(state.live?'Simulation resumed · Scores refresh every 12 seconds':'Simulation paused · Your current snapshot is preserved');});
$('#help-button').addEventListener('click',()=>{$('#help-dialog').showModal();document.body.style.overflow='hidden';});
$('#close-help').addEventListener('click',()=>$('#help-dialog').close());$('#help-done').addEventListener('click',()=>$('#help-dialog').close());
document.querySelectorAll('dialog').forEach(dialog=>{dialog.addEventListener('click',event=>{if(event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close();}});dialog.addEventListener('close',()=>{document.body.style.overflow='';if(dialog.id==='vendor-dialog'){state.selected=null;if(lastTrigger?.isConnected)lastTrigger.focus();else $('#vendor-search').focus();}});});
document.addEventListener('keydown',event=>{if(event.key==='/'&&!document.querySelector('dialog[open]')&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)){event.preventDefault();if(!['overview','vendors','watchlist'].includes(state.view)){location.hash='vendors';navigate();}$('#vendor-search').focus();}});
window.addEventListener('hashchange',navigate);
hydrateIcons();renderMetrics();navigate();

// Replace this simulation with an API subscription when the risk model is ready.
// Historical points stay fixed; only today's endpoint changes, preserving the 7-day label.
let simulationTick=0;
setInterval(()=>{
  if(!state.live||document.hidden)return;
  simulationTick++;
  const v=vendors[(simulationTick*5)%vendors.length];
  const delta=simulationTick%3===0?-1:1;
  v.score=Math.max(v.baseScore-5,Math.min(v.baseScore+5,v.score+delta));v.history[6]=v.score;
  // Update the open vendor as well so the assessment visibly reflects the live snapshot.
  if(state.selected&&state.selected!==v.id){const selected=vendors.find(item=>item.id===state.selected);selected.score=Math.max(selected.baseScore-5,Math.min(selected.baseScore+5,selected.score+(simulationTick%2?1:-1)));selected.history[6]=selected.score;}
  state.updatedAt=Date.now();
  if(simulationTick%3===0){signals.unshift({vendor:v.id,severity:riskLevel(v.score),title:`Scheduled demo assessment refreshed · Risk score ${v.score}/100`,source:'Monitoring · Simulated update',time:state.updatedAt,type:'activity'});signals=signals.slice(0,30);}
  // Avoid removing keyboard focus from table controls during a background refresh.
  const focused=document.activeElement;
  const focusSelector=focused?.dataset.open?`[data-open="${focused.dataset.open}"]`:focused?.dataset.watch?`[data-watch="${focused.dataset.watch}"]`:null;
  renderMetrics();renderTable();renderSignals();refreshDetail();
  if(focusSelector&&!focused.isConnected){const root=$('#vendor-dialog').open?$('#vendor-dialog'):$('#portfolio-content');root.querySelector(focusSelector)?.focus({preventScroll:true});}
  $('#last-updated').textContent=`Updated ${formatTime(state.updatedAt)}`;
},12000);
