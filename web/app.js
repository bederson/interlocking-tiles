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

// Frame/corner pieces: built against a canonical bottom (frame) or
// bottom-left corner (corner) tile edge, exactly mirroring
// frame_piece_outline / corner_piece_outline in generate_tiles.py -- see
// that file's comments for why the tile-facing side is guaranteed to fit.
//
// Their short end caps get a "keyhole"/dog-bone connector (a neck
// narrower than the bulb it leads to, so a mated pair can't be pulled
// straight apart) instead of a plain straight edge, so pieces connect to
// their neighbor around the border. One fixed convention (tab always at
// the "x=size" end, socket always at the "start" end) makes every tab
// meet the next piece's socket automatically going around the loop in one
// consistent direction. Mirrors generate_tiles.py's CONNECTOR_* ratios.
const CONNECTOR_NECK_RATIO = 0.1125;
const CONNECTOR_BULB_RADIUS_RATIO = 0.21;
const CONNECTOR_STEM_RATIO = 0.35;

function connectorProtrusion(frameWidth) {
  return frameWidth * (CONNECTOR_STEM_RATIO + CONNECTOR_BULB_RADIUS_RATIO);
}

function keyholeCapPoints(p0, p1, bulgeDirection, neckHalfWidth, bulbRadius, stemLength, n = 24) {
  const mid = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2];
  const capDir = normalize([p1[0] - p0[0], p1[1] - p0[1]]);
  const h = Math.sqrt(bulbRadius * bulbRadius - neckHalfWidth * neckHalfWidth);

  const localToGlobal = (u, v) => [
    mid[0] + capDir[0] * u + bulgeDirection[0] * v,
    mid[1] + capDir[1] * u + bulgeDirection[1] * v,
  ];

  const center = localToGlobal(0, stemLength);
  const bMinus = localToGlobal(-neckHalfWidth, 0);
  const bPlus = localToGlobal(neckHalfWidth, 0);
  const pMinus = localToGlobal(-neckHalfWidth, stemLength - h);
  const pPlus = localToGlobal(neckHalfWidth, stemLength - h);

  const angleFromCenter = (point) => {
    const vx = point[0] - center[0];
    const vy = point[1] - center[1];
    const u = vx * capDir[0] + vy * capDir[1];
    const v = vx * bulgeDirection[0] + vy * bulgeDirection[1];
    return Math.atan2(v, u);
  };

  const phiMinus = angleFromCenter(pMinus);
  const phiPlus = angleFromCenter(pPlus);
  const twoPi = 2 * Math.PI;
  const sweep = (((phiPlus - phiMinus) % twoPi) + twoPi) % twoPi - twoPi;

  const arc = [];
  for (let i = 0; i <= n; i++) {
    const phi = phiMinus + (sweep * i) / n;
    arc.push([
      center[0] + bulbRadius * (Math.cos(phi) * capDir[0] + Math.sin(phi) * bulgeDirection[0]),
      center[1] + bulbRadius * (Math.cos(phi) * capDir[1] + Math.sin(phi) * bulgeDirection[1]),
    ]);
  }
  return [p0, bMinus].concat(arc, [bPlus, p1]);
}

function connectorCap(p0, p1, outwardDirection, kind, frameWidth) {
  const neckHalfWidth = frameWidth * CONNECTOR_NECK_RATIO;
  const bulbRadius = frameWidth * CONNECTOR_BULB_RADIUS_RATIO;
  const stemLength = frameWidth * CONNECTOR_STEM_RATIO;
  const bulge = kind === "tab" ? outwardDirection : [-outwardDirection[0], -outwardDirection[1]];
  return keyholeCapPoints(p0, p1, bulge, neckHalfWidth, bulbRadius, stemLength);
}

function frameOutline(size, frameWidth, harmonics, n) {
  const inner = edgePoints([0, 0], [size, 0], harmonics, n);
  const tab = connectorCap([size, 0], [size, -frameWidth], [1, 0], "tab", frameWidth);
  const socket = connectorCap([0, -frameWidth], [0, 0], [-1, 0], "socket", frameWidth);
  return inner.slice(0, -1).concat(tab, [[0, -frameWidth]], socket.slice(1));
}

function frameEngraveLines(size, frameWidth, harmonics, engraveWidth, engraveLinesN) {
  const mid = size / 2;
  const overshoot = maxWiggleAmplitude(harmonics);
  const line = extendPolylineEnds([[mid, 0], [mid, -frameWidth]], overshoot);
  return parallelLines(line, engraveWidth, engraveLinesN);
}

