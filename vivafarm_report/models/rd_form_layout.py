"""Official RD form field layout (rd.go.th AcroForm rects, พิมพ์ มี.ค. 2560).

Coordinates in PDF POINTS from the top-left of the official page. The QWeb
overlay templates convert pt→mm (x25.4/72) and position data over the
rasterized official background (static/src/forms/*_bg.png).

Field names are the official PDF AcroForm widget names. If the RD re-publishes
a form version, re-extract with pymupdf and replace this dict + the PNGs.
"""

# Printed digit-cell centers (pt) measured from the official form rasters —
# the printed X-XXXX-XXXXX-XX-X tax ID box and the 5-box branch code are NOT
# uniform subdivisions of the AcroForm widget rect, so digit placement must use
# these measured centers instead of the widget width / N.
PRINTED_TAXID_CELLS = {
    'pnd3_cover': [166.5, 183.3, 194.6, 206.0, 217.35, 234.15, 245.5, 256.9,
                   268.2, 279.45, 296.65, 307.95, 324.85],
    'pnd53_cover': [175.05, 191.85, 203.1, 214.5, 225.85, 242.65, 253.95,
                    265.3, 276.7, 288.05, 305.15, 316.45, 333.35],
}
# PND3 and PND53 both have a real 5-slot postcode box (dividers measured from
# the rasters; pitch ~10.7-11.3pt), followed by the dotted line.
# ใบแนบ ภ.ง.ด.3 (attach3): the header tax-id box (371.7→556pt) and the per-row
# tax-id cells (56.8→239.9pt + row pitch ~54.9pt) use the same X-XXXX-XXXXX-XX-X
# 13-cell grid as the covers — centers mapped from the cover's measured cells.
ATTACH3_HDR_TAXID_CELLS = [378.39, 396.52, 408.71, 421.01, 433.26, 451.39,
                           463.63, 475.94, 488.13, 500.27, 518.83, 531.02,
                           549.26]
ATTACH3_ROW_TAXID_CELLS = [63.45, 81.46, 93.57, 105.79, 117.96, 135.97,
                           148.14, 160.36, 172.47, 184.53, 202.97, 215.08,
                           233.2]
ATTACH3_ROW_PITCH = 54.9   # row band 2 starts at y167 (row 1 at y112.2)

PRINTED_POSTCODE_CELLS = {
    'pnd3_cover': [96.1, 106.75, 117.45, 128.05, 138.65],
    'pnd53_cover': [105.2, 116.5, 127.9, 139.25, 150.55],
}

PRINTED_BRANCH_CELLS = {
    'pnd3_cover': [281.75, 292.8, 303.9, 315.0, 326.05],
    'pnd53_cover': [290.45, 301.5, 312.55, 323.65, 334.75],  # measured
}

