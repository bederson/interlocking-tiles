#!/usr/bin/env python3
"""Generate self-interlocking, Truchet-style square tile files for laser cutting.

Every tile in a batch shares one edge-curve function, applied identically
(rotated) to all four sides of the square. That curve is built to be
point-symmetric about its own midpoint, which guarantees that any tile can
sit next to any other tile, in any of the four rotations, and its edge will
mate correctly. See the plan / README for the geometric reasoning.

Emits both SVG (for viewing/editing) and DXF (for laser software that
handles explicit units more reliably than SVG import scaling).
"""

import argparse
import math
import random
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Edge curve
# ---------------------------------------------------------------------------

def edge_offset(t, harmonics):
    """g(t): perpendicular displacement of the edge at parameter t in [0,1].

    g(t) = sin(pi*t) * sum(A_k * sin(2*pi*k*t))

    The sin(pi*t) envelope forces g(0) = g(1) = 0 with zero slope at both
    ends. For any integer k, sin(2*pi*k*(1-t)) = -sin(2*pi*k*t), so this
    construction guarantees g(1-t) = -g(t) for any choice of harmonics.
    """
    envelope = math.sin(math.pi * t)
    wiggle = sum(a * math.sin(2 * math.pi * k * t) for k, a in harmonics)
    return envelope * wiggle


def _normalize(v):
    length = math.hypot(v[0], v[1])
    if length < 1e-12:
        return (0.0, 0.0)
    return (v[0] / length, v[1] / length)


def edge_points(p0, p1, harmonics, n_samples):
    """Sample one tile edge from corner p0 to corner p1 as a polyline.

    The outward normal is a consistent 90-degree (clockwise) rotation of the
    edge direction; applying the same g(t) with this consistent construction
    on every edge of the square is what makes all four edges rotated copies
    of one another.
    """
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    normal = _normalize((dy, -dx))
    pts = []
    for i in range(n_samples + 1):
        t = i / n_samples
        base_x = p0[0] + dx * t
        base_y = p0[1] + dy * t
        g = edge_offset(t, harmonics)
        pts.append((base_x + normal[0] * g, base_y + normal[1] * g))
    return pts


def tile_cut_outline(size, harmonics, n_samples):
    """Build the closed polygon (list of points) for one tile's cut edge."""
    corners = [(0.0, 0.0), (size, 0.0), (size, size), (0.0, size)]
    outline = []
    for i in range(4):
        p0, p1 = corners[i], corners[(i + 1) % 4]
        pts = edge_points(p0, p1, harmonics, n_samples)
        outline.extend(pts[:-1])  # drop last point; next edge starts there
    return outline


# ---------------------------------------------------------------------------
# Truchet-style face engraving
# ---------------------------------------------------------------------------

