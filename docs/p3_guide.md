# XTool P3 Guide for Interlocking Tiles

You're new to the P3, so read this fully before cutting real material.

## Machine basics

The P3 is an 80W CO2 laser with a 36"x18" bed and a LiDAR autofocus plus
onboard cameras for positioning. It's rated to cut hardwood up to about
3/4" thick, so 2"x2" tiles in thin plywood are well within its comfort
zone — the challenge here is precision (clean curves, correct scale), not
power.

## Material

- **Recommended**: 1/8" (3mm) basswood or cherry plywood. Thin enough to
  cut crisp detail in the curved interlock at 2" tile scale, while still
  strong enough not to snap at the narrow "necks" where the curve pinches
  in near a bump.
- **Alternative**: 3/16" plywood for a heftier, more tactile tile — expect
  slightly coarser detail on tight curves.
- Avoid PVC, vinyl, or other chlorine-containing plastics — they release
  toxic/corrosive fumes when laser cut. Stick to wood for this project.

## Starting settings (always verify with a test cut)

These are starting points, not guarantees — actual results vary with the
specific plywood batch, grain, moisture, and focus accuracy.

| Material              | Speed     | Power | Passes |
|------------------------|-----------|-------|--------|
| 1/8" (3mm) basswood ply | ~50 mm/s  | 80%   | 1      |
| 1/8" (3mm) cherry ply   | ~45 mm/s  | 80%   | 1      |

- Turn on **air assist** — reduces charring, clears smoke out of the cut
  path, and protects the lens.
- Use the **cut** layer settings above for the red (`#FF0000`) outline
  paths.
- The blue (`#0000FF`) decorative paths are a set of parallel open lines
  (`--engrave-lines`, default 3) spanning the channel width — assign them
  to a line-trace **Score/Engrave** operation, not Fill (there's no closed
  shape to fill). Score settings vary more by look-preference than the cut
  settings above; start low-power (~15-20%) at a moderate speed and do a
  test pass, since it's cosmetic and forgiving.

## Safety

- Run ventilation/fume extraction *before* starting any cut.
- Never leave the machine unattended while it's running.
- Keep a fire extinguisher (CO2 or Class ABC) within reach.
- Check the honeycomb bed is clean — debris underneath can flare up.
- Re-run autofocus whenever you change material or thickness.
- Clean the lens and mirrors per the P3's maintenance schedule; a dirty
  lens both cuts poorly and is a fire risk.
- Wear laser-safety eyewear rated for the P3's wavelength if you ever have
  the enclosure open during operation.
- Keep flammable materials and liquids away from the work area.

## Importing the file correctly

The generator writes an `.svg` and a `.dxf` for every tile and sheet, plus
a combined `.pdf` for each sheet (a reference/print document showing the
whole layout at a glance — not meant for import into XCS; use the DXF).
**Prefer the `.dxf`** if you hit any scale weirdness — SVG has no inherent
physical unit and different tools assume different DPI, which is the single
most common source of "my part came out the wrong size" problems. DXF
carries an explicit units flag ($INSUNITS) that XCS reads directly, so it
isn't subject to that ambiguity. There's no proprietary XCS project format
(`.xcs`) generator here — that format is undocumented and being replaced by
XTool's own newer `.xs` format, so hand-generating it would risk producing
a file that silently fails to open. DXF is the standard, well-specified way
to get exact scale without manual fiddling.

1. Import `output/sheet_0001.dxf` (or an individual `pieces/tile_NNNN.dxf`)
   into XTool Creative Space (XCS). If you use the `.svg` instead, import at
   **original size** — not "scale to fit canvas."
2. Either way, click the object after import and **verify the exact width
   and height** (e.g. 2.000 in) in XCS's size field before cutting.
3. Every cut outline and every engrave shape is grouped into two named
   groups — `CUT` and `ENGRAVE` (a DXF layer in the `.dxf`, an SVG `<g>` in
   the `.svg`) — covering the whole sheet. XCS should let you select the
   entire CUT group in one click and assign it the cut settings, then
   select the entire ENGRAVE group and assign it the fill settings, instead
   of clicking every individual shape.

## Order of operations

1. Generate files: `python3 generate_tiles.py --count N --edge-seed S1 --face-seed S2`
   (start with `--kerf-adjust 0`), or use the web design console (`python3
   server.py`) to preview live and export.
2. Import the `.dxf` into XCS, verify exact scale (above).
3. Assign the red paths/layer to a **Cut** operation and blue paths/layer to
   an **Engrave/Score** operation, using the settings table above as a
   starting point.
4. **Cut a small test coupon first** — generate and cut just 2 tiles, not
   the full batch.
5. Physically test-fit the 2 tiles together. Too loose/sloppy? Increase
   `--kerf-adjust`. Too tight, won't seat? Decrease it. Regenerate and
   re-cut the coupon if needed.
6. Once the fit is good, generate and cut the full batch (`--count`,
   `--grid-cols`/`--grid-rows` if you're finishing the mosaic with a frame) —
   keep the same `--edge-seed` you validated with, and use whatever
   `--face-seed` you like for visual variety. This also cuts the matching
   frame and corner pieces, nested onto the same `sheet_000N` file(s) as the
   tiles — same cut/kerf settings, since their tile-facing edge uses the
   identical curve.
7. Lightly sand the cut edges (fine grit) to knock off any laser char and
   ease friction at the interlock.
8. Do a full assembly test: arrange tiles in a grid, freely rotating and
   swapping them, and confirm they interlock in every combination and that
   the engraved arcs connect visually across tile boundaries. If using a
   frame, confirm the frame/corner pieces seat against the border tiles the
   same way and the engraving continues smoothly into them. Frame/corner
   pieces connect to each other via a "keyhole"/dog-bone joint (a bulb
   wider than its neck) on their short ends — place them going around the
   border in **one consistent direction** (e.g. clockwise) so each tab
   meets the next piece's socket; going the wrong way around presents two
   tabs (or two sockets) to each other, which won't seat. Since the bulb is
   wider than the neck opening, seating each joint takes a bit more than a
   straight push — a slight flex or angled press, same as the tiles'
   wiggly edges already require — but once seated it resists being pulled
   straight back apart.
