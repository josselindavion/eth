# EDM cutting plans (Task II)

Tool that makes the **wire EDM cutting plans** of the specimens: from a list of specimens, it produces the DXF for the
workshop, the notice and the specimen registry.

## Run

**Installation, once on the lab PC:**

```bash
py -m pip install ezdxf shapely matplotlib scipy pyyaml spyrrow==0.9.0 packingsolver
```

`packingsolver` and `spyrrow` are the two placement engines (PackingSolver and sparrow). They need Python 3.10 to
3.14: check with `py --version`.

**The two ready orders:**

```bash
cd ~/Documents/eth
git pull
py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/CAMPAIGN_600x500mm_WATERJET.yaml
```

| Order | Content |
|---|---|
| `orders/CAMPAIGN_600x500mm_WATERJET.yaml` | complete testing campaign of one material (no shear: EDM) for waterjet cutting on **one 600 (RD) × 500 (TD) sheet**: 61 specimens (UT40 at 7 angles, NT20, NT06, CHD48, MNAK_RECT at 0/45/90°, 3 repeats; 1 LASER strip), 4 single clamps 50 × 40 mm (2 per side of the L), 5 mm edge, clamp and placement margins, gap 5 mm, `spread_tries: 3` |
| `orders/AB_SHEETS23_600x500mm_WATERJET.yaml` | campaigns A and B, sheets 2 and 3 (common to both): the rest of campaign B, 126 specimens (tension-type and shear) + 3 LASER, 61 + 68 pieces |
| `orders/A_SHEET4_600x500mm_WATERJET.yaml` | campaign A only, sheet 4: the 24 shear of A not in B (SHLD and SHHD at 45 and 90°) |
| `orders/C_SHEET2_600x500mm_WATERJET.yaml` | campaign C only, its sheet 2: the rest of campaign C, 46 specimens + 3 LASER |
| `orders/B_LARGE_900x1146mm_WATERJET.yaml` | campaign B on **one large sheet** (RA980, RA1200, CR1200Y1500T): one plan of 900 (RD) × 1146 (TD) that replaces the 3 sheets of B (same 186 specimens and codes + 4 LASER), 4 clamps of the L. The 600 × 500 plans stay for the 600 × 500 sheets |
| `orders/campaign_sources/` | written by `make_campaign_orders.py`: `TENSION_AB` (156 tension-type + 4 LASER), `SHEAR_A` (54), `SHEAR_B` (30) |
| `orders/PARTLY_USED_600x500mm_WATERJET_TEST.yaml` | test of the optional forbidden zone (partly used 600 × 500 sheet of 11/11/2026): 24 specimens for the test (campaign C, medium and high rate, tension-type at 0°) |

Campaigns A, B and C are nested (C inside B inside A, same notch codes), so they share their first sheets (`make_nested_orders.py`, journal of 12/11/2026; diagram and previews in `campaigns/campaigns_A_B_C_sheets.pdf`). Every campaign has 4 LASER (1 on sheet 1 + 3).

| Campaign | Sheets | Orders |
|---|---|---|
| A | 4 | `CAMPAIGN` (sheet 1) + `AB_SHEETS23` (sheets 2 and 3) + `A_SHEET4` |
| B | 3 | `CAMPAIGN` (sheet 1) + `AB_SHEETS23` (sheets 2 and 3) |
| B on a large sheet | 1 | `B_LARGE` (one plan of 900 × 1146 instead of the 3 sheets) |
| C | 2 | `CAMPAIGN` (sheet 1) + `C_SHEET2` |

The result of the campaign order is kept in `output/CAMPAIGN_600x500mm_WATERJET/` (one sheet, all checks OK, 1 pair of repeats side by side:
UT40 60°). The other orders (lab plans of 2025 for the EDM, campaigns on the other sheet sizes) were removed on
10/11/2026 (only the 600 × 500 sheet is used); they are in the git history (commit 2e3b00f). To make a new order,
copy this one and change it (fields below).

