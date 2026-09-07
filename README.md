# Interlocking Tiles

Small vector tiles designed to be manufactured by a laser cutter. Every tile uses the exact
same edge pattern on all four sides, so any tile mates with any other tile
in any rotation — Escher-esque, self-interlocking, no straight edges.

**[Download the native macOS app](https://github.com/bederson/interlocking-tiles/releases/latest)**
— a double-clickable `.app`, no Python or dependencies required (Apple
Silicon only). It's unsigned/not notarized, so see the release notes for
how to get macOS to open it. Or run the [web console](#design-console-web-ui)
from source instead.

![Interlocking Tile Design Console](docs/Screenshot.png)

## How it works

Each edge of the square is a smooth curve built so that it is symmetric
under a 180-degree rotation about its own midpoint. Applying the same curve
(rotated) to all four sides of the tile guarantees that when two identical
tiles sit edge to edge, one tile's bump is exactly the other's notch — in
any of the four rotations. The math is documented in comments in
[generate_tiles.py](generate_tiles.py).

Each tile also gets a decorative engraved motif connecting its edge
midpoints, which line up across tile boundaries regardless of rotation, so
the engraving flows continuously from tile to tile. Three motifs are chosen
at random per tile (seeded by `--face-seed`): two curved (Truchet-style
quarter-circle arcs, in either diagonal), and one straight pass-through (a
"+" through the tile, for a pipe/maze look instead of a flowing curve).

Each engrave path is drawn as `--engrave-lines` (default 3) parallel
strokes, evenly spaced across `--engrave-width` (default 0.5in / 12.7mm) —
N distinct scored lines spanning that channel, rather than one solid filled
band.

The two curved motifs' corner-rounding is controlled by `--curve` (0-1,
default 1): 1 is today's full quarter-circle arc, 0 collapses it to a sharp
90-degree elbow through the tile center instead, and anything in between is
a smoothly rounded corner (a superellipse blend of the two). The straight
pass-through motif has no corner to round, so it's unaffected.

**Flourishes** optionally interrupt one (or two) of the N parallel lines on
each curved motif with a decorative detour, while the line stays one
continuous path: `--flourish-inside` and/or `--flourish-outside` pick
whether the innermost (smallest-radius) and/or outermost (largest-radius)
of the N lines gets a gap bridged by a flourish shape (the untouched
middle lines, if any, still follow the plain curve) — the straight
pass-through motif has no inside/outside to distinguish, so it's never
flourished. `--flourish` selects which shape fills every such gap: a
built-in flourish name (see the web console's 5x5 picker grid — 23 shapes
plus "none" and "random" — for the full set: steps, Greek-key meanders,
loops, figure-eights, spirals, and S-swashes), `random` for a different
one per tile (seeded by `--face-seed`), or `none` (default) for a plain
straight connector across the gap. Each flourish is stored in a canonical
orientation and automatically rotated 180 degrees as needed so it always
bulges away from the rest of the N-line bundle it's inserted next to,
rather than crossing into it.

Each engrave path is also deliberately extended a bit past the tile's
idealized flat edge, since the real (wiggly) cut edge bows outward past
that flat line on one side of every crossing. Any overshoot past the tile's
actual boundary is simply removed when the tile is cut out — same as it
would be if it crossed into a neighboring tile's territory — so this is
harmless and keeps the engraving reaching all the way to the real edge
instead of stopping short and leaving a gap.

## Frame and corner pieces

If you're assembling the tiles into a finished rectangular mosaic, the
generator also builds a matching border: **frame pieces** (one per
non-corner border tile) and **corner pieces** (one per grid corner, L-shaped
so they wrap both of that corner tile's outward-facing edges). A 3x3 grid
needs 4 frame + 4 corner pieces; the grid shape defaults to a roughly-square
layout inferred from `--count` (matching the web preview), or set it
explicitly with `--grid-cols`/`--grid-rows`.

Both piece types are `--frame-width` deep (default: 0.5in / 12.7mm,
regardless of tile size) with one
long/short side an exact copy of the matching tile edge curve (guaranteed to
fit, the same way two tiles fit each other) and the opposite side flat,
completing the assembly's outer rectangle. The decorative engraving
continues straight out from each edge midpoint into the frame, since every
motif meets an edge midpoint moving perpendicular to it regardless of which
of the three motifs it is — so one frame/corner design works no matter which
motif ended up on the neighboring tile.

Frame and corner pieces also connect to *each other* end to end, via a
"keyhole"/dog-bone jigsaw connector on their short ends (one end a bump,
the opposite a matching notch). Unlike a plain semicircular bump, the
bulb is wider than the neck that leads to it, so once seated, a mated
pair can't be pulled straight back apart along the joint — the wide bulb
catches behind the narrower neck opening, giving genuine mechanical
interlock instead of relying on friction alone (seating the joint takes
a bit more than a straight push together, e.g. a slight flex or angled
press, same as the tiles' own wiggly bump-and-notch edges already do).
Every piece uses the same fixed convention, so going around the border
in one consistent direction, each tab automatically meets the next
piece's socket — verified to align exactly all the way around the loop,
corners included.

All frame pieces are identical (as are all corner pieces) — like tiles,
they're exported unrotated and rotated by hand during assembly (this also
means you must assemble the border going around in one consistent
direction, so each tab meets a socket rather than another tab). Files:
`frame_edge_0001.svg`/`.dxf`, `frame_corner_0001.svg`/`.dxf` (individually, for
inspection), and nested alongside the tiles in the combined `sheet_0001.*`
files below rather than a separate sheet, for more efficient material use.

On the cutting sheet specifically (not the individual inspection files,
and not the assembled mosaic), frame and corner pieces are packed in
tightly-nested pairs rather than each getting its own separate slot, since
there are always an even number of each:

- **Frame pairs**: two pieces stacked with one rotated 180°, so their flat
  outer edges face each other with only a small ~1/8in (3mm) gap between
  them — much closer than their wiggly tile-facing edges could safely get.
- **Corner pairs**: two pieces rotated 180° relative to each other so one's
  L-shape fills the square gap the other's L-shape leaves empty, nested
  into very nearly the footprint of a single corner piece.

Every pairing is verified (numerically, across a range of sizes/amplitudes)
to have zero overlap between the two pieces. This packing typically cuts
material use by roughly 10-15% versus placing every frame/corner piece
independently.

## Output files

Each run writes into a fresh timestamped subfolder under
`~/Documents/Interlocking Tile Output/<YYYYMMDD_HHMMSS>/` so successive
exports don't overwrite each other and both the web console and the native
macOS app (whose app bundle is read-only) always land somewhere writable
without any configuration. Pass `--output-dir` (CLI) to use a specific
folder instead.

## Design console (web UI)

```
./run.sh
```

This starts the server and opens the console in your browser automatically
(default `http://127.0.0.1:8765/`; pass a port to use another, e.g.
`./run.sh 8080`). Or run `python3 server.py` yourself and open the printed
URL manually. Click **Export design** at the top any time — it writes the
real SVG + DXF + PDF files using the same `generate_tiles.py` code the CLI
uses, so what you preview is exactly what gets written. Drag the sliders to
preview the tile shape live — the preview grid always shows exactly the
number of tiles set by "# Tiles", each in a random rotation, demonstrating
the edges mesh in every orientation, wrapped in the matching frame/corner
border pieces shown in their correct assembly orientation. Set "Columns"
under "Cutting layout" and the console live-updates the material size
required: that many tile-widths is the material's fixed width, and tiles,
then frame pieces, then corner pieces flow left to right within it,
wrapping to a new row whenever the next piece wouldn't fit — you specify
how many tiles wide the material is, not a target size to fit everything
into. Sliders snap to clean increments (inches in quarter-inch steps, etc.)
so you don't end up with odd decimal values baked into the design.

Control values are saved in your browser (`localStorage`) as you change
them, so reopening the console later picks up where you left off. This is
per-browser, not shared or synced anywhere.

## Native macOS app

The same design console is also available as a standard double-clickable
macOS app — one window, no local web server — built from this same `web/`
and `generate_tiles.py` with no duplicated logic. [Download a prebuilt
copy](https://github.com/bederson/interlocking-tiles/releases/latest), or
see [macos/README.md](macos/README.md) to build it yourself.

## CLI usage

```
python3 generate_tiles.py --count 9 --edge-seed 42 --face-seed 7
```

This writes one combined `sheet_0001.svg`/`.dxf`/`.pdf` per sheet of
material — tiles, frame pieces, and corner pieces all together (frame/corner
nested into the leftover space beside and below the tile grid, rather than
a separate sheet, for more efficient material use) — directly in the output
folder, since those are the files you actually cut. Everything else —
individual `tile_0001.svg`/`.dxf`, `frame_edge_0001.svg`/`.dxf`,
`frame_corner_0001.svg`/`.dxf` files, for inspection/editing one piece at a time —
goes in a `pieces/` subfolder, out of the way.

- **SVG** is for humans — open it in a browser, Illustrator, or Inkscape to
  eyeball the design.
- **DXF** is for the laser software — it carries explicit, unambiguous
  units, so it avoids the classic "SVG imported at the wrong scale" problem
  (see [p3_guide.md](docs/p3_guide.md)). Prefer importing the `.dxf`
  file into XCS if you hit any scale issues with the SVG.
- **PDF** is a single combined reference/print document showing the whole
  sheet layout at once — handy for a print-and-check-against-the-material
  step, or just to see everything together. Generated from scratch (no
  dependency); not intended as a laser-cut source format, use the DXF for
  that.

Key options:

- `--edge-seed` — controls the one shared edge curve for the whole batch.
  **Must be the same for every tile you want to interlock together** —
  regenerating with a different edge seed produces tiles that no longer
  mate with an earlier batch.
- `--face-seed` — controls the per-tile decorative engrave motif; safe to
  vary freely, it doesn't affect the physical fit.
- `--amplitude` — how deep the bumps/notches are (inches).
- `--kerf-adjust` — fine-tune the physical fit after a test cut (positive
  tightens, negative loosens). See [p3_guide.md](docs/p3_guide.md).
  Hidden in the web console (rarely needed once a material's kerf is
  dialed in) but fully functional via the CLI or a direct API call.
- `--engrave-width` — width of the engraved decorative channel (default
  0.5in / 12.7mm).
- `--engrave-lines` — number of parallel lines spanning that channel width
  (default 3).
- `--curve` — 0 (sharp 90-degree corners) to 1 (full quarter-circle arcs,
  default), for the two curved engrave motifs.
- `--flourish` / `--flourish-inside` / `--flourish-outside` — insert a
  decorative flourish shape into the inside and/or outside curve of each
  curved motif; see "How it works" above.
- `--columns` — how many tiles wide the cutting sheet is (default: roughly
  square). That establishes a fixed material width; tiles, then frame
  pieces, then corner pieces flow left to right within it, wrapping to a
  new row whenever the next piece wouldn't fit, so the material is never
  wider than `--columns` tiles. The resulting height is *computed* and
  printed/returned, rather than you specifying a target size to fit.
- `--grid-cols`/`--grid-rows`/`--frame-width` — the final assembled mosaic
  shape (for frame/corner pieces) — a different concept from `--columns`,
  which only affects how pieces are packed for cutting. See "Frame and
  corner pieces" above.
- `--sheet-margin` — gap between pieces on the cutting layout (default
  0.25in / 6mm).
- `--size`, `--count`, `--units` — see `python3 generate_tiles.py --help`
  for the full list.

## Cutting on the XTool P3

See [p3_guide.md](docs/p3_guide.md) for material choice, starting
settings, safety, and the recommended order of operations (always test-cut
a small coupon before committing to a full batch).

# Copyright
Ben Bederson
September 2026
https://www.cs.umd.edu/~bederson/
https://github.com/bederson