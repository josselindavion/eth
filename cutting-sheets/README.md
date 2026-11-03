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
py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/ETH_450x380mm_ShearEDM_v20250520.yaml
py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/ETH_300x300_6_SHEET_v20250520.yaml
```

| Order | Content |
|---|---|
| `orders/ETH_300x300_6_SHEET_v20250520.yaml` | lab plan of the same name (66 specimens + 5 extra strips): 4 sheets |
| `orders/ETH_450x400_3_SHEET_v20250520.yaml` | lab plan of the same name (66 specimens + 5 extra strips): 4 sheets |
| `orders/ETH_600x500mm_2_SHEET_v20250220.yaml` | lab plan of the same name (64 specimens + 4 extra strips): 4 sheets |
| `orders/ETH_450x380mm_ShearEDM_v20250520.yaml` | lab shear plan of the same name (24 shear specimens + 1 extra strip): 1 sheet |
| `orders/ETH_600x500mm_2_SHEET_v20260901_CT_bardcode.yaml` | CT drawing of 2026 of the same name (68 specimens, already Christmas tree models; discs replaced by the rectangular Mini-Nakajima): 4 sheets |

One order per lab plan of `input/` (the `.pdf` / `.dxf` of 2025, and the CT drawing of 2026), for the EDM machine (400 × 300 mm sheets on the
CUT E 350, L-shaped 40 mm clamping, effective area 340 × 240 mm). The old models of those plans (straight grips,
140 mm; shear blanks 93 mm) are replaced by the catalogue models with the "Christmas tree" grips; same angles and same
notch codes as in the plans (read in their DXF); the discs are replaced by the rectangular Mini-Nakajima, and extra
`TENS_FULL` strips fill the space left on the sheets. Each order file explains its correspondence in its header.

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

Copy one of the orders under a new name and edit the lines:

```yaml
name: ETH_400x300mm_SHEET_v20261103_UT30
sheet: 400x300                     # complete sheet
clamping: {left: 40, bottom: 40}   # L-shaped clamping
machine_area: 350x250              # wire travel of the EDM (AgieCharmilles CUT E 350)
placement_margin: 5                # tolerance on the position of the sheet in the machine
specimens:
  - {type: UTUT, angle: 30, count: 5}
  - {type: NT20, angle: 45, count: 3}
