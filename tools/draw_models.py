#!/usr/bin/env python3
"""Draw the fryer illustrations for the dashboard card (own artwork, no photos).

All drawings share one canvas (1081 x 802) so the card can lay the live control
panel over the glass area of every model. Writes
custom_components/cosori_airfryer/frontend/models/<id>.svg

  python3 tools/draw_models.py
"""

from pathlib import Path

W, H = 1081, 802
OUT = Path(__file__).resolve().parent.parent / "custom_components/cosori_airfryer/frontend/models"

DEFS = """
<defs>
  <linearGradient id="glass" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2c2c30"/><stop offset=".2" stop-color="#141416"/>
    <stop offset=".8" stop-color="#0a0a0b"/><stop offset="1" stop-color="#171719"/>
  </linearGradient>
  <radialGradient id="sheen" cx=".5" cy="0" r="1">
    <stop offset="0" stop-color="#fff" stop-opacity=".13"/><stop offset=".55" stop-color="#fff" stop-opacity=".02"/>
    <stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="black" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#09090a"/><stop offset=".08" stop-color="#242428"/>
    <stop offset=".5" stop-color="#1b1b1e"/><stop offset=".92" stop-color="#242428"/><stop offset="1" stop-color="#09090a"/>
  </linearGradient>
  <linearGradient id="grey" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#2a2b2e"/><stop offset=".08" stop-color="#4a4c51"/>
    <stop offset=".5" stop-color="#3e4044"/><stop offset=".92" stop-color="#4a4c51"/><stop offset="1" stop-color="#2a2b2e"/>
  </linearGradient>
  <linearGradient id="shadeV" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#000" stop-opacity=".45"/><stop offset=".12" stop-color="#000" stop-opacity="0"/>
    <stop offset=".85" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".45"/>
  </linearGradient>
  <linearGradient id="hiV" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity=".18"/><stop offset=".25" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#efcfb9"/><stop offset=".3" stop-color="#d2a68c"/>
    <stop offset=".75" stop-color="#a9806a"/><stop offset="1" stop-color="#6c4a3a"/>
  </linearGradient>
  <linearGradient id="goldH" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#7d5a48"/><stop offset=".04" stop-color="#e6c3ab"/>
    <stop offset=".12" stop-color="#c79f86"/><stop offset=".88" stop-color="#c79f86"/>
    <stop offset=".96" stop-color="#e6c3ab"/><stop offset="1" stop-color="#7d5a48"/>
  </linearGradient>
  <linearGradient id="goldVert" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#8f5d43"/><stop offset=".3" stop-color="#f0c4a3"/>
    <stop offset=".6" stop-color="#d39a77"/><stop offset="1" stop-color="#8a573e"/>
  </linearGradient>
  <linearGradient id="silver" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#6d7075"/><stop offset=".3" stop-color="#e4e6ea"/>
    <stop offset=".6" stop-color="#b4b7bd"/><stop offset="1" stop-color="#5f6267"/>
  </linearGradient>
  <linearGradient id="grip" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#030303"/><stop offset=".45" stop-color="#202022"/><stop offset="1" stop-color="#030303"/>
  </linearGradient>
  <linearGradient id="gripV" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#050506"/><stop offset=".4" stop-color="#2a2a2e"/><stop offset="1" stop-color="#050506"/>
  </linearGradient>
  <filter id="soft" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
</defs>"""


def logo(x, y, size=23, lower=False, color="#ececee"):
    txt = "cosori" if lower else "COSORI"
    weight = 500 if lower else 700
    spacing = 1 if lower else 2.5
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif" '
            f'font-weight="{weight}" font-size="{size}" letter-spacing="{spacing}" fill="{color}">{txt}</text>')


def floor(cx, y, rx):
    return f'<ellipse cx="{cx}" cy="{y}" rx="{rx}" ry="16" fill="#000" opacity=".55" filter="url(#soft)"/>'


