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


def rotate_points(points, angle_deg, cx, cy):
    angle = math.radians(angle_deg)
    ca, sa = math.cos(angle), math.sin(angle)
    return [
        (cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca)
        for x, y in points
    ]


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
# turned into parallel lines the same as any other engrave path, extends
# the pattern into the frame piece correctly regardless of which motif the
# neighboring tile actually has.
#
# Frame and corner pieces meet their NEIGHBORING frame/corner piece (not a
# tile) along their short end caps -- those get a "keyhole"/dog-bone
# tab-and-socket jigsaw connector instead of a plain straight edge, so the
# whole border assembles into a connected loop. Every piece uses the same
# fixed convention (see CONNECTOR_TAB/CONNECTOR_SOCKET below): one end is
# always a tab, the other always the matching socket, so going around the
# border in one consistent direction, each tab meets the next piece's
# socket automatically.
# ---------------------------------------------------------------------------

CONNECTOR_TAB = "tab"
CONNECTOR_SOCKET = "socket"
# "Keyhole"/dog-bone connector: a neck narrower than the bulb it leads to, so
# a mated tab/socket pair can't be pulled straight apart along the cap's own
# axis -- only a plain semicircular bump could do that, since its widest
# point is at the base. All three ratios are fractions of frame_width.
CONNECTOR_NECK_RATIO = 0.1125
CONNECTOR_BULB_RADIUS_RATIO = 0.21
CONNECTOR_STEM_RATIO = 0.35


def connector_protrusion(frame_width):
    """How far the tab's bulb tip extends past the piece's nominal edge."""
    return frame_width * (CONNECTOR_STEM_RATIO + CONNECTOR_BULB_RADIUS_RATIO)


def _keyhole_cap_points(p0, p1, bulge_direction, neck_half_width, bulb_radius, stem_length, n_samples=24):
    """Replace the straight segment from p0 to p1 with a "keyhole"/dog-bone
    shape: two short straight segments pinch in to a neck of half-width
    `neck_half_width`, which opens out into a round bulb of `bulb_radius`
    centered `stem_length` from the cap's midpoint along `bulge_direction`
    (a unit vector perpendicular to p1-p0) -- a tab if bulge_direction points
    away from the piece's material, or a matching socket if it points into
    it. Since the bulb is wider than the neck, a mated pair mechanically
    interlocks rather than just relying on friction. Returns the full
    replacement point list, including p0 and p1.
    """
    mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
    cap_dir = _normalize((p1[0] - p0[0], p1[1] - p0[1]))
    h = math.sqrt(bulb_radius ** 2 - neck_half_width ** 2)

    def local_to_global(u, v):
        return (
            mid[0] + cap_dir[0] * u + bulge_direction[0] * v,
            mid[1] + cap_dir[1] * u + bulge_direction[1] * v,
        )

    center = local_to_global(0.0, stem_length)
    b_minus = local_to_global(-neck_half_width, 0.0)
    b_plus = local_to_global(neck_half_width, 0.0)
    p_minus = local_to_global(-neck_half_width, stem_length - h)
    p_plus = local_to_global(neck_half_width, stem_length - h)

    def angle_from_center(point):
        vx, vy = point[0] - center[0], point[1] - center[1]
        u = vx * cap_dir[0] + vy * cap_dir[1]
        v = vx * bulge_direction[0] + vy * bulge_direction[1]
        return math.atan2(v, u)

    phi_minus = angle_from_center(p_minus)
    phi_plus = angle_from_center(p_plus)
    # The short way around from phi_minus to phi_plus passes through the
    # neck opening (v<0 side); the tip of the bulb is the long way around,
    # through local angle +90 deg -- verified numerically to hold regardless
    # of the actual global cap_dir/bulge_direction, since both are expressed
    # consistently in that same local frame.
    sweep = ((phi_plus - phi_minus) % (2 * math.pi)) - 2 * math.pi

    arc = []
    for i in range(n_samples + 1):
        phi = phi_minus + sweep * i / n_samples
        arc.append((
            center[0] + bulb_radius * (math.cos(phi) * cap_dir[0] + math.sin(phi) * bulge_direction[0]),
            center[1] + bulb_radius * (math.cos(phi) * cap_dir[1] + math.sin(phi) * bulge_direction[1]),
        ))
    return [p0, b_minus] + arc + [b_plus, p1]


