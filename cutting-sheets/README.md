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

Its result is kept in `output/CAMPAIGN_600x500mm_WATERJET/` (one sheet, all checks OK, 1 pair of repeats side by side:
UT40 60°). The other orders (lab plans of 2025 for the EDM, campaigns on the other sheet sizes) were removed on
10/11/2026 (only the 600 × 500 sheet is used); they are in the git history (commit 2e3b00f). To make a new order,
copy this one and change it (fields below).

## Folder content

| Folder | Content |
|---|---|
| `orders/` | the orders (one YAML file per plan) |
| `catalogue/` | the catalogues in DXF: lab catalogue `specimen_templates_261029_barcoded.dxf`, complementary catalogue `specimen_templates_extra_MNAK_RECT.dxf` and its source (Erik's SolidWorks export `RoundSample_Dual_Hole_rectange.dxf`) |
| `catalogue/CTLG_261102/` | the templates used by the program (without code), made from both catalogues: `templates.dxf`, `templates.csv`, `validation.csv`, `templates.png` (every type with its code and its Mikrosteg recesses), `README.md` |
| `scripts/` | `make_plan.py` (order → plan), `placement.py` (placement with PackingSolver and sparrow + DXF), `sparrow_worker.py` (one sparrow run in its own process), `zones.py` (zones of the sheet on the machine: clamping, machine area, placement margin, effective area), `progress.py` (progress bar), `notchcode.py` (notch code), `make_templates.py` (templates from the catalogues), `build_mnak_rect.py` (complementary catalogue of the rectangular Mini-Nakajima), `check_sheet.py` (check of a DXF), `sheetlib.py` (DXF reading), `mikrosteg.py` (Mikrosteg recesses), `make_user_guide.py` (rebuilds `user_guide.pdf` after a run of the shear plan order) |
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