def _arc_points(center, radius, angle_start_deg, angle_end_deg, n_samples):
    pts = []
    for i in range(n_samples + 1):
        t = i / n_samples
        angle = math.radians(angle_start_deg + (angle_end_deg - angle_start_deg) * t)
        pts.append((center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
    return pts


MOTIFS = ("A", "B", "S")


def truchet_face_paths(size, motif, n_samples=32):
    """Return the engrave centerline polylines for a tile's decorative face.

    "A" and "B" connect the four edge-midpoints (which sit at fixed points
    regardless of edge amplitude/harmonics/rotation, since g(0.5) == 0) with
    corner-centered quarter-circle arcs, in the classic two-tile Truchet
    style. "S" is a straight pass-through: two straight lines (vertical and
    horizontal) through the same four midpoints, forming a "+" -- the
    straight-tile counterpart to the curved motifs, for pipe/maze-style
    layouts instead of flowing curves.
    """
    r = size / 2.0
    mid = size / 2.0
    if motif == "A":
        return [
            _arc_points((0.0, 0.0), r, 0, 90, n_samples),
            _arc_points((size, size), r, 180, 270, n_samples),
        ]
    if motif == "B":
        return [
            _arc_points((size, 0.0), r, 90, 180, n_samples),
            _arc_points((0.0, size), r, 270, 360, n_samples),
        ]
    return [
        [(mid, 0.0), (mid, size)],  # vertical pass-through
        [(0.0, mid), (size, mid)],  # horizontal pass-through
    ]


def extend_polyline_ends(points, amount):
    """Extend a polyline past both its ends by `amount`, continuing in each
    end's local direction.

    Every motif centerline stops exactly at an edge's flat, unwiggled
    midpoint (the one point per edge guaranteed to have zero curve offset).
    But the real cut edge immediately bows outward (a bump) on one side of
    that point -- a centerline stopping exactly there falls short of the
    bump, leaving a visible gap. Overshooting past it fixes that; the
    overshoot itself is harmless; whatever lands outside the tile's real
    (wiggly) boundary is simply removed when the tile is cut out, same as
    it would be if it crossed into a neighboring tile's territory.
    """
    def step(p_from, p_to, dist):
        dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            return p_to
        return (p_to[0] + dx / length * dist, p_to[1] + dy / length * dist)

    start = step(points[1], points[0], amount)
    end = step(points[-2], points[-1], amount)
    return [start] + points + [end]


def max_wiggle_amplitude(harmonics):
    """An upper bound on |g(t)| for any t, given g(t) = sin(pi t) * sum(a_k sin(2 pi k t))."""
    return sum(abs(a) for _, a in harmonics)


# ---------------------------------------------------------------------------
# Frame and corner pieces
#
# A frame piece borders one non-corner edge tile; a corner piece borders one
# corner tile (touching both of its outward-facing edges at once, in an
# L-shape). Both reuse edge_points directly, so their tile-facing side is
# built from the exact same curve as the tile edge it sits against --
# guaranteed to fit, for the same reason two tiles fit each other.
#
# Every motif's engrave lines meet an edge midpoint moving straight out,
# perpendicular to that edge (true of the arcs and the straight pass-through
# alike) -- so a single straight continuation line from each edge midpoint,
# thickened the same as any other engrave ribbon, extends the pattern into
# the frame piece correctly regardless of which motif the neighboring tile
# actually has.
# ---------------------------------------------------------------------------

def frame_piece_outline(size, frame_width, harmonics, n_samples):
    """One frame piece: wiggly tile-matching edge on one long side, flat
    outer edge on the other, straight short end caps. Built against a
    canonical bottom tile edge; other orientations are this same piece
    rotated 90/180/270 degrees by hand during assembly, same as tiles."""
    inner = edge_points((0.0, 0.0), (size, 0.0), harmonics, n_samples)
    return inner + [(size, -frame_width), (0.0, -frame_width)]


def frame_piece_engrave_ribbons(size, frame_width, harmonics, engrave_width):
    mid = size / 2.0
    overshoot = max_wiggle_amplitude(harmonics)
    line = extend_polyline_ends([(mid, 0.0), (mid, -frame_width)], overshoot)
    return [thicken_polyline(line, engrave_width)]


def corner_piece_outline(size, frame_width, harmonics, n_samples):
    """One corner piece: wiggly tile-matching edges on the two sides that
    touch the corner tile (its bottom and left edges, canonically), flat
    edges completing the frame's outer corner, straight end caps. Built
    against a canonical bottom-left tile corner; the other 3 corners are
    this same piece rotated 90/180/270 degrees during assembly."""
    bottom = list(reversed(edge_points((0.0, 0.0), (size, 0.0), harmonics, n_samples)))
    left = list(reversed(edge_points((0.0, size), (0.0, 0.0), harmonics, n_samples)))
    inner = bottom + left[1:]  # (size,0) -> ... -> (0,0) -> ... -> (0,size), skipping the shared (0,0)
    return inner + [(-frame_width, size), (-frame_width, -frame_width), (size, -frame_width)]


def corner_piece_engrave_ribbons(size, frame_width, harmonics, engrave_width):
    mid = size / 2.0
    overshoot = max_wiggle_amplitude(harmonics)
    bottom_line = extend_polyline_ends([(mid, 0.0), (mid, -frame_width)], overshoot)
    left_line = extend_polyline_ends([(0.0, mid), (-frame_width, mid)], overshoot)
    return [thicken_polyline(bottom_line, engrave_width), thicken_polyline(left_line, engrave_width)]


def frame_and_corner_counts(grid_cols, grid_rows):
    """Non-corner border tiles need a frame piece; the 4 corner tiles each
    need one corner piece. Assumes a simple rectangular grid at least 2x2."""
    frame_count = max(0, 2 * (grid_cols - 2)) + max(0, 2 * (grid_rows - 2))
    corner_count = 4 if grid_cols >= 2 and grid_rows >= 2 else 0
    return frame_count, corner_count


# ---------------------------------------------------------------------------
# Kerf compensation
# ---------------------------------------------------------------------------

def offset_polygon(points, delta):
    """Nudge a closed polygon outward (delta > 0) or inward (delta < 0).

    Naive per-vertex offset: average the normals of the two edges meeting at
    each vertex and move the point along that averaged normal. Adequate for
    the small kerf-scale deltas used here relative to the curve's amplitude;
    not a robust general polygon offset (can self-intersect at very tight
    curvature / very small amplitude).
    """
    if delta == 0:
        return points
    n = len(points)
    result = []
    for i in range(n):
        p_prev, p, p_next = points[(i - 1) % n], points[i], points[(i + 1) % n]
        e1 = (p[0] - p_prev[0], p[1] - p_prev[1])
        e2 = (p_next[0] - p[0], p_next[1] - p[1])
        n1 = _normalize((e1[1], -e1[0]))
        n2 = _normalize((e2[1], -e2[0]))
        avg = _normalize((n1[0] + n2[0], n1[1] + n2[1]))
        result.append((p[0] + avg[0] * delta, p[1] + avg[1] * delta))
    return result


def thicken_polyline(points, width):
    """Turn a centerline polyline into a closed ribbon polygon `width` wide.

    Laser software engraves based on geometry, not a cosmetic stroke-width
    number, so a genuinely wide engraved channel needs an actual filled
    band shape -- not just a thicker-looking line. Offsets each point by
    half the width along the local normal (averaging the two adjacent
    segment normals at interior points; using the single adjacent segment's
    normal, i.e. a butt cap, at the two open ends), then stitches the two
    offset sides into one closed loop.
    """
    half = width / 2.0
    n = len(points)
    left, right = [], []
    for i in range(n):
        segment_normals = []
        if i > 0:
            d = (points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
            segment_normals.append(_normalize((d[1], -d[0])))
        if i < n - 1:
            d = (points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
            segment_normals.append(_normalize((d[1], -d[0])))
        avg = tuple(sum(v) for v in zip(*segment_normals))
        normal = _normalize(avg)
        left.append((points[i][0] + normal[0] * half, points[i][1] + normal[1] * half))
        right.append((points[i][0] - normal[0] * half, points[i][1] - normal[1] * half))
    return left + list(reversed(right))


def default_engrave_width(units):
    return 12.7 if units == "mm" else 0.5  # 0.5 inch


# ---------------------------------------------------------------------------
# SVG output ("for humans" -- easy to view/edit in a browser or Illustrator)
# ---------------------------------------------------------------------------

CUT_COLOR = "#FF0000"
ENGRAVE_COLOR = "#0000FF"


def points_to_svg_path(points, closed=True):
    if not points:
        return ""
    parts = [f"M {points[0][0]:.4f},{points[0][1]:.4f}"]
    parts.extend(f"L {x:.4f},{y:.4f}" for x, y in points[1:])
    if closed:
        parts.append("Z")
    return " ".join(parts)


def svg_groups(cut_path_ds, engrave_path_ds, stroke_width):
    """Wrap the cut and engrave paths in separate named <g> groups.

    Vector/laser software (XCS included) treats each top-level group as a
    distinct selectable object, so this lets the whole cut outline (or the
    whole engrave fill) be selected and assigned an operation in one click,
    rather than every individual path needing to be picked out by hand.
    `engrave_path_ds` are closed filled bands (see thicken_polyline), not
    thin centerlines -- they render (and laser-engrave, if assigned to a
    Fill operation) as solid `width`-wide channels.
    """
    cut_lines = "\n".join(
        f'    <path d="{d}" fill="none" stroke="{CUT_COLOR}" stroke-width="{stroke_width}"/>' for d in cut_path_ds
    )
    engrave_lines = "\n".join(f'    <path d="{d}" fill="{ENGRAVE_COLOR}" stroke="none"/>' for d in engrave_path_ds)
    return f'  <g id="CUT">\n{cut_lines}\n  </g>\n  <g id="ENGRAVE">\n{engrave_lines}\n  </g>'


def write_piece_svg(path, min_x, min_y, width, height, units, cut_points, engrave_ribbons):
    """Write one piece's SVG with an explicit (min_x, min_y, width, height)
    viewBox -- the *nominal* bounding box for this piece type, not one
    computed from the actual (possibly slightly overshooting) geometry, so
    the declared physical size stays exact for XCS's scale verification."""
    stroke_width = max(width, height) * 0.002
    cut_path_ds = [points_to_svg_path(cut_points, closed=True)]
    engrave_path_ds = [points_to_svg_path(ribbon, closed=True) for ribbon in engrave_ribbons]
    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}{units}" height="{height}{units}" '
        f'viewBox="{min_x} {min_y} {width} {height}">\n'
        f"{svg_groups(cut_path_ds, engrave_path_ds, stroke_width)}\n"
        f"</svg>\n"
    )
    path.write_text(svg)


def write_tile_svg(path, size, units, cut_points, engrave_ribbons):
    write_piece_svg(path, 0, 0, size, size, units, cut_points, engrave_ribbons)


# ---------------------------------------------------------------------------
# DXF output (machine-friendly: explicit units, no SVG import-scale gotcha)
# ---------------------------------------------------------------------------

def _dxf_insunits(units):
    return 4 if units == "mm" else 1  # 4 = millimeters, 1 = inches


def _dxf_polyline_lines(points, layer, color, closed):
    flag = 1 if closed else 0
    lines = ["0", "POLYLINE", "8", layer, "62", str(color), "66", "1", "70", str(flag)]
    for x, y in points:
        lines += ["0", "VERTEX", "8", layer, "10", f"{x:.4f}", "20", f"{y:.4f}"]
    lines += ["0", "SEQEND"]
    return lines


def _dxf_document(entity_lines, units):
    """CUT and ENGRAVE are declared as named layers (DXF's equivalent of SVG
    <g> groups -- the mechanism laser/CAD software uses to let a whole
    operation be selected and assigned at once), not just referenced ad hoc
    by entities."""
    header = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", str(_dxf_insunits(units)), "0", "ENDSEC"]
    tables = [
        "0", "SECTION", "2", "TABLES",
        "0", "TABLE", "2", "LAYER", "70", "2",
        "0", "LAYER", "2", "CUT", "70", "0", "62", "1",
        "0", "LAYER", "2", "ENGRAVE", "70", "0", "62", "5",
        "0", "ENDTAB",
        "0", "ENDSEC",
    ]
    entities = ["0", "SECTION", "2", "ENTITIES"] + entity_lines + ["0", "ENDSEC"]
    footer = ["0", "EOF"]
    return "\n".join(header + tables + entities + footer) + "\n"


def write_tile_dxf(path, units, cut_points, engrave_ribbons):
    """`engrave_ribbons` are closed bands; writing them as closed polylines
    lets XCS assign an Engrave-Fill (raster infill) operation to the layer,
    which is what actually produces a wide engraved channel."""
    entities = _dxf_polyline_lines(cut_points, "CUT", 1, closed=True)
    for ribbon in engrave_ribbons:
        entities += _dxf_polyline_lines(ribbon, "ENGRAVE", 5, closed=True)
    path.write_text(_dxf_document(entities, units))


# ---------------------------------------------------------------------------
# PDF output (a single combined reference/print document -- built from
# scratch, no dependency, since only a handful of PDF primitives are
# needed: one page, straight-line paths, fill and stroke).
#
# PDF pages are sized in points (72/inch) with the origin at the bottom
# left; like DXF (which just reuses our raw coordinates unflipped), no
# vertical flip is applied here either, for consistency between the two --
# harmless, since the design's interlock is symmetric either way.
# ---------------------------------------------------------------------------

def _pdf_points_per_unit(units):
    return 72.0 / 25.4 if units == "mm" else 72.0


def _pdf_path_ops(points, scale):
    if not points:
        return ""
    ops = [f"{points[0][0] * scale:.3f} {points[0][1] * scale:.3f} m"]
    ops += [f"{x * scale:.3f} {y * scale:.3f} l" for x, y in points[1:]]
    ops.append("h")
    return " ".join(ops)


def pdf_document(sheet_w, sheet_h, units, cut_polys, engrave_polys):
    scale = _pdf_points_per_unit(units)
    width_pt, height_pt = sheet_w * scale, sheet_h * scale

    lines = []
    if cut_polys:
        r, g, b = tuple(int(CUT_COLOR[i : i + 2], 16) / 255 for i in (1, 3, 5))
        lines.append(f"{r:.3f} {g:.3f} {b:.3f} RG")
        lines.append("0.5 w")
        for pts in cut_polys:
            lines.append(_pdf_path_ops(pts, scale))
            lines.append("S")
    if engrave_polys:
        r, g, b = tuple(int(ENGRAVE_COLOR[i : i + 2], 16) / 255 for i in (1, 3, 5))
        lines.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
        for pts in engrave_polys:
            lines.append(_pdf_path_ops(pts, scale))
            lines.append("f")
    content_bytes = "\n".join(lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width_pt:.3f} {height_pt:.3f}] "
            f"/Contents 4 0 R /Resources << >> >>"
        ).encode("latin-1"),
        f"<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1") + content_bytes + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("latin-1") + body + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode("latin-1")
    return bytes(out)