function cornerOutline(size, frameWidth, harmonics, n) {
  const bottom = edgePoints([0, 0], [size, 0], harmonics, n).slice().reverse();
  const left = edgePoints([0, size], [0, 0], harmonics, n).slice().reverse();
  const inner = bottom.concat(left.slice(1));
  const tab = connectorCap([size, -frameWidth], [size, 0], [1, 0], "tab", frameWidth);
  const socket = connectorCap([0, size], [-frameWidth, size], [0, 1], "socket", frameWidth);
  return inner.slice(0, -1).concat(socket, [[-frameWidth, -frameWidth], [size, -frameWidth]], tab.slice(1));
}

function cornerEngraveLines(size, frameWidth, harmonics, engraveWidth, engraveLinesN) {
  const mid = size / 2;
  const overshoot = maxWiggleAmplitude(harmonics);
  const bottomLine = extendPolylineEnds([[mid, 0], [mid, -frameWidth]], overshoot);
  const leftLine = extendPolylineEnds([[0, mid], [-frameWidth, mid]], overshoot);
  return parallelLines(bottomLine, engraveWidth, engraveLinesN).concat(
    parallelLines(leftLine, engraveWidth, engraveLinesN)
  );
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

function openPolylineNormals(points) {
  const n = points.length;
  const normals = [];
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
    normals.push(normalize(sum));
  }
  return normals;
}

// Return `n` open polylines, evenly spaced across `width` and offset from
// the centerline -- N distinct engraved strokes spanning the same width a
// single filled channel would, rather than one solid band. n=1 places a
// single line along the centerline itself.
function parallelLines(points, width, n) {
  const normals = openPolylineNormals(points);
  let offsets;
  if (n <= 1) {
    offsets = [0];
  } else {
    const step = width / (n - 1);
    offsets = Array.from({ length: n }, (_, i) => -width / 2 + i * step);
  }
  return offsets.map((off) => points.map((p, i) => [p[0] + normals[i][0] * off, p[1] + normals[i][1] * off]));
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
    engraveWidth: { min: 0.1, max: 0.5, step: 0.05, default: 0.5, decimals: 2 },
    sheetMargin: 0.25,
    frameWidth: 0.5,
    nestGap: 0.125,
  },
  mm: {
    size: { min: 25, max: 100, step: 5, default: 50, decimals: 0 },
    amplitude: { min: 1, max: 12, step: 1, default: 6, decimals: 0 },
    kerf: { min: -0.5, max: 0.5, step: 0.1, default: 0, decimals: 2 },
    engraveWidth: { min: 2, max: 12, step: 1, default: 12, decimals: 0 },
    sheetMargin: 6,
    frameWidth: 12.7,
    nestGap: 3.175,
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
  updateReadouts();
}

function updateReadouts() {
  const cfg = UNIT_CONFIG[units];
  el("sizeValue").textContent = `${parseFloat(el("size").value).toFixed(cfg.size.decimals)} ${units}`;
  el("amplitudeValue").textContent = `${parseFloat(el("amplitude").value).toFixed(cfg.amplitude.decimals)} ${units}`;
  el("kerfValue").textContent = `${parseFloat(el("kerf").value).toFixed(cfg.kerf.decimals)} ${units}`;
  el("engraveWidthValue").textContent = `${parseFloat(el("engraveWidth").value).toFixed(cfg.engraveWidth.decimals)} ${units}`;
  el("engraveLinesValue").textContent = el("engraveLines").value;
  el("columnsValue").textContent = el("columns").value;
  el("wigglesValue").textContent = el("wiggles").value;
  el("countValue").textContent = el("count").value;
}

function frameAndCornerCounts(gridCols, gridRows) {
  const frameCount = Math.max(0, 2 * (gridCols - 2)) + Math.max(0, 2 * (gridRows - 2));
  const cornerCount = gridCols >= 2 && gridRows >= 2 ? 4 : 0;
  return [frameCount, cornerCount];
}

