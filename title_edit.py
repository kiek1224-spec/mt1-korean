#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""타이틀 본문「여신전생」을 **손으로 고칠 수 있게** PNG 로 뽑는다.

    python title_edit.py            # 지금 모습을 title_main.png 로 뽑는다 (+ 확대 미리보기)
    python title_edit.py --preview  # title_main.png 를 확대해서 다시 보기만 한다

## 쓰는 법
1. `python title_edit.py` 를 돌린다 -> `title_main.png` (128x32) 와
   `title_main_zoom.png` (8배 확대 + 8픽셀 타일 격자) 가 생긴다.
2. **`title_main.png` 를 그림판 등에서 픽셀 단위로 고친다.** 크기는 그대로 두어야 한다.
3. 빌드하면 빌더가 그 PNG 를 보고 그대로 구워 넣는다(폰트 렌더는 건너뛴다).
   되돌리려면 `title_main.png` 를 지우면 된다.

## 규칙
- 크기 **128x32 고정**. 상자(열8~23, 행8~11)에 그대로 대응한다.
- 쓸 수 있는 색은 **셋뿐**이다. 다른 색을 칠하면 가장 가까운 것으로 붙는다:
      #000000  배경(투명)
      #BD3C30  본체   - 팔레트 색2
      #FFCECE  테두리 - 팔레트 색3
- 팔레트는 **16x16 픽셀 단위**라 이 상자 안에서는 세 색이 전부다. 새 색은 못 늘린다.
- 잉크가 닿는 8x8 칸이 늘면 타일을 더 쓴다. 예산은 자막까지 합쳐 94칸이고
  지금 여유가 몇 칸 없으니, 칸을 크게 늘리는 그림이면 빌드가 멈출 수 있다(그때 알려준다).
"""
import os
import sys

from PIL import Image, ImageDraw

import make_title as MT

ZOOM = 8


def zoom_preview(src=MT.MAIN_PNG):
    im = Image.open(src).convert("RGB")
    W, H = im.size
    out = im.resize((W * ZOOM, H * ZOOM), Image.NEAREST).convert("RGB")
    d = ImageDraw.Draw(out)
    for x in range(0, W + 1, 8):                 # 8픽셀 = 타일 경계
        d.line([(x * ZOOM, 0), (x * ZOOM, H * ZOOM)], fill=(60, 60, 80))
    for y in range(0, H + 1, 8):
        d.line([(0, y * ZOOM), (W * ZOOM, y * ZOOM)], fill=(60, 60, 80))
    p = os.path.splitext(src)[0] + "_zoom.png"
    out.save(p)
    return p


def export():
    """지금 빌더가 그리는 모습을 그대로 PNG 로 뽑는다"""
    W, H = MT.MAIN_W * 8, MT.MAIN_H * 8
    # 폰트 렌더 경로를 타려면 PNG 가 없어야 한다 - 잠시 치워 둔다
    tmp = None
    if os.path.exists(MT.MAIN_PNG):
        tmp = MT.MAIN_PNG + ".bak"
        os.replace(MT.MAIN_PNG, tmp)
    try:
        pool = MT.Pool(list(range(256)))         # 뽑기용이라 예산 제한 없이
        cells = {}
        MT.main_title(pool, cells)
    finally:
        if tmp:
            os.replace(tmp, MT.MAIN_PNG)
    im = Image.new("RGB", (W, H), MT.C_BG)
    px = im.load()
    for pos, tid in cells.items():
        r, c = pos // 32, pos % 32
        tr, tc = r - MT.MAIN_ROW, c - MT.MAIN_COL
        b = pool.tiles[tid]
        for y in range(8):
            lo, hi = b[y], b[8 + y]
            for x in range(8):
                v = ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
                if v == 2: px[tc * 8 + x, tr * 8 + y] = MT.C_BODY
                elif v == 3: px[tc * 8 + x, tr * 8 + y] = MT.C_RING
    im.save(MT.MAIN_PNG)
    return MT.MAIN_PNG


if __name__ == "__main__":
    if "--preview" in sys.argv:
        print(zoom_preview())
    else:
        p = export()
        print(p)
        print(zoom_preview(p))
        print("\n이 파일을 픽셀 단위로 고친 뒤 빌드하면 그대로 들어갑니다.")
        print("색 세 가지만: #000000 배경 / #BD3C30 본체 / #FFCECE 테두리")
        print("되돌리려면 title_main.png 를 지우세요.")