def write_sheet_pdf(path, sheet_w, sheet_h, units, cut_polys, engrave_polys):
    path.write_bytes(pdf_document(sheet_w, sheet_h, units, cut_polys, engrave_polys))


# ---------------------------------------------------------------------------
# Sheet layout (batch of tiles on one P3-bed-sized page, SVG + DXF)
# ---------------------------------------------------------------------------

def sheet_grid_dims(size, sheet_w, sheet_h, margin):
    """How many tile columns/rows fit on one sheet.

    Raises ValueError if a single tile (plus its margin) doesn't fit at all.
    """
    if size + margin > sheet_w or size + margin > sheet_h:
        raise ValueError(
            f"A {size:g} tile (plus {margin:g} margin) does not fit on a "
            f"{sheet_w:g} x {sheet_h:g} sheet."
        )
    cols = max(1, int((sheet_w + margin) // (size + margin)))
    rows = max(1, int((sheet_h + margin) // (size + margin)))
    return cols, rows


def pack_into_region(items, region_x, region_y, region_w, region_h, margin):
    """Shelf-pack items (dicts with 'width'/'height') into a bounded
    rectangle on the sheet, left-to-right then top-to-bottom. Not
    space-optimal, but robust for the modest number of pieces a frame
    needs. Returns (placements, leftover) -- placements is a list of
    (item, x, y) giving where that item's own (min_x, min_y) bounding-box
    corner lands; leftover is the items (in order) that didn't fit.
    """
    placements = []
    cursor_x, shelf_y, shelf_height, shelf_has_item = region_x + margin, region_y + margin, 0.0, False
    idx = 0
    for item in items:
        w, h = item["width"], item["height"]
        if w + 2 * margin > region_w:
            break  # doesn't fit in this region on any shelf, regardless of state
        if shelf_has_item and cursor_x + w > region_x + region_w - margin:
            cursor_x, shelf_y, shelf_height, shelf_has_item = region_x + margin, shelf_y + shelf_height + margin, 0.0, False
        if shelf_y + h > region_y + region_h - margin:
            break
        placements.append((item, cursor_x, shelf_y))
        cursor_x += w + margin
        shelf_height = max(shelf_height, h)
        shelf_has_item = True
        idx += 1
    return placements, items[idx:]


def validate_piece_fits(width, height, sheet_w, sheet_h, margin, label):
    if width + 2 * margin > sheet_w or height + 2 * margin > sheet_h:
        raise ValueError(f"A {label} ({width:g} x {height:g}) does not fit on a {sheet_w:g} x {sheet_h:g} sheet.")


def compute_combined_layout(tiles, frame_items, corner_items, size, sheet_w, sheet_h, margin):
    """Lay out tiles in their grid, then nest frame/corner pieces into the
    leftover sheet space beside and below that grid -- rather than a wholly
    separate sheet -- for more efficient material usage. Falls back to
    dedicated sheets for any pieces that don't fit alongside tiles.

    Returns a list of sheets; each sheet is a list of placement dicts:
    {'cut_points': [...], 'engrave_ribbons': [[...], ...]}, already in
    absolute sheet coordinates.
    """
    cols, rows = sheet_grid_dims(size, sheet_w, sheet_h, margin)
    per_sheet = cols * rows
    # Tallest first packs a little more efficiently into the leftover strips.
    pending = sorted(list(frame_items) + list(corner_items), key=lambda it: -it["height"])

    def place(item, shift_x, shift_y):
        return {
            "cut_points": [(x + shift_x, y + shift_y) for x, y in item["cut_points"]],
            "engrave_ribbons": [[(x + shift_x, y + shift_y) for x, y in r] for r in item["engrave_ribbons"]],
        }

    sheets = []
    tile_idx = 0
    while tile_idx < len(tiles) or pending:
        chunk = tiles[tile_idx : tile_idx + per_sheet]
        tile_idx += len(chunk)
        placements = []

        for i, tile in enumerate(chunk):
            col, row = i % cols, i // cols
            ox, oy = margin + col * (size + margin), margin + row * (size + margin)
            placements.append(place(tile, ox, oy))

        if chunk:
            # cols_used is the sheet's full column capacity only if at least
            # one row is completely full; otherwise it's just this single
            # (partial) row's tile count -- reclaiming the rest of the width
            # for frame/corner nesting instead of reserving the sheet's full
            # capacity for however many tiles actually got cut.
            cols_used = cols if len(chunk) > cols else len(chunk)
            block_right = cols_used * (size + margin)
            block_bottom = math.ceil(len(chunk) / cols) * (size + margin)
        else:
            block_right = block_bottom = 0.0

        right_placed, pending = pack_into_region(pending, block_right, 0.0, sheet_w - block_right, sheet_h, margin)
        bottom_placed, pending = pack_into_region(pending, 0.0, block_bottom, block_right, sheet_h - block_bottom, margin)
        for item, px, py in right_placed + bottom_placed:
            placements.append(place(item, px - item["min_x"], py - item["min_y"]))

        if not placements and pending:
            raise ValueError("A frame or corner piece does not fit on the given sheet size.")
        sheets.append(placements)

    return sheets


def write_combined_sheet(output_dir, sheet_number, placements, units, sheet_w, sheet_h):
    """Write one sheet's SVG + DXF + PDF, all three from the same placement
    list -- tiles, frame pieces and corner pieces together, each format's
    CUT geometry grouped/layered separately from its ENGRAVE geometry."""
    stroke_width = sheet_w * 0.001
    cut_path_ds, engrave_path_ds = [], []
    dxf_entities = []
    cut_polys, engrave_polys = [], []
    for p in placements:
        cut_path_ds.append(points_to_svg_path(p["cut_points"], closed=True))
        engrave_path_ds.extend(points_to_svg_path(r, closed=True) for r in p["engrave_ribbons"])
        dxf_entities += _dxf_polyline_lines(p["cut_points"], "CUT", 1, closed=True)
        for r in p["engrave_ribbons"]:
            dxf_entities += _dxf_polyline_lines(r, "ENGRAVE", 5, closed=True)
        cut_polys.append(p["cut_points"])
        engrave_polys.extend(p["engrave_ribbons"])

    svg_path = output_dir / f"sheet_{sheet_number:04d}.svg"
    svg_path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet_w}{units}" height="{sheet_h}{units}" '
        f'viewBox="0 0 {sheet_w} {sheet_h}">\n'
        f"{svg_groups(cut_path_ds, engrave_path_ds, stroke_width)}\n</svg>\n"
    )

    dxf_path = output_dir / f"sheet_{sheet_number:04d}.dxf"
    dxf_path.write_text(_dxf_document(dxf_entities, units))

    pdf_path = output_dir / f"sheet_{sheet_number:04d}.pdf"
    write_sheet_pdf(pdf_path, sheet_w, sheet_h, units, cut_polys, engrave_polys)

    return svg_path, dxf_path, pdf_path


# ---------------------------------------------------------------------------
# Harmonics
# ---------------------------------------------------------------------------

def parse_harmonics_spec(spec):
    """Parse 'k:amplitude,k:amplitude,...' into [(k, amplitude), ...]."""
    harmonics = []
    for term in spec.split(","):
        term = term.strip()
        if not term:
            continue
        k_str, a_str = term.split(":")
        harmonics.append((int(k_str), float(a_str)))
    return harmonics


def build_edge_harmonics(amplitude, wiggles, harmonics_spec, edge_seed):
    if harmonics_spec:
        return parse_harmonics_spec(harmonics_spec)
    if edge_seed is not None:
        rng = random.Random(edge_seed)
        n_harmonics = rng.randint(1, 3)
        ks = rng.sample(range(1, 6), n_harmonics)
        raw = [rng.uniform(0.3, 1.0) for _ in ks]
        total = sum(raw)
        return [(k, amplitude * r / total) for k, r in zip(ks, raw)]
    return [(wiggles, amplitude)]


def self_check(size, harmonics, n_samples):
    """Sanity-check the antisymmetry property and corner placement."""
    for t in (0.05, 0.2, 0.37, 0.5, 0.63, 0.8, 0.95):
        g1, g2 = edge_offset(t, harmonics), edge_offset(1 - t, harmonics)
        assert abs(g1 + g2) < 1e-9, f"g(t) != -g(1-t) at t={t}: {g1} vs {g2}"

    outline = tile_cut_outline(size, harmonics, n_samples)
    expected_corners = [(0.0, 0.0), (size, 0.0), (size, size), (0.0, size)]
    corner_stride = n_samples
    for i, expected in enumerate(expected_corners):
        actual = outline[i * corner_stride]
        assert math.hypot(actual[0] - expected[0], actual[1] - expected[1]) < 1e-6, (
            f"corner {i} at {actual}, expected {expected}"
        )


# ---------------------------------------------------------------------------
# Batch generation -- the single entry point used by both the CLI and the
# web design console's server, so both always produce identical geometry.
# ---------------------------------------------------------------------------

def default_sheet_dims(units):
    # P3 bed is 36in x 18in; margin is a small gap between tiles.
    if units == "mm":
        return 900.0, 450.0, 6.0
    return 36.0, 18.0, 0.25


def default_output_dir():
    """A fresh timestamped subfolder so successive runs don't overwrite each other."""
    return f"output/{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def infer_grid_dims(count):
    """A roughly-square grid_cols x grid_rows for `count` tiles, matching the
    web console's live preview grid so frame/corner counts default to
    whatever grid the preview is already showing."""
    cols = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / cols))
    return cols, rows


