Cutting templates, Mohr lab, ETH Zurich (waterjet)

templates.pdf     every template: name, content (rate, type, angles, number), specimens drawn in colour,
                  rolling direction (RD = vertical on the plans)
instructions.pdf  for each material: which sheet gets which template, and which DXF file to cut
dxf/              one DXF per template, sheet frame at the origin (bottom-left corner = clamp corner),
                  and a PDF with the same name (drawing of the sheet: RD, qualities, dimensions)
                  name: ETH_<RD>x<TD>mm_<NAME>_<sheets of the module>_SHEET_<sheet>_<version>
                  NAME: SLOW78 = slow, INT66 = intermediate (medium) rate, FAST66 = high rate,
                  INTFAST36 = intermediate + fast of campaign C, SLOWINTFAST_210 = whole campaign A

Sizes RD x TD in mm (RD = rolling direction, first value). Lay every template with its RD along the RD of
the sheet, in the bottom-left corner of the sheet.

ETH_600x500mm_SLOW78_2_SHEET_1_v20261113.dxf
    template SLOW78-1, 41 pieces, cut on: 2020_06_03A-3
ETH_600x500mm_SLOW78_2_SHEET_2_v20261113.dxf
    template SLOW78-2, 41 pieces, cut on: 2020_06_03A-5
ETH_600x500mm_INT66_1_SHEET_1_v20261113.dxf
    template MEDIUM66, 66 pieces, cut on: 2020_06_03A-1, 2023_02_28_D-1, 2023_02_28_A-1, 2023_02_28_C-1
ETH_600x500mm_FAST66_1_SHEET_1_v20261113.dxf
    template HIGH66, 66 pieces, cut on: 2020_06_03A-6, 2023_02_28_D-2, 2023_02_28_A-2, 2023_02_28_C-2
ETH_600x500mm_INTFAST36_1_SHEET_1_v20261113.dxf
    template MH18, 36 pieces, cut on: 2025_11_25_B-1
ETH_900x1140mm_SLOWINTFAST_210_1_SHEET_1_v20261113.dxf
    template A_LARGE, 214 pieces, cut on: 2022_05_04_D-1, 2022_05_04_E-1, 2022_05_04_G-1
