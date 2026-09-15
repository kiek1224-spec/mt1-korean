#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""롬에서 던전 지도를 뽑아 그림으로 저장한다.

형식 (2026-09-08 역어셈블·실측으로 확정)
  지도는 **뱅크 $0A 하나**뿐이다. 뱅크가 $8000 에 걸리고 시작은 $8004(파일 $14014).
  읽는 코드는 고정뱅크 `$CAA4~$CAD9` 한 곳:

      주소 = $8004 + X + Y*$80          (한 줄 128칸, 전체 128 x 64 = 8192칸)

  한 칸 = 1바이트, **2비트씩 네 방향**:

      비트 0-1 = 서   비트 2-3 = 남   비트 4-5 = 동   비트 6-7 = 북
      값 0 = 뚫림 / 1 = 벽 / 3 = 문(추정)

  근거: 「내 서쪽 벽」과 「왼쪽 칸의 동쪽 벽」이 **99.1%** 일치한다(비트0<->비트4).
        북/남도 99.1%(비트6<->비트2). 우연이 아니다.
        니블이 {0,1,3,4,5,7,C,D,F} 9종뿐인 것도 2비트 필드 두 개라서 설명된다.

  층: **16 x 16 이 한 층**. 위 16블록은 테두리가 100% 닫혀 있다(= 독립된 층).
      아래쪽 일부는 90% 안팎이라 층끼리 이어졌거나 더 큰 구역으로 보인다.

사용:  python make_maps.py [롬파일]
       기본은 원본(mt1_m191_v3.nes). 한글판을 넣어도 결과는 같다 -
       **우리 패치는 뱅크 $0A 를 한 바이트도 안 건드린다**(확인 완료).
"""
import os
import sys

from PIL import Image, ImageDraw

ROM = sys.argv[1] if len(sys.argv) > 1 else "mt1_m191_v3.nes"
BASE, W, H = 0x14014, 128, 64          # 파일오프셋 / 전체 폭·높이(칸)
FW = FH = 16                           # 한 층 크기
OUTDIR = "지도"

BG = (14, 14, 20)
WALL = (238, 238, 245)                 # 값 1
DOOR = (80, 190, 255)                  # 값 3
GRID = (48, 48, 64)
LABEL = (150, 150, 170)
MARK = (255, 120, 90)

rom = open(ROM, "rb").read()
cell = lambda x, y: rom[BASE + y * W + x]


def walls(c):
    """한 바이트 -> (북, 동, 남, 서) 각 0/1/3"""
    return (c >> 6) & 3, (c >> 4) & 3, (c >> 2) & 3, c & 3


def colour(v):
    return None if v == 0 else (WALL if v == 1 else DOOR)


# 특수 좌표표 (고정뱅크 $CB5C, 4바이트 x N, $FF 로 끝) - 이벤트 자리
def specials():
    p = 0x3C010 + (0xCB5C - 0xC000)
    out = []
    while rom[p] != 0xFF and len(out) < 64:
        out.append((rom[p], rom[p + 1], rom[p + 2], rom[p + 3]))
        p += 4
    return out


SPECIAL = specials()


def draw_region(x0, y0, w, h, s, pad, title):
    """한 구역을 그린다. s = 칸 크기(px), pad = 눈금 여백"""
    im = Image.new("RGB", (w * s + pad + 8, h * s + pad + 8), BG)
    d = ImageDraw.Draw(im)
    ox = oy = pad
    for gy in range(h + 1):                                  # 옅은 격자
        d.line([(ox, oy + gy * s), (ox + w * s, oy + gy * s)], fill=GRID)
    for gx in range(w + 1):
        d.line([(ox + gx * s, oy), (ox + gx * s, oy + h * s)], fill=GRID)
    for y in range(h):
        for x in range(w):
            n, e, so, we = walls(cell(x0 + x, y0 + y))
            X, Y = ox + x * s, oy + y * s
            if colour(n): d.line([(X, Y), (X + s, Y)], fill=colour(n), width=2)
            if colour(we): d.line([(X, Y), (X, Y + s)], fill=colour(we), width=2)
            if colour(so): d.line([(X, Y + s), (X + s, Y + s)], fill=colour(so), width=2)
            if colour(e): d.line([(X + s, Y), (X + s, Y + s)], fill=colour(e), width=2)
    for sx, sy, mask, data in SPECIAL:                       # 이벤트 자리 표시
        if x0 <= sx < x0 + w and y0 <= sy < y0 + h:
            X, Y = ox + (sx - x0) * s + s // 2, oy + (sy - y0) * s + s // 2
            d.ellipse([X - 4, Y - 4, X + 4, Y + 4], outline=MARK, width=2)
    if pad >= 14:                                            # 좌표 눈금
        for x in range(w):
            d.text((ox + x * s + 3, 4), "%X" % ((x0 + x) & 0xF), fill=LABEL)
        for y in range(h):
            d.text((4, oy + y * s + s // 2 - 4), "%X" % ((y0 + y) & 0xF), fill=LABEL)
    d.text((ox + 2, oy + h * s + 6), title, fill=LABEL)
    return im


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    # 1) 전체 조감도 - 층 경계와 번호
    s = 6
    im = Image.new("RGB", (W * s + 30, H * s + 30), BG)
    d = ImageDraw.Draw(im)
    for y in range(H):
        for x in range(W):
            n, e, so, we = walls(cell(x, y))
            X, Y = 24 + x * s, 20 + y * s
            if colour(n): d.line([(X, Y), (X + s, Y)], fill=colour(n))
            if colour(we): d.line([(X, Y), (X, Y + s)], fill=colour(we))
            if colour(so): d.line([(X, Y + s), (X + s, Y + s)], fill=colour(so))
            if colour(e): d.line([(X + s, Y), (X + s, Y + s)], fill=colour(e))
    for by in range(H // FH):
        for bx in range(W // FW):
            d.rectangle([24 + bx * FW * s, 20 + by * FH * s,
                         24 + (bx + 1) * FW * s, 20 + (by + 1) * FH * s],
                        outline=(200, 70, 70))
            d.text((24 + bx * FW * s + 4, 20 + by * FH * s + 3),
                   "%d-%d" % (by, bx), fill=(255, 170, 90))
    im.save(os.path.join(OUTDIR, "_전체.png"))

    # 2) 층별 확대
    n = 0
    for by in range(H // FH):
        for bx in range(W // FW):
            t = "구역 %d-%d   (전역 X %d~%d, Y %d~%d)" % (
                by, bx, bx * FW, bx * FW + FW - 1, by * FH, by * FH + FH - 1)
            img = draw_region(bx * FW, by * FH, FW, FH, 34, 18, t)
            img.save(os.path.join(OUTDIR, "구역_%d-%d.png" % (by, bx)))
            n += 1
    print("%s/ 에 전체 1장 + 구역 %d장 저장" % (OUTDIR, n))
    print("특수 좌표 %d곳: %s" % (len(SPECIAL),
                              " ".join("(%d,%d)" % (a, b) for a, b, _, _ in SPECIAL)))


if __name__ == "__main__":
    main()
