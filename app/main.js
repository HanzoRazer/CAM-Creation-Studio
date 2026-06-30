// main.js — CAM-Creation-Studio browser app.
//
// Vanilla-JS port of the original DC component. Behavior is preserved:
// machine/units/positioning/home toggles, Marlin heaters, CNC spindle, manual
// moves, image etching (raster + outline), live preview, and copy/download.
//
// The G-code generation has been EXTRACTED to src/gcode and is imported here —
// this file owns UI state, the preview canvas, and (for now) the image-etch
// path generation. Preview and image modules are scheduled for later extraction.

import { buildProgram } from '../src/gcode/generator.js';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  machine: 'marlin', // 'marlin' | 'genericCnc'
  units: 'mm',
  positioning: 'abs',
  home: true,
  safeZ: '5',
  hotend: '210',
  bed: '60',
  spindleOn: true,
  spindleRpm: '12000',
  builderMode: 'manual', // 'manual' | 'etch'
  // etch / image
  workW: '100',
  workH: '100',
  imgLoaded: false,
  imgName: '',
  etchStrategy: 'raster', // 'raster' | 'outline'
  etchControl: 'power', // 'power' (S) | 'depth' (Z)
  lineSpacing: '0.8',
  threshold: '55',
  etchFeed: '600',
  etchPower: '200',
  engraveZ: '-0.2',
  copied: false,
  seq: 4,
  moves: [
    { id: 1, type: 'G0', x: '0', y: '0', z: '', f: '', e: '', i: '', j: '' },
    { id: 2, type: 'G1', x: '', y: '', z: '-0.5', f: '300', e: '', i: '', j: '' },
    { id: 3, type: 'G1', x: '40', y: '0', z: '', f: '800', e: '', i: '', j: '' },
    { id: 4, type: 'G1', x: '40', y: '30', z: '', f: '', e: '', i: '', j: '' },
  ],
};

// Image data, held off-state (mirrors the original component fields).
let imgEl = null;
let field = null; // { gw, gh, dark: Float32Array }
let etchCache = null;
let etchSig = null;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// ---------------------------------------------------------------------------
// G-code: map UI state into a generator config + job
// ---------------------------------------------------------------------------
function buildGcode() {
  if (state.builderMode === 'etch') {
    const power = state.etchControl === 'power';
    const config = {
      machine: power ? 'laserGrbl' : 'genericCnc',
      units: state.units,
      positioning: 'abs',
      home: state.home,
      safeZ: state.safeZ,
      spindleOn: true,
      spindleRpm: state.spindleRpm || '10000',
      etch: {
        strategy: state.etchStrategy,
        control: state.etchControl,
        feed: state.etchFeed || '600',
        power: state.etchPower || '200',
        engraveZ: state.engraveZ || '-0.2',
      },
    };
    return buildProgram(config, { mode: 'etch', paths: generateEtch() });
  }

  const config = {
    machine: state.machine,
    units: state.units,
    positioning: state.positioning,
    home: state.home,
    safeZ: state.safeZ,
    hotend: state.hotend,
    bed: state.bed,
    spindleOn: state.spindleOn,
    spindleRpm: state.spindleRpm,
  };
  return buildProgram(config, { mode: 'manual', moves: state.moves });
}

// ---------------------------------------------------------------------------
// Image etch geometry  (ported verbatim; slated for extraction to src/image)
// ---------------------------------------------------------------------------
function fitRect() {
  const W = parseFloat(state.workW) || 100;
  const H = parseFloat(state.workH) || 100;
  const ar = field ? field.gw / field.gh : 1;
  let drawW = W;
  let drawH = W / ar;
  if (drawH > H) {
    drawH = H;
    drawW = H * ar;
  }
  return { W, H, drawW, drawH, offX: (W - drawW) / 2, offY: (H - drawH) / 2 };
}

function darknessAt(u, v) {
  if (!field) return 0;
  const gx = Math.min(field.gw - 1, Math.max(0, Math.round(u * (field.gw - 1))));
  const gy = Math.min(field.gh - 1, Math.max(0, Math.round(v * (field.gh - 1))));
  return field.dark[gy * field.gw + gx];
}