**Results** in `cutting-sheets/runs/<name>/`:
- `<name>.dxf`: the plan for the workshop;
- `notice.pdf`: one page per sheet (numbered specimens, qualities, rolling direction) and the specimen list;
- `registry.csv`: one line per specimen (number, type, angle, code, position, specimen ID);
- `preview.png`: the plan with the **zones of the sheet on the machine**: clamping (red hatching), machine area =
  wire travel (black dashed), placement margin (orange band), **effective area** where the specimens are placed
  (purple), part of the sheet out of reach of the wire (grey); a problem found by the checks is circled in red. The
  notice shows the same zones.

Nothing else: the intermediate files (coded specimens, detailed check report) are temporary and deleted. The result
of the checks is shown in the terminal.

The terminal shows the 6 steps (`[3/6] Placement`…) and a progress bar with the remaining time. During the placement,
the bar also shows the best height found so far. The checks come at the end: everything must be `OK`.

`runs/` is **ignored by git**: runs can be repeated without git conflicts. To keep a plan in the repository (for
example the one sent to the workshop), add `--final`: it then goes to `output/<name>/`; then
`git add cutting-sheets/output/<name>`, `git commit`, `git push`.

## Writing an order

Copy the order under a new name and edit the lines:

```yaml
name: ETH_300x400mm_SHEET_v20261103_UT30
sheet: 300x400                     # complete sheet, RD x TD (rolling direction first)
clamping: {left: 40, bottom: 40}   # L-shaped clamping
machine_area: 250x350              # wire travel of the EDM (AgieCharmilles CUT E 350), RD x TD
placement_margin: 5                # tolerance on the position of the sheet in the machine
specimens:
  - {type: UT40, angle: 30, count: 5}
  - {type: NT20, angle: 45, count: 3}
```

| Field | Meaning | Default |
|---|---|---|
| `name` | name of the plan, of the output folder and of the DXF | file name |
| `templates` | folder of the templates without code | `catalogue/CTLG_261102` (lab catalogue + `MNAK_RECT`) |
| `sheet` | **complete sheet** in mm, **rolling direction first**: `RDxTD` (`600x500` = 600 mm along the rolling direction × 500 mm across); on the drawing the rolling direction is +Y (vertical) | **required** |
| `clamping` | bands of the sheet held by the clamps, per side (mm), e.g. `{left: 40, bottom: 40}` = L-shaped; bottom = start of the rolling direction | none |
| `machine_area` | area the cutting head can reach, RD × TD in mm (CUT E 350: `250x350` = Y × X travel); leave it out for the waterjet (whole sheet, minus `edge_margin`) | whole sheet |
| `clamps` | single clamps, one line each: `{side: left, at: 175, width: 50, depth: 40}` = clamp of 50 mm along the left edge × 40 mm into the sheet, centred 175 mm from the bottom-left corner; nothing is placed within `clamp_margin` + `placement_margin` of a clamp | none |
| `clamp_margin` | minimum distance between a specimen and a clamp (room for the nozzle) | 5 |
| `machine_position` | distance from the left and bottom edges of the sheet to the machine area, `{left, bottom}` | inner corner of the clamping |
| `placement_margin` | the sheet is not positioned to the mm in the machine: nothing is placed within this distance of the machine area edge (mm) | 5 |
| `edge_margin` | minimum distance to a free (not clamped) edge of the sheet (mm) | 5 |
| `gap` | minimum gap between two pieces (mm) | 5 |
| `assign_time` | seconds of PackingSolver to put all the specimens on sheets (step 1 of the placement) | 30 |
| `fill_tries` | **failed** tries allowed when moving specimens to empty one sheet (step 2); a try that succeeds does not count; 0 = no reduction, faster | 8 |
| `fill_time` | seconds of sparrow at most per try; a try that succeeds stops as soon as everything fits (often 1–3 s); a try less than 2 mm too long gets as much time again | 10 |
| `time` | seconds of sparrow at most per sheet for the compaction (step 3; stopped earlier when it no longer improves); 0 = no compaction | 15 |
| `seed` | seed of sparrow's random draws (change it to try another solution) | 1 |
| `max_sheets` | maximum number of sheets | 20 |
| `spread_distance` | two **repeats** (same type and same angle, e.g. UT40 0° index 1 and 2) closer than this are "side by side" (mm; supervisors: avoid it). After the placement, specimens of other types placed at the same rotation and with the same outer shape swap places to separate them (no space lost); the pairs left are a **warning** (check "Repeats side by side", orange circles on the preview) | 10 |
| `spread_tries` | placements tried to keep the repeats apart (seed, seed + 1, …; swaps on each); the best is kept: fewest sheets, then fewest pairs side by side; stops as soon as no pair is left. Time up to × tries. Command line: `--spread-tries N` | 1 |
| `forbidden` | **optional**, partly used sheet: zone where nothing may be cut, as a union of rectangles `{rd: [from, to], td: [from, to]}` (mm from the bottom-left corner, rolling direction first); see "Partly used sheet" below | none |
| `forbidden_margin` | minimum distance between a specimen and the forbidden zone (mm) | 5 |
| `specimen_id` | optional: `batch`, `sample_geometry`, `additional`, `test_geometry` (per type), for the full specimen ID in the registry | – |
| `specimens` | one line per group: `type`, `angle`, `count`, and optionally `first_index` | – |

