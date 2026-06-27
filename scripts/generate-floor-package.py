#!/usr/bin/env python3
"""
Generate src/lx-floor-package.svg — faithful reproduction of IMG_0382
(SYNRGY · Trance Tour 2026 · TOURIST · "SMALL RIG").

Three stacked views with 60px pure-white separator gaps (split-the-views
detection rows) and a right-hand SYNRGY title block per view.

GitHub-Preview safe: no <use>, no <symbol>, no xlink, no <?xml?> prolog —
all fixture geometry is emitted inline.
"""

# ───────────────────────── canvas ─────────────────────────
CW = 3600                     # canvas width
VH = 900                      # per-view height
GAP = 60                      # white separator gap
CH = VH * 3 + GAP * 2         # 2820

TBX = 3150                    # title-block left edge
TBW = CW - TBX - 10           # title-block width (440)
DAX0, DAX1 = 30, TBX - 20     # drawing-area x extents

BLUE = "#0a52d8"              # dimension colour
RED = "#e23b2e"               # Ayrton marker / DESIGN INTENT
GRY = "#888888"
LGRY = "#cccccc"
HDR = "#111111"

out = []
def e(s): out.append(s)


# ───────────────────────── primitives ─────────────────────────
def rect(x, y, w, h, sw=1.0, fill="white", stroke="black", rx=0, dash=None, opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{opacity}"' if opacity is not None else ""
    r = f' rx="{rx}"' if rx else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"{r} '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{o}/>')

def line(x1, y1, x2, y2, sw=1.0, stroke="black", dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

def circ(cx, cy, r, sw=1.0, fill="white", stroke="black", dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

def text(x, y, s, size=12, anchor="start", weight="normal", style="normal",
         fill="black", family="Helvetica, Arial, sans-serif", spacing=None):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    s = (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" font-style="{style}" fill="{fill}" '
            f'text-anchor="{anchor}"{ls}>{s}</text>')


# ───────────────────────── plan fixtures ─────────────────────────
def base_plate(cx, cy, w, h):
    """Doughty tank-trap base plate, top-down: square with corner bolt ticks."""
    g = [rect(cx - w/2, cy - h/2, w, h, sw=1.1)]
    t = 3
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx, by = cx + sx*(w/2 - 4), cy + sy*(h/2 - 4)
            g.append(rect(bx - t/2, by - t/2, t, t, sw=0.6))
    return "".join(g)

def led_par_plan(cx, cy, scale):
    """LED Par on base plate (top-down): plate + barrel + top indicator tab."""
    w = 1.9*scale; h = 2.1*scale
    g = [base_plate(cx, cy, w, h)]
    # top indicator tab (rounded)
    g.append(rect(cx - 0.45*scale, cy - h/2 + 0.12*scale, 0.9*scale, 0.32*scale,
                  sw=0.7, rx=2))
    # barrel: two stacked rounded segments
    bw = 0.95*scale
    g.append(rect(cx - bw/2, cy - 0.55*scale, bw, 0.55*scale, sw=0.8, rx=2))
    g.append(rect(cx - bw/2, cy,            bw, 0.55*scale, sw=0.8, rx=2))
    # yoke legs
    g.append(line(cx - bw/2, cy + 0.55*scale, cx - bw/2, cy + 0.9*scale, 0.7))
    g.append(line(cx + bw/2, cy + 0.55*scale, cx + bw/2, cy + 0.9*scale, 0.7))
    return "".join(g)

def ayrton_plan(cx, cy, scale):
    """Ayrton Rivale Profile (top-down): dashed movement circle + body + RED marker."""
    r = 1.35*scale
    g = [circ(cx, cy, r, sw=0.7, fill="none", dash="3,2.5")]
    bw, bh = 1.5*scale, 1.7*scale
    g.append(rect(cx - bw/2, cy - bh/2, bw, bh, sw=1.0, rx=3))
    # side yoke nubs
    g.append(rect(cx - bw/2 - 0.18*scale, cy - 0.3*scale, 0.18*scale, 0.6*scale, sw=0.6))
    g.append(rect(cx + bw/2,              cy - 0.3*scale, 0.18*scale, 0.6*scale, sw=0.6))
    # bottom lens hint
    g.append(rect(cx - 0.45*scale, cy + 0.15*scale, 0.9*scale, 0.5*scale, sw=0.6, rx=2))
    # RED marker tab at top — the Ayrton identifier
    g.append(rect(cx - 0.42*scale, cy - bh/2 + 0.1*scale, 0.84*scale, 0.34*scale,
                  sw=0.9, stroke=RED, rx=1.5))
    return "".join(g)

def chauvet_plan(cx, cy, scale):
    """Chauvet Color Strike M strobe (top-down): horizontal divided bar."""
    w, h = 2.0*scale, 0.7*scale
    g = [rect(cx - w/2, cy - h/2, w, h, sw=1.0, rx=2)]
    g.append(rect(cx - w/2 + 0.12*scale, cy - h/2 + 0.12*scale,
                  w - 0.24*scale, h - 0.24*scale, sw=0.5, rx=1))
    return "".join(g)

def ctrl_gear(cx, cy, scale, kind):
    """Downstage control gear pieces (top-down)."""
    if kind == 0:    # small node
        w, h = 1.3*scale, 0.8*scale
        return (rect(cx-w/2, cy-h/2, w, h, sw=0.9, rx=1) +
                rect(cx-w/2+0.12*scale, cy-h/2+0.1*scale, 0.5*scale, h-0.2*scale, sw=0.5))
    if kind == 1:    # dimmer / grid box
        w, h = 1.5*scale, 1.0*scale
        g = [rect(cx-w/2, cy-h/2, w, h, sw=0.9, rx=1)]
        for i in range(5):
            for j in range(3):
                gx = cx-w/2+0.25*scale + i*0.22*scale
                gy = cy-h/2+0.2*scale + j*0.22*scale
                g.append(rect(gx, gy, 0.12*scale, 0.12*scale, sw=0.35))
        return "".join(g)
    # console / screen box
    w, h = 1.5*scale, 1.3*scale
    g = [rect(cx-w/2, cy-h/2, w, h, sw=0.9, rx=1)]
    g.append(rect(cx-w/2+0.18*scale, cy-0.1*scale, 0.7*scale, 0.7*scale, sw=0.5))
    for j in range(3):
        g.append(line(cx-w/2+0.18*scale, cy-h/2+0.22*scale + j*0.16*scale,
                      cx+w/2-0.18*scale, cy-h/2+0.22*scale + j*0.16*scale, 0.35))
    return "".join(g)


# ───────────────────────── dimension helpers ─────────────────────────
def dim_h(x1, x2, y, label, tick=8):
    g = [line(x1, y, x2, y, 0.8, BLUE)]
    for x in (x1, x2):
        g.append(line(x, y - tick, x, y + tick, 0.8, BLUE))
    g.append(text((x1+x2)/2, y - 5, label, size=12, anchor="middle", fill=BLUE))
    return "".join(g)

def dim_v(x, y1, y2, label, tick=8):
    g = [line(x, y1, x, y2, 0.8, BLUE)]
    for y in (y1, y2):
        g.append(line(x - tick, y, x + tick, y, 0.8, BLUE))
    g.append(f'<text x="{x-5:.1f}" y="{(y1+y2)/2:.1f}" font-family="Helvetica, Arial, sans-serif" '
             f'font-size="12" fill="{BLUE}" text-anchor="middle" '
             f'transform="rotate(-90 {x-5:.1f} {(y1+y2)/2:.1f})">{label}</text>')
    return "".join(g)


# ───────────────────────── title block ─────────────────────────
NOTES = ("This drawing is the property of SYNRGY Live Experiences LLC. It may not be "
         "reproduced or distributed without written consent. All dimensions are design "
         "intent and must be field-verified before fabrication or install. The supplier "
         "is responsible for confirming all structural loads, rigging points and weighted "
         "base ballast with the venue prior to build. Equipment shown is indicative; "
         "approved substitutions permitted with LD sign-off. © 2026 SYNRGY.")

def title_block(y0, sheet_title, sheet_no, scale_lbl, region):
    g = []
    x0 = TBX
    g.append(rect(x0, y0 + 6, TBW, VH - 12, sw=1.2))
    cx = x0 + TBW/2
    # heading
    g.append(text(cx, y0 + 52, "Tourist", size=40, anchor="middle", style="italic",
                  family="Georgia, 'Times New Roman', serif"))
    g.append(text(cx, y0 + 70, "projects@synrgy.live", size=11, anchor="middle", fill="#555"))
    g.append(line(x0 + 12, y0 + 80, x0 + TBW - 12, y0 + 80, 0.6))
    # general notes
    g.append(text(x0 + 14, y0 + 96, "General Notes", size=11, weight="bold"))
    words = NOTES.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 64:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur: lines.append(cur)
    ty = y0 + 110
    for ln in lines[:11]:
        g.append(text(x0 + 14, ty, ln, size=7.4, fill="#333"))
        ty += 10
    # DESIGN INTENT ONLY band
    by = y0 + 232
    g.append(line(x0, by - 6, x0 + TBW, by - 6, 0.6))
    g.append(text(cx, by + 9, "DESIGN INTENT ONLY", size=15, anchor="middle",
                  weight="bold", fill=RED, spacing="1"))
    g.append(line(x0, by + 18, x0 + TBW, by + 18, 0.6))
    # revision table header
    ry = by + 18
    g.append(text(x0 + 10, ry + 13, "No.", size=8, weight="bold"))
    g.append(text(x0 + 70, ry + 13, "Date", size=8, weight="bold"))
    g.append(text(x0 + 180, ry + 13, "Revision Notes", size=8, weight="bold"))
    g.append(line(x0, ry + 18, x0 + TBW, ry + 18, 0.5))
    g.append(line(x0 + 60, ry, x0 + 60, ry + 120, 0.5))
    g.append(line(x0 + 170, ry, x0 + 170, ry + 120, 0.5))
    for i in range(3):
        yy = ry + 18 + (i+1)*30
        g.append(line(x0, yy, x0 + TBW, yy, 0.4))
    # project info fields
    fields = [
        ("Project Name", "TRANCE TOUR 2026"),
        ("Project Date", "21/02/2026"),
        ("Job Number", "SN0001"),
        ("Client", "TOURIST"),
        ("Venue", "VARIOUS"),
        ("Sheet Title", sheet_title),
        ("Sheet Number", sheet_no),
        ("Scale", scale_lbl),
        ("Drawn By", "TH"),
    ]
    fy = ry + 140
    rowh = (y0 + VH - 100 - fy) / len(fields)
    for lbl, val in fields:
        g.append(line(x0, fy, x0 + TBW, fy, 0.4))
        g.append(text(x0 + 10, fy + 11, lbl, size=7.5, weight="bold", fill="#555"))
        g.append(text(x0 + 10, fy + 23, val, size=11))
        fy += rowh
    g.append(line(x0, fy, x0 + TBW, fy, 0.5))
    # SYNRGY stacked wordmark
    sy = fy + 4
    for i, ch in enumerate("SYNRGY"):
        g.append(text(x0 + TBW - 14, sy + 16 + i*15, ch, size=20, anchor="end",
                      weight="bold", fill=LGRY, family="Arial, sans-serif"))
    # region tag
    g.append(text(x0 + 12, y0 + VH - 14, region, size=8, fill="#999"))
    return "".join(g)


def sheet_header(y0, label):
    return text(DAX0 + 6, y0 + 28, label, size=20, weight="500",
                family="Helvetica, Arial, sans-serif")

def view_tag(y0, num, label, scale_lbl):
    yy = y0 + VH - 26
    g = [circ(DAX0 + 22, yy, 13, sw=1.0)]
    g.append(text(DAX0 + 22, yy + 5, str(num), size=14, anchor="middle"))
    g.append(text(DAX0 + 42, yy - 2, label, size=12, weight="bold"))
    g.append(text(DAX0 + 42, yy + 11, "Scale: " + scale_lbl, size=9, fill="#555"))
    return "".join(g)


# ════════════════════════ VIEW 1 — PLAN ════════════════════════
def view1():
    y0 = 0
    g = []
    g.append(sheet_header(y0, "TOURIST US 2026 – SMALL RIG"))
    S = 30.0                       # px per foot (plan)
    rig_w = 32 * S                 # 960
    RX0 = 360
    RX1 = RX0 + rig_w
    cxL = (RX0 + RX1) / 2          # centreline
    # ---- row 1 (upstage) ----
    r1y0 = y0 + 150
    r1h = 4 * S                    # 120
    g.append(rect(RX0, r1y0, rig_w/2 - 4, r1h, sw=1.3))
    g.append(rect(cxL + 4, r1y0, rig_w/2 - 4, r1h, sw=1.3))
    # deck divisions (4 decks each 8ft)
    for k in range(1, 4):
        if k == 2: continue
        x = RX0 + k*8*S
        g.append(line(x, r1y0, x, r1y0 + r1h, 0.5, LGRY))
    r1cy = r1y0 + r1h/2
    # 8 LED Par across (4ft spacing, starting 2ft), 6 Ayrton interspersed (3 per half)
    par_xs = [RX0 + (2 + 4*i)*S for i in range(8)]
    for px in par_xs:
        g.append(led_par_plan(px, r1cy, S))
    # ayrton between pars: gaps within each half (skip centre gap)
    ay_xs = []
    for i in range(7):
        gx = (par_xs[i] + par_xs[i+1]) / 2
        if abs(gx - cxL) < 0.6*S:   # skip the centreline gap
            continue
        ay_xs.append(gx)
    for ax in ay_xs:
        g.append(ayrton_plan(ax, r1cy, S))
    # ---- row 2 (downstage of row1) ----
    r2y0 = r1y0 + r1h + 1.0*S
    r2h = 4 * S
    g.append(rect(RX0, r2y0, rig_w/2 - 4, r2h, sw=1.3))
    g.append(rect(cxL + 4, r2y0, rig_w/2 - 4, r2h, sw=1.3))
    for k in range(1, 4):
        if k == 2: continue
        x = RX0 + k*8*S
        g.append(line(x, r2y0, x, r2y0 + r2h, 0.5, LGRY))
    r2cy = r2y0 + r2h/2
    for px in par_xs:
        g.append(led_par_plan(px, r2cy, S))
    # 3 Chauvet strobes on top edge of row 2 (pos 2, 5, 7 of the par columns)
    for idx in (1, 4, 6):
        g.append(chauvet_plan(par_xs[idx], r2y0 + 0.45*S, S))
    # ---- 2 downstage vertical decks (4w x 8d) ----
    vw, vh = 4*S, 8*S
    vy0 = r2y0 + r2h + 1.4*S
    vdx = [RX0 + 6*S, RX0 + 18*S]
    for vx in vdx:
        g.append(rect(vx, vy0, vw, vh, sw=1.3))
        ccx = vx + vw/2
        g.append(ctrl_gear(ccx, vy0 + 1.6*S, S, 0))
        g.append(ctrl_gear(ccx, vy0 + 4.0*S, S, 1))
        g.append(ctrl_gear(ccx, vy0 + 6.4*S, S, 2))
    # ---- dimensions ----
    # top: 7 spans of 1,000mm aligned to par columns 1..8
    dimy = r1y0 - 40
    for i in range(7):
        g.append(dim_h(par_xs[i], par_xs[i+1], dimy, "1,000mm", tick=7))
    # right: 2,440mm overall depth (row1 top to row2 bottom)
    g.append(dim_v(RX1 + 70, r1y0, r2y0 + r2h, "2,440mm"))
    # vertical deck depth dim
    g.append(dim_v(vdx[1] + vw + 36, vy0, vy0 + vh, "2,440mm"))
    # legend + title
    g.append(plan_legend(y0))
    g.append(view_tag(y0, 1, "PLAN VIEW", "1:15"))
    g.append(title_block(y0, "PLAN VIEW", "001", "1:15", "US 2026 – SMALL RIG"))
    return "".join(g)


def plan_legend(y0):
    """4-cell symbol legend box (bottom-centre of plan drawing area)."""
    S = 26.0
    bx, by = 1500, y0 + 700
    bw, bh = 1480, 165
    cellw = bw / 4
    g = [rect(bx, by, bw, bh, sw=1.0, fill="#f2f2f2")]
    for k in range(1, 4):
        g.append(line(bx + k*cellw, by, bx + k*cellw, by + bh, 0.6, "#bbb"))
    icon_cy = by + 55
    labels = [
        ("Doughty Tank Trap", ["6' poles – Qty: 8", "4' poles – Qty: 8"]),
        ("LED", ["Par", "Qty: 16"]),
        ("Ayrton Rivale", ["Profile", "Qty: 6"]),
        ("Chauvet Color Strike M", ["Strobe", "Qty: 3"]),
    ]
    for k, (name, sub) in enumerate(labels):
        icx = bx + k*cellw + cellw/2
        if k == 0:
            g.append(base_plate(icx, icon_cy, 2.2*S, 2.4*S))
            g.append(line(icx, icon_cy, icx, icon_cy + 1.3*S, 0.9))
            g.append(circ(icx, icon_cy, 0.3*S, 0.8))
        elif k == 1:
            g.append(led_par_plan(icx, icon_cy, S*0.9))
        elif k == 2:
            g.append(ayrton_plan(icx, icon_cy, S*0.9))
        else:
            g.append(chauvet_plan(icx, icon_cy, S*1.1))
        ly = by + bh - 52
        g.append(text(bx + k*cellw + 14, ly, name, size=12))
        for j, sline in enumerate(sub):
            g.append(text(bx + k*cellw + 14, ly + 16 + j*15, sline, size=11, fill="#444"))
    return "".join(g)


# ════════════════════════ VIEW 2 — SIDE ELEVATION ════════════════════════
def pole_side(x, base_y, height, fixture, scale, par_on_pole=False):
    """Scaffold pole on weighted base, side view, with fixture on top."""
    g = []
    # weighted base plate
    bw = 2.6*scale
    g.append(rect(x - bw/2, base_y - 0.45*scale, bw, 0.45*scale, sw=1.1))
    g.append(rect(x - bw/2 - 0.2*scale, base_y - 0.18*scale, 0.2*scale, 0.18*scale,
                  sw=0.8, stroke=RED))
    g.append(rect(x + bw/2,             base_y - 0.18*scale, 0.2*scale, 0.18*scale,
                  sw=0.8, stroke=RED))
    # pole
    top_y = base_y - height
    g.append(rect(x - 0.16*scale, top_y, 0.32*scale, height, sw=1.0))
    if par_on_pole:
        # LED pars clamped on lower pole (dark)
        for hy in (base_y - 1.4*scale, base_y - 2.3*scale):
            g.append(rect(x - 0.55*scale, hy, 1.1*scale, 0.8*scale, sw=0.9, fill="#222"))
    if fixture == "ayrton":
        # moving head on yoke at pole top
        g.append(line(x, top_y, x - 1.0*scale, top_y - 0.2*scale, 0.9))
        g.append(rect(x - 1.7*scale, top_y - 1.5*scale, 1.5*scale, 1.4*scale, sw=1.0, rx=3))
        g.append(circ(x - 0.95*scale, top_y - 0.8*scale, 0.32*scale, 0.7))
    return "".join(g)

def view2():
    y0 = 960
    g = []
    g.append(sheet_header(y0, "TOURIST US 2026 – SMALL RIG"))
    S = 30.0
    floor_y = y0 + 720
    # stage base
    g.append(rect(DAX0 + 20, floor_y, 2980, 120, sw=1.3))
    g.append(line(DAX0 + 20, floor_y, 3000, floor_y, 1.0))
    # control table (left) with gear on top
    tx0, tw = 300, 380
    th = 130
    ty = floor_y - th
    g.append(rect(tx0, ty, tw, 18, sw=1.2))              # table top
    g.append(line(tx0 + 20, ty + 18, tx0 + 20, floor_y, 1.0))
    g.append(line(tx0 + tw - 20, ty + 18, tx0 + tw - 20, floor_y, 1.0))
    g.append(line(tx0 + tw/2, ty + 18, tx0 + tw/2, floor_y, 1.0))
    for gx in (tx0 + 70, tx0 + 190, tx0 + 300):
        g.append(rect(gx, ty - 16, 60, 16, sw=0.8))
        for j in range(4):
            g.append(line(gx + 8 + j*12, ty - 14, gx + 8 + j*12, ty - 4, 0.4))
    # two poles on weighted bases (short 1.2m + tall 2.4m)
    g.append(pole_side(1750, floor_y, 3.0*S, "ayrton", S, par_on_pole=False))
    g.append(pole_side(2300, floor_y, 6.0*S, "ayrton", S, par_on_pole=True))
    # small tank-trap base detail between
    g.append(rect(1980, floor_y - 0.9*S, 1.4*S, 0.9*S, sw=0.8))
    g.append(line(1980, floor_y - 0.45*S, 1980 + 1.4*S, floor_y - 0.45*S, 0.5))
    # blue callout
    cx = 2480
    leads = [(2300, floor_y - 6.0*S - 0.4*S), (1750, floor_y - 3.0*S)]
    cyl = y0 + 300
    g.append(line(cx, cyl + 30, 2360, floor_y - 3.0*S, 0.7, BLUE))
    for i, t in enumerate([
        "Scaffold poles on weighted bases",
        "Doughty Tank Trap (or similar)",
        "2.4mH (8 ft) poles x8",
        "1.2mH (4 ft) poles x8"]):
        g.append(text(cx, cyl + i*16, t, size=12, fill=BLUE))
    g.append(view_tag(y0, 2, "SIDE ELEVATION", "1:15"))
    g.append(title_block(y0, "SIDE ELEVATION", "002", "1:15", "US 2026 – SMALL RIG"))
    return "".join(g)


# ════════════════════════ VIEW 3 — FRONT ELEVATION (UK/EU) ════════════════════════
def person(cx, base_y, scale):
    """Simple filled human silhouette for scale (~6ft)."""
    h = 6*scale
    head_r = 0.42*scale
    top = base_y - h
    pts = []
    # crude body via path
    return (f'<path d="M {cx:.1f} {top:.1f} '
            f'a {head_r:.1f} {head_r:.1f} 0 1 0 0.1 0 z" fill="#3a3a3a"/>'
            + f'<path d="M {cx-0.7*scale:.1f} {top+1.0*scale:.1f} '
              f'L {cx+0.7*scale:.1f} {top+1.0*scale:.1f} '
              f'L {cx+0.5*scale:.1f} {top+3.4*scale:.1f} '
              f'L {cx+0.9*scale:.1f} {base_y:.1f} '
              f'L {cx+0.2*scale:.1f} {base_y:.1f} '
              f'L {cx:.1f} {top+3.6*scale:.1f} '
              f'L {cx-0.2*scale:.1f} {base_y:.1f} '
              f'L {cx-0.9*scale:.1f} {base_y:.1f} '
              f'L {cx-0.5*scale:.1f} {top+3.4*scale:.1f} Z" fill="#3a3a3a"/>')

def view3():
    y0 = 1920
    g = []
    g.append(sheet_header(y0, "TOURIST UK/EU 2026 – SMALL RIG"))
    S = 30.0
    floor_y = y0 + 760
    g.append(rect(DAX0 + 20, floor_y, 2980, 110, sw=1.3))
    deck_y = floor_y
    # 8 poles across, each with 2 LED par circles (upper + mid)
    px0, pxN = 380, 380 + 32*S
    pole_xs = [px0 + i*(pxN - px0)/7 for i in range(8)]
    pole_top = y0 + 150
    for x in pole_xs:
        g.append(line(x, pole_top, x, deck_y - 8, 1.0))
        g.append(circ(x, pole_top + 30, 13, sw=1.2))        # upper LED par
        g.append(circ(x, pole_top + 200, 13, sw=1.2))       # mid LED par
    # Ayrtons + par base boxes on deck between poles
    ay_pairs = [1, 3, 5, 6]
    for i, x in enumerate(pole_xs):
        # par base box at foot of pole
        g.append(rect(x - 16, deck_y - 26, 32, 26, sw=0.9))
        g.append(rect(x - 10, deck_y - 8, 20, 6, sw=0.6, stroke=RED))
    # chunky Ayrton moving heads sitting on deck between some poles
    for i in (0, 2, 4, 6):
        ax = (pole_xs[i] + pole_xs[i+1]) / 2
        g.append(rect(ax - 22, deck_y - 52, 44, 52, sw=1.1, rx=4))
        g.append(circ(ax, deck_y - 30, 11, sw=0.8))
    # two control tables centre with person between
    for txc in (pole_xs[3] - 10, pole_xs[4] + 10):
        g.append(rect(txc - 70, deck_y - 96, 140, 14, sw=1.0))
        g.append(line(txc - 56, deck_y - 82, txc - 56, deck_y, 0.9))
        g.append(line(txc + 56, deck_y - 82, txc + 56, deck_y, 0.9))
    g.append(person((pole_xs[3] + pole_xs[4]) / 2 + 4, deck_y, S))
    # dimensions
    g.append(dim_h(pole_xs[0], pole_xs[-1], pole_top - 40, "9,600mm", tick=8))
    g.append(dim_v(px0 - 60, pole_top + 30, deck_y, "3,100mm"))
    g.append(view_tag(y0, 3, "FRONT ELEVATION", "1:15"))
    g.append(title_block(y0, "FRONT ELEVATION", "003", "1:15", "UK/EU 2026 – SMALL RIG"))
    return "".join(g)


# ════════════════════════ ASSEMBLE ════════════════════════
def build():
    e(f'<svg xmlns="http://www.w3.org/2000/svg" width="{CW}" height="{CH}" '
      f'viewBox="0 0 {CW} {CH}" font-family="Helvetica, Arial, sans-serif">')
    e(rect(0, 0, CW, CH, sw=0, fill="white", stroke="none"))
    e('<g id="view-1-plan">'      + view1() + '</g>')
    e('<g id="view-2-side-elev">' + view2() + '</g>')
    e('<g id="view-3-front-elev">'+ view3() + '</g>')
    # white separator gaps (ensure pure white)
    e(rect(0, VH, CW, GAP, sw=0, fill="white", stroke="none"))
    e(rect(0, VH*2 + GAP, CW, GAP, sw=0, fill="white", stroke="none"))
    e('</svg>')
    return "\n".join(out)


if __name__ == "__main__":
    import os, sys
    svg = build()
    default = os.path.join(os.path.dirname(__file__), "..", "src", "lx-floor-package.svg")
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(default)
    with open(path, "w") as f:
        f.write(svg)
    print("wrote", path, len(svg), "bytes")