def _connector_cap(p0, p1, outward_direction, kind, frame_width):
    """A tab's bulb bulges outward (away from the piece); a socket's bulb
    bulges inward (the same absolute direction as the tab it must receive)
    -- see the module comment above. `outward_direction` is the unit vector
    pointing away from the piece's material at this end."""
    neck_half_width = frame_width * CONNECTOR_NECK_RATIO
    bulb_radius = frame_width * CONNECTOR_BULB_RADIUS_RATIO
    stem_length = frame_width * CONNECTOR_STEM_RATIO
    bulge = outward_direction if kind == CONNECTOR_TAB else (-outward_direction[0], -outward_direction[1])
    return _keyhole_cap_points(p0, p1, bulge, neck_half_width, bulb_radius, stem_length)


def frame_piece_outline(size, frame_width, harmonics, n_samples):
    """One frame piece: wiggly tile-matching edge on one long side, flat
    outer edge on the other, tab-and-socket connectors on the two short
    ends (a tab at x=size, a socket at x=0) so pieces connect end to end.
    Built against a canonical bottom tile edge; other orientations are this
    same piece rotated 90/180/270 degrees by hand during assembly, same as
    tiles."""
    inner = edge_points((0.0, 0.0), (size, 0.0), harmonics, n_samples)
    tab = _connector_cap((size, 0.0), (size, -frame_width), (1.0, 0.0), CONNECTOR_TAB, frame_width)
    socket = _connector_cap((0.0, -frame_width), (0.0, 0.0), (-1.0, 0.0), CONNECTOR_SOCKET, frame_width)
    return inner[:-1] + tab + [(0.0, -frame_width)] + socket[1:]


def frame_piece_engrave_lines(size, frame_width, harmonics, engrave_width, engrave_lines_n):
    mid = size / 2.0
    overshoot = max_wiggle_amplitude(harmonics)
    line = extend_polyline_ends([(mid, 0.0), (mid, -frame_width)], overshoot)
    return parallel_lines(line, engrave_width, engrave_lines_n)


def corner_piece_outline(size, frame_width, harmonics, n_samples):
    """One corner piece: wiggly tile-matching edges on the two sides that
    touch the corner tile (its bottom and left edges, canonically), flat
    edges completing the frame's outer corner, and the same tab-and-socket
    connectors as a frame piece on its two far ends (a tab at x=size,
    matching a frame piece's socket end; a socket at y=size, matching a
    frame piece's tab end coming from the other direction). Built against
    a canonical bottom-left tile corner; the other 3 corners are this same
    piece rotated 90/180/270 degrees during assembly."""
    bottom = list(reversed(edge_points((0.0, 0.0), (size, 0.0), harmonics, n_samples)))
    left = list(reversed(edge_points((0.0, size), (0.0, 0.0), harmonics, n_samples)))
    inner = bottom + left[1:]  # (size,0) -> ... -> (0,0) -> ... -> (0,size), skipping the shared (0,0)
    tab = _connector_cap((size, -frame_width), (size, 0.0), (1.0, 0.0), CONNECTOR_TAB, frame_width)
    socket = _connector_cap((0.0, size), (-frame_width, size), (0.0, 1.0), CONNECTOR_SOCKET, frame_width)
    return inner[:-1] + socket + [(-frame_width, -frame_width), (size, -frame_width)] + tab[1:]


def corner_piece_engrave_lines(size, frame_width, harmonics, engrave_width, engrave_lines_n):
    mid = size / 2.0
    overshoot = max_wiggle_amplitude(harmonics)
    bottom_line = extend_polyline_ends([(mid, 0.0), (mid, -frame_width)], overshoot)
    left_line = extend_polyline_ends([(0.0, mid), (-frame_width, mid)], overshoot)
    return parallel_lines(bottom_line, engrave_width, engrave_lines_n) + parallel_lines(
        left_line, engrave_width, engrave_lines_n
    )