There is **one order format**: any other field (a typo, or an old field such as `margins` or the French keys of the
first version) is rejected with the list of allowed fields.

**Effective area** (where the specimens are placed) = machine area minus the placement margin on each side, inside
the sheet, outside the clamping and at least `edge_margin` from a free edge. Example: sheet `300x400` (RD × TD), clamping
left 40 and bottom 40, machine area `250x350`, placement margin 5 → machine area from x 40, y 40 to x 390, y 290,
effective area 240 (RD) × 340 (TD) mm from x 45, y 45. The terminal, the notice and the preview print every size
rolling direction first, marked (RD) / (TD); x = across (TD), y = rolling direction (RD).

**Types** = families of the lab catalogue (`catalogue/specimen_templates_261029_barcoded.dxf`) and of the complementary
catalogue `MNAK_RECT`:

Names of the lab convention (user, 10/11/2026); the older names are still accepted in an order file.

| Type (lab name) | Older names | Catalogue family | Specimen |
|---|---|---|---|
| `UT40` | `UTUT`, `UT` | `CTLG_UTUT` | uniaxial tension, 106 mm; gauge zone 10 mm wide, ≈ 40 mm long |
| `NT20` / `NT06` | `NT6.67` for NT06 | `CTLG_NT20` / `CTLG_NT06` | notched tension, radius 20 / 6.67 mm, 106 mm |
| `CHD48` | `CHCH`, `CH` | `CTLG_CHCH` | central hole Ø 4.8 mm, 106 mm |
| `UT19` | `UTST` | `CTST_UTST` | short uniaxial tension, 81 mm; gauge zone 5 mm wide, ≈ 19 mm between the shoulders |
| `SHLD` / `SHMD` / `SHHD` | – | `CTST_SHLD` / … | short shear, 81 mm; same outline, only the corner next to the code differs |
| `MNAK_ROUND_FULL` | `MNAK_FULL`, `DISC0` | `MNAK_FULL` | round Mini-Nakajima (disc) without holes |
| `MNAK_ROUND_HOLE` | `MNAK_HOLE`, `DISC2` | `MNAK_HOLE` | round Mini-Nakajima with 2 holes; holes at **angle + 90°** (angle 90° = holes along the rolling direction) |
| `MNAK_RECT_HOLE` | `MNAK_RECT` | `MNAK_RECT_HOLE` | **rectangular** Mini-Nakajima 80 × 54 mm with 2 holes (proposal of Erik, 02/11/2026): code on an **end** (short side), chamfer on the left of the code; **angle = same hole orientation as `MNAK_ROUND_HOLE` with the same angle** (90° = holes along the rolling direction), so the coded end is placed at angle − 90° |
| `MNAK_RECT_FULL` | – | `MNAK_RECT_FULL` | the same **without holes** |
| `LASER` | `TENS_FULL`, `STRIP` | `TENS_FULL` | strip 140 × 30 mm without code, for the speckle contrast tests |