def generate_batch(params):
    """Generate a full tile batch (per-tile + sheet SVG/DXF files) on disk.

    `params` is a dict; see main()'s argparse definitions for accepted keys
    and defaults. Returns a summary dict describing what was written.
    """
    size = float(params.get("size", 2.0))
    units = params.get("units", "in")
    samples = int(params.get("samples_per_edge", 120))
    count = int(params.get("count", 9))

    default_w, default_h, default_margin = default_sheet_dims(units)
    sheet_w = params.get("sheet_width") or default_w
    sheet_h = params.get("sheet_height") or default_h
    margin = params.get("sheet_margin")
    margin = default_margin if margin is None else margin

    sheet_grid_dims(size, sheet_w, sheet_h, margin)  # raises if it won't fit, before any files are written

    harmonics = build_edge_harmonics(
        float(params.get("amplitude", 0.25)),
        int(params.get("wiggles", 1)),
        params.get("harmonics"),
        params.get("edge_seed"),
    )
    self_check(size, harmonics, samples)

    output_dir = Path(params.get("output_dir") or default_output_dir())
    output_dir.mkdir(parents=True, exist_ok=True)

    cut_outline = tile_cut_outline(size, harmonics, samples)
    cut_outline = offset_polygon(cut_outline, float(params.get("kerf_adjust", 0.0)))

    engrave_width = params.get("engrave_width") or default_engrave_width(units)
    overshoot = max_wiggle_amplitude(harmonics)  # guaranteed >= the true boundary's max excursion anywhere

    face_rng = random.Random(params.get("face_seed"))
    tiles, tile_files = [], []
    for i in range(count):
        motif = face_rng.choice(MOTIFS)
        engrave_ribbons = [
            thicken_polyline(extend_polyline_ends(arc, overshoot), engrave_width)
            for arc in truchet_face_paths(size, motif)
        ]
        tiles.append({"cut_points": cut_outline, "engrave_ribbons": engrave_ribbons, "motif": motif})

        svg_path = output_dir / f"tile_{i + 1:04d}.svg"
        dxf_path = output_dir / f"tile_{i + 1:04d}.dxf"
        write_tile_svg(svg_path, size, units, cut_outline, engrave_ribbons)
        write_tile_dxf(dxf_path, units, cut_outline, engrave_ribbons)
        tile_files.append({"svg": str(svg_path), "dxf": str(dxf_path)})

    # Frame and corner pieces border the grid the tiles will be assembled
    # into -- a different concept from how many sheets of material it takes
    # to cut them, hence the separate grid_cols/grid_rows (defaulting to the
    # same roughly-square grid the web preview already shows for `count`).
    default_cols, default_rows = infer_grid_dims(count)
    grid_cols = int(params.get("grid_cols") or default_cols)
    grid_rows = int(params.get("grid_rows") or default_rows)
    frame_width = float(params.get("frame_width") or size / 3.0)
    kerf_adjust = float(params.get("kerf_adjust", 0.0))

    validate_piece_fits(size, frame_width, sheet_w, sheet_h, margin, "frame piece")
    validate_piece_fits(size + frame_width, size + frame_width, sheet_w, sheet_h, margin, "corner piece")

    frame_count, corner_count = frame_and_corner_counts(grid_cols, grid_rows)

    frame_outline = offset_polygon(frame_piece_outline(size, frame_width, harmonics, samples), kerf_adjust)
    frame_ribbons = frame_piece_engrave_ribbons(size, frame_width, harmonics, engrave_width)
    corner_outline = offset_polygon(corner_piece_outline(size, frame_width, harmonics, samples), kerf_adjust)
    corner_ribbons = corner_piece_engrave_ribbons(size, frame_width, harmonics, engrave_width)

    frame_files, corner_files = [], []
    for i in range(frame_count):
        svg_path = output_dir / f"frame_{i + 1:04d}.svg"
        dxf_path = output_dir / f"frame_{i + 1:04d}.dxf"
        write_piece_svg(svg_path, 0, -frame_width, size, frame_width, units, frame_outline, frame_ribbons)
        write_tile_dxf(dxf_path, units, frame_outline, frame_ribbons)
        frame_files.append({"svg": str(svg_path), "dxf": str(dxf_path)})
    for i in range(corner_count):
        svg_path = output_dir / f"corner_{i + 1:04d}.svg"
        dxf_path = output_dir / f"corner_{i + 1:04d}.dxf"
        write_piece_svg(
            svg_path, -frame_width, -frame_width, size + frame_width, size + frame_width,
            units, corner_outline, corner_ribbons,
        )
        write_tile_dxf(dxf_path, units, corner_outline, corner_ribbons)
        corner_files.append({"svg": str(svg_path), "dxf": str(dxf_path)})

    frame_items = [
        {
            "cut_points": frame_outline, "engrave_ribbons": frame_ribbons,
            "width": size, "height": frame_width, "min_x": 0.0, "min_y": -frame_width,
        }
        for _ in range(frame_count)
    ]
    corner_items = [
        {
            "cut_points": corner_outline, "engrave_ribbons": corner_ribbons,
            "width": size + frame_width, "height": size + frame_width,
            "min_x": -frame_width, "min_y": -frame_width,
        }
        for _ in range(corner_count)
    ]

    # Tiles, frame pieces, and corner pieces are laid out together on each
    # sheet (frame/corner nested into the leftover space beside and below
    # the tile grid) and each sheet is written once as SVG + DXF + PDF, all
    # three combining every piece type instead of splitting tiles from
    # frame/corner into separate files.
    combined_sheets = compute_combined_layout(tiles, frame_items, corner_items, size, sheet_w, sheet_h, margin)
    sheet_files = []
    for sheet_number, placements in enumerate(combined_sheets, start=1):
        svg_path, dxf_path, pdf_path = write_combined_sheet(output_dir, sheet_number, placements, units, sheet_w, sheet_h)
        sheet_files.append({"svg": str(svg_path), "dxf": str(dxf_path), "pdf": str(pdf_path)})

    return {
        "harmonics": harmonics,
        "tile_count": count,
        "tile_files": tile_files,
        "sheet_files": sheet_files,
        "grid_cols": grid_cols,
        "grid_rows": grid_rows,
        "frame_width": frame_width,
        "frame_count": frame_count,
        "corner_count": corner_count,
        "frame_files": frame_files,
        "corner_files": corner_files,
        "output_dir": str(output_dir),
        "sheet_width": sheet_w,
        "sheet_height": sheet_h,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=float, default=2.0, help="tile side length")
    parser.add_argument("--count", type=int, default=9, help="number of tiles to generate")
    parser.add_argument("--amplitude", type=float, default=0.25, help="bump/notch depth")
    parser.add_argument("--wiggles", type=int, default=1, help="harmonic number when --harmonics not given")
    parser.add_argument("--harmonics", type=str, default=None, help="explicit 'k:amplitude,...' list, overrides --wiggles/--edge-seed randomization")
    parser.add_argument("--edge-seed", type=int, default=None, help="seed for randomizing the one shared edge curve")
    parser.add_argument("--face-seed", type=int, default=None, help="seed for per-tile engrave motif choice")
    parser.add_argument("--kerf-adjust", type=float, default=0.0, help="signed fine-tune offset (+ tighter, - looser)")
    parser.add_argument("--engrave-width", type=float, default=None, help="engrave channel width; default 0.5in / 12.7mm")
    parser.add_argument("--units", choices=["in", "mm"], default="in")
    parser.add_argument("--samples-per-edge", type=int, default=120)
    parser.add_argument("--sheet-width", type=float, default=None, help="material width to lay tiles out on; default: P3 bed width (36in / 900mm)")
    parser.add_argument("--sheet-height", type=float, default=None, help="material height to lay tiles out on; default: P3 bed height (18in / 450mm)")
    parser.add_argument("--sheet-margin", type=float, default=None, help="default: 0.25in / 6mm")
    parser.add_argument("--grid-cols", type=int, default=None, help="tile grid width for frame/corner pieces; default: inferred square-ish from --count")
    parser.add_argument("--grid-rows", type=int, default=None, help="tile grid height for frame/corner pieces; default: inferred square-ish from --count")
    parser.add_argument("--frame-width", type=float, default=None, help="frame/corner piece depth; default: size/3")
    parser.add_argument("--output-dir", type=str, default=None, help="default: output/<timestamp>, a fresh folder per run")
    args = parser.parse_args()

    try:
        summary = generate_batch(vars(args))
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}")

    print(f"Wrote {len(summary['tile_files'])} tile SVG+DXF pairs, "
          f"{summary['frame_count']} frame + {summary['corner_count']} corner piece SVG+DXF pairs, and "
          f"{len(summary['sheet_files'])} combined sheet SVG+DXF+PDF set(s) to {summary['output_dir']}/")
    print(f"Grid: {summary['grid_cols']}x{summary['grid_rows']}, frame width {summary['frame_width']:g} {args.units} "
          "(frame/corner pieces nested alongside tiles on the same sheet where they fit)")
    print(f"Sheet size: {summary['sheet_width']:g} x {summary['sheet_height']:g} {args.units}")
    print(f"Edge harmonics used (shared by every tile): {summary['harmonics']}")


if __name__ == "__main__":
    main()