def frame_and_corner_counts(grid_cols, grid_rows):
    """Non-corner border tiles need a frame piece; the 4 corner tiles each
    need one corner piece. Assumes a simple rectangular grid at least 2x2."""
    frame_count = max(0, 2 * (grid_cols - 2)) + max(0, 2 * (grid_rows - 2))
    corner_count = 4 if grid_cols >= 2 and grid_rows >= 2 else 0
    return frame_count, corner_count


# ---------------------------------------------------------------------------
# Cutting-sheet nesting: pairing frame/corner pieces so two share a much
# smaller combined bounding box than placing them independently would need.
# Every frame/corner piece is identical, so all pairs reuse the same base
# outline/engrave-lines -- only the *packing* differs from the individually-
# exported pieces/ files, physical assembly is unaffected either way (every
# piece is already exported unrotated and hand-rotated into place).
# ---------------------------------------------------------------------------

def paired_frame_item(frame_outline, frame_lines, frame_width, size, gap, overshoot):
    """Two frame pieces stacked as one packing unit: the first is rotated
    180 degrees about its own bounding-box center so its flat outer edge
    ends up facing up, then the second (unrotated) sits directly above it
    with only `gap` between their flat edges -- verified numerically to
    need no more clearance than that, since a flat edge (unlike a wiggly
    one) has no wiggle to leave room for.
    Returns one flow_layout item with two 'parts'.
    """
    pivot = (size / 2.0, -frame_width / 2.0)
    bottom_outline = rotate_points(frame_outline, 180.0, *pivot)
    bottom_lines = [rotate_points(line, 180.0, *pivot) for line in frame_lines]

    dy = frame_width + gap
    top_outline = [(x, y + dy) for x, y in frame_outline]
    top_lines = [[(x, y + dy) for x, y in line] for line in frame_lines]

    # Nominal (not exact-point) bounding box, matching the rest of this
    # module's items and the JS mirror in requiredMaterialSize() -- both
    # tabs end up on opposite sides after the rotation, so the pair is `r`
    # wider on each side than a single piece. Height is padded by
    # `overshoot` on the pair's outward-facing top/bottom (the two wiggly
    # tile-facing edges, now on the outside of the stack) for the same
    # reason tile items are -- see the comment there.
    r = connector_protrusion(frame_width)
    return {
        "parts": [
            {"cut_points": bottom_outline, "engrave_lines": bottom_lines},
            {"cut_points": top_outline, "engrave_lines": top_lines},
        ],
        "width": size + 2 * r, "height": 2 * frame_width + gap + 2 * overshoot,
        "min_x": -r, "min_y": -frame_width - overshoot,
    }


def paired_corner_item(corner_outline, corner_lines, size, frame_width, gap):
    """Two corner pieces as one packing unit: the second is rotated 180
    degrees about the tile corner point (size/2, size/2) so its L-shape
    fills the square left empty by the first piece's own L-shape, then
    nudged up by `gap` to clear a single near-touching point between their
    connector caps right at (size, 0) -- verified numerically across
    several size/frame_width/harmonics combinations that this small nudge
    is enough (the two wiggly boundaries themselves stay far apart, since
    they're separated by roughly the whole tile corner square).
    Returns one flow_layout item with two 'parts'.
    """
    pivot = (size / 2.0, size / 2.0)
    rotated_outline = rotate_points(corner_outline, 180.0, *pivot)
    rotated_outline = [(x, y + gap) for x, y in rotated_outline]
    rotated_lines = [
        [(x, y + gap) for x, y in rotate_points(line, 180.0, *pivot)]
        for line in corner_lines
    ]

    # Nominal bounding box (see paired_frame_item) -- assumes the tab
    # protrusion r is smaller than frame_width, true for this module's
    # connector ratios (stem+bulb well under 1x frame_width).
    return {
        "parts": [
            {"cut_points": corner_outline, "engrave_lines": corner_lines},
            {"cut_points": rotated_outline, "engrave_lines": rotated_lines},
        ],
        "width": size + 2 * frame_width, "height": size + 2 * frame_width + gap,
        "min_x": -frame_width, "min_y": -frame_width,
    }


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