// Mirrors wrap_flow_layout() + paired_frame_item()/paired_corner_item() in
// generate_tiles.py: `columns` tiles establishes a fixed material width,
// and tiles, then paired frame units, then paired corner units flow left
// to right within it in that order, wrapping to a new row whenever the
// next piece wouldn't fit -- so that width is never exceeded regardless
// of what's flowing. Frame/corner pieces are always even in count, so
// every one of them pairs up (see generate_tiles.py's module comment on
// cutting-sheet nesting).
function requiredMaterialSize(size, frameWidth, count, gridCols, gridRows, columns, margin, overshoot) {
  const [frameCount, cornerCount] = frameAndCornerCounts(gridCols, gridRows);
  const r = connectorProtrusion(frameWidth);
  const gap = UNIT_CONFIG[units].nestGap;
  const framePairCount = frameCount / 2;
  const cornerPairCount = cornerCount / 2;

  const items = [];
  for (let i = 0; i < count; i++) {
    items.push({ width: size + 2 * overshoot, height: size + 2 * overshoot });
  }
  for (let i = 0; i < framePairCount; i++) {
    items.push({ width: size + 2 * r, height: 2 * frameWidth + gap + 2 * overshoot });
  }
  for (let i = 0; i < cornerPairCount; i++) {
    items.push({ width: size + 2 * frameWidth, height: size + 2 * frameWidth + gap });
  }

  const tileWidth = size + 2 * overshoot;
  const rowWidth = columns * tileWidth + (columns + 1) * margin;

  let cursorX = margin;
  let cursorY = margin;
  let rowHeight = 0;
  let rowHasItem = false;
  for (const item of items) {
    if (rowHasItem && cursorX + item.width + margin > rowWidth) {
      cursorY += rowHeight + margin;
      cursorX = margin;
      rowHeight = 0;
      rowHasItem = false;
    }
    cursorX += item.width + margin;
    rowHeight = Math.max(rowHeight, item.height);
    rowHasItem = true;
  }
  const sheetH = cursorY + rowHeight + margin;

  return { sheetW: rowWidth, sheetH, frameCount, cornerCount, totalItems: count + frameCount + cornerCount };
}

function updateSheetStatus() {
  const size = parseFloat(el("size").value);
  const frameWidth = UNIT_CONFIG[units].frameWidth;
  const margin = UNIT_CONFIG[units].sheetMargin;
  const count = parseInt(el("count").value, 10);
  const columns = parseInt(el("columns").value, 10);
  const gridCols = Math.max(1, Math.ceil(Math.sqrt(count)));
  const gridRows = Math.max(1, Math.ceil(count / gridCols));
  const overshoot = maxWiggleAmplitude(currentHarmonics());

  const { sheetW, sheetH, frameCount, cornerCount, totalItems } = requiredMaterialSize(
    size, frameWidth, count, gridCols, gridRows, columns, margin, overshoot
  );
  const statusEl = el("sheetStatus");
  statusEl.classList.remove("error");
  statusEl.textContent =
    `${count} tiles + ${frameCount} frame + ${cornerCount} corner = ${totalItems} pieces, ` +
    `${columns} tiles wide → required material: ${sheetW.toFixed(2)} × ${sheetH.toFixed(2)} ${units}.`;
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
  const engraveLinesN = parseInt(el("engraveLines").value, 10);
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
  const frameWidth = UNIT_CONFIG[units].frameWidth;

  // Pad by frameWidth (the frame/corner border depth) *plus* overshoot: the
  // frame/corner engrave lines deliberately extend `overshoot` past their
  // own flat outer edge (same harmless-overshoot pattern used everywhere
  // else in this file), so the real content reaches frameWidth+overshoot
  // beyond the tile grid, not just frameWidth -- without this, that
  // overshoot silently clips against the SVG's own edge.
  const pad = frameWidth + overshoot;
  const svg = el("previewSvg");
  svg.setAttribute(
    "viewBox",
    `${-pad} ${-pad} ${size * gridCols + 2 * pad} ${size * gridRows + 2 * pad}`
  );
  svg.innerHTML = "";

  const strokeWidth = size * 0.008;

  const drawPiece = (cutPts, engraveLines, transform) => {
    const g = document.createElementNS(svgNS, "g");
    g.setAttribute("transform", transform);
    const cutEl = document.createElementNS(svgNS, "path");
    cutEl.setAttribute("d", pointsToPath(cutPts, true));
    cutEl.setAttribute("fill", "none");
    cutEl.setAttribute("stroke", "#d1372c");
    cutEl.setAttribute("stroke-width", strokeWidth);
    g.appendChild(cutEl);
    for (const line of engraveLines) {
      const lineEl = document.createElementNS(svgNS, "path");
      lineEl.setAttribute("d", pointsToPath(line, false));
      lineEl.setAttribute("fill", "none");
      lineEl.setAttribute("stroke", "#2b5fb0");
      lineEl.setAttribute("stroke-width", strokeWidth);
      g.appendChild(lineEl);
    }
    svg.appendChild(g);
  };

  for (let i = 0; i < count; i++) {
    const row = Math.floor(i / gridCols);
    const col = i % gridCols;
    const angle = rotations[Math.floor(rotRng() * rotations.length)];
    const motif = MOTIFS[Math.floor(motifRng() * MOTIFS.length)];
    const engraveLines = truchetFacePaths(size, motif).flatMap((arc) =>
      parallelLines(extendPolylineEnds(arc, overshoot), engraveWidth, engraveLinesN)
    );
    drawPiece(outline, engraveLines, `translate(${col * size},${row * size}) rotate(${angle},${size / 2},${size / 2})`);
  }

  // Frame/corner pieces around the grid's border, in their correct
  // orientation for that position (unlike tiles, these aren't rotation-
  // agnostic) -- demonstrating the frame fits regardless of how each
  // border tile above happened to be randomly rotated, since every tile
  // shares the same edge curve no matter its rotation.
  if (gridCols >= 2 && gridRows >= 2) {
    const fOutline = frameOutline(size, frameWidth, harmonics, samples);
    const fLines = frameEngraveLines(size, frameWidth, harmonics, engraveWidth, engraveLinesN);
    const cOutline = cornerOutline(size, frameWidth, harmonics, samples);
    const cLines = cornerEngraveLines(size, frameWidth, harmonics, engraveWidth, engraveLinesN);

    for (let row = 0; row < gridRows; row++) {
      for (let col = 0; col < gridCols; col++) {
        const isTop = row === 0, isBottom = row === gridRows - 1;
        const isLeft = col === 0, isRight = col === gridCols - 1;
        const tx = col * size, ty = row * size;

        if ((isTop || isBottom) && (isLeft || isRight)) {
          const angle = isTop && isLeft ? 0 : isTop && isRight ? 90 : isBottom && isRight ? 180 : 270;
          drawPiece(cOutline, cLines, `translate(${tx},${ty}) rotate(${angle},${size / 2},${size / 2})`);
        } else if (isTop || isBottom || isLeft || isRight) {
          const angle = isTop ? 0 : isBottom ? 180 : isRight ? 90 : 270;
          drawPiece(fOutline, fLines, `translate(${tx},${ty}) rotate(${angle},${size / 2},${size / 2})`);
        }
      }
    }
  }

  el("previewCaption").textContent =
    `Preview of all ${count} tile${count === 1 ? "" : "s"} you're about to export, each shown in a random ` +
    "rotation (0/90/180/270°) to demonstrate every orientation still interlocks, framed by the matching " +
    "frame/corner border pieces (shown here in their correct assembly orientation). Red = cut, blue = engrave. " +
    "The exported tile files themselves are unrotated -- physical rotation happens when you place the cut tiles.";

  updateSheetStatus();
}

