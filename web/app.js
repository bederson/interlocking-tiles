// Tile geometry, ported from generate_tiles.py, for a fast client-side preview.
// The exported files are always regenerated authoritatively by the Python
// server from the same explicit harmonics this preview is showing, so what
// you see here is exactly what gets written to disk.

function edgeOffset(t, harmonics) {
  const envelope = Math.sin(Math.PI * t);
  let wiggle = 0;
  for (const [k, a] of harmonics) wiggle += a * Math.sin(2 * Math.PI * k * t);
  return envelope * wiggle;
}

function normalize([x, y]) {
  const len = Math.hypot(x, y);
  if (len < 1e-12) return [0, 0];
  return [x / len, y / len];
}

function edgePoints(p0, p1, harmonics, n) {
  const dx = p1[0] - p0[0], dy = p1[1] - p0[1];
  const normal = normalize([dy, -dx]);
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const bx = p0[0] + dx * t, by = p0[1] + dy * t;
    const g = edgeOffset(t, harmonics);
    pts.push([bx + normal[0] * g, by + normal[1] * g]);
  }
  return pts;
}

function tileCutOutline(size, harmonics, n) {
  const corners = [[0, 0], [size, 0], [size, size], [0, size]];
  let outline = [];
  for (let i = 0; i < 4; i++) {
    const pts = edgePoints(corners[i], corners[(i + 1) % 4], harmonics, n);
    outline = outline.concat(pts.slice(0, -1));
  }
  return outline;
}

function arcPoints(center, radius, a0deg, a1deg, n) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const ang = ((a0deg + (a1deg - a0deg) * t) * Math.PI) / 180;
    pts.push([center[0] + radius * Math.cos(ang), center[1] + radius * Math.sin(ang)]);
  }
  return pts;
}

const MOTIFS = ["A", "B", "S"];

function truchetFacePaths(size, motif, n = 24) {
  const r = size / 2;
  const mid = size / 2;
  if (motif === "A") {
    return [arcPoints([0, 0], r, 0, 90, n), arcPoints([size, size], r, 180, 270, n)];
  }
  if (motif === "B") {
    return [arcPoints([size, 0], r, 90, 180, n), arcPoints([0, size], r, 270, 360, n)];
  }
  return [
    [[mid, 0], [mid, size]],
    [[0, mid], [size, mid]],
  ];
}

// Extend a centerline past both ends, continuing each end's local
// direction. Every motif centerline stops exactly at an edge's flat,
// unwiggled midpoint, but the real cut edge immediately bows outward (a
// bump) on one side of that point -- stopping exactly there falls short
// of the bump, leaving a visible gap. Overshooting fixes that; the
// overshoot itself is harmless since whatever lands outside the tile's
// real (wiggly) boundary is simply removed when the tile is cut out.
function extendPolylineEnds(points, amount) {
  const step = (pFrom, pTo, dist) => {
    const dx = pTo[0] - pFrom[0], dy = pTo[1] - pFrom[1];
    const length = Math.hypot(dx, dy);
    if (length < 1e-12) return pTo;
    return [pTo[0] + (dx / length) * dist, pTo[1] + (dy / length) * dist];
  };
  const start = step(points[1], points[0], amount);
  const end = step(points[points.length - 2], points[points.length - 1], amount);
  return [start].concat(points, [end]);
}

function maxWiggleAmplitude(harmonics) {
  return harmonics.reduce((sum, [, a]) => sum + Math.abs(a), 0);
}

function thickenPolyline(points, width) {
  const half = width / 2;
  const n = points.length;
  const left = [], right = [];
  for (let i = 0; i < n; i++) {
    const segNormals = [];
    if (i > 0) {
      const d = [points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]];
      segNormals.push(normalize([d[1], -d[0]]));
    }
    if (i < n - 1) {
      const d = [points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]];
      segNormals.push(normalize([d[1], -d[0]]));
    }
    const sum = segNormals.reduce((a, b) => [a[0] + b[0], a[1] + b[1]], [0, 0]);
    const normal = normalize(sum);
    left.push([points[i][0] + normal[0] * half, points[i][1] + normal[1] * half]);
    right.push([points[i][0] - normal[0] * half, points[i][1] - normal[1] * half]);
  }
  return left.concat(right.reverse());
}

function offsetPolygon(points, delta) {
  if (delta === 0) return points;
  const n = points.length;
  const result = [];
  for (let i = 0; i < n; i++) {
    const pPrev = points[(i - 1 + n) % n], p = points[i], pNext = points[(i + 1) % n];
    const e1 = [p[0] - pPrev[0], p[1] - pPrev[1]];
    const e2 = [pNext[0] - p[0], pNext[1] - p[1]];
    const n1 = normalize([e1[1], -e1[0]]);
    const n2 = normalize([e2[1], -e2[0]]);
    const avg = normalize([n1[0] + n2[0], n1[1] + n2[1]]);
    result.push([p[0] + avg[0] * delta, p[1] + avg[1] * delta]);
  }
  return result;
}