def rrect(x, y, w, h, r, fill, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" {extra}/>'


def glass_panel(x, y, w, h, r):
    """Black glass control surface with a soft top reflection."""
    return (rrect(x, y, w, h, r, "url(#glass)") +
            rrect(x, y, w, h, r, "url(#sheen)") +
            f'<path d="M{x + r} {y + 1.5} H{x + w - r}" stroke="#fff" stroke-opacity=".18" stroke-width="2"/>')


def vents(x0, x1, y, h=14, step=16, color="#0b0b0c"):
    return "".join(rrect(x, y, 7, h, 3.5, color) for x in range(int(x0), int(x1), step))


def svg(body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{DEFS}{body}</svg>\n'


# ---------------------------------------------------------------- TwinFry
def twinfry():
    """Dual Blaze TwinFry (CAF-TF101S/TF102S): wide, two baskets in one drawer."""
    return svg(f"""
  {floor(540, 772, 445)}
  <!-- drawer -->
  <path d="M100 560 H982 V700 Q982 758 924 758 H158 Q100 758 100 700 Z" fill="url(#black)"/>
  <path d="M100 560 H982 V700 Q982 758 924 758 H158 Q100 758 100 700 Z" fill="url(#shadeV)"/>
  <path d="M150 760 H932 Q940 770 920 772 H162 Q142 770 150 760 Z" fill="#060607"/>
  <!-- body -->
  <path d="M94 318 H988 V452 Q988 500 940 500 H142 Q94 500 94 452 Z" fill="url(#black)"/>
  <path d="M94 318 H988 V452 Q988 500 940 500 H142 Q94 500 94 452 Z" fill="url(#shadeV)"/>
  {logo(543, 386)}
  <!-- lid: glass top, sides curving down into the band -->
  <path d="M150 8 Q128 8 126 34 L94 240 Q88 290 140 292 H942 Q994 290 988 240 L956 34 Q954 8 932 8 Z" fill="url(#glass)"/>
  <path d="M150 8 Q128 8 126 34 L112 120 H970 L956 34 Q954 8 932 8 Z" fill="url(#sheen)"/>
  <path d="M112 121 H970" stroke="#000" stroke-opacity=".5" stroke-width="2"/>
  <path d="M152 9.5 H930" stroke="#fff" stroke-opacity=".22" stroke-width="2"/>
  <!-- rose-gold band, wraps round the corners -->
  <path d="M82 262 Q84 280 106 282 Q300 286 541 286 Q782 286 976 282 Q998 280 1000 262 V284
           Q1000 316 962 318 H120 Q82 316 82 284 Z" fill="url(#gold)"/>
  <path d="M86 268 Q90 284 112 286 Q320 290 541 290 Q762 290 970 286 Q992 284 996 268"
        stroke="#ffe9d8" stroke-opacity=".75" stroke-width="2" fill="none"/>
  <path d="M118 319 H964" stroke="#000" stroke-opacity=".55" stroke-width="4"/>
  <!-- printed controls -->
  <g fill="none" stroke="#9a9aa0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" opacity=".85">
    <path d="M370 160 l9 -7 l9 7"/><path d="M370 181 l9 7 l9 -7"/>
    <path d="M709 160 l9 -7 l9 7"/><path d="M709 181 l9 7 l9 -7"/>
  </g>
  <g transform="translate(325 206)"><circle r="12" fill="none" stroke="#b9632b" stroke-width="2"/>
    <path d="M0 -6 V1 M-5 -3 A6 6 0 1 0 5 -3" fill="none" stroke="#d9722f" stroke-width="2" stroke-linecap="round"/></g>
  <g transform="translate(771 205)"><circle r="13" fill="none" stroke="#d6d6da" stroke-width="2"/>
    <path d="M-6 -6 L1 0 L-6 6 Z" fill="#e6e6ea"/><rect x="3" y="-6" width="2" height="12" fill="#e6e6ea"/>
    <rect x="6.5" y="-6" width="2" height="12" fill="#e6e6ea"/></g>
  <!-- handle: round tube ends -->
  <path d="M10 488 Q10 420 64 420 Q84 420 84 446 V512 H997 V446 Q997 420 1017 420 Q1071 420 1071 488 V548
           Q1071 594 1025 594 H56 Q10 594 10 548 Z" fill="url(#goldH)"/>
  <path d="M10 488 Q10 420 64 420 Q84 420 84 446 V512 H997 V446 Q997 420 1017 420 Q1071 420 1071 488 V548
           Q1071 594 1025 594 H56 Q10 594 10 548 Z" fill="url(#hiV)"/>
  <rect x="58" y="530" width="965" height="48" rx="24" fill="url(#grip)"/>
  <path d="M462 538 H620 Q624 538 621 542 L612 552 H470 L461 542 Q458 538 462 538 Z" fill="#2b2b2e"/>
  <path d="M20 470 Q24 430 58 426" stroke="#fff1e6" stroke-opacity=".7" stroke-width="3" fill="none" stroke-linecap="round"/>
  <path d="M1061 470 Q1057 430 1023 426" stroke="#fff1e6" stroke-opacity=".7" stroke-width="3" fill="none" stroke-linecap="round"/>
""")


# ---------------------------------------------------------------- Dual Blaze
def dualblaze():
    """Dual Blaze 6.8 Qt (CAF-P583S): tall, grey, glass strip on top front."""
    x0, x1 = 300, 782
    return svg(f"""
  {floor(541, 774, 250)}
  <!-- base with vents -->
  {rrect(x0 + 18, 708, x1 - x0 - 36, 58, 22, "#141416")}
  {vents(x0 + 40, x1 - 40, 736)}
  <!-- drawer -->
  <path d="M{x0 + 6} 452 H{x1 - 6} V676 Q{x1 - 6} 720 {x1 - 50} 720 H{x0 + 50} Q{x0 + 6} 720 {x0 + 6} 676 Z" fill="url(#grey)"/>
  <path d="M{x0 + 6} 452 H{x1 - 6} V676 Q{x1 - 6} 720 {x1 - 50} 720 H{x0 + 50} Q{x0 + 6} 720 {x0 + 6} 676 Z" fill="url(#shadeV)"/>
  <!-- body -->
  <path d="M{x0} 96 Q{x0} 56 {x0 + 40} 56 H{x1 - 40} Q{x1} 56 {x1} 96 V440 Q{x1} 452 {x1 - 12} 452 H{x0 + 12} Q{x0} 452 {x0} 440 Z" fill="url(#grey)"/>
  <path d="M{x0} 96 Q{x0} 56 {x0 + 40} 56 H{x1 - 40} Q{x1} 56 {x1} 96 V440 Q{x1} 452 {x1 - 12} 452 H{x0 + 12} Q{x0} 452 {x0} 440 Z" fill="url(#shadeV)" opacity=".7"/>
  <path d="M{x0 + 40} 57.5 H{x1 - 40}" stroke="#fff" stroke-opacity=".2" stroke-width="2"/>
  {glass_panel(x0 + 16, 70, x1 - x0 - 32, 196, 26)}
  {logo(541, 318, 21)}
  <path d="M{x0 + 4} 452 H{x1 - 4}" stroke="#16171a" stroke-width="5"/>
  <!-- handle -->
  {rrect(510, 426, 62, 26, 10, "#18181a")}
  {rrect(514, 438, 54, 262, 22, "url(#gripV)")}
  {rrect(514, 438, 54, 40, 14, "#3a3b3f")}
  <g stroke="#55565b" stroke-width="2">{"".join(f'<path d="M520 {446 + i * 6} H562"/>' for i in range(5))}</g>
""")


# ---------------------------------------------------------------- TurboBlaze
def turboblaze():
    """TurboBlaze 6 Qt (CAF-DC601S): wide, very rounded, copper accents."""
    x0, x1 = 236, 846
    return svg(f"""
  {floor(541, 774, 300)}
  {rrect(x0 + 40, 726, x1 - x0 - 80, 40, 18, "#121214")}
  <!-- one rounded shell -->
  <path d="M{x0} 220 Q{x0} 108 {x0 + 112} 108 H{x1 - 112} Q{x1} 108 {x1} 220 V640 Q{x1} 740 {x1 - 100} 740 H{x0 + 100} Q{x0} 740 {x0} 640 Z" fill="url(#grey)"/>
  <path d="M{x0} 220 Q{x0} 108 {x0 + 112} 108 H{x1 - 112} Q{x1} 108 {x1} 220 V640 Q{x1} 740 {x1 - 100} 740 H{x0 + 100} Q{x0} 740 {x0} 640 Z" fill="url(#shadeV)" opacity=".8"/>
  <!-- glass top with copper rim -->
  <path d="M{x0 + 8} 214 Q{x0 + 10} 112 {x0 + 112} 112 H{x1 - 112} Q{x1 - 10} 112 {x1 - 8} 214 V286 Q{x1 - 8} 300 {x1 - 22} 300 H{x0 + 22} Q{x0 + 8} 300 {x0 + 8} 286 Z" fill="url(#glass)"/>
  <path d="M{x0 + 8} 214 Q{x0 + 10} 112 {x0 + 112} 112 H{x1 - 112} Q{x1 - 10} 112 {x1 - 8} 214 V230 H{x0 + 8} Z" fill="url(#sheen)"/>
  <path d="M{x0 + 6} 300 H{x1 - 6}" stroke="url(#goldH)" stroke-width="8" stroke-linecap="round"/>
  <path d="M{x0 + 112} 113.5 H{x1 - 112}" stroke="#fff" stroke-opacity=".22" stroke-width="2"/>
  {logo(541, 388, 30, lower=True)}
  <!-- drawer seam -->
  <path d="M{x0 + 4} 452 H{x1 - 4}" stroke="#1d1e21" stroke-width="5"/>
  <!-- handle with copper inlay -->
  {rrect(510, 470, 62, 230, 26, "url(#gripV)")}
  {rrect(526, 500, 30, 180, 14, "url(#goldVert)")}
  {rrect(512, 468, 58, 22, 10, "#2a2b2e")}
""")


# ---------------------------------------------------------------- CS158
def cs158():
    """Smart / Pro 5.8 Qt (CS158/CS137): black, sloped glossy top, angled grip."""
    x0, x1 = 286, 796
    return svg(f"""
  {floor(541, 774, 270)}
  {rrect(x0 + 30, 722, x1 - x0 - 60, 44, 18, "#0e0e10")}
  <!-- body: rounded box, slightly narrower at the top -->
  <path d="M{x0 + 30} 140 Q{x0 + 34} 96 {x0 + 80} 96 H{x1 - 80} Q{x1 - 34} 96 {x1 - 30} 140 L{x1} 640
           Q{x1} 738 {x1 - 90} 738 H{x0 + 90} Q{x0} 738 {x0} 640 Z" fill="url(#black)"/>
  <path d="M{x0 + 30} 140 Q{x0 + 34} 96 {x0 + 80} 96 H{x1 - 80} Q{x1 - 34} 96 {x1 - 30} 140 L{x1} 640
           Q{x1} 738 {x1 - 90} 738 H{x0 + 90} Q{x0} 738 {x0} 640 Z" fill="url(#shadeV)"/>
  <!-- glossy sloped control panel -->
  <path d="M{x0 + 44} 132 Q{x0 + 48} 104 {x0 + 84} 104 H{x1 - 84} Q{x1 - 48} 104 {x1 - 44} 132 L{x1 - 26} 278
           Q{x1 - 24} 300 {x1 - 50} 300 H{x0 + 50} Q{x0 + 24} 300 {x0 + 26} 278 Z" fill="url(#glass)"/>
  <path d="M{x0 + 44} 132 Q{x0 + 48} 104 {x0 + 84} 104 H{x1 - 84} Q{x1 - 48} 104 {x1 - 44} 132 L{x1 - 38} 180 H{x0 + 38} Z" fill="url(#sheen)"/>
  {logo(541, 128, 17)}
  <!-- drawer seam and brushed front -->
  <path d="M{x0 + 6} 360 H{x1 - 6}" stroke="#050506" stroke-width="5"/>
  <g stroke="#fff" stroke-opacity=".035" stroke-width="2">{"".join(f'<path d="M{x0 + 20} {380 + i * 9} H{x1 - 20}"/>' for i in range(36))}</g>
  <!-- angled grip -->
  <path d="M496 452 Q496 432 516 432 H566 Q586 432 586 452 V470 L600 640 Q602 662 580 662 H502 Q480 662 482 640 L496 470 Z" fill="url(#gripV)"/>
  <path d="M500 446 H582" stroke="#6b6c70" stroke-width="3" stroke-linecap="round"/>
  {rrect(518, 448, 46, 20, 8, "#d8d9dc")}
""")


# ---------------------------------------------------------------- CS358
def cs358():
    """Pro II 5.8 Qt (CS358): flatter top, display window, straight grip."""
    x0, x1 = 280, 802
    return svg(f"""
  {floor(541, 774, 275)}
  {rrect(x0 + 30, 722, x1 - x0 - 60, 44, 18, "#0e0e10")}
  <path d="M{x0} 170 Q{x0} 98 {x0 + 72} 98 H{x1 - 72} Q{x1} 98 {x1} 170 V650 Q{x1} 738 {x1 - 88} 738 H{x0 + 88} Q{x0} 738 {x0} 650 Z" fill="url(#black)"/>
  <path d="M{x0} 170 Q{x0} 98 {x0 + 72} 98 H{x1 - 72} Q{x1} 98 {x1} 170 V650 Q{x1} 738 {x1 - 88} 738 H{x0 + 88} Q{x0} 738 {x0} 650 Z" fill="url(#shadeV)"/>
  {glass_panel(x0 + 22, 110, x1 - x0 - 44, 196, 50)}
  <path d="M{x0 + 22} 330 H{x1 - 22}" stroke="url(#silver)" stroke-width="4" stroke-linecap="round" opacity=".8"/>
  {logo(541, 356, 18)}
  <path d="M{x0 + 6} 392 H{x1 - 6}" stroke="#050506" stroke-width="5"/>
  <!-- straight grip -->
  {rrect(502, 424, 78, 256, 26, "url(#gripV)")}
  {rrect(510, 432, 62, 26, 12, "url(#silver)")}
""")


# ---------------------------------------------------------------- Turbo Tower
def turbotower():
    """Turbo Tower Pro (CAF-DC111S): tall, two drawers stacked."""
    x0, x1 = 318, 764
    return svg(f"""
  {floor(541, 776, 240)}
  {rrect(x0 + 24, 734, x1 - x0 - 48, 34, 14, "#0e0e10")}
  <path d="M{x0} 92 Q{x0} 30 {x0 + 62} 30 H{x1 - 62} Q{x1} 30 {x1} 92 V680 Q{x1} 748 {x1 - 68} 748 H{x0 + 68} Q{x0} 748 {x0} 680 Z" fill="url(#grey)"/>
  <path d="M{x0} 92 Q{x0} 30 {x0 + 62} 30 H{x1 - 62} Q{x1} 30 {x1} 92 V680 Q{x1} 748 {x1 - 68} 748 H{x0 + 68} Q{x0} 748 {x0} 680 Z" fill="url(#shadeV)" opacity=".8"/>
  {glass_panel(x0 + 14, 42, x1 - x0 - 28, 176, 48)}
  <path d="M{x0 + 10} 226 H{x1 - 10}" stroke="url(#silver)" stroke-width="4" stroke-linecap="round" opacity=".7"/>
  <!-- upper drawer -->
  <path d="M{x0 + 4} 236 H{x1 - 4}" stroke="#1d1e21" stroke-width="4"/>
  <path d="M{x0 + 4} 470 H{x1 - 4}" stroke="#1d1e21" stroke-width="5"/>
  {logo(541, 502, 22, lower=True)}
  <path d="M{x0 + 4} 520 H{x1 - 4}" stroke="#1d1e21" stroke-width="5"/>
  <!-- handles -->
  {rrect(516, 256, 50, 196, 20, "url(#silver)")}
  {rrect(524, 266, 34, 176, 14, "#2b2c30", 'opacity=".25"')}
  {rrect(516, 536, 50, 190, 20, "url(#silver)")}
  {rrect(524, 546, 34, 170, 14, "#2b2c30", 'opacity=".25"')}
""")


MODELS = {
    "twinfry": twinfry,
    "dualblaze": dualblaze,
    "turboblaze": turboblaze,
    "cs158": cs158,
    "cs358": cs358,
    "turbotower": turbotower,
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in MODELS.items():
        (OUT / f"{name}.svg").write_text(fn())
        print("wrote", OUT / f"{name}.svg")