def _open_polyline_normals(points):
    """Per-vertex outward normal for an OPEN polyline: the average of the
    two adjacent segment normals at interior points, or the single
    adjacent segment's normal (a butt end) at the two open ends."""
    normals = []
    n = len(points)
    for i in range(n):
        segment_normals = []
        if i > 0:
            d = (points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
            segment_normals.append(_normalize((d[1], -d[0])))
        if i < n - 1:
            d = (points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
            segment_normals.append(_normalize((d[1], -d[0])))
        avg = tuple(sum(v) for v in zip(*segment_normals))
        normals.append(_normalize(avg))
    return normals


def parallel_lines(points, width, n):
    """Return `n` open polylines, evenly spaced across `width` and offset
    from the centerline perpendicular to it at each point -- N distinct
    engraved strokes spanning the same width a single filled channel would,
    rather than one solid band. n=1 places a single line along the
    centerline itself (no spacing to speak of with only one line).
    """
    normals = _open_polyline_normals(points)
    if n <= 1:
        offsets = [0.0]
    else:
        step = width / (n - 1)
        offsets = [-width / 2.0 + i * step for i in range(n)]
    return [[(p[0] + nrm[0] * off, p[1] + nrm[1] * off) for p, nrm in zip(points, normals)] for off in offsets]


def default_engrave_width(units):
    return 12.7 if units == "mm" else 0.5  # 0.5 inch


def default_frame_width(units):
    return 12.7 if units == "mm" else 0.5  # 0.5 inch, regardless of tile size


def default_nest_gap(units):
    """Tight clearance for pairing frame/corner pieces on the cutting sheet
    (see paired_frame_item/paired_corner_item) -- much smaller than the
    regular sheet margin, since it only needs to clear a flat edge (frame
    pairs) or a single near-touching connector point (corner pairs), not a
    full wiggly boundary."""
    return 3.175 if units == "mm" else 0.125  # 1/8 inch


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
    distinct selectable object, so this lets the whole cut outline (or all
    the engrave lines) be selected and assigned an operation in one click,
    rather than every individual path needing to be picked out by hand.
    `engrave_path_ds` are open polylines (parallel_lines) -- distinct
    stroked lines, not a filled band.
    """
    cut_html = "\n".join(
        f'    <path d="{d}" fill="none" stroke="{CUT_COLOR}" stroke-width="{stroke_width}"/>' for d in cut_path_ds
    )
    engrave_html = "\n".join(
        f'    <path d="{d}" fill="none" stroke="{ENGRAVE_COLOR}" stroke-width="{stroke_width}"/>'
        for d in engrave_path_ds
    )
    return f'  <g id="CUT">\n{cut_html}\n  </g>\n  <g id="ENGRAVE">\n{engrave_html}\n  </g>'


def write_piece_svg(path, min_x, min_y, width, height, units, cut_points, engrave_lines):
    """Write one piece's SVG with an explicit (min_x, min_y, width, height)
    viewBox -- the *nominal* bounding box for this piece type, not one
    computed from the actual (possibly slightly overshooting) geometry, so
    the declared physical size stays exact for XCS's scale verification."""
    stroke_width = max(width, height) * 0.002
    cut_path_ds = [points_to_svg_path(cut_points, closed=True)]
    engrave_path_ds = [points_to_svg_path(line, closed=False) for line in engrave_lines]
    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}{units}" height="{height}{units}" '
        f'viewBox="{min_x} {min_y} {width} {height}">\n'
        f"{svg_groups(cut_path_ds, engrave_path_ds, stroke_width)}\n"
        f"</svg>\n"
    )
    path.write_text(svg)