The lab name is used in the orders, the notice, the registry (`alias` column; `type` = catalogue family) and the
block names of the plan DXF (`CHD48__090deg__i3`).

- **Angle**: direction of the coded head, measured from the rolling direction (+Y), counter-clockwise. 0° to 135° in
  steps of 15°, for all types. Only exception: `MNAK_RECT` / `MNAK_RECT_FULL`, placed with the coded end at
  angle − 90° so that their holes are oriented as on the disc of the same angle (the code still carries the ordered
  angle).
- **Index**: 0, 1, 2… per type and angle, as in the catalogue (0 to 9, so at most 10 specimens per type and angle).
  `first_index: 1` starts at 1.
- A wrong order is rejected with a message, and nothing is written:
  - angle that cannot be coded (150°, 20°…);
  - more than 10 specimens at the same angle;
  - the same code twice on the same type;
  - unknown type.

## What the program does

1. **Reads the order** and checks it.
2. **Takes the template** of each type (without code), turns it by the placement angle and **adds the code**.
3. **Places** all the specimens:
   - ordered angle or half turn (+180°), never mirrored;
   - gap between pieces and margins per side;
   - two engines (see below), in 3 steps:
     1. **assignment**: PackingSolver puts all the specimens on sheets in `assign_time` seconds → n sheets, each
        with a valid layout;
     2. **reduction**: as long as the specimens could fill n − 1 sheets (≤ 85 % of their area), the specimens of
        the least filled sheet are moved, largest first, to the sheets with the most room (lowest top after
        compaction). For each move, sparrow packs the receiving sheet with one specimen more and is **stopped as soon
        as it fits**. When a specimen misses a sheet by less than 10 mm, that sheet gives its smallest specimen to a
        third sheet (**rebalancing**). Nothing is started again from scratch: specimens already moved stay. When the
        sheet is empty, n − 1;
     3. **compaction**: sparrow packs each sheet as low as possible; the result is kept only if it fits.
4. **Writes the DXF**: mm, layers `Q3_NORMAL` / `Q4_MEDIUM` / `Q5_HIGH`.
5. **Checks the final DXF** without assumptions:
   - closed contours, colours, gaps, margins, overlaps (`check_sheet.py`);
   - **outline** of each specimen = template with its code, turned by the placement angle (≤ 0.02 mm);
   - **code read back** = code ordered, and direction of the coded head = placement angle.
6. Writes the **notice** and the **registry**.

## The placement engines: PackingSolver and sparrow