function pointsToPath(points, closed = true) {
  if (!points.length) return "";
  let d = `M ${points[0][0].toFixed(4)},${points[0][1].toFixed(4)}`;
  for (let i = 1; i < points.length; i++) d += ` L ${points[i][0].toFixed(4)},${points[i][1].toFixed(4)}`;
  if (closed) d += " Z";
  return d;
}

// Small seeded PRNG (mulberry32) so the preview's randomized-edge mode and
// its demo grid arrangement are deterministic per seed, without needing to
// match Python's RNG bit-for-bit (the export sends explicit harmonics, so
// exact cross-language RNG parity is never required for correctness).
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function randomHarmonics(amplitude, seed) {
  const rng = mulberry32(seed);
  const nHarmonics = 1 + Math.floor(rng() * 3); // 1..3
  const pool = [1, 2, 3, 4, 5];
  const ks = [];
  for (let i = 0; i < nHarmonics && pool.length; i++) ks.push(pool.splice(Math.floor(rng() * pool.length), 1)[0]);
  const raw = ks.map(() => 0.3 + rng() * 0.7);
  const total = raw.reduce((a, b) => a + b, 0) || 1;
  return ks.map((k, i) => [k, (amplitude * raw[i]) / total]);
}

// ---------------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------------

const UNIT_CONFIG = {
  in: {
    size: { min: 1, max: 4, step: 0.25, default: 2, decimals: 2 },
    amplitude: { min: 0.05, max: 0.5, step: 0.05, default: 0.25, decimals: 2 },
    kerf: { min: -0.02, max: 0.02, step: 0.005, default: 0, decimals: 3 },
    engraveWidth: { min: 0.1, max: 1.0, step: 0.05, default: 0.5, decimals: 2 },
    sheetWidth: { step: 0.25, default: 36, decimals: 2 },
    sheetHeight: { step: 0.25, default: 18, decimals: 2 },
    sheetMargin: 0.25,
  },
  mm: {
    size: { min: 25, max: 100, step: 5, default: 50, decimals: 0 },
    amplitude: { min: 1, max: 12, step: 1, default: 6, decimals: 0 },
    kerf: { min: -0.5, max: 0.5, step: 0.1, default: 0, decimals: 2 },
    engraveWidth: { min: 2, max: 25, step: 1, default: 13, decimals: 0 },
    sheetWidth: { step: 5, default: 900, decimals: 0 },
    sheetHeight: { step: 5, default: 450, decimals: 0 },
    sheetMargin: 6,
  },
};

const el = (id) => document.getElementById(id);
const svgNS = "http://www.w3.org/2000/svg";

let units = "in";
let previewSeed = Date.now() % 100000;

function configureSlider(input, cfg, ticksEl) {
  input.min = cfg.min;
  input.max = cfg.max;
  input.step = cfg.step;
  input.value = cfg.default;
  ticksEl.innerHTML = "";
  for (let v = cfg.min; v <= cfg.max + 1e-9; v += cfg.step) {
    const opt = document.createElement("option");
    opt.value = v.toFixed(cfg.decimals);
    ticksEl.appendChild(opt);
  }
}

function applyUnitConfig() {
  const cfg = UNIT_CONFIG[units];
  configureSlider(el("size"), cfg.size, el("sizeTicks"));
  configureSlider(el("amplitude"), cfg.amplitude, el("amplitudeTicks"));
  configureSlider(el("kerf"), cfg.kerf, el("kerfTicks"));
  configureSlider(el("engraveWidth"), cfg.engraveWidth, el("engraveWidthTicks"));
  el("sheetWidth").step = cfg.sheetWidth.step;
  el("sheetWidth").value = cfg.sheetWidth.default;
  el("sheetHeight").step = cfg.sheetHeight.step;
  el("sheetHeight").value = cfg.sheetHeight.default;
  updateReadouts();
}

function updateReadouts() {
  const cfg = UNIT_CONFIG[units];
  el("sizeValue").textContent = `${parseFloat(el("size").value).toFixed(cfg.size.decimals)} ${units}`;
  el("amplitudeValue").textContent = `${parseFloat(el("amplitude").value).toFixed(cfg.amplitude.decimals)} ${units}`;
  el("kerfValue").textContent = `${parseFloat(el("kerf").value).toFixed(cfg.kerf.decimals)} ${units}`;
  el("engraveWidthValue").textContent = `${parseFloat(el("engraveWidth").value).toFixed(cfg.engraveWidth.decimals)} ${units}`;
  el("sheetWidthValue").textContent = units;
  el("sheetHeightValue").textContent = units;
  el("wigglesValue").textContent = el("wiggles").value;
  el("countValue").textContent = el("count").value;
}