def write_tile_svg(path, size, units, cut_points, engrave_lines):
    write_piece_svg(path, 0, 0, size, size, units, cut_points, engrave_lines)


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


def write_tile_dxf(path, units, cut_points, engrave_lines):
    """`engrave_lines` are open polylines (parallel_lines) -- N distinct
    stroked lines on the ENGRAVE layer, for a Score/Line operation."""
    entities = _dxf_polyline_lines(cut_points, "CUT", 1, closed=True)
    for line in engrave_lines:
        entities += _dxf_polyline_lines(line, "ENGRAVE", 5, closed=False)
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


def _pdf_path_ops(points, scale, closed=True):
    if not points:
        return ""
    ops = [f"{points[0][0] * scale:.3f} {points[0][1] * scale:.3f} m"]
    ops += [f"{x * scale:.3f} {y * scale:.3f} l" for x, y in points[1:]]
    if closed:
        ops.append("h")
    return " ".join(ops)


def pdf_document(sheet_w, sheet_h, units, cut_polys, engrave_polys):
    """`engrave_polys` are open polylines (parallel_lines) -- N distinct
    stroked lines, drawn the same way as the cut outline (open here too,
    since cut outlines are also stroked, just closed back to their start)."""
    scale = _pdf_points_per_unit(units)
    width_pt, height_pt = sheet_w * scale, sheet_h * scale

    lines = []
    if cut_polys:
        r, g, b = tuple(int(CUT_COLOR[i : i + 2], 16) / 255 for i in (1, 3, 5))
        lines.append(f"{r:.3f} {g:.3f} {b:.3f} RG")
        lines.append("0.5 w")
        for pts in cut_polys:
            lines.append(_pdf_path_ops(pts, scale, closed=True))
            lines.append("S")
    if engrave_polys:
        r, g, b = tuple(int(ENGRAVE_COLOR[i : i + 2], 16) / 255 for i in (1, 3, 5))
        lines.append(f"{r:.3f} {g:.3f} {b:.3f} RG")
        lines.append("0.5 w")
        for pts in engrave_polys:
            lines.append(_pdf_path_ops(pts, scale, closed=False))
            lines.append("S")
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
# Sheet layout: the tile grid's own `columns` count establishes a fixed
# material width, and every piece (tiles, then paired frame units, then
# paired corner units, in that order) flows left to right within that
# width, wrapping to a new row whenever the next piece wouldn't fit --
# never exceeding the width `columns` tiles need. One combined sheet,
# since there's no fixed height to overflow.
# ---------------------------------------------------------------------------

def default_columns(count):
    """A roughly-square default: about as many tile columns as rows."""
    return max(1, math.ceil(math.sqrt(count)))


def wrap_flow_layout(items, row_width, margin):
    """Lay out `items` (dicts with 'width'/'height'/'min_x'/'min_y'/'parts',
    where 'parts' is a list of {'cut_points','engrave_lines'} -- more than
    one part for a combined packing unit like paired_frame_item/
    paired_corner_item, just one for a plain tile) left to right, wrapping
    to a new row whenever the next item wouldn't fit within `row_width` --
    a text-wrap/shelf packing, rather than a fixed items-per-row count, so
    `row_width` (fixed -- established by the tile grid's own column count)
    is never exceeded no matter what's flowing.

    Returns (placements, sheet_w, sheet_h): placements is a list of dicts
    with a 'parts' list, each part's points already shifted to absolute
    coordinates; sheet_w is exactly `row_width`, sheet_h is however tall
    that ends up requiring.
    """
    def place(item, shift_x, shift_y):
        return {
            "parts": [
                {
                    "cut_points": [(x + shift_x, y + shift_y) for x, y in part["cut_points"]],
                    "engrave_lines": [
                        [(x + shift_x, y + shift_y) for x, y in r] for r in part["engrave_lines"]
                    ],
                }
                for part in item["parts"]
            ],
        }

    placements = []
    cursor_x = margin
    cursor_y = margin
    row_height = 0.0
    row_has_item = False
    for item in items:
        if row_has_item and cursor_x + item["width"] + margin > row_width:
            cursor_y += row_height + margin
            cursor_x = margin
            row_height = 0.0
            row_has_item = False
        placements.append(place(item, cursor_x - item["min_x"], cursor_y - item["min_y"]))
        cursor_x += item["width"] + margin
        row_height = max(row_height, item["height"])
        row_has_item = True

    sheet_h = cursor_y + row_height + margin
    return placements, row_width, sheet_h


