# Wood working tiles that go together

## High Level goals
- Use XTool P3 laser cutter to demonstrate some of its features
- Make 2x2" interlocking tiles
- Interlock like standard puzzle pieces - but all use the same pattern so any piece can go anywhere.  Interlock should be Escher-esque
- We are motivated by the design at this website, but we want more visually interesting options (and our tiles are interconnected not straight edges as described above): https://www.fractalkitty.com/week-38-knotty-math-tiles/
- We are new to the P3, so we want detailed guidance on settings, safetey, and order of operations.

## Design approach

- Every tile's four edges are built from one shared curve that is
  point-symmetric about its own midpoint (`g(1-t) = -g(t)`). Applying it to
  all four sides makes any tile mate with any other tile in any of its four
  rotations — the same trick behind self-tiling Escher tessellations.
- A decorative Truchet-style engraved arc connects each tile's edge
  midpoints (which sit at fixed, rotation-invariant points), so the
  engraving flows continuously across tile boundaries regardless of
  rotation, echoing the fractalkitty inspiration while the physical edge
  itself is now the interlocking curve (not a straight edge).
- Geometry is generated in Python (`generate_tiles.py`), no external
  dependencies.

## Deliverables (implemented)

- `generate_tiles.py` — CLI that generates a tile batch as both SVG (for
  viewing/editing) and DXF (for the laser software — has explicit units, so
  it avoids SVG's import-scale ambiguity) plus a bed-sized sheet layout.
- `server.py` + `web/` — a local web design console (`python3 server.py`)
  with live sliders (size, bump depth, kerf fine-tune, edge randomness,
  tile count) that snap to clean increments, a live rotating-grid preview,
  and an Export button that writes files via the same code path as the CLI.
- `p3_guide.md` — XTool P3 material choice, starting cut/engrave
  settings, safety checklist, and order of operations.
- No native XCS/`.xs` project file export — that format is proprietary,
  undocumented, and being replaced by XTool's own newer format, so
  hand-generating one risked producing a file that silently fails to open.
  DXF's explicit units solve the actual scale problem instead.

## Frame, corner, and layout (implemented)

- Frame pieces (border non-corner tiles) and L-shaped corner pieces (border
  corner tiles) reuse the tile's own edge curve on their tile-facing side,
  and connect to *each other* via a "keyhole"/dog-bone jigsaw connector
  (bulb wider than its neck, so a mated pair can't be pulled straight
  apart) on their short ends — one fixed convention so going around the
  border in one direction, every tab meets the next piece's socket.
  Frame/corner depth defaults to a fixed 0.5in / 12.7mm, regardless of
  tile size.
- Cutting layout is columns-first: `--columns` tiles establishes a fixed
  material width, never exceeded by anything that flows afterward. Tiles,
  then paired frame units, then paired corner units flow left to right
  within that width in that order, wrapping to a new row whenever the next
  piece wouldn't fit (frame pairs may wrap to their own row(s); corner
  pairs simply continue from wherever the frame pairs left off). The
  resulting height is computed and reported, not the other way around.
  Frame and corner pieces (always an even count) are packed as tightly-
  nested rotated pairs rather than individually — frame pairs stacked
  flat-edge-to-flat-edge with a small gap, corner pairs rotated 180° so
  one's L-shape fills the other's empty square — cutting material use by
  roughly 10-15% versus independent placement.
- Default output location: `~/Documents/Interlocking Tile Output/
  <timestamp>/`, for both the web console and the native macOS app (whose
  read-only app bundle has nowhere else sensible to write).
- Combined `sheet_0001.svg`/`.dxf`/`.pdf` per sheet (tiles + frame + corner
  together); a from-scratch PDF writer (no dependency) is included purely
  as a combined reference/print document, not a cut source format.

## Status / next steps

- Generator, web console, and P3 guide are built and smoke-tested (self-
  consistency checks, DXF validated with `ezdxf`, JS preview math verified
  identical to the Python export math, tab/socket alignment verified
  numerically all the way around a full border loop, and the whole
  generated sheet DXF checked pairwise for any cut-path crossing --
  including a real margin-vs-wiggle-amplitude bug this check caught and
  fixed, where a tile's actual wiggly boundary could bow past its nominal
  footprint by more than the default margin allowed for).
- Not yet done: an actual physical test cut. Per `p3_guide.md`, cut a
  small (2-4 tile) coupon first to validate the fit and calibrate
  `--kerf-adjust` before committing to a full batch.