function sheetGridDims(size, sheetW, sheetH, margin) {
  if (size + margin > sheetW || size + margin > sheetH) return null;
  const cols = Math.max(1, Math.floor((sheetW + margin) / (size + margin)));
  const rows = Math.max(1, Math.floor((sheetH + margin) / (size + margin)));
  return { cols, rows };
}

function updateSheetStatus() {
  const size = parseFloat(el("size").value);
  const sheetW = parseFloat(el("sheetWidth").value);
  const sheetH = parseFloat(el("sheetHeight").value);
  const margin = UNIT_CONFIG[units].sheetMargin;
  const count = parseInt(el("count").value, 10);
  const statusEl = el("sheetStatus");
  const dims = sheetGridDims(size, sheetW, sheetH, margin);
  if (!dims) {
    statusEl.textContent = `⚠ A ${size} ${units} tile does not fit on a ${sheetW} × ${sheetH} ${units} sheet.`;
    statusEl.classList.add("error");
    return;
  }
  statusEl.classList.remove("error");
  const perSheet = dims.cols * dims.rows;
  const sheetCount = Math.ceil(count / perSheet);
  statusEl.textContent = `${dims.cols} × ${dims.rows} = ${perSheet} tiles per sheet → ${sheetCount} sheet${sheetCount === 1 ? "" : "s"} for ${count} tiles.`;
}

function currentEdgeMode() {
  return document.querySelector('input[name="edgeMode"]:checked').value;
}

function currentHarmonics() {
  const amplitude = parseFloat(el("amplitude").value);
  if (currentEdgeMode() === "random") {
    const seed = parseInt(el("edgeSeed").value, 10) || 0;
    return randomHarmonics(amplitude, seed);
  }
  return [[parseInt(el("wiggles").value, 10), amplitude]];
}

function redraw() {
  updateReadouts();

  const size = parseFloat(el("size").value);
  const kerf = parseFloat(el("kerf").value);
  const engraveWidth = parseFloat(el("engraveWidth").value);
  const harmonics = currentHarmonics();
  const samples = 60;

  let outline = tileCutOutline(size, harmonics, samples);
  outline = offsetPolygon(outline, kerf);
  const cutPath = pointsToPath(outline, true);
  const overshoot = maxWiggleAmplitude(harmonics);

  const count = parseInt(el("count").value, 10);
  const gridCols = Math.max(1, Math.ceil(Math.sqrt(count)));
  const gridRows = Math.max(1, Math.ceil(count / gridCols));
  const rotRng = mulberry32(previewSeed);
  const motifRng = mulberry32(previewSeed + 99991);
  const rotations = [0, 90, 180, 270];

  const svg = el("previewSvg");
  svg.setAttribute("viewBox", `0 0 ${size * gridCols} ${size * gridRows}`);
  svg.innerHTML = "";

  const strokeWidth = size * 0.008;

  for (let i = 0; i < count; i++) {
    const row = Math.floor(i / gridCols);
    const col = i % gridCols;
    const angle = rotations[Math.floor(rotRng() * rotations.length)];
    const motif = MOTIFS[Math.floor(motifRng() * MOTIFS.length)];
    const g = document.createElementNS(svgNS, "g");
    g.setAttribute(
      "transform",
      `translate(${col * size},${row * size}) rotate(${angle},${size / 2},${size / 2})`
    );

    const cutEl = document.createElementNS(svgNS, "path");
    cutEl.setAttribute("d", cutPath);
    cutEl.setAttribute("fill", "none");
    cutEl.setAttribute("stroke", "#d1372c");
    cutEl.setAttribute("stroke-width", strokeWidth);
    g.appendChild(cutEl);

    const ribbons = truchetFacePaths(size, motif).map((arc) =>
      thickenPolyline(extendPolylineEnds(arc, overshoot), engraveWidth)
    );
    for (const ribbon of ribbons) {
      const ribbonEl = document.createElementNS(svgNS, "path");
      ribbonEl.setAttribute("d", pointsToPath(ribbon, true));
      ribbonEl.setAttribute("fill", "#2b5fb0");
      ribbonEl.setAttribute("stroke", "none");
      g.appendChild(ribbonEl);
    }

    svg.appendChild(g);
  }

  el("previewCaption").textContent =
    `Preview of all ${count} tile${count === 1 ? "" : "s"} you're about to export, each shown in a random ` +
    "rotation (0/90/180/270°) to demonstrate every orientation still interlocks. Red = cut, blue = engrave. " +
    "The exported files themselves are unrotated -- physical rotation happens when you place the cut tiles.";

  updateSheetStatus();
}