function harmonicsToSpec(harmonics) {
  return harmonics.map(([k, a]) => `${k}:${a}`).join(",");
}

// Same export call works two ways: the web console posts to the local
// python server; the native macOS app (no server, per its design) instead
// has a WKScriptMessageHandlerWithReply bridge registered as
// `window.webkit.messageHandlers.export`, which runs the identical
// generate_tiles.generate_batch() in-process via a small Python bridge
// script and replies with the same JSON shape -- so this is the only
// place doExport() needs to know which host it's running in.
async function exportRequest(payload) {
  const nativeBridge = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.export;
  if (nativeBridge) {
    return await nativeBridge.postMessage(payload);
  }
  const resp = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok && !data.error) throw new Error(`HTTP ${resp.status}`);
  return data;
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
    engrave_lines: parseInt(el("engraveLines").value, 10),
    count: parseInt(el("count").value, 10),
    face_seed: parseInt(el("faceSeed").value, 10),
    columns: parseInt(el("columns").value, 10),
  };
  try {
    const data = await exportRequest(payload);
    if (!data.ok) throw new Error(data.error || "export failed");
    status.textContent =
      `Wrote ${data.tile_count} tiles + ${data.frame_count} frame edge + ${data.corner_count} frame corner piece(s) ` +
      `for a ${data.grid_cols}x${data.grid_rows} grid, ${data.columns} tiles wide → required material ` +
      `${data.sheet_width.toFixed(2)} × ${data.sheet_height.toFixed(2)} ${units}, to ${data.output_dir}/`;
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
  "size", "amplitude", "wiggles", "edgeSeed", "kerf", "engraveWidth", "engraveLines",
  "count", "faceSeed", "columns",
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

  ["size", "amplitude", "wiggles", "kerf", "engraveWidth", "engraveLines", "count"].forEach((id) => el(id).addEventListener("input", redraw));
  el("edgeSeed").addEventListener("input", redraw);
  el("columns").addEventListener("input", updateSheetStatus);

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