function generateEtch() {
  if (!field) return [];
  const sig = JSON.stringify([
    state.workW, state.workH, state.lineSpacing, state.threshold, state.etchStrategy, state.imgName,
  ]);
  if (etchCache && etchSig === sig) return etchCache;
  const out = state.etchStrategy === 'outline' ? genOutline() : genRaster();
  etchCache = out;
  etchSig = sig;
  return out;
}

function genRaster() {
  const { drawW, drawH, offX, offY } = fitRect();
  const sp = Math.max(0.15, parseFloat(state.lineSpacing) || 0.8);
  const th = (parseFloat(state.threshold) || 55) / 100;
  const rows = Math.max(1, Math.round(drawH / sp));
  const cols = Math.max(2, Math.round(drawW / sp));
  const segs = [];
  for (let r = 0; r <= rows; r++) {
    const v = r / rows;
    const yMM = offY + drawH - r * (drawH / rows);
    const ltr = r % 2 === 0;
    let start = null;
    let lastX = null;
    for (let c = 0; c <= cols; c++) {
      const u = ltr ? c / cols : 1 - c / cols;
      const xMM = offX + u * drawW;
      const on = darknessAt(u, v) >= th;
      if (on && start === null) start = xMM;
      if (start !== null && (!on || c === cols)) {
        segs.push({ poly: [{ x: start, y: yMM }, { x: lastX !== null ? lastX : xMM, y: yMM }] });
        start = null;
      }
      if (on) lastX = xMM;
    }
  }
  return segs;
}

function genOutline() {
  const gw = field.gw;
  const gh = field.gh;
  const { drawW, drawH, offX, offY } = fitRect();
  const th = (parseFloat(state.threshold) || 55) / 100;
  const val = (x, y) => field.dark[y * gw + x];
  const mm = (gx, gy) => ({ x: offX + (gx / (gw - 1)) * drawW, y: offY + (1 - gy / (gh - 1)) * drawH });
  const raw = [];
  for (let y = 0; y < gh - 1; y++) {
    for (let x = 0; x < gw - 1; x++) {
      const tl = val(x, y);
      const tr = val(x + 1, y);
      const br = val(x + 1, y + 1);
      const bl = val(x, y + 1);
      let idx = 0;
      if (tl >= th) idx |= 8;
      if (tr >= th) idx |= 4;
      if (br >= th) idx |= 2;
      if (bl >= th) idx |= 1;
      if (idx === 0 || idx === 15) continue;
      const it = (a, b) => (th - a) / ((b - a) || 1e-6);
      const top = () => mm(x + it(tl, tr), y);
      const right = () => mm(x + 1, y + it(tr, br));
      const bottom = () => mm(x + it(bl, br), y + 1);
      const left = () => mm(x, y + it(tl, bl));
      const P = (a, b) => raw.push([a, b]);
      switch (idx) {
        case 1: case 14: P(left(), bottom()); break;
        case 2: case 13: P(bottom(), right()); break;
        case 3: case 12: P(left(), right()); break;
        case 4: case 11: P(top(), right()); break;
        case 5: P(left(), top()); P(bottom(), right()); break;
        case 6: case 9: P(top(), bottom()); break;
        case 7: case 8: P(left(), top()); break;
        case 10: P(top(), right()); P(left(), bottom()); break;
      }
    }
  }
  return chain(raw);
}

function chain(raw) {
  const key = (p) => Math.round(p.x * 50) / 50 + ',' + Math.round(p.y * 50) / 50;
  const used = new Array(raw.length).fill(false);
  const map = new Map();
  raw.forEach((s, i) => [0, 1].forEach((e) => {
    const k = key(s[e]);
    if (!map.has(k)) map.set(k, []);
    map.get(k).push({ i, e });
  }));
  const polys = [];
  for (let i = 0; i < raw.length; i++) {
    if (used[i]) continue;
    used[i] = true;
    const poly = [raw[i][0], raw[i][1]];
    let grow = true;
    while (grow) {
      grow = false;
      const cand = map.get(key(poly[poly.length - 1])) || [];
      for (const c of cand) {
        if (used[c.i]) continue;
        poly.push(raw[c.i][1 - c.e]);
        used[c.i] = true;
        grow = true;
        break;
      }
    }
    grow = true;
    while (grow) {
      grow = false;
      const cand = map.get(key(poly[0])) || [];
      for (const c of cand) {
        if (used[c.i]) continue;
        poly.unshift(raw[c.i][1 - c.e]);
        used[c.i] = true;
        grow = true;
        break;
      }
    }
    polys.push({ poly });
  }
  return polys;
}

