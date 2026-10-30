# Cutting plan `ETH_300x300mm_SHEET_v20261030_exemple`

*Generated on 2026-10-30 by `cutting-sheets/scripts/make_plan.py` from the order `exemple.yaml` and the templates `CT_v20260901`.*

## Order

| Type | Angle to RD | Number | Indices (notch code) |
|---|---|---|---|
| UT | 30° | 5 | 1, 2, 3, 4, 5 |
| NT20 | 45° | 3 | 1, 2, 3 |
| CH | 0° | 2 | 1, 2 |
| DISC2 | 90° | 2 | 1, 2 |

## Result

12 specimens on 1 sheet(s) of 300 × 300 mm (gap ≥ 5 mm, margin ≥ 5 mm).

| Sheet | Specimens | Height used (mm) |
|---|---|---|
| 1 | 12 | 203.0 |

## Checks of the final DXF

| Check | Status | Detail |
|---|---|---|
| Units | OK | $INSUNITS = 4 (millimetres) |
| Sheets | OK | 1 sheet frame(s): 300 × 300 mm |
| Closed contours | OK | all cutting contours are closed |
| Duplicate lines | OK | none |
| Colours = EDM quality | OK | cutting lines use only colours 3 / 4 / 5 (Q3 / Q4 / Q5): {3: 780, 4: 176, 5: 274} |
| Overlaps | OK | none |
| Gap between pieces | OK | smallest gap 5.43 mm; 0 pair(s) below 5.0 mm, 0 more below 5.0 mm |
| Margin to sheet edge | OK | smallest margin 5.1 mm (limit 5.0 mm) |
| ID codes | OK | 12 of 12 specimens carry a notch code; 12 distinct codes |
| Notch codes / angles | OK | 12 of 12 specimens: code read in the DXF = code ordered, direction = angle ordered |

![Plan](check/preview.png)

## Files

- `ETH_300x300mm_SHEET_v20261030_exemple.dxf`: the plan for the workshop (mm, layers `Q3_NORMAL` / `Q4_MEDIUM` / `Q5_HIGH`, no Mikrosteg).
- `notice.pdf`: one page per sheet (specimen numbers, proposed Mikrosteg in red, qualities, rolling direction) and the specimen list.
- `registry.csv`: one line per specimen: number, sheet, type, angle, notch code (angle digit, index), position, specimen ID (when the batch and geometry codes are given in the order).
- `placement.csv`, `specimens.dxf`: blocks and their insertion; `check/`: report of `check_sheet.py`.