def write_combined_sheet(output_dir, sheet_number, placements, units, sheet_w, sheet_h):
    """Write one sheet's SVG + DXF + PDF, all three from the same placement
    list -- tiles, frame pieces and corner pieces together, each format's
    CUT geometry grouped/layered separately from its ENGRAVE geometry."""
    stroke_width = sheet_w * 0.001
    cut_path_ds, engrave_path_ds = [], []
    dxf_entities = []
    cut_polys, engrave_polys = [], []
    for p in placements:
        for part in p["parts"]:
            cut_path_ds.append(points_to_svg_path(part["cut_points"], closed=True))
            engrave_path_ds.extend(points_to_svg_path(r, closed=False) for r in part["engrave_lines"])
            dxf_entities += _dxf_polyline_lines(part["cut_points"], "CUT", 1, closed=True)
            for r in part["engrave_lines"]:
                dxf_entities += _dxf_polyline_lines(r, "ENGRAVE", 5, closed=False)
            cut_polys.append(part["cut_points"])
            engrave_polys.extend(part["engrave_lines"])

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

def default_margin(units):
    return 6.0 if units == "mm" else 0.25


def default_output_dir():
    """A fresh timestamped subfolder under ~/Documents so successive runs
    don't overwrite each other, and so the web console and native macOS
    app (whose read-only app bundle can't write next to the script) both
    land somewhere writable and easy to find without configuration."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path.home() / "Documents" / "Interlocking Tile Output" / stamp)


def infer_grid_dims(count):
    """A roughly-square grid_cols x grid_rows for `count` tiles, matching the
    web console's live preview grid so frame/corner counts default to
    whatever grid the preview is already showing."""
    cols = max(1, math.ceil(math.sqrt(count)))
    rows = max(1, math.ceil(count / cols))
    return cols, rows


# The subset of generate_batch()'s summary dict that transport adapters
# (server.py's HTTP handler, the native macOS app's subprocess bridge) send
# back to the browser/WKWebView -- kept as one shared list so every
# transport reports the same shape without duplicating it per adapter.
EXPORT_RESPONSE_FIELDS = [
    "tile_count", "sheet_files", "output_dir", "harmonics",
    "grid_cols", "grid_rows", "frame_count", "corner_count",
    "columns", "sheet_width", "sheet_height",
]


def generate_batch(params):
    """Generate a full tile batch (per-tile + sheet SVG/DXF files) on disk.

    `params` is a dict; see main()'s argparse definitions for accepted keys
    and defaults. Returns a summary dict describing what was written.
    """
    size = float(params.get("size", 2.0))
    units = params.get("units", "in")
    samples = int(params.get("samples_per_edge", 120))
    count = int(params.get("count", 9))

    margin = params.get("sheet_margin")
    margin = default_margin(units) if margin is None else margin

    harmonics = build_edge_harmonics(
        float(params.get("amplitude", 0.25)),
        int(params.get("wiggles", 1)),
        params.get("harmonics"),
        params.get("edge_seed"),
    )
    self_check(size, harmonics, samples)

    output_dir = Path(params.get("output_dir") or default_output_dir())
    output_dir.mkdir(parents=True, exist_ok=True)
    pieces_dir = output_dir / "pieces"
    pieces_dir.mkdir(parents=True, exist_ok=True)

    cut_outline = tile_cut_outline(size, harmonics, samples)
    cut_outline = offset_polygon(cut_outline, float(params.get("kerf_adjust", 0.0)))

    engrave_width = params.get("engrave_width") or default_engrave_width(units)
    engrave_lines_n = int(params.get("engrave_lines") or 3)
    overshoot = max_wiggle_amplitude(harmonics)  # guaranteed >= the true boundary's max excursion anywhere

    face_rng = random.Random(params.get("face_seed"))
    tiles, tile_files = [], []
    for i in range(count):
        motif = face_rng.choice(MOTIFS)
        engrave_lines = [
            line
            for arc in truchet_face_paths(size, motif)
            for line in parallel_lines(extend_polyline_ends(arc, overshoot), engrave_width, engrave_lines_n)
        ]
        tiles.append({
            "parts": [{"cut_points": cut_outline, "engrave_lines": engrave_lines}],
            # Padded by `overshoot` on every side: the wiggly edge runs the
            # whole perimeter and can bow outward past the nominal square
            # anywhere except exactly at the corners, so the flow layout's
            # margin needs to clear that, not just the idealized size x size
            # footprint -- otherwise two rows can wiggle into each other
            # when amplitude is comparable to the margin (verified this
            # actually happens at this module's own CLI defaults).
            "width": size + 2 * overshoot, "height": size + 2 * overshoot,
            "min_x": -overshoot, "min_y": -overshoot,
        })

        svg_path = pieces_dir / f"tile_{i + 1:04d}.svg"
        dxf_path = pieces_dir / f"tile_{i + 1:04d}.dxf"
        write_tile_svg(svg_path, size, units, cut_outline, engrave_lines)
        write_tile_dxf(dxf_path, units, cut_outline, engrave_lines)
        tile_files.append({"svg": str(svg_path), "dxf": str(dxf_path)})

    # Frame and corner pieces border the grid the tiles will be assembled
    # into -- a different concept from how many sheets of material it takes
    # to cut them, hence the separate grid_cols/grid_rows (defaulting to the
    # same roughly-square grid the web preview already shows for `count`).
    default_cols, default_rows = infer_grid_dims(count)
    grid_cols = int(params.get("grid_cols") or default_cols)
    grid_rows = int(params.get("grid_rows") or default_rows)
    frame_width = float(params.get("frame_width") or default_frame_width(units))
    kerf_adjust = float(params.get("kerf_adjust", 0.0))

    frame_count, corner_count = frame_and_corner_counts(grid_cols, grid_rows)

    frame_outline = offset_polygon(frame_piece_outline(size, frame_width, harmonics, samples), kerf_adjust)
    frame_lines = frame_piece_engrave_lines(size, frame_width, harmonics, engrave_width, engrave_lines_n)
    corner_outline = offset_polygon(corner_piece_outline(size, frame_width, harmonics, samples), kerf_adjust)
    corner_lines = corner_piece_engrave_lines(size, frame_width, harmonics, engrave_width, engrave_lines_n)

    # The tab connector protrudes connector_protrusion() past x=size; pad
    # just the per-piece SVG's viewBox (not its declared width/height used
    # for XCS scale verification -- see write_piece_svg) so the standalone
    # inspection file shows the whole piece instead of clipping the tab.
    # The DXF and the combined sheet aren't viewBox-limited, so this is
    # purely cosmetic for the individual preview file.
    r = connector_protrusion(frame_width)

    frame_files, corner_files = [], []
    for i in range(frame_count):
        svg_path = pieces_dir / f"frame_edge_{i + 1:04d}.svg"
        dxf_path = pieces_dir / f"frame_edge_{i + 1:04d}.dxf"
        write_piece_svg(svg_path, 0, -frame_width, size + r, frame_width, units, frame_outline, frame_lines)
        write_tile_dxf(dxf_path, units, frame_outline, frame_lines)
        frame_files.append({"svg": str(svg_path), "dxf": str(dxf_path)})
    for i in range(corner_count):
        svg_path = pieces_dir / f"frame_corner_{i + 1:04d}.svg"
        dxf_path = pieces_dir / f"frame_corner_{i + 1:04d}.dxf"
        write_piece_svg(
            svg_path, -frame_width, -frame_width, size + frame_width + r, size + frame_width,
            units, corner_outline, corner_lines,
        )
        write_tile_dxf(dxf_path, units, corner_outline, corner_lines)
        corner_files.append({"svg": str(svg_path), "dxf": str(dxf_path)})

    # Frame and corner pieces are always needed in even counts (2 per
    # non-corner border run, 4 corners total), so every one of them pairs
    # up -- each pair packed into roughly the footprint of 1.something
    # pieces instead of 2 separate ones (see paired_frame_item/
    # paired_corner_item for the exact nesting).
    gap = default_nest_gap(units)
    frame_pair_items = [
        paired_frame_item(frame_outline, frame_lines, frame_width, size, gap, overshoot)
        for _ in range(frame_count // 2)
    ]
    corner_pair_items = [
        paired_corner_item(corner_outline, corner_lines, size, frame_width, gap)
        for _ in range(corner_count // 2)
    ]

    # The tile grid's own `columns` count establishes a fixed material
    # width; tiles, then paired frame units, then paired corner units flow
    # left to right in that order within it, wrapping to a new row
    # whenever the next piece wouldn't fit -- so frame pairs may wrap to
    # their own row(s), and corner pairs simply continue flowing from
    # wherever the frame pairs left off, never exceeding that width.
    columns = int(params.get("columns") or default_columns(count))
    tile_width = size + 2 * overshoot
    row_width = columns * tile_width + (columns + 1) * margin

    all_items = tiles + frame_pair_items + corner_pair_items
    placements, sheet_w, sheet_h = wrap_flow_layout(all_items, row_width, margin)

    svg_path, dxf_path, pdf_path = write_combined_sheet(output_dir, 1, placements, units, sheet_w, sheet_h)
    sheet_files = [{"svg": str(svg_path), "dxf": str(dxf_path), "pdf": str(pdf_path)}]

    return {
        "harmonics": harmonics,
        "tile_count": count,
        "tile_files": tile_files,
        "sheet_files": sheet_files,
        "columns": columns,
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
    parser.add_argument("--engrave-lines", type=int, default=None, help="number of parallel engrave lines spanning the channel width; default 3")
    parser.add_argument("--units", choices=["in", "mm"], default="in")
    parser.add_argument("--samples-per-edge", type=int, default=120)
    parser.add_argument("--columns", type=int, default=None, help="pieces (tiles+frame+corner) per row when flowing the cutting layout; default: roughly square")
    parser.add_argument("--sheet-margin", type=float, default=None, help="gap between pieces; default: 0.25in / 6mm")
    parser.add_argument("--grid-cols", type=int, default=None, help="tile grid width for frame/corner pieces; default: inferred square-ish from --count")
    parser.add_argument("--grid-rows", type=int, default=None, help="tile grid height for frame/corner pieces; default: inferred square-ish from --count")
    parser.add_argument("--frame-width", type=float, default=None, help="frame/corner piece depth; default 0.5in / 12.7mm")
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="default: ~/Documents/Interlocking Tile Output/<timestamp>, a fresh folder per run",
    )
    args = parser.parse_args()

    try:
        summary = generate_batch(vars(args))
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}")

    print(f"Wrote {len(summary['tile_files'])} tile SVG+DXF pairs, "
          f"{summary['frame_count']} frame + {summary['corner_count']} corner piece SVG+DXF pairs, and "
          f"{len(summary['sheet_files'])} combined sheet SVG+DXF+PDF set to {summary['output_dir']}/")
    print(f"Assembly grid: {summary['grid_cols']}x{summary['grid_rows']}, frame width {summary['frame_width']:g} {args.units}")
    print(f"Cutting layout: {summary['columns']} columns -> required material "
          f"{summary['sheet_width']:g} x {summary['sheet_height']:g} {args.units}")
    print(f"Edge harmonics used (shared by every tile): {summary['harmonics']}")


if __name__ == "__main__":
    main()