// ---------------------------------------------------------------------------
// Preview canvas  (ported; slated for extraction to src/preview)
// ---------------------------------------------------------------------------
function depthColor(z) {
  const t = Math.max(0, Math.min(1, z == null || isNaN(z) ? 0 : -z / 3));
  const a = [201, 138, 63];
  const b = [94, 52, 16];
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

function draw() {
  const cv = $('#preview');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  const W = cv.width;
  const H = cv.height;
  ctx.clearRect(0, 0, W, H);

  const etch = state.builderMode === 'etch';
  const useWork = etch || state.imgLoaded;

  let minX;
  let maxX;
  let minY;
  let maxY;
  let manualSegs = null;
  let etchSegs = null;
  if (useWork) {
    const fr = fitRect();
    minX = 0; maxX = fr.W; minY = 0; maxY = fr.H;
  }
  if (etch) {
    etchSegs = generateEtch();
  } else {
    manualSegs = [];
    let cur = { x: 0, y: 0 };
    let curZ = 0;
    const pts = [{ x: 0, y: 0 }];
    state.moves.forEach((m) => {
      const nx = m.x === '' ? cur.x : parseFloat(m.x);
      const ny = m.y === '' ? cur.y : parseFloat(m.y);
      const tz = m.z === '' ? curZ : parseFloat(m.z);
      const tx = isNaN(nx) ? cur.x : nx;
      const ty = isNaN(ny) ? cur.y : ny;
      if (m.type === 'G2' || m.type === 'G3') {
        const i = parseFloat(m.i);
        const j = parseFloat(m.j);
        if (!isNaN(i) && !isNaN(j)) {
          const cx = cur.x + i;
          const cy = cur.y + j;
          const rad = Math.hypot(cur.x - cx, cur.y - cy);
          let a0 = Math.atan2(cur.y - cy, cur.x - cx);
          const a1 = Math.atan2(ty - cy, tx - cx);
          let d = a1 - a0;
          if (m.type === 'G2') { if (d >= 0) d -= 2 * Math.PI; } else if (d <= 0) d += 2 * Math.PI;
          const N = 40;
          const poly = [];
          for (let k = 0; k <= N; k++) {
            const a = a0 + d * (k / N);
            const px = cx + rad * Math.cos(a);
            const py = cy + rad * Math.sin(a);
            poly.push({ x: px, y: py });
            pts.push({ x: px, y: py });
          }
          manualSegs.push({ kind: 'cut', poly, z: tz });
          cur = { x: tx, y: ty }; curZ = tz; return;
        }
      }
      manualSegs.push({ kind: m.type === 'G0' ? 'rapid' : 'cut', poly: [{ x: cur.x, y: cur.y }, { x: tx, y: ty }], z: tz });
      pts.push({ x: tx, y: ty });
      cur = { x: tx, y: ty };
      curZ = tz;
    });
    if (!useWork) {
      minX = Math.min(...pts.map((p) => p.x));
      maxX = Math.max(...pts.map((p) => p.x));
      minY = Math.min(...pts.map((p) => p.y));
      maxY = Math.max(...pts.map((p) => p.y));
    }
  }
  if (!isFinite(minX)) { minX = 0; maxX = 1; minY = 0; maxY = 1; }
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const pad = 38;
  const scale = Math.min((W - 2 * pad) / spanX, (H - 2 * pad) / spanY);
  const ox = (W - spanX * scale) / 2;
  const oy = (H - spanY * scale) / 2;
  const T = (p) => ({ X: ox + (p.x - minX) * scale, Y: H - (oy + (p.y - minY) * scale) });

  if (state.imgLoaded && imgEl) {
    const fr = fitRect();
    const tl = T({ x: fr.offX, y: fr.offY + fr.drawH });
    ctx.globalAlpha = etch ? 0.32 : 0.5;
    try { ctx.drawImage(imgEl, tl.X, tl.Y, fr.drawW * scale, fr.drawH * scale); } catch (e) { /* ignore */ }
    ctx.globalAlpha = 1;
  }

  ctx.strokeStyle = '#ece4d2';
  ctx.lineWidth = 1;
  for (let gx = 0; gx <= 6; gx++) {
    const X = pad + gx * (W - 2 * pad) / 6;
    ctx.beginPath(); ctx.moveTo(X, pad); ctx.lineTo(X, H - pad); ctx.stroke();
  }
  for (let gy = 0; gy <= 4; gy++) {
    const Y = pad + gy * (H - 2 * pad) / 4;
    ctx.beginPath(); ctx.moveTo(pad, Y); ctx.lineTo(W - pad, Y); ctx.stroke();
  }

  if (useWork) {
    const a = T({ x: minX, y: minY });
    const b = T({ x: maxX, y: maxY });
    ctx.strokeStyle = '#d8cdb8'; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
    ctx.strokeRect(Math.min(a.X, b.X), Math.min(a.Y, b.Y), Math.abs(b.X - a.X), Math.abs(b.Y - a.Y));
    ctx.setLineDash([]);
  }

  if (etch && etchSegs) {
    ctx.strokeStyle = '#cabfac'; ctx.lineWidth = 0.6; ctx.setLineDash([3, 3]);
    let prev = null;
    etchSegs.forEach((sg) => {
      const a = T(sg.poly[0]);
      if (prev) { ctx.beginPath(); ctx.moveTo(prev.X, prev.Y); ctx.lineTo(a.X, a.Y); ctx.stroke(); }
      prev = T(sg.poly[sg.poly.length - 1]);
    });
    ctx.setLineDash([]);
    ctx.strokeStyle = '#b06a23';
    ctx.lineWidth = state.etchStrategy === 'raster' ? 1.4 : 1.8;
    ctx.lineJoin = 'round';
    etchSegs.forEach((sg) => {
      ctx.beginPath();
      sg.poly.forEach((p, k) => { const t = T(p); k === 0 ? ctx.moveTo(t.X, t.Y) : ctx.lineTo(t.X, t.Y); });
      ctx.stroke();
    });
  } else if (manualSegs) {
    manualSegs.forEach((sg) => {
      ctx.beginPath();
      sg.poly.forEach((p, k) => { const t = T(p); k === 0 ? ctx.moveTo(t.X, t.Y) : ctx.lineTo(t.X, t.Y); });
      if (sg.kind === 'rapid') { ctx.strokeStyle = '#b3a89a'; ctx.lineWidth = 1.5; ctx.setLineDash([5, 4]); }
      else { ctx.strokeStyle = depthColor(sg.z); ctx.lineWidth = 2.6; ctx.setLineDash([]); }
      ctx.stroke();
    });
    ctx.setLineDash([]);
  }

  const o = T({ x: 0, y: 0 });
  ctx.fillStyle = '#2c6e63'; ctx.beginPath(); ctx.arc(o.X, o.Y, 4, 0, 2 * Math.PI); ctx.fill();
  ctx.fillStyle = '#6b645c'; ctx.font = '10px IBM Plex Mono, monospace'; ctx.fillText('0,0', o.X + 7, o.Y - 6);
}

// ---------------------------------------------------------------------------
// Moves table rendering
// ---------------------------------------------------------------------------
function renderMoves() {
  const list = $('#movesList');
  list.innerHTML = '';
  const isMarlin = state.machine === 'marlin';
  state.moves.forEach((m, idx) => {
    const isArc = m.type === 'G2' || m.type === 'G3';
    const row = document.createElement('div');
    row.className = 'move-row';
    row.innerHTML = `
      <div class="move-num">${String(idx + 1).padStart(2, '0')}</div>
      <select data-id="${m.id}" data-role="type">
        <option value="G0">G0 rapid</option>
        <option value="G1">G1 cut</option>
        <option value="G2">G2 arc cw</option>
        <option value="G3">G3 arc ccw</option>
      </select>
      <div class="move-fields">
        <label>X<input type="text" inputmode="decimal" data-id="${m.id}" data-field="x" value="${m.x}"></label>
        <label>Y<input type="text" inputmode="decimal" data-id="${m.id}" data-field="y" value="${m.y}"></label>
        <label class="axis-z">Z<input type="text" inputmode="decimal" data-id="${m.id}" data-field="z" value="${m.z}"></label>
        <label>F<input type="text" inputmode="decimal" data-id="${m.id}" data-field="f" value="${m.f}"></label>
        ${isMarlin ? `<label class="axis-z">E<input type="text" inputmode="decimal" data-id="${m.id}" data-field="e" value="${m.e}"></label>` : ''}
        ${isArc ? `<label class="axis-arc">I<input type="text" inputmode="decimal" data-id="${m.id}" data-field="i" value="${m.i}"></label>` : ''}
        ${isArc ? `<label class="axis-arc">J<input type="text" inputmode="decimal" data-id="${m.id}" data-field="j" value="${m.j}"></label>` : ''}
      </div>
      <div class="move-ops">
        <button data-id="${m.id}" data-op="up" title="Move up">&#8593;</button>
        <button data-id="${m.id}" data-op="down" title="Move down">&#8595;</button>
        <button class="del" data-id="${m.id}" data-op="remove" title="Delete">&times;</button>
      </div>`;
    row.querySelector('select[data-role="type"]').value = m.type;
    list.appendChild(row);
  });
  $('#moveCount').textContent = state.moves.length;
}

// ---------------------------------------------------------------------------
// Render: reflect state into the DOM
// ---------------------------------------------------------------------------
function setActive(selector, attr, value) {
  $$(selector).forEach((btn) => btn.classList.toggle('active', btn.dataset[attr] === value));
}

function render() {
  const isMarlin = state.machine === 'marlin';
  const isEtch = state.builderMode === 'etch';

  setActive('.machine-tabs .tab', 'machine', state.machine);
  setActive('.seg.light .mode', 'mode', state.builderMode);
  setActive('#unitsSeg button', 'units', state.units);
  setActive('#posSeg button', 'pos', state.positioning);
  setActive('#strategySeg button', 'strategy', state.etchStrategy);
  setActive('#controlSeg button', 'control', state.etchControl);

  $('#homeToggle').classList.toggle('on', state.home);
  $('#homeToggle').textContent = state.home ? 'G28 · ON' : 'OFF';
  $('#spindleToggle').classList.toggle('on', state.spindleOn);
  $('#spindleToggle').textContent = state.spindleOn ? 'M3 · ON' : 'OFF';

  $('#marlinFields').classList.toggle('hidden', !isMarlin);
  $('#cncFields').classList.toggle('hidden', isMarlin);
  $('#manualCard').classList.toggle('hidden', isEtch);
  $('#etchCard').classList.toggle('hidden', !isEtch);

  // sync input values
  $$('[data-key]').forEach((el) => { if (el.value !== state[el.dataset.key]) el.value = state[el.dataset.key]; });

  // etch sub-fields
  $('#lineSpacingField').classList.toggle('hidden', state.etchStrategy !== 'raster');
  $('#powerField').classList.toggle('hidden', state.etchControl !== 'power');
  $('#depthField').classList.toggle('hidden', state.etchControl !== 'depth');

  // file chip
  $('#fileChip').classList.toggle('hidden', !state.imgLoaded);
  $('#noImageHint').classList.toggle('hidden', state.imgLoaded);
  $('#fileName').textContent = state.imgName;

  // etch info
  const segCount = isEtch && state.imgLoaded ? generateEtch().length : 0;
  let etchInfo;
  if (!state.imgLoaded) etchInfo = 'No image yet — upload a graphic to generate a toolpath.';
  else if (!segCount) etchInfo = 'No burn regions at this cutoff — lower the darkness %.';
  else etchInfo = `${segCount} ${state.etchStrategy === 'raster' ? 'scan passes' : 'outline paths'}`;
  $('#etchInfo').textContent = etchInfo;

  renderMoves();

  const gcode = buildGcode();
  $('#gcode').textContent = gcode;
  $('#lineCount').textContent = gcode.split('\n').length;
  $('#copyBtn').textContent = state.copied ? 'Copied ✓' : 'Copy';

  draw();
}

function update(patch) {
  Object.assign(state, patch);
  etchCache = null; // any state change can invalidate the etch toolpath
  render();
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------
function wire() {
  $$('.machine-tabs .tab').forEach((b) => b.addEventListener('click', () => update({ machine: b.dataset.machine })));
  $$('.seg.light .mode').forEach((b) => b.addEventListener('click', () => update({ builderMode: b.dataset.mode })));
  $$('#unitsSeg button').forEach((b) => b.addEventListener('click', () => update({ units: b.dataset.units })));
  $$('#posSeg button').forEach((b) => b.addEventListener('click', () => update({ positioning: b.dataset.pos })));
  $$('#strategySeg button').forEach((b) => b.addEventListener('click', () => update({ etchStrategy: b.dataset.strategy })));
  $$('#controlSeg button').forEach((b) => b.addEventListener('click', () => update({ etchControl: b.dataset.control })));

  $('#homeToggle').addEventListener('click', () => update({ home: !state.home }));
  $('#spindleToggle').addEventListener('click', () => update({ spindleOn: !state.spindleOn }));

  document.body.addEventListener('change', (e) => {
    const key = e.target.dataset.key;
    if (key) update({ [key]: e.target.value });
  });

  // moves: delegated input/change/click
  $('#movesList').addEventListener('input', (e) => {
    const id = +e.target.dataset.id;
    const f = e.target.dataset.field;
    if (!id || !f) return;
    state.moves = state.moves.map((m) => (m.id === id ? { ...m, [f]: e.target.value } : m));
    etchCache = null;
    const g = buildGcode();
    $('#gcode').textContent = g;
    $('#lineCount').textContent = g.split('\n').length;
    draw();
  });
  $('#movesList').addEventListener('change', (e) => {
    if (e.target.dataset.role !== 'type') return;
    const id = +e.target.dataset.id;
    update({ moves: state.moves.map((m) => (m.id === id ? { ...m, type: e.target.value } : m)) });
  });
  $('#movesList').addEventListener('click', (e) => {
    const op = e.target.dataset.op;
    const id = +e.target.dataset.id;
    if (!op) return;
    if (op === 'remove') update({ moves: state.moves.filter((m) => m.id !== id) });
    else if (op === 'up') {
      const i = state.moves.findIndex((m) => m.id === id);
      if (i > 0) { const a = [...state.moves]; [a[i - 1], a[i]] = [a[i], a[i - 1]]; update({ moves: a }); }
    } else if (op === 'down') {
      const i = state.moves.findIndex((m) => m.id === id);
      if (i >= 0 && i < state.moves.length - 1) { const a = [...state.moves]; [a[i + 1], a[i]] = [a[i], a[i + 1]]; update({ moves: a }); }
    }
  });

  $('#addMoveBtn').addEventListener('click', () => {
    const id = state.seq + 1;
    update({ seq: id, moves: [...state.moves, { id, type: 'G1', x: '', y: '', z: '', f: '', e: '', i: '', j: '' }] });
  });

  $('#imageInput').addEventListener('change', onImagePick);
  $('#removeImageBtn').addEventListener('click', () => {
    imgEl = null; field = null; etchCache = null;
    update({ imgLoaded: false, imgName: '' });
  });

  $('#copyBtn').addEventListener('click', () => {
    const txt = buildGcode();
    if (navigator.clipboard) navigator.clipboard.writeText(txt).catch(() => {});
    update({ copied: true });
    clearTimeout(wire._ct);
    wire._ct = setTimeout(() => update({ copied: false }), 1500);
  });
  $('#downloadBtn').addEventListener('click', () => {
    const blob = new Blob([buildGcode()], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'program.gcode';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}

function onImagePick(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  const img = new Image();
  img.onload = () => {
    const maxD = 220;
    const sc = Math.min(1, maxD / Math.max(img.width, img.height));
    const gw = Math.max(2, Math.round(img.width * sc));
    const gh = Math.max(2, Math.round(img.height * sc));
    const off = document.createElement('canvas');
    off.width = gw; off.height = gh;
    const octx = off.getContext('2d');
    octx.fillStyle = '#fff'; octx.fillRect(0, 0, gw, gh);
    octx.drawImage(img, 0, 0, gw, gh);
    const data = octx.getImageData(0, 0, gw, gh).data;
    const dark = new Float32Array(gw * gh);
    for (let p = 0; p < gw * gh; p++) {
      const r = data[p * 4];
      const g = data[p * 4 + 1];
      const b = data[p * 4 + 2];
      const a = data[p * 4 + 3];
      const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      dark[p] = a < 20 ? 0 : 1 - lum;
    }
    imgEl = img;
    field = { gw, gh, dark };
    etchCache = null;
    update({ imgLoaded: true, imgName: file.name, builderMode: 'etch' });
  };
  img.src = URL.createObjectURL(file);
}

// ---------------------------------------------------------------------------
wire();
render();