function harmonicsToSpec(harmonics) {
  return harmonics.map(([k, a]) => `${k}:${a}`).join(",");
}

async function doExport() {
  const status = el("exportStatus");
  status.textContent = "Exporting…";
  const payload = {
    size: parseFloat(el("size").value),
    units,
    amplitude: parseFloat(el("amplitude").value),
    harmonics: harmonicsToSpec(currentHarmonics()),
    kerf_adjust: parseFloat(el("kerf").value),
    engrave_width: parseFloat(el("engraveWidth").value),
    count: parseInt(el("count").value, 10),
    face_seed: parseInt(el("faceSeed").value, 10),
    output_dir: el("outputDir").value || null,
    sheet_width: parseFloat(el("sheetWidth").value),
    sheet_height: parseFloat(el("sheetHeight").value),
  };
  try {
    const resp = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) throw new Error(data.error || `HTTP ${resp.status}`);
    status.textContent =
      `Wrote ${data.tile_count} tiles + ${data.sheet_files.length} sheet(s), ` +
      `${data.frame_count} frame + ${data.corner_count} corner piece(s) for a ` +
      `${data.grid_cols}x${data.grid_rows} grid, to ${data.output_dir}/`;
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  }
}

// ---------------------------------------------------------------------------
// Persist control panel values across sessions (this browser only -- a
// lightweight per-viewer convenience, not shared/critical data).
// ---------------------------------------------------------------------------

const STORAGE_KEY = "tileConsole.controls";
const PERSISTED_FIELD_IDS = [
  "size", "amplitude", "wiggles", "edgeSeed", "kerf", "engraveWidth",
  "count", "faceSeed", "sheetWidth", "sheetHeight", "outputDir",
];

function currentControlState() {
  const state = { units, edgeMode: currentEdgeMode() };
  for (const id of PERSISTED_FIELD_IDS) state[id] = el(id).value;
  return state;
}

function saveControlState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(currentControlState()));
  } catch (err) {
    // private browsing / storage disabled / etc -- persistence is a nicety, not required
  }
}

function loadControlState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (err) {
    return null;
  }
}

function applyControlState(state) {
  if (!state) return;
  if (state.edgeMode) {
    const radio = document.querySelector(`input[name="edgeMode"][value="${state.edgeMode}"]`);
    if (radio) radio.checked = true;
    const isRandom = state.edgeMode === "random";
    el("wigglesControl").hidden = isRandom;
    el("edgeSeedControl").hidden = !isRandom;
  }
  for (const id of PERSISTED_FIELD_IDS) {
    if (state[id] !== undefined && state[id] !== null && state[id] !== "") el(id).value = state[id];
  }
}

function wireEvents() {
  document.querySelectorAll('input[name="units"]').forEach((r) =>
    r.addEventListener("change", (e) => {
      units = e.target.value;
      applyUnitConfig();
      redraw();
    })
  );

  document.querySelectorAll('input[name="edgeMode"]').forEach((r) =>
    r.addEventListener("change", (e) => {
      const isRandom = e.target.value === "random";
      el("wigglesControl").hidden = isRandom;
      el("edgeSeedControl").hidden = !isRandom;
      redraw();
    })
  );

  ["size", "amplitude", "wiggles", "kerf", "engraveWidth", "count"].forEach((id) => el(id).addEventListener("input", redraw));
  el("edgeSeed").addEventListener("input", redraw);
  ["sheetWidth", "sheetHeight"].forEach((id) => el(id).addEventListener("input", updateSheetStatus));

  el("edgeSeedRandomize").addEventListener("click", () => {
    el("edgeSeed").value = Math.floor(Math.random() * 100000);
    redraw();
    saveControlState();
  });
  el("faceSeedRandomize").addEventListener("click", () => {
    el("faceSeed").value = Math.floor(Math.random() * 100000);
    saveControlState();
  });
  el("shuffleBtn").addEventListener("click", () => {
    previewSeed = Math.floor(Math.random() * 100000);
    redraw();
  });

  el("exportBtn").addEventListener("click", doExport);

  document.addEventListener("input", saveControlState);
  document.addEventListener("change", saveControlState);
}

const savedControlState = loadControlState();
if (savedControlState && savedControlState.units) units = savedControlState.units;
document.querySelector(`input[name="units"][value="${units}"]`).checked = true;

applyUnitConfig();
applyControlState(savedControlState);
wireEvents();
redraw();