```

| Field | Meaning | Default |
|---|---|---|
| `name` | name of the plan, of the output folder and of the DXF | file name |
| `templates` | folder of the templates without code | `templates/CTLG_261102` (lab catalogue + `MNAK_RECT`) |
| `sheet` | **complete sheet**, width × height in mm; the height is the rolling direction | **required** |
| `clamping` | bands of the sheet held by the clamps, per side (mm), e.g. `{left: 40, bottom: 40}` = L-shaped; bottom = start of the rolling direction | none |
| `machine_area` | area the wire can reach, width × height in mm (CUT E 350: `350x250`, X × Y travel) | **required** |
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
| `specimen_id` | optional: `batch`, `sample_geometry`, `additional`, `test_geometry` (per type), for the full specimen ID in the registry | – |
| `specimens` | one line per group: `type`, `angle`, `count`, and optionally `first_index` | – |

There is **one order format**: any other field (a typo, or an old field such as `margins` or the French keys of the
first version) is rejected with the list of allowed fields.

**Effective area** (where the specimens are placed) = machine area minus the placement margin on each side, inside
the sheet, outside the clamping and at least `edge_margin` from a free edge. Example: sheet 400 × 300, clamping left
40 and bottom 40, machine area 350 × 250, placement margin 5 → machine area from (40, 40) to (390, 290), effective
area 340 × 240 mm from (45, 45). The terminal and the notice print these numbers.

**Types** = families of the lab catalogue (`input/specimen_templates_261029_barcoded.dxf`) and of the complementary
catalogue `MNAK_RECT`:

| Type | Short name | Specimen |
|---|---|---|
| `UTUT` | `UT` | uniaxial tension, 106 mm |
| `NT20` / `NT06` | `NT6.67` for NT06 | notched tension, radius 20 / 6.67 mm, 106 mm |
| `CHCH` | `CH` | central hole Ø 4.8 mm, 106 mm |
| `UTST` | – | short uniaxial tension, 81 mm |
| `SHLD` / `SHMD` / `SHHD` | – | short shear, 81 mm; same outline, only the corner next to the code differs |
| `MNAK_FULL` | `DISC0` | disc without holes |
| `MNAK_HOLE` | `DISC2` | disc with 2 holes; holes at **angle + 90°** (angle 90° = holes along the rolling direction) |
| `MNAK_RECT_HOLE` | `MNAK_RECT` | **rectangular** Mini-Nakajima 80 × 54 mm with 2 holes (proposal of Erik, 02/11/2026): code on an **end** (short side), chamfer on the left of the code; **angle = same hole orientation as the disc `MNAK_HOLE` with the same angle** (90° = holes along the rolling direction), so the coded end is placed at angle − 90° |
| `MNAK_RECT_FULL` | – | the same **without holes** (equivalent of `MNAK_FULL`) |
| `TENS_FULL` | `STRIP` | strip 140 × 30 mm without code |

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
| CT programme, 63 specimens, one 500 × 600 sheet | 1 sheet, 514 mm high in 60 s (old in-house engine, dropped on 30/10/2026: 564–571 mm) | 1 min |
| CT programme, 68 specimens, 350 × 250 sheets, L-shaped 40 mm, without filling | 5 sheets of 13–14 specimens, 215–230 mm used of 245 | ~4 min 30 s |
| same, with filling (`fill_tries: 8`) | 5 sheets: 14, 14, 15, 15, then 10 specimens; 230–239 mm used on sheets 1–4 | ~11–13 min |
| CT programme with the rectangular Mini-Nakajima (02/11/2026), sparrow only, `time: 10` | 6 sheets (the last with 2 specimens) | 5 min 12 s |
| same, **PackingSolver + sparrow** (350 × 250 sheet, L 40 inside the sheet) | 5 sheets of 13–14 specimens, 238–245 mm used of 245 | 6 min 20 s |
| same, **400 × 300 sheet on the CUT E 350** (clamping outside the machine area, effective area 340 × 240; order removed on 03/11/2026) | **4 sheets** (14, 16, 19, 19 specimens) | **1 min 28 s** |

## Folder content

| Folder | Content |
|---|---|
| `orders/` | the orders: one per lab plan of `input/` |
| `docs/` | `user_guide.pdf`: user guide (installation, running, writing an order, results, checks, error messages); `make_user_guide.py` rebuilds it after a run of the shear plan order |
| `templates/CTLG_261102/` | templates without code, from the lab catalogue and the complementary catalogue `MNAK_RECT`: `templates.dxf`, `templates.csv`, `validation.csv`, `templates.png`, `README.md` |
| `scripts/` | `make_plan.py` (order → plan), `placement.py` (placement with PackingSolver and sparrow + DXF), `sparrow_worker.py` (one sparrow run in its own process), `zones.py` (zones of the sheet on the machine: clamping, machine area, placement margin, effective area), `progress.py` (progress bar), `notchcode.py` (notch code), `make_templates.py` (templates from the catalogues), `build_mnak_rect.py` (complementary catalogue of the rectangular Mini-Nakajima), `check_sheet.py` (check of a DXF), `sheetlib.py` (DXF reading) |
| `input/` | files received from the lab: catalogue `specimen_templates_261029_barcoded.dxf`, CT drawing `…v20260901_CT_bardcode.dxf`, 2025 drawings (`.dxf` + notices `.pptx` / `.pdf`), SolidWorks export `RoundSample_Dual_Hole_rectange.dxf`, and the complementary catalogue `specimen_templates_extra_MNAK_RECT.dxf` |
| `runs/` | **ignored by git**: everything that is run |

## Other tools

**Check any DXF** (for example a drawing received):

```bash
py cutting-sheets/scripts/check_sheet.py cutting-sheets/input/ETH_600x500mm_2_SHEET_v20260901_CT_bardcode.dxf
```

- The report goes to `runs/reports/<plan>/`.
- Options: `--min-gap 5` (minimum gap, ERROR below), `--warn-gap 5`, `--min-margin 5` (same margin everywhere) or
  `--margins 40 40 5 5` (left, bottom, right, top).
- Checks: units, sheet frame, closed contours, duplicate lines, colours, pieces outside a sheet or overlapping, gaps,
  margins, codes.

**Rebuild the templates** (only if the lab sends a new catalogue):

```bash
py cutting-sheets/scripts/make_templates.py cutting-sheets/input/specimen_templates_261029_barcoded.dxf cutting-sheets/input/specimen_templates_extra_MNAK_RECT.dxf CTLG_261102
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
(`input/RoundSample_Dual_Hole_rectange.dxf`) and writes `input/specimen_templates_extra_MNAK_RECT.dxf` in the format of
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
| *Mikrosteg* | half-circle recess R 1 mm in the outline (2 per specimen); red square on the notice | the workshop leaves the bridge at the bottom of the recess (internal Mikrosteg, see below) |

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

Each specimen gets **2 half-circle recesses** (radius 1 mm) in its outline (`scripts/mikrosteg.py`). The workshop
stops the wire at the **bottom of each recess**, marked by a red square on the notice: the specimen stays attached by
this small bridge, and after breaking it out the rest of the bridge stays inside the recess, never beyond the specimen
edge. The recesses are part of the closed contour (really cut); there is no gap in the cutting line.

| Type | Mikrosteg 1 | Mikrosteg 2 |
|---|---|---|
| UTUT, NT20, NT06, CHCH (106 mm) | end face of the bottom grip, centred | right side of the top grip (top end = code, left = chamfer) |
| UTST, SHLD, SHMD, SHHD (81 mm) | same | same |
| MNAK_HOLE, MNAK_FULL (disc) | rim at 30° | rim at 210° (diametrically opposite) |
| MNAK_RECT_HOLE, MNAK_RECT_FULL | bottom end, 14 mm left of centre | coded end, 14 mm right of centre |
| TENS_FULL | bottom end face, centred | top end face, centred |

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