[PackingSolver](https://github.com/fontanf/packingsolver) (F. Fontan, open source, MIT licence) solves "bin
packing" of arbitrary shapes: which piece on which sheet of fixed size. It gives a valid layout of all the sheets
quickly, but not the densest. It gets the usable area of the sheet (margins removed), the same gap + 0.05 mm and the
same two angles per specimen.

[sparrow](https://arxiv.org/abs/2509.13329) is open-source software (MIT licence) from KU Leuven (2025). It is
published as better than the state of the art for packing arbitrary shapes on a strip of minimum length. It is used
through its Python interface `spyrrow`.

| What it is given | Value |
|---|---|
| Strip | the sheet lying on its side: fixed height = sheet width; length to minimise = rolling direction |
| Shapes | outer outline of each template (without notches, so slightly larger than the piece) |
| Allowed angles | for each specimen, the placement angle and the angle + 180° only (no mirror) |
| Minimum gap | `gap` + 0.05 mm, since sparrow allows about 0.01 mm less; it also keeps this distance to the border |
| Time | `fill_time` per try (stopped as soon as it fits), `time` per sheet for the compaction |
| Process | sparrow runs in a separate process (`sparrow_worker.py`), so that it can be stopped as soon as the answer is known |

Measured results:

| Order | Sheets | Duration |
|---|---|---|
| CT programme, 63 specimens, one 600 (RD) × 500 (TD) sheet | 1 sheet, 514 mm high in 60 s (old in-house engine, dropped on 30/10/2026: 564–571 mm) | 1 min |
| CT programme, 68 specimens, 250 (RD) × 350 (TD) sheets, L-shaped 40 mm, without filling | 5 sheets of 13–14 specimens, 215–230 mm used of 245 | ~4 min 30 s |
| same, with filling (`fill_tries: 8`) | 5 sheets: 14, 14, 15, 15, then 10 specimens; 230–239 mm used on sheets 1–4 | ~11–13 min |
| CT programme with the rectangular Mini-Nakajima (02/11/2026), sparrow only, `time: 10` | 6 sheets (the last with 2 specimens) | 5 min 12 s |
| same, **PackingSolver + sparrow** (250 (RD) × 350 (TD) sheet, L 40 inside the sheet) | 5 sheets of 13–14 specimens, 238–245 mm used of 245 | 6 min 20 s |
| same, **300 (RD) × 400 (TD) sheet on the CUT E 350** (clamping outside the machine area, effective area 240 (RD) × 340 (TD); order removed on 03/11/2026) | **4 sheets** (14, 16, 19, 19 specimens) | **1 min 28 s** |

## Partly used sheet (forbidden zone)

Optional: a sheet whose middle part is already used. The order lists that part as rectangles (they may touch or
overlap; they are merged):

```yaml
forbidden:                          # mm from the bottom-left corner, rolling direction first
  - {rd: [35, 325],  td: [80, 400]}
  - {rd: [325, 450], td: [170, 390]}
  - {rd: [160, 325], td: [400, 430]}
forbidden_margin: 5
```

Nothing is placed within `forbidden_margin` of the zone; it is hatched in grey on the preview and the notice, and a
check "Forbidden zone" verifies the final DXF. How the placement handles it: PackingSolver takes it as a defect;
for sparrow (which knows no obstacles) the zone becomes part of the fixed "wall" item, joined to the clamp comb by a
thin bridge placed where it crosses the least free area; the wall then also has a top bar (clamps of the top edge hang
from it) and 1 mm of play across the strip (every part widened by 1 mm so that the zones stay covered). Without
`forbidden`, none of this is used and the placement is exactly the same as before (checked on the 600 × 500
campaign). Example: `orders/PARTLY_USED_600x500mm_WATERJET_TEST.yaml` (user's sheet of 11/11/2026, 24 specimens,
1 sheet, all checks OK, 20 s).

## Folder content

| Folder | Content |
|---|---|
| `orders/` | the orders (one YAML file per plan) |
| `catalogue/` | the catalogues in DXF: lab catalogue `specimen_templates_261029_barcoded.dxf`, complementary catalogue `specimen_templates_extra_MNAK_RECT.dxf` and its source (Erik's SolidWorks export `RoundSample_Dual_Hole_rectange.dxf`) |
| `catalogue/CTLG_261102/` | the templates used by the program (without code), made from both catalogues: `templates.dxf`, `templates.csv`, `validation.csv`, `templates.png` (every type with its code and its Mikrosteg recesses), `README.md` |
| `scripts/` | `make_plan.py` (order → plan), `placement.py` (placement with PackingSolver and sparrow + DXF), `sparrow_worker.py` (one sparrow run in its own process), `zones.py` (zones of the sheet on the machine: clamping, machine area, placement margin, effective area, optional forbidden zone), `spread.py` (repeats kept apart; bounding-box test before the exact distance since 12/11/2026, same result, faster), `make_campaign_orders.py` + `make_nested_orders.py` (orders of the nested campaigns A, B and C, see the journal of 12/11/2026; `split_campaigns.py` = older A/B split of 11/11/2026), `make_campaign_sheets_pdf.py` (PDF: diagram of the campaign sheets + previews), `orders_from_registry.py` (order from chosen sheets of a plan), `make_campaigns_pdf.py` / `make_campaigns_xlsx.py` (campaign tables), `materials_data.py` (materials, sheets, campaigns: shared data) + `make_materials_pdf.py` (materials and sheets inventory) + `make_material_cuts_pdf.py` (the cutting sheets drawn on the real sheets of each material; needs the DXF of the campaign orders in `output/` or `runs/`), `progress.py` (progress bar), `notchcode.py` (notch code), `make_templates.py` (templates from the catalogues), `build_mnak_rect.py` (complementary catalogue of the rectangular Mini-Nakajima), `check_sheet.py` (check of a DXF), `sheetlib.py` (DXF reading), `mikrosteg.py` (Mikrosteg recesses), `make_user_guide.py` (rebuilds `user_guide.pdf` after a run of the shear plan order) |
| `materials/` | `materials_and_sheets.pdf` (inventory: 8 materials, 22 sheets, campaign of each material and of each sheet), `material_cuts.pdf` (per material, its sheets with the 600 × 500 cutting sheets of its campaign drawn on them) |
| `campaigns/` | campaign tables (Beerli et al. 2026) and `campaigns_A_B_C_sheets.pdf` (which sheet each campaign uses) |
| `runs/` | **ignored by git**: everything that is run |
| `user_guide.pdf` | user guide (installation, running, writing an order, results, checks, error messages) |

## Other tools

**Check any DXF** (for example a drawing received):

```bash
py cutting-sheets/scripts/check_sheet.py path/to/drawing.dxf
```

- The report goes to `runs/reports/<plan>/`.
- Options: `--min-gap 5` (minimum gap, ERROR below), `--warn-gap 5`, `--min-margin 5` (same margin everywhere) or
  `--margins 40 40 5 5` (left, bottom, right, top).
- Checks: units, sheet frame, closed contours, duplicate lines, colours, pieces outside a sheet or overlapping, gaps,
  margins, codes.

**Rebuild the templates** (only if the lab sends a new catalogue):

```bash
py cutting-sheets/scripts/make_templates.py cutting-sheets/catalogue/specimen_templates_261029_barcoded.dxf cutting-sheets/catalogue/specimen_templates_extra_MNAK_RECT.dxf CTLG_261102
```

Several catalogues can be given; the last argument is the name of the template set.

- The type of each specimen is the name of its block family (`CTLG_UTUT_21` → `CTLG_UTUT`).
- Block `_00` is the model. Its 19 code lines and the Q3 line after the code are removed: the length of that line
  depends on the code, which is 12 or 13 mm long.
- **Validation:** every block of the catalogue is rebuilt from the template and the code read on it, then compared
  with the original. The code read must be the block number (`_21` = angle 2 × 15° = 30°, index 1).
- For `CTLG_261102`: 410 / 410 blocks of the lab catalogue + 60 / 60 `MNAK_RECT` blocks correct; code lines within
  0.012 mm, outline within 0.017 mm.

**Complementary catalogue `MNAK_RECT`**: `build_mnak_rect.py` reads Erik's SolidWorks export
(`catalogue/RoundSample_Dual_Hole_rectange.dxf`) and writes `catalogue/specimen_templates_extra_MNAK_RECT.dxf` in the format of
the lab catalogue: 30 blocks `MNAK_RECT_HOLE_<angle><index>` (2 holes) and 30 blocks `MNAK_RECT_FULL_<angle><index>`
(no holes), angles 0, 45, 90°, index 0–9; outline Q3, holes Q5, code on the 49 mm **end** (starting at x = −6 mm, as on
the bars). Erik's part is symmetric, so the rounded corner on the left of the coded end (code on top) is replaced by a
**4 × 4 mm 45° chamfer**, like the chamfered corner of the other specimens (it tells the face from which the code is
read).

## Conventions of the lab drawings

| Element | In the DXF | Meaning |
|---|---|---|
| Units | millimetres (`$INSUNITS = 4`) | – |
| Black frame (colour 7) | rectangle | the raw sheet (minimum size) |
| Green (colour 3) | general outline: heads, sides | quality **Q3** (normal) |
| Cyan (colour 4) | fillets | quality **Q4** (medium) |
| Blue (colour 5) | gauge section, notches, holes, code | quality **Q5** (highest) |
| Rolling direction | +Y axis | the angle of each specimen is measured from +Y |
| Chamfered corner | one 45° corner | orientation and face marker |
| *Mikrosteg* | half-circle recess of radius 1.5 mm in the outline (2 per specimen); red square on the notice | the workshop leaves the bridge at the bottom of the recess (internal Mikrosteg, see below) |

The **colour** gives the quality, not the layer name.

**Rules of the supervisors (29/10/2026, 02/11/2026):**
- 5 mm between pieces;
- L-shaped clamping (workshop, and the lab EDM: AgieCharmilles CUT E 350); 40 mm as for the waterjet (to confirm);
- EDM cutting area = wire travel of the CUT E 350: 350 × 250 mm (X × Y, maker's data); the sheet itself can be
  larger (max. workpiece 820 × 680 mm);
- placement margin inside the machine area, since the sheet is not positioned to the mm (03/11/2026);
- no mirror;
- 2 internal Mikrostegs per specimen (03/11/2026, see below).

## Mikrostegs (internal micro-joints)

Each specimen gets **2 half-circle recesses** (radius 1.5 mm, `R` in `mikrosteg.py`) in its outline (`scripts/mikrosteg.py`). The workshop
stops the wire at the **bottom of each recess**, marked by a red square on the notice: the specimen stays attached by
this small bridge, and after breaking it out the rest of the bridge stays inside the recess, never beyond the specimen
edge. The recesses are part of the closed contour (really cut); there is no gap in the cutting line.

| Type | Mikrosteg 1 | Mikrosteg 2 |
|---|---|---|
| UT40, NT20, NT06, CHD48 (106 mm) | end face of the bottom grip, centred | right side of the top grip (top end = code, left = chamfer) |
| UT19, SHLD, SHMD, SHHD (81 mm) | same | same |
| MNAK_ROUND_HOLE, MNAK_ROUND_FULL (disc) | rim at 30° | rim at 210° (diametrically opposite) |
| MNAK_RECT_HOLE, MNAK_RECT_FULL | bottom end, 14 mm left of centre | coded end, 14 mm right of centre |
| LASER | bottom end face, centred | top end face, centred |

Positions chosen with the user on 03/11/2026: opposite places, in the clamping zones, as far as possible from the test
zone (figures in `journal/2026-11-03.md`). The final check compares every specimen of the DXF with its template
**including the recesses**.

## The notch code

**"Interleaved 2 of 5"** barcode cut in the edge of a head (lab document "Specimen ID"):

| Element | Width | Reading |
|---|---|---|
| 5 notches (white when backlit), 3 mm deep | 1 mm or 2 mm, always **2 wide** | **index** = sum of the weights 1-2-4-7-0 of the 2 wide notches (4 + 7 → 0) |
| 4 lands (black) between the notches, + 1 implicit (edge of the head) | 1 mm or 2 mm, **2 wide** counting the implicit one | **angle** = (sum of the weights 1-2-4-7-0 of the 2 wide lands) × 15° |

- The code is read on top, left to right, with the chamfered corner on the left.
- Example: wide notches no. 2 and 5 → 2 + 0 = index 2; only one wide visible land, no. 2 (the other is the implicit
  one) → 2 × 15° = 30°.
- The visible code is 12 or 13 mm long, 14 mm with the implicit bar.
- Codable angles: 0° to 135° in steps of 15° (150° and 165° are not).
- The full specimen ID (batch, geometries, angle, index…) is not cut: it is used for the lab QR code.
