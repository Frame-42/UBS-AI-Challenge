// Lightweight browser-logic regressions. These are not visual/browser tests.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const vm = require('node:vm');

function appContext() {
  const elements = new Map();
  const element = key => {
    if (!elements.has(key)) elements.set(key, {
      value: '', innerHTML: '', hidden: true, open: false, dataset: {},
      style: { setProperty() {}, removeProperty() {} },
      classList: { toggle() {}, add() {}, remove() {} },
      addEventListener() {}, setAttribute() {}, querySelectorAll() { return []; },
    });
    return elements.get(key);
  };
  const document = {
    querySelector: element, getElementById: element, querySelectorAll: () => [],
    addEventListener() {}, activeElement: { dataset: {}, isConnected: true },
  };
  const context = vm.createContext({
    document, window: { addEventListener() {} },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    setInterval() {}, setTimeout() {}, clearTimeout() {}, AbortController, URL,
  });
  // Keep all functions and listeners, but do not start polling or network activity.
  const source = readFileSync(new URL('../app.js', `file://${__filename}`), 'utf8')
    .replace('hydrateIcons();loadDashboard();', '');
  vm.runInContext(source, context);
  return context;
}

function snapshot(categories, weights) {
  return {
    score_basis: 'collector_heuristic',
    scoreboard: { records: [], normalized_weights: weights, config: { categories, risk_levels: [] } },
    dashboard: { default_weights: weights }, evidence: {},
  };
}

function response(data, status = 200) {
  return { status, ok: status === 200, json: async () => data };
}

function skipRendering(context) {
  // The tests exercise requests/control state, not an emulated layout engine.
  vm.runInContext('renderMetrics=()=>{}; renderTable=()=>{}; refreshDetail=()=>{};', context);
}

test('single category stays at 100%; remaining weights rebalance without drift', () => {
  const context = appContext();
  vm.runInContext("riskDimensions=[{key:'a'}]; state.weights={a:100}; rebalanceWeights('a',20);", context);
  assert.equal(vm.runInContext('state.weights.a', context), 100);
  vm.runInContext("riskDimensions=[{key:'a'},{key:'b'},{key:'c'}]; state.weights={a:40,b:30,c:30}; rebalanceWeights('a',70);", context);
  assert.equal(vm.runInContext('JSON.stringify(state.weights)', context), '{"a":70,"b":15,"c":15}');
});

test('inferred category IDs are supported and escaped in controls', () => {
  const context = appContext();
  context.example = snapshot(null, { 'new/risk"<': 100 });
  vm.runInContext('payload=example; setupControls();', context);
  const html = vm.runInContext("document.querySelector('#weight-controls').innerHTML", context);
  assert.ok(html.includes('data-weight="new/risk&quot;&lt;"'));
  assert.ok(html.includes('weight-new%2Frisk%22%3C'));
  assert.equal(vm.runInContext('riskDimensions.length', context), 1);
});

test('removed categories trigger a default-weight retry and rebuild controls', async () => {
  const context = appContext();
  skipRendering(context);
  context.fetch = async () => response(snapshot(['old'], { old: 100 }));
  await vm.runInContext('loadDashboard()', context);
  const requested = [];
  context.fetch = async url => {
    requested.push(url);
    return requested.length === 1
      ? response({ error: 'Unknown category: old' }, 400)
      : response(snapshot(['new'], { new: 100 }));
  };
  await vm.runInContext('loadDashboard()', context);
  assert.equal(requested.length, 2);
  assert.equal(requested[1], '/api/dashboard');
  assert.equal(vm.runInContext('JSON.stringify(state.weights)', context), '{"new":100}');
  assert.equal(vm.runInContext('pending', context), false);
});

test('changed default weights are requested before the view is considered current', async () => {
  const context = appContext();
  skipRendering(context);
  context.fetch = async () => response(snapshot(['a', 'b'], { a: 50, b: 50 }));
  await vm.runInContext('loadDashboard()', context);
  const requested = [];
  context.fetch = async url => {
    requested.push(url);
    return response(snapshot(['a', 'b'], { a: 80, b: 20 }));
  };
  await vm.runInContext('loadDashboard()', context);
  assert.equal(requested.length, 2);
  assert.ok(decodeURIComponent(requested[1]).includes('"a":80'));
  assert.equal(vm.runInContext('JSON.stringify(state.weights)', context), '{"a":80,"b":20}');
});