RD_FORM_LAYOUT = {
 "pnd3_cover": {
  "page_w_pt": 595.2760009765625,
  "page_h_pt": 841.8900146484375,
  "fields": [
   {
    "name": "Button1",
    "type": "Button",
    "x": 506.6,
    "y": 6.6,
    "w": 57.9,
    "h": 22.4,
    "on_state": None
   },
   {
    "name": "Text1.0",
    "type": "Text",
    "x": 160.3,
    "y": 97.0,
    "w": 170.8,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text1.1",
    "type": "Text",
    "x": 274.7,
    "y": 128.0,
    "w": 58.5,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.2",
    "type": "Text",
    "x": 38.4,
    "y": 144.4,
    "w": 294.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.3",
    "type": "Text",
    "x": 88.9,
    "y": 160.6,
    "w": 63.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.4",
    "type": "Text",
    "x": 188.4,
    "y": 160.6,
    "w": 19.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.5",
    "type": "Text",
    "x": 224.6,
    "y": 160.2,
    "w": 12.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.6",
    "type": "Text",
    "x": 264.8,
    "y": 160.4,
    "w": 68.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.7",
    "type": "Text",
    "x": 58.9,
    "y": 175.5,
    "w": 78.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.8",
    "type": "Text",
    "x": 155.3,
    "y": 176.3,
    "w": 13.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.9",
    "type": "Text",
    "x": 210.4,
    "y": 176.1,
    "w": 64.8,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.10",
    "type": "Text",
    "x": 292.9,
    "y": 175.9,
    "w": 39.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.11",
    "type": "Text",
    "x": 56.4,
    "y": 192.4,
    "w": 112.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.12",
    "type": "Text",
    "x": 213.9,
    "y": 192.2,
    "w": 119.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.13",
    "type": "Text",
    "x": 79.4,
    "y": 208.2,
    "w": 107.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.14",
    "type": "Text",
    "x": 214.9,
    "y": 208.0,
    "w": 117.8,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.15",
    "type": "Text",
    "x": 89.6,
    "y": 223.7,
    "w": 54.9,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.16",
    "type": "Text",
    "x": 150.4,
    "y": 224.4,
    "w": 182.1,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Radio Button0",
    "type": "RadioButton",
    "x": 81.3,
    "y": 265.9,
    "w": 13.1,
    "h": 13.3,
    "on_state": "0"
   },
   {
    "name": "Text1.17",
    "type": "Text",
    "x": 279.2,
    "y": 264.0,
    "w": 18.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.18",
    "type": "Text",
    "x": 524.7,
    "y": 114.8,
    "w": 36.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 338.3,
    "y": 142.3,
    "w": 10.8,
    "h": 12.4,
    "on_state": "0"
   },
   {
    "name": "Radio Button2",
    "type": "RadioButton",
    "x": 126.2,
    "y": 308.5,
    "w": 13.1,
    "h": 13.3,
    "on_state": "0"
   },
   {
    "name": "Radio Button3",
    "type": "RadioButton",
    "x": 274.0,
    "y": 340.9,
    "w": 13.1,
    "h": 13.3,
    "on_state": "0"
   },
   {
    "name": "Text1.19",
    "type": "Text",
    "x": 516.6,
    "y": 339.4,
    "w": 26.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.20",
    "type": "Text",
    "x": 517.0,
    "y": 356.1,
    "w": 26.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.21",
    "type": "Text",
    "x": 516.4,
    "y": 392.7,
    "w": 26.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.22",
    "type": "Text",
    "x": 517.3,
    "y": 412.4,
    "w": 25.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.23",
    "type": "Text",
    "x": 451.5,
    "y": 427.0,
    "w": 110.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.24",
    "type": "Text",
    "x": 486.5,
    "y": 441.4,
    "w": 74.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Radio Button0",
    "type": "RadioButton",
    "x": 177.4,
    "y": 266.7,
    "w": 13.1,
    "h": 13.3,
    "on_state": "1"
   },
   {
    "name": "Radio Button2",
    "type": "RadioButton",
    "x": 242.4,
    "y": 308.4,
    "w": 13.1,
    "h": 13.3,
    "on_state": "1"
   },
   {
    "name": "Radio Button2",
    "type": "RadioButton",
    "x": 358.9,
    "y": 308.5,
    "w": 13.1,
    "h": 13.3,
    "on_state": "2"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 394.7,
    "y": 142.3,
    "w": 10.8,
    "h": 12.4,
    "on_state": "1"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 452.9,
    "y": 142.1,
    "w": 10.8,
    "h": 12.4,
    "on_state": "2"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 507.5,
    "y": 142.9,
    "w": 10.8,
    "h": 12.4,
    "on_state": "3"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 338.4,
    "y": 166.0,
    "w": 10.8,
    "h": 12.4,
    "on_state": "4"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 394.9,
    "y": 165.9,
    "w": 10.8,
    "h": 12.4,
    "on_state": "5"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 452.7,
    "y": 165.7,
    "w": 10.8,
    "h": 12.4,
    "on_state": "6"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 507.7,
    "y": 165.5,
    "w": 10.8,
    "h": 12.4,
    "on_state": "7"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 338.2,
    "y": 190.1,
    "w": 10.8,
    "h": 12.4,
    "on_state": "8"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 395.1,
    "y": 189.9,
    "w": 10.8,
    "h": 12.4,
    "on_state": "9"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 452.6,
    "y": 189.9,
    "w": 10.8,
    "h": 12.4,
    "on_state": "11"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 507.7,
    "y": 189.3,
    "w": 10.8,
    "h": 12.4,
    "on_state": "10"
   },
   {
    "name": "Radio Button3",
    "type": "RadioButton",
    "x": 274.0,
    "y": 394.8,
    "w": 13.1,
    "h": 13.3,
    "on_state": "1"
   },
   {
    "name": "Text2.1",
    "type": "Text",
    "x": 441.8,
    "y": 497.5,
    "w": 81.3,
    "h": 13.2,
    "on_state": None
   },
   {
    "name": "Text2.2",
    "type": "Text",
    "x": 441.8,
    "y": 515.4,
    "w": 81.3,
    "h": 13.2,
    "on_state": None
   },
   {
    "name": "Text2.3",
    "type": "Text",
    "x": 441.2,
    "y": 533.2,
    "w": 82.2,
    "h": 14.1,
    "on_state": None
   },
   {
    "name": "Text2.4",
    "type": "Text",
    "x": 441.4,
    "y": 551.4,
    "w": 81.3,
    "h": 13.2,
    "on_state": None
   },
   {
    "name": "Text2.23",
    "type": "Text",
    "x": 226.1,
    "y": 647.6,
    "w": 150.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.24",
    "type": "Text",
    "x": 240.8,
    "y": 664.5,
    "w": 166.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.25",
    "type": "Text",
    "x": 234.8,
    "y": 681.9,
    "w": 16.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.26",
    "type": "Text",
    "x": 272.8,
    "y": 681.7,
    "w": 68.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.27",
    "type": "Text",
    "x": 360.2,
    "y": 681.5,
    "w": 30.7,
    "h": 14.4,
    "on_state": None
   }
  ]
 },
 "pnd53_cover": {
  "page_w_pt": 612.2830200195312,
  "page_h_pt": 858.8980102539062,
  "fields": [
   {
    "name": "Button1",
    "type": "Button",
    "x": 506.6,
    "y": 6.6,
    "w": 57.9,
    "h": 22.4,
    "on_state": None
   },
   {
    "name": "Text1.0",
    "type": "Text",
    "x": 168.7,
    "y": 99.0,
    "w": 170.8,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text1.1",
    "type": "Text",
    "x": 283.5,
    "y": 131.0,
    "w": 58.5,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.2",
    "type": "Text",
    "x": 47.1,
    "y": 147.4,
    "w": 294.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.3",
    "type": "Text",
    "x": 97.7,
    "y": 163.1,
    "w": 63.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.4",
    "type": "Text",
    "x": 197.2,
    "y": 163.1,
    "w": 19.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.5",
    "type": "Text",
    "x": 234.3,
    "y": 163.5,
    "w": 12.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.6",
    "type": "Text",
    "x": 272.7,
    "y": 163.4,
    "w": 68.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.7",
    "type": "Text",
    "x": 68.1,
    "y": 178.9,
    "w": 78.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.8",
    "type": "Text",
    "x": 164.1,
    "y": 179.6,
    "w": 13.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.9",
    "type": "Text",
    "x": 217.8,
    "y": 179.0,
    "w": 64.8,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.10",
    "type": "Text",
    "x": 300.8,
    "y": 178.8,
    "w": 40.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.11",
    "type": "Text",
    "x": 65.6,
    "y": 195.3,
    "w": 112.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.12",
    "type": "Text",
    "x": 223.2,
    "y": 195.1,
    "w": 119.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.13",
    "type": "Text",
    "x": 89.1,
    "y": 211.6,
    "w": 107.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.14",
    "type": "Text",
    "x": 223.7,
    "y": 210.9,
    "w": 117.8,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.15",
    "type": "Text",
    "x": 98.8,
    "y": 226.2,
    "w": 58.9,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.16",
    "type": "Text",
    "x": 158.8,
    "y": 227.3,
    "w": 183.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.17",
    "type": "Text",
    "x": 315.3,
    "y": 256.1,
    "w": 23.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 199.7,
    "y": 272.2,
    "w": 10.8,
    "h": 12.4,
    "on_state": "0"
   },
   {
    "name": "Radio Button0",
    "type": "RadioButton",
    "x": 379.8,
    "y": 125.4,
    "w": 13.1,
    "h": 13.3,
    "on_state": "2"
   },
   {
    "name": "Radio Button2",
    "type": "RadioButton",
    "x": 369.1,
    "y": 205.9,
    "w": 13.1,
    "h": 13.3,
    "on_state": "0"
   },
   {
    "name": "Text1.18",
    "type": "Text",
    "x": 548.7,
    "y": 204.5,
    "w": 18.5,
    "h": 13.0,
    "on_state": None
   },
   {
    "name": "Radio Button3",
    "type": "RadioButton",
    "x": 276.5,
    "y": 330.3,
    "w": 13.1,
    "h": 13.3,
    "on_state": "0"
   },
   {
    "name": "Text1.19",
    "type": "Text",
    "x": 511.0,
    "y": 328.4,
    "w": 41.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.20",
    "type": "Text",
    "x": 511.0,
    "y": 342.8,
    "w": 41.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.21",
    "type": "Text",
    "x": 510.8,
    "y": 382.1,
    "w": 42.8,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.22",
    "type": "Text",
    "x": 511.2,
    "y": 397.0,
    "w": 41.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.23",
    "type": "Text",
    "x": 454.4,
    "y": 411.1,
    "w": 112.4,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.24",
    "type": "Text",
    "x": 489.0,
    "y": 425.5,
    "w": 74.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Radio Button0",
    "type": "RadioButton",
    "x": 379.8,
    "y": 144.3,
    "w": 13.1,
    "h": 13.3,
    "on_state": "0"
   },
   {
    "name": "Radio Button0",
    "type": "RadioButton",
    "x": 380.3,
    "y": 164.1,
    "w": 13.1,
    "h": 13.3,
    "on_state": "1"
   },
   {
    "name": "Radio Button2",
    "type": "RadioButton",
    "x": 465.5,
    "y": 205.7,
    "w": 13.1,
    "h": 13.3,
    "on_state": "1"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 44.7,
    "y": 272.8,
    "w": 10.8,
    "h": 12.4,
    "on_state": "2"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 121.7,
    "y": 272.4,
    "w": 10.8,
    "h": 12.4,
    "on_state": "1"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 274.6,
    "y": 272.9,
    "w": 10.8,
    "h": 12.4,
    "on_state": "3"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 44.8,
    "y": 286.7,
    "w": 10.8,
    "h": 12.4,
    "on_state": "4"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 121.5,
    "y": 286.9,
    "w": 10.8,
    "h": 12.4,
    "on_state": "5"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 199.5,
    "y": 286.8,
    "w": 10.8,
    "h": 12.4,
    "on_state": "6"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 274.8,
    "y": 286.6,
    "w": 10.8,
    "h": 12.4,
    "on_state": "7"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 44.6,
    "y": 300.3,
    "w": 10.8,
    "h": 12.4,
    "on_state": "8"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 121.7,
    "y": 300.6,
    "w": 10.8,
    "h": 12.4,
    "on_state": "9"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 199.9,
    "y": 301.1,
    "w": 10.8,
    "h": 12.4,
    "on_state": "10"
   },
   {
    "name": "Radio Button10",
    "type": "RadioButton",
    "x": 274.7,
    "y": 300.4,
    "w": 10.8,
    "h": 12.4,
    "on_state": "11"
   },
   {
    "name": "Radio Button3",
    "type": "RadioButton",
    "x": 276.5,
    "y": 384.7,
    "w": 13.1,
    "h": 13.3,
    "on_state": "1"
   },
   {
    "name": "Text2.1",
    "type": "Text",
    "x": 414.2,
    "y": 487.4,
    "w": 96.6,
    "h": 13.2,
    "on_state": None
   },
   {
    "name": "Text2.2",
    "type": "Text",
    "x": 414.1,
    "y": 507.1,
    "w": 97.1,
    "h": 14.1,
    "on_state": None
   },
   {
    "name": "Text2.3",
    "type": "Text",
    "x": 413.6,
    "y": 527.1,
    "w": 98.0,
    "h": 14.6,
    "on_state": None
   },
   {
    "name": "Text2.4",
    "type": "Text",
    "x": 413.8,
    "y": 547.6,
    "w": 97.1,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text2.23",
    "type": "Text",
    "x": 243.0,
    "y": 644.7,
    "w": 150.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.24",
    "type": "Text",
    "x": 257.7,
    "y": 661.6,
    "w": 137.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.25",
    "type": "Text",
    "x": 251.7,
    "y": 679.0,
    "w": 16.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.26",
    "type": "Text",
    "x": 289.7,
    "y": 678.8,
    "w": 60.8,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.27",
    "type": "Text",
    "x": 369.0,
    "y": 678.6,
    "w": 30.7,
    "h": 14.4,
    "on_state": None
   }
  ]
 },
 "pnd3_attach": {
  "page_w_pt": 841.8900146484375,
  "page_h_pt": 595.2760009765625,
  "fields": [
   {
    "name": "Button1",
    "type": "Button",
    "x": 626.7,
    "y": 3.4,
    "w": 57.9,
    "h": 22.4,
    "on_state": None
   },
   {
    "name": "Text1.0",
    "type": "Text",
    "x": 376.3,
    "y": 14.7,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text1.1",
    "type": "Text",
    "x": 766.1,
    "y": 13.6,
    "w": 58.5,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.2",
    "type": "Text",
    "x": 708.9,
    "y": 31.5,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.3",
    "type": "Text",
    "x": 772.0,
    "y": 32.2,
    "w": 36.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.27",
    "type": "Text",
    "x": 26.7,
    "y": 111.6,
    "w": 26.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.4",
    "type": "Text",
    "x": 61.2,
    "y": 111.5,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text1.5",
    "type": "Text",
    "x": 284.3,
    "y": 112.3,
    "w": 61.8,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.6",
    "type": "Text",
    "x": 74.6,
    "y": 129.4,
    "w": 168.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.7",
    "type": "Text",
    "x": 276.2,
    "y": 129.9,
    "w": 126.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.8",
    "type": "Text",
    "x": 79.6,
    "y": 146.4,
    "w": 323.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.9",
    "type": "Text",
    "x": 405.5,
    "y": 110.8,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.10",
    "type": "Text",
    "x": 468.5,
    "y": 110.3,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.11",
    "type": "Text",
    "x": 584.0,
    "y": 110.6,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.12",
    "type": "Text",
    "x": 607.5,
    "y": 110.6,
    "w": 94.2,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text1.13",
    "type": "Text",
    "x": 708.6,
    "y": 110.6,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text1.14",
    "type": "Text",
    "x": 804.3,
    "y": 110.3,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.15",
    "type": "Text",
    "x": 405.6,
    "y": 126.9,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.16",
    "type": "Text",
    "x": 468.6,
    "y": 127.1,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.17",
    "type": "Text",
    "x": 584.1,
    "y": 126.7,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.18",
    "type": "Text",
    "x": 607.6,
    "y": 126.7,
    "w": 94.2,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text1.19",
    "type": "Text",
    "x": 708.6,
    "y": 126.7,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text1.20",
    "type": "Text",
    "x": 804.3,
    "y": 126.4,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.21",
    "type": "Text",
    "x": 405.9,
    "y": 143.6,
    "w": 59.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.22",
    "type": "Text",
    "x": 468.9,
    "y": 143.1,
    "w": 113.6,
    "h": 15.0,
    "on_state": None
   },
   {
    "name": "Text1.23",
    "type": "Text",
    "x": 584.3,
    "y": 144.0,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.24",
    "type": "Text",
    "x": 607.3,
    "y": 144.0,
    "w": 94.2,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text1.25",
    "type": "Text",
    "x": 708.9,
    "y": 144.0,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text1.26",
    "type": "Text",
    "x": 804.6,
    "y": 143.1,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.27",
    "type": "Text",
    "x": 26.7,
    "y": 167.3,
    "w": 26.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.1",
    "type": "Text",
    "x": 61.3,
    "y": 167.4,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text2.2",
    "type": "Text",
    "x": 284.3,
    "y": 168.2,
    "w": 61.8,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text2.3",
    "type": "Text",
    "x": 74.6,
    "y": 185.3,
    "w": 168.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.4",
    "type": "Text",
    "x": 276.2,
    "y": 185.8,
    "w": 126.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.5",
    "type": "Text",
    "x": 79.6,
    "y": 202.3,
    "w": 323.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.6",
    "type": "Text",
    "x": 405.5,
    "y": 166.7,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.7",
    "type": "Text",
    "x": 468.5,
    "y": 166.2,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.8",
    "type": "Text",
    "x": 584.0,
    "y": 166.5,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.9",
    "type": "Text",
    "x": 607.6,
    "y": 166.5,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text2.10",
    "type": "Text",
    "x": 708.6,
    "y": 166.5,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text2.11",
    "type": "Text",
    "x": 804.3,
    "y": 166.2,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.12",
    "type": "Text",
    "x": 405.6,
    "y": 182.8,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.13",
    "type": "Text",
    "x": 468.6,
    "y": 183.0,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.14",
    "type": "Text",
    "x": 584.1,
    "y": 182.6,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.15",
    "type": "Text",
    "x": 607.6,
    "y": 182.6,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text2.16",
    "type": "Text",
    "x": 708.6,
    "y": 182.6,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text2.17",
    "type": "Text",
    "x": 804.4,
    "y": 182.3,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.18",
    "type": "Text",
    "x": 405.9,
    "y": 199.5,
    "w": 59.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.19",
    "type": "Text",
    "x": 468.9,
    "y": 199.0,
    "w": 113.6,
    "h": 15.0,
    "on_state": None
   },
   {
    "name": "Text2.20",
    "type": "Text",
    "x": 584.4,
    "y": 199.9,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.21",
    "type": "Text",
    "x": 607.3,
    "y": 199.9,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text2.22",
    "type": "Text",
    "x": 708.9,
    "y": 199.9,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text2.23",
    "type": "Text",
    "x": 804.7,
    "y": 199.0,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.27",
    "type": "Text",
    "x": 26.3,
    "y": 222.5,
    "w": 26.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.1",
    "type": "Text",
    "x": 61.9,
    "y": 223.1,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text3.2",
    "type": "Text",
    "x": 285.0,
    "y": 223.8,
    "w": 61.8,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text3.3",
    "type": "Text",
    "x": 75.3,
    "y": 240.9,
    "w": 168.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.4",
    "type": "Text",
    "x": 276.9,
    "y": 241.4,
    "w": 126.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.5",
    "type": "Text",
    "x": 80.3,
    "y": 258.0,
    "w": 323.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.6",
    "type": "Text",
    "x": 405.5,
    "y": 221.0,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.7",
    "type": "Text",
    "x": 468.5,
    "y": 221.2,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.8",
    "type": "Text",
    "x": 584.0,
    "y": 221.5,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.9",
    "type": "Text",
    "x": 607.6,
    "y": 221.5,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text3.10",
    "type": "Text",
    "x": 708.6,
    "y": 221.4,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text3.11",
    "type": "Text",
    "x": 804.3,
    "y": 221.2,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.12",
    "type": "Text",
    "x": 405.6,
    "y": 237.8,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.13",
    "type": "Text",
    "x": 468.6,
    "y": 238.0,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.14",
    "type": "Text",
    "x": 584.1,
    "y": 237.6,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.15",
    "type": "Text",
    "x": 607.6,
    "y": 238.2,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text3.16",
    "type": "Text",
    "x": 708.6,
    "y": 238.2,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text3.17",
    "type": "Text",
    "x": 804.4,
    "y": 237.3,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.18",
    "type": "Text",
    "x": 406.6,
    "y": 254.5,
    "w": 59.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.19",
    "type": "Text",
    "x": 469.5,
    "y": 254.6,
    "w": 113.6,
    "h": 15.0,
    "on_state": None
   },
   {
    "name": "Text3.20",
    "type": "Text",
    "x": 585.0,
    "y": 255.6,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.21",
    "type": "Text",
    "x": 607.9,
    "y": 254.9,
    "w": 94.2,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text3.22",
    "type": "Text",
    "x": 708.9,
    "y": 254.9,
    "w": 91.0,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text3.23",
    "type": "Text",
    "x": 805.3,
    "y": 254.6,
    "w": 18.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.27",
    "type": "Text",
    "x": 26.6,
    "y": 278.5,
    "w": 26.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.1",
    "type": "Text",
    "x": 60.8,
    "y": 277.8,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text4.2",
    "type": "Text",
    "x": 284.5,
    "y": 278.5,
    "w": 61.8,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text4.3",
    "type": "Text",
    "x": 74.1,
    "y": 296.3,
    "w": 168.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.4",
    "type": "Text",
    "x": 275.8,
    "y": 296.8,
    "w": 126.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.5",
    "type": "Text",
    "x": 79.2,
    "y": 313.4,
    "w": 323.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.6",
    "type": "Text",
    "x": 405.1,
    "y": 277.1,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.7",
    "type": "Text",
    "x": 468.0,
    "y": 276.6,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.8",
    "type": "Text",
    "x": 583.5,
    "y": 277.5,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.9",
    "type": "Text",
    "x": 607.1,
    "y": 276.9,
    "w": 94.2,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text4.10",
    "type": "Text",
    "x": 709.4,
    "y": 276.8,
    "w": 89.7,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text4.11",
    "type": "Text",
    "x": 804.5,
    "y": 277.2,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.12",
    "type": "Text",
    "x": 405.8,
    "y": 293.9,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.13",
    "type": "Text",
    "x": 468.8,
    "y": 293.4,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.14",
    "type": "Text",
    "x": 584.3,
    "y": 293.6,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.15",
    "type": "Text",
    "x": 607.2,
    "y": 293.6,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text4.16",
    "type": "Text",
    "x": 709.5,
    "y": 293.6,
    "w": 89.7,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text4.17",
    "type": "Text",
    "x": 804.6,
    "y": 293.4,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.18",
    "type": "Text",
    "x": 406.1,
    "y": 310.5,
    "w": 59.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.19",
    "type": "Text",
    "x": 468.4,
    "y": 309.4,
    "w": 113.6,
    "h": 15.0,
    "on_state": None
   },
   {
    "name": "Text4.20",
    "type": "Text",
    "x": 583.9,
    "y": 310.3,
    "w": 21.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.21",
    "type": "Text",
    "x": 607.5,
    "y": 310.9,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text4.22",
    "type": "Text",
    "x": 709.8,
    "y": 310.2,
    "w": 90.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text4.23",
    "type": "Text",
    "x": 804.8,
    "y": 309.4,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.27",
    "type": "Text",
    "x": 26.2,
    "y": 333.7,
    "w": 26.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.1",
    "type": "Text",
    "x": 61.1,
    "y": 333.4,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text5.2",
    "type": "Text",
    "x": 284.8,
    "y": 334.1,
    "w": 61.8,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text5.3",
    "type": "Text",
    "x": 74.5,
    "y": 351.8,
    "w": 168.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.4",
    "type": "Text",
    "x": 276.1,
    "y": 352.4,
    "w": 126.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.5",
    "type": "Text",
    "x": 79.5,
    "y": 368.9,
    "w": 323.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.6",
    "type": "Text",
    "x": 406.1,
    "y": 332.6,
    "w": 59.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.7",
    "type": "Text",
    "x": 469.0,
    "y": 332.8,
    "w": 112.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.8",
    "type": "Text",
    "x": 584.5,
    "y": 332.4,
    "w": 20.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.9",
    "type": "Text",
    "x": 607.4,
    "y": 332.4,
    "w": 94.2,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text5.10",
    "type": "Text",
    "x": 709.7,
    "y": 332.4,
    "w": 89.7,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text5.11",
    "type": "Text",
    "x": 804.2,
    "y": 332.8,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.12",
    "type": "Text",
    "x": 406.1,
    "y": 348.8,
    "w": 59.9,
    "h": 15.0,
    "on_state": None
   },
   {
    "name": "Text5.13",
    "type": "Text",
    "x": 469.1,
    "y": 348.9,
    "w": 112.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.14",
    "type": "Text",
    "x": 584.6,
    "y": 349.2,
    "w": 20.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.15",
    "type": "Text",
    "x": 607.5,
    "y": 349.2,
    "w": 94.2,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text5.16",
    "type": "Text",
    "x": 709.8,
    "y": 349.2,
    "w": 89.7,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text5.17",
    "type": "Text",
    "x": 804.2,
    "y": 348.9,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.18",
    "type": "Text",
    "x": 405.8,
    "y": 366.1,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.19",
    "type": "Text",
    "x": 468.7,
    "y": 366.2,
    "w": 112.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.20",
    "type": "Text",
    "x": 584.2,
    "y": 365.9,
    "w": 20.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.21",
    "type": "Text",
    "x": 607.8,
    "y": 365.9,
    "w": 94.2,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text5.22",
    "type": "Text",
    "x": 708.8,
    "y": 365.8,
    "w": 91.0,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text5.23",
    "type": "Text",
    "x": 804.5,
    "y": 364.9,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.27",
    "type": "Text",
    "x": 25.9,
    "y": 389.7,
    "w": 26.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.1",
    "type": "Text",
    "x": 61.3,
    "y": 388.9,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text6.2",
    "type": "Text",
    "x": 285.0,
    "y": 389.6,
    "w": 61.8,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text6.3",
    "type": "Text",
    "x": 74.6,
    "y": 408.0,
    "w": 168.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.4",
    "type": "Text",
    "x": 276.2,
    "y": 407.9,
    "w": 126.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.5",
    "type": "Text",
    "x": 79.6,
    "y": 425.1,
    "w": 323.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.6",
    "type": "Text",
    "x": 405.5,
    "y": 388.2,
    "w": 60.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.7",
    "type": "Text",
    "x": 468.5,
    "y": 388.3,
    "w": 113.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.8",
    "type": "Text",
    "x": 584.7,
    "y": 387.9,
    "w": 20.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.9",
    "type": "Text",
    "x": 607.6,
    "y": 387.9,
    "w": 94.3,
    "h": 13.9,
    "on_state": None
   },
   {
    "name": "Text6.10",
    "type": "Text",
    "x": 708.6,
    "y": 387.9,
    "w": 91.0,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text6.11",
    "type": "Text",
    "x": 804.3,
    "y": 388.3,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.12",
    "type": "Text",
    "x": 405.6,
    "y": 404.3,
    "w": 60.5,
    "h": 15.0,
    "on_state": None
   },
   {
    "name": "Text6.13",
    "type": "Text",
    "x": 469.2,
    "y": 404.4,
    "w": 112.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.14",
    "type": "Text",
    "x": 584.7,
    "y": 404.7,
    "w": 20.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.15",
    "type": "Text",
    "x": 607.6,
    "y": 404.7,
    "w": 94.3,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text6.16",
    "type": "Text",
    "x": 708.6,
    "y": 404.7,
    "w": 91.0,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text6.17",
    "type": "Text",
    "x": 804.4,
    "y": 404.4,
    "w": 19.3,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.18",
    "type": "Text",
    "x": 405.9,
    "y": 421.6,
    "w": 59.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.19",
    "type": "Text",
    "x": 468.9,
    "y": 421.7,
    "w": 112.9,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.20",
    "type": "Text",
    "x": 584.4,
    "y": 421.4,
    "w": 20.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.21",
    "type": "Text",
    "x": 607.3,
    "y": 421.4,
    "w": 94.9,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text6.22",
    "type": "Text",
    "x": 709.6,
    "y": 420.7,
    "w": 89.7,
    "h": 15.2,
    "on_state": None
   },
   {
    "name": "Text6.23",
    "type": "Text",
    "x": 804.7,
    "y": 420.4,
    "w": 18.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.24",
    "type": "Text",
    "x": 607.8,
    "y": 443.4,
    "w": 93.9,
    "h": 14.5,
    "on_state": None
   },
   {
    "name": "Text6.25",
    "type": "Text",
    "x": 708.6,
    "y": 443.1,
    "w": 89.7,
    "h": 15.2,
    "on_state": None
   },
   {
    "name": "Text9.1",
    "type": "Text",
    "x": 615.5,
    "y": 511.9,
    "w": 142.1,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text9.2",
    "type": "Text",
    "x": 624.9,
    "y": 529.4,
    "w": 160.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text9.3",
    "type": "Text",
    "x": 618.9,
    "y": 545.9,
    "w": 22.8,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text9.4",
    "type": "Text",
    "x": 664.1,
    "y": 546.6,
    "w": 66.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text9.5",
    "type": "Text",
    "x": 750.7,
    "y": 546.7,
    "w": 37.9,
    "h": 14.4,
    "on_state": None
   }
  ]
 },
 "pnd53_attach": {
  "page_w_pt": 841.8900146484375,
  "page_h_pt": 595.2760009765625,
  "fields": [
   {
    "name": "Button1",
    "type": "Button",
    "x": 745.9,
    "y": 3.4,
    "w": 57.9,
    "h": 22.4,
    "on_state": None
   },
   {
    "name": "Text1.0",
    "type": "Text",
    "x": 376.3,
    "y": 14.0,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text1.1",
    "type": "Text",
    "x": 590.0,
    "y": 13.6,
    "w": 61.1,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.2",
    "type": "Text",
    "x": 704.3,
    "y": 30.8,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.3",
    "type": "Text",
    "x": 768.0,
    "y": 30.9,
    "w": 36.7,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.4",
    "type": "Text",
    "x": 25.9,
    "y": 111.4,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.5",
    "type": "Text",
    "x": 58.4,
    "y": 111.5,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text1.6",
    "type": "Text",
    "x": 72.6,
    "y": 125.4,
    "w": 265.6,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text1.7",
    "type": "Text",
    "x": 78.5,
    "y": 137.7,
    "w": 260.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text1.8",
    "type": "Text",
    "x": 78.3,
    "y": 147.7,
    "w": 260.2,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text1.9",
    "type": "Text",
    "x": 339.9,
    "y": 110.9,
    "w": 62.4,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text1.10",
    "type": "Text",
    "x": 404.4,
    "y": 127.6,
    "w": 60.0,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text1.11",
    "type": "Text",
    "x": 467.3,
    "y": 128.0,
    "w": 113.7,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text1.12",
    "type": "Text",
    "x": 583.5,
    "y": 127.6,
    "w": 20.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text1.13",
    "type": "Text",
    "x": 605.4,
    "y": 127.9,
    "w": 95.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text1.14",
    "type": "Text",
    "x": 708.4,
    "y": 127.5,
    "w": 90.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text1.15",
    "type": "Text",
    "x": 803.6,
    "y": 128.5,
    "w": 19.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text1.16",
    "type": "Text",
    "x": 404.4,
    "y": 138.0,
    "w": 60.4,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.17",
    "type": "Text",
    "x": 467.4,
    "y": 138.3,
    "w": 114.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.18",
    "type": "Text",
    "x": 583.5,
    "y": 137.9,
    "w": 19.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.19",
    "type": "Text",
    "x": 605.4,
    "y": 138.2,
    "w": 95.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.20",
    "type": "Text",
    "x": 708.5,
    "y": 137.8,
    "w": 89.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.21",
    "type": "Text",
    "x": 803.7,
    "y": 138.8,
    "w": 19.2,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.22",
    "type": "Text",
    "x": 404.2,
    "y": 149.3,
    "w": 60.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.23",
    "type": "Text",
    "x": 467.1,
    "y": 149.6,
    "w": 114.2,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text1.24",
    "type": "Text",
    "x": 583.3,
    "y": 149.2,
    "w": 20.0,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.25",
    "type": "Text",
    "x": 605.2,
    "y": 149.5,
    "w": 95.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.26",
    "type": "Text",
    "x": 708.2,
    "y": 149.2,
    "w": 90.0,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text1.27",
    "type": "Text",
    "x": 804.1,
    "y": 150.1,
    "w": 18.7,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text2.4",
    "type": "Text",
    "x": 25.6,
    "y": 163.8,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.5",
    "type": "Text",
    "x": 58.0,
    "y": 163.9,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text2.6",
    "type": "Text",
    "x": 72.3,
    "y": 177.8,
    "w": 266.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text2.7",
    "type": "Text",
    "x": 78.2,
    "y": 190.1,
    "w": 260.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text2.8",
    "type": "Text",
    "x": 77.9,
    "y": 200.1,
    "w": 260.2,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text2.9",
    "type": "Text",
    "x": 339.6,
    "y": 163.3,
    "w": 62.4,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text2.10",
    "type": "Text",
    "x": 404.0,
    "y": 180.0,
    "w": 60.0,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text2.11",
    "type": "Text",
    "x": 467.0,
    "y": 179.7,
    "w": 113.7,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text2.12",
    "type": "Text",
    "x": 583.1,
    "y": 180.0,
    "w": 20.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text2.13",
    "type": "Text",
    "x": 605.0,
    "y": 180.3,
    "w": 95.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text2.14",
    "type": "Text",
    "x": 708.1,
    "y": 179.9,
    "w": 90.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text2.15",
    "type": "Text",
    "x": 803.3,
    "y": 180.9,
    "w": 19.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text2.16",
    "type": "Text",
    "x": 404.1,
    "y": 190.4,
    "w": 60.4,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.17",
    "type": "Text",
    "x": 467.0,
    "y": 190.7,
    "w": 114.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.18",
    "type": "Text",
    "x": 583.2,
    "y": 190.3,
    "w": 20.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.19",
    "type": "Text",
    "x": 605.0,
    "y": 190.6,
    "w": 95.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.20",
    "type": "Text",
    "x": 708.1,
    "y": 190.2,
    "w": 89.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.21",
    "type": "Text",
    "x": 803.3,
    "y": 191.2,
    "w": 19.2,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.22",
    "type": "Text",
    "x": 403.8,
    "y": 201.7,
    "w": 60.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.23",
    "type": "Text",
    "x": 466.8,
    "y": 202.0,
    "w": 114.2,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text2.24",
    "type": "Text",
    "x": 582.9,
    "y": 201.6,
    "w": 20.6,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.25",
    "type": "Text",
    "x": 604.8,
    "y": 201.9,
    "w": 95.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.26",
    "type": "Text",
    "x": 708.5,
    "y": 201.6,
    "w": 89.3,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text2.27",
    "type": "Text",
    "x": 803.1,
    "y": 202.5,
    "w": 20.0,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text3.4",
    "type": "Text",
    "x": 25.6,
    "y": 216.2,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.5",
    "type": "Text",
    "x": 58.0,
    "y": 216.2,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text3.6",
    "type": "Text",
    "x": 72.3,
    "y": 230.2,
    "w": 266.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text3.7",
    "type": "Text",
    "x": 78.2,
    "y": 242.5,
    "w": 260.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text3.8",
    "type": "Text",
    "x": 77.9,
    "y": 252.5,
    "w": 260.2,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text3.9",
    "type": "Text",
    "x": 339.6,
    "y": 215.7,
    "w": 62.4,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text3.10",
    "type": "Text",
    "x": 404.0,
    "y": 232.4,
    "w": 60.0,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text3.11",
    "type": "Text",
    "x": 467.0,
    "y": 232.1,
    "w": 113.7,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text3.12",
    "type": "Text",
    "x": 583.1,
    "y": 232.4,
    "w": 20.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text3.13",
    "type": "Text",
    "x": 605.0,
    "y": 232.6,
    "w": 95.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text3.14",
    "type": "Text",
    "x": 708.1,
    "y": 232.3,
    "w": 90.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text3.15",
    "type": "Text",
    "x": 803.3,
    "y": 233.2,
    "w": 19.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text3.16",
    "type": "Text",
    "x": 404.1,
    "y": 242.7,
    "w": 60.4,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.17",
    "type": "Text",
    "x": 467.0,
    "y": 243.0,
    "w": 114.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.18",
    "type": "Text",
    "x": 583.2,
    "y": 242.7,
    "w": 20.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.19",
    "type": "Text",
    "x": 605.0,
    "y": 243.0,
    "w": 95.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.20",
    "type": "Text",
    "x": 708.1,
    "y": 242.6,
    "w": 89.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.21",
    "type": "Text",
    "x": 803.3,
    "y": 243.5,
    "w": 19.2,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.22",
    "type": "Text",
    "x": 403.8,
    "y": 254.0,
    "w": 60.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.23",
    "type": "Text",
    "x": 466.8,
    "y": 254.4,
    "w": 114.2,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text3.24",
    "type": "Text",
    "x": 582.9,
    "y": 254.0,
    "w": 20.6,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.25",
    "type": "Text",
    "x": 604.8,
    "y": 254.3,
    "w": 95.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.26",
    "type": "Text",
    "x": 708.5,
    "y": 253.9,
    "w": 89.3,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text3.27",
    "type": "Text",
    "x": 803.1,
    "y": 254.9,
    "w": 20.0,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text4.4",
    "type": "Text",
    "x": 26.1,
    "y": 269.2,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.5",
    "type": "Text",
    "x": 58.5,
    "y": 269.2,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text4.6",
    "type": "Text",
    "x": 72.8,
    "y": 283.2,
    "w": 266.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text4.7",
    "type": "Text",
    "x": 78.7,
    "y": 295.5,
    "w": 260.7,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text4.8",
    "type": "Text",
    "x": 78.4,
    "y": 305.5,
    "w": 260.8,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text4.9",
    "type": "Text",
    "x": 340.1,
    "y": 268.7,
    "w": 62.4,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text4.10",
    "type": "Text",
    "x": 404.5,
    "y": 285.4,
    "w": 60.0,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text4.11",
    "type": "Text",
    "x": 467.5,
    "y": 285.1,
    "w": 113.7,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text4.12",
    "type": "Text",
    "x": 583.5,
    "y": 285.0,
    "w": 20.7,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text4.13",
    "type": "Text",
    "x": 605.5,
    "y": 285.7,
    "w": 95.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text4.14",
    "type": "Text",
    "x": 708.6,
    "y": 285.3,
    "w": 90.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text4.15",
    "type": "Text",
    "x": 803.8,
    "y": 286.2,
    "w": 19.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text4.16",
    "type": "Text",
    "x": 404.6,
    "y": 295.7,
    "w": 60.4,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.17",
    "type": "Text",
    "x": 467.5,
    "y": 296.1,
    "w": 113.4,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.18",
    "type": "Text",
    "x": 582.9,
    "y": 295.4,
    "w": 21.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.19",
    "type": "Text",
    "x": 605.5,
    "y": 296.0,
    "w": 95.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.20",
    "type": "Text",
    "x": 708.6,
    "y": 295.6,
    "w": 89.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.21",
    "type": "Text",
    "x": 803.8,
    "y": 296.6,
    "w": 19.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.22",
    "type": "Text",
    "x": 404.3,
    "y": 307.1,
    "w": 60.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.23",
    "type": "Text",
    "x": 467.3,
    "y": 307.4,
    "w": 114.2,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text4.24",
    "type": "Text",
    "x": 583.3,
    "y": 306.0,
    "w": 20.6,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text4.25",
    "type": "Text",
    "x": 605.3,
    "y": 307.3,
    "w": 95.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.26",
    "type": "Text",
    "x": 709.0,
    "y": 307.0,
    "w": 89.3,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text4.27",
    "type": "Text",
    "x": 803.6,
    "y": 307.9,
    "w": 20.0,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text5.4",
    "type": "Text",
    "x": 26.0,
    "y": 321.5,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.5",
    "type": "Text",
    "x": 58.4,
    "y": 321.6,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text5.6",
    "type": "Text",
    "x": 72.7,
    "y": 335.6,
    "w": 266.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text5.7",
    "type": "Text",
    "x": 78.6,
    "y": 347.9,
    "w": 260.7,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text5.8",
    "type": "Text",
    "x": 78.4,
    "y": 357.9,
    "w": 260.8,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text5.9",
    "type": "Text",
    "x": 340.0,
    "y": 321.1,
    "w": 62.4,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text5.10",
    "type": "Text",
    "x": 404.5,
    "y": 337.8,
    "w": 60.0,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text5.11",
    "type": "Text",
    "x": 467.4,
    "y": 337.4,
    "w": 113.7,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text5.12",
    "type": "Text",
    "x": 582.8,
    "y": 337.4,
    "w": 21.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text5.13",
    "type": "Text",
    "x": 605.5,
    "y": 338.0,
    "w": 95.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text5.14",
    "type": "Text",
    "x": 708.5,
    "y": 337.7,
    "w": 90.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text5.15",
    "type": "Text",
    "x": 803.7,
    "y": 338.6,
    "w": 19.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text5.16",
    "type": "Text",
    "x": 404.5,
    "y": 348.1,
    "w": 60.4,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.17",
    "type": "Text",
    "x": 467.4,
    "y": 348.4,
    "w": 114.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.18",
    "type": "Text",
    "x": 582.8,
    "y": 347.7,
    "w": 21.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.19",
    "type": "Text",
    "x": 605.5,
    "y": 348.4,
    "w": 95.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.20",
    "type": "Text",
    "x": 708.5,
    "y": 348.0,
    "w": 89.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.21",
    "type": "Text",
    "x": 803.7,
    "y": 348.9,
    "w": 19.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.22",
    "type": "Text",
    "x": 404.3,
    "y": 359.4,
    "w": 60.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.23",
    "type": "Text",
    "x": 467.2,
    "y": 359.8,
    "w": 114.2,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text5.24",
    "type": "Text",
    "x": 582.6,
    "y": 358.4,
    "w": 21.3,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text5.25",
    "type": "Text",
    "x": 605.3,
    "y": 359.7,
    "w": 95.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.26",
    "type": "Text",
    "x": 708.3,
    "y": 359.3,
    "w": 90.0,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text5.27",
    "type": "Text",
    "x": 803.5,
    "y": 360.3,
    "w": 20.0,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text6.4",
    "type": "Text",
    "x": 26.0,
    "y": 373.9,
    "w": 27.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.5",
    "type": "Text",
    "x": 58.4,
    "y": 374.0,
    "w": 179.9,
    "h": 15.8,
    "on_state": None
   },
   {
    "name": "Text6.6",
    "type": "Text",
    "x": 72.7,
    "y": 387.9,
    "w": 266.2,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text6.7",
    "type": "Text",
    "x": 78.6,
    "y": 400.2,
    "w": 260.7,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text6.8",
    "type": "Text",
    "x": 78.4,
    "y": 410.2,
    "w": 260.8,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text6.9",
    "type": "Text",
    "x": 340.0,
    "y": 373.5,
    "w": 62.4,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text6.10",
    "type": "Text",
    "x": 404.5,
    "y": 390.1,
    "w": 60.0,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text6.11",
    "type": "Text",
    "x": 467.4,
    "y": 389.8,
    "w": 113.7,
    "h": 13.7,
    "on_state": None
   },
   {
    "name": "Text6.12",
    "type": "Text",
    "x": 582.8,
    "y": 389.8,
    "w": 21.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text6.13",
    "type": "Text",
    "x": 605.5,
    "y": 390.4,
    "w": 95.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text6.14",
    "type": "Text",
    "x": 708.5,
    "y": 390.0,
    "w": 90.1,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text6.15",
    "type": "Text",
    "x": 803.7,
    "y": 391.0,
    "w": 19.4,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text6.16",
    "type": "Text",
    "x": 404.5,
    "y": 400.5,
    "w": 60.4,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.17",
    "type": "Text",
    "x": 467.4,
    "y": 400.8,
    "w": 114.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.18",
    "type": "Text",
    "x": 582.8,
    "y": 400.1,
    "w": 21.1,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.19",
    "type": "Text",
    "x": 605.5,
    "y": 400.7,
    "w": 95.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.20",
    "type": "Text",
    "x": 708.5,
    "y": 400.4,
    "w": 89.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.21",
    "type": "Text",
    "x": 803.7,
    "y": 401.3,
    "w": 19.8,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.22",
    "type": "Text",
    "x": 404.3,
    "y": 411.8,
    "w": 60.5,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.23",
    "type": "Text",
    "x": 467.2,
    "y": 412.1,
    "w": 114.2,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text6.24",
    "type": "Text",
    "x": 582.6,
    "y": 410.8,
    "w": 21.3,
    "h": 13.1,
    "on_state": None
   },
   {
    "name": "Text6.25",
    "type": "Text",
    "x": 605.3,
    "y": 412.0,
    "w": 95.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.26",
    "type": "Text",
    "x": 708.3,
    "y": 411.7,
    "w": 90.0,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.27",
    "type": "Text",
    "x": 803.5,
    "y": 412.6,
    "w": 20.0,
    "h": 11.7,
    "on_state": None
   },
   {
    "name": "Text6.28",
    "type": "Text",
    "x": 605.3,
    "y": 426.8,
    "w": 95.9,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text6.29",
    "type": "Text",
    "x": 708.4,
    "y": 426.8,
    "w": 90.0,
    "h": 12.4,
    "on_state": None
   },
   {
    "name": "Text9.1",
    "type": "Text",
    "x": 616.1,
    "y": 510.6,
    "w": 141.5,
    "h": 17.0,
    "on_state": None
   },
   {
    "name": "Text9.2",
    "type": "Text",
    "x": 624.3,
    "y": 528.8,
    "w": 161.8,
    "h": 15.7,
    "on_state": None
   },
   {
    "name": "Text9.3",
    "type": "Text",
    "x": 618.9,
    "y": 547.2,
    "w": 23.5,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text9.4",
    "type": "Text",
    "x": 664.1,
    "y": 547.3,
    "w": 66.0,
    "h": 14.4,
    "on_state": None
   },
   {
    "name": "Text9.5",
    "type": "Text",
    "x": 750.7,
    "y": 547.3,
    "w": 30.7,
    "h": 14.4,
    "on_state": None
   }
  ]
 }
}
