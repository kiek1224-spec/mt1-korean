#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
갈무리M[고딕,8x8] TTF -> 8x8 비트맵 -> NES 2bpp CHR 타일

TTF를 16px로 렌더하면 원점에서 정확히 8x8 셀 안에 글리프가 들어온다.
자소 조합이 필요 없으므로 hangul8.py 의 조합기보다 품질·정확도가 낫다.
폰트에 없는 글자는 has_glyph()로 걸러진다(KS X 1001 상용 자수 계열, 11172자 전체 아님).
"""
import io, os
from PIL import Image, ImageDraw, ImageFont

TTF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "galmuri", "galmuriM_8x8.ttf")
TBL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "galmuri", "galmuriM_8x8.tbl")
_font = ImageFont.truetype(TTF, 16)
ORIGIN = (8, 8)          # 이 좌표에 그리면 글리프 셀이 (8,8)~(15,15)

_cache = {}

def bitmap(ch):
    """문자 1개 -> 8x8 0/1 격자. 글리프가 없으면 None."""
    if ch in _cache: return _cache[ch]
    im = Image.new("L", (32, 32), 0)
    ImageDraw.Draw(im).text(ORIGIN, ch, font=_font, fill=255)
    px = im.load()
    g = [[1 if px[ORIGIN[0]+c, ORIGIN[1]+r] > 127 else 0 for c in range(8)] for r in range(8)]
    if not any(any(row) for row in g) and ch.strip():
        g = None
    _cache[ch] = g
    return g

def has_glyph(ch):
    return ch == ' ' or bitmap(ch) is not None

def to_chr(g, color=3):
    """8x8 격자 -> NES 2bpp 16바이트. 원본 대화 글꼴과 같이 색3(양 플레인) 사용."""
    if g is None: g = [[0]*8 for _ in range(8)]
    rows = [sum(g[r][c] << (7-c) for c in range(8)) for r in range(8)]
    p0 = bytes(rows) if color & 1 else bytes(8)
    p1 = bytes(rows) if color & 2 else bytes(8)
    return p0 + p1

def art(g):
    if g is None: return ["????????"]*8
    return ["".join("#" if v else "." for v in row) for row in g]

def table_chars():
    """.tbl 에 정의된 문자 집합"""
    out = {}
    for line in io.open(TBL, encoding="utf-8-sig").read().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            try: out[chr(int(k, 16))] = v
            except ValueError: pass
    return out

def check(text):
    """문자열에서 폰트에 없는 글자를 돌려준다."""
    return sorted({c for c in text if c != ' ' and not has_glyph(c)})

if __name__ == "__main__":
    import sys
    t = table_chars()
    hang = [c for c in t if 0xAC00 <= ord(c) <= 0xD7A3]
    print("tbl 정의 문자 %d개 (그중 한글 음절 %d자)" % (len(t), len(hang)))
    missing = [c for c in t if not has_glyph(c)]
    print("tbl에 있으나 렌더 안 되는 글자: %d개" % len(missing))
    s = sys.argv[1] if len(sys.argv) > 1 else "한글여신전생"
    for r in range(8):
        print("  " + "  ".join(art(bitmap(c))[r] for c in s))
