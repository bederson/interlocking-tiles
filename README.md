# Interlocking Tiles

2"x2" wooden tiles for the XTool P3 laser cutter. Every tile uses the exact
same edge pattern on all four sides, so any tile mates with any other tile
in any rotation — Escher-esque, self-interlocking, no straight edges.

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

Engrave paths are generated as filled bands (0.5in / 12.7mm wide by
default, `--engrave-width` to change), not thin lines — see the note in
[docs/p3_guide.md](docs/p3_guide.md) about assigning them to an
Engrave/Fill operation in XCS so the laser actually rasters the full width.

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

Both piece types are `--frame-width` deep (default: tile size / 3) with one
long/short side an exact copy of the matching tile edge curve (guaranteed to
fit, the same way two tiles fit each other) and the opposite side flat,
completing the assembly's outer rectangle. The decorative engraving
continues straight out from each edge midpoint into the frame, since every
motif meets an edge midpoint moving perpendicular to it regardless of which
of the three motifs it is — so one frame/corner design works no matter which
motif ended up on the neighboring tile.

All frame pieces are identical (as are all corner pieces) — like tiles,
they're exported unrotated and rotated by hand during assembly. Files:
`frame_0001.svg`/`.dxf`, `corner_0001.svg`/`.dxf` (individually, for
inspection), plus `frame_sheet_0001.svg`/`.dxf` packing all of them
together for cutting.

## Output files

Each run writes into a fresh timestamped subfolder (`output/<YYYYMMDD_HHMMSS>/`)
so successive exports don't overwrite each other. Pass `--output-dir` (CLI)
or type a path into the "Output folder" field (web console) to use a
specific folder instead.

## Design console (web UI)

```
./run.sh
```

This starts the server and opens the console in your browser automatically
(default `http://127.0.0.1:8765/`; pass a port to use another, e.g.
`./run.sh 8080`). Or run `python3 server.py` yourself and open the printed
URL manually. Drag the sliders to preview the tile shape live — the preview
grid always shows exactly the number of tiles set by "Tiles to export", each
in a random rotation, demonstrating the edges mesh in every orientation.
Enter your material's width/height under "Material sheet to cut on" and the
console live-updates how many tiles fit per sheet and how many sheets are
needed, flagging an error if a single tile won't fit at all. Click
**Export to disk** to write the real SVG + DXF files — the export always
uses the same `generate_tiles.py` code the CLI uses, so what you preview is
exactly what gets written. Sliders snap to clean increments (inches in
quarter-inch steps, etc.) so you don't end up with odd decimal values baked
into the design.

Control values are saved in your browser (`localStorage`) as you change
them, so reopening the console later picks up where you left off. This is
per-browser, not shared or synced anywhere.

## CLI usage

```
python3 generate_tiles.py --count 9 --edge-seed 42 --face-seed 7
```

This writes, per tile, both `tile_0001.svg`/`tile_0001.dxf` ... (for
inspection/editing) and a batch `sheet_0001.svg`/`sheet_0001.dxf` laid out
on a P3-sized bed.

- **SVG** is for humans — open it in a browser, Illustrator, or Inkscape to
  eyeball the design.
- **DXF** is for the laser software — it carries explicit, unambiguous
  units, so it avoids the classic "SVG imported at the wrong scale" problem
  (see [docs/p3_guide.md](docs/p3_guide.md)). Prefer importing the `.dxf`
  file into XCS if you hit any scale issues with the SVG.

Key options:

- `--edge-seed` — controls the one shared edge curve for the whole batch.
  **Must be the same for every tile you want to interlock together** —
  regenerating with a different edge seed produces tiles that no longer
  mate with an earlier batch.
- `--face-seed` — controls the per-tile decorative engrave motif; safe to
  vary freely, it doesn't affect the physical fit.
- `--amplitude` — how deep the bumps/notches are (inches).
- `--kerf-adjust` — fine-tune the physical fit after a test cut (positive
  tightens, negative loosens). See [docs/p3_guide.md](docs/p3_guide.md).
- `--engrave-width` — width of the engraved decorative channel (default
  0.5in / 12.7mm).
- `--sheet-width`/`--sheet-height` — the material size to lay tiles out on
  (default: P3 bed, 36in x 18in). If `--count` needs more tiles than fit on
  one sheet, multiple numbered sheet files are written. If a single tile
  doesn't fit on the given sheet at all, generation stops with a clear
  error instead of producing a broken layout.
- `--grid-cols`/`--grid-rows`/`--frame-width` — the final assembled mosaic
  shape (for frame/corner pieces), independent of sheet packing. See "Frame
  and corner pieces" above.
- `--size`, `--count`, `--units` — see `python3 generate_tiles.py --help`
  for the full list.

## Cutting on the XTool P3

See [docs/p3_guide.md](docs/p3_guide.md) for material choice, starting
settings, safety, and the recommended order of operations (always test-cut
a small coupon before committing to a full batch).
