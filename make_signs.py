#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시설 세로 간판 3종과 「소지금」 상자를 한글로 그린다.

    邪教の館 -> 사교의관   回復の泉 -> 치료의샘   辺境の店 -> 만물의회
    もちきん -> 소지금

## 구조 (2026-09-06 실측)
간판 글자는 **스프라이트가 아니라 배경 네임테이블 타일**이다. 한 글자 = **2x2 타일**,
네 글자가 세로로 쌓인다(열4~5, 행4~11 / NT1). 색은 **흰색 단색** - 두 비트플레인이 같다.

★★CHR 뱅크는 한 프레임 안에서 두 번 바뀐다(MMC3 IRQ 분할).
  vblank(스캔라인 250~251)에서 **화면 상단용**을, 스캔라인 119~120 에서 하단(대사창)용을 넣는다.
  그래서 프레임 끝에서 패턴테이블을 뜨면 **폰트 뱅크가 잡혀 엉뚱한 그림**이 나온다.
  상단용 패턴테이블1 = R2~R5:
      사교의관  $2C~$2F   -> 파일 CHR+$2C*0x400
      치료의샘  $28~$2B   -> 파일 CHR+$28*0x400
      만물의회  $28~$2B   -> ★치료의샘과 **같은 뱅크**

★★원본은 두 간판의 셋째 글자가 똑같이 「の」라 **타일을 공유**한다($89 $8A $99 $9A).
  그래서 **치료의샘과 만물의회의 셋째 글자는 반드시 같아야 한다** - 둘 다 「의」다.
  (한때 「만물상회」로 하려다 셋째가 「상」이 되어 회복의 샘이 「치료상샘」으로 깨졌다.
   타일을 새로 배정하려면 화면 데이터도 고쳐야 하는데, 시설 화면 데이터는 PRG 어디에도
   네임테이블 형태로 들어 있지 않다 - 압축/메타타일이라 위치를 못 찾았다. 2026-09-06.
   사용자가 「만물의회」로 정리해서 문제 자체가 없어졌다. 셋이 나란히 「○○의○」로도 맞는다.)
  ★이름을 다시 바꿀 거면 **셋째 글자가 치료의샘과 같은지** 먼저 확인할 것.
"""
import os

from PIL import Image, ImageDraw, ImageFont

# ★간판 글자는 **갈무리14**(14px 비트맵 폰트, SIL OFL)를 원래 크기로 찍는다.
#   공식 저장소 github.com/quiple/galmuri 에서 받아 galmuri/ 에 두었다.
#   배포물에 저작자 표시를 넣을 것.
GALMURI14 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "galmuri", "Galmuri14.ttf")
GALMURI14_PX = 15                        # 이 크기로 찍으면 글리프가 14x14 로 떨어진다

# (태그, 1KB뱅크, 한글4글자, [(좌상,우상,좌하,우하)] x4)
SIGNS = [
    ("사교의관", 0x2C, "사교의관",
     [(0x30, 0x31, 0x40, 0x41), (0x50, 0x51, 0x60, 0x61),
      (0x70, 0x71, 0x32, 0x33), (0x42, 0x43, 0x52, 0x53)]),
    ("치료의샘", 0x28, "치료의샘",
     [(0x87, 0x88, 0x97, 0x98), (0xA7, 0xA8, 0xB7, 0xB8),
      (0x89, 0x8A, 0x99, 0x9A), (0xA9, 0xAA, 0xB9, 0xBA)]),
    ("만물의회", 0x28, "만물의회",
     [(0x65, 0x66, 0x75, 0x76), (0x6D, 0x6E, 0x7D, 0x7E),
      (0x89, 0x8A, 0x99, 0x9A), (0x67, 0x68, 0x77, 0x78)]),   # 셋째는 치료의샘과 공유
    # ★2026-09-15 라그의 가게(ラグの店). 사용자 보고 「일본어로 쓰여진 라그」.
    #   세이브 _5 에서 vblank R2~R5 = 28 29 2A 2B, NT1 열4~5 행4~11 을 떠서 확정.
    #   ラ/グ 만 제 타일이고 の·店 은 만물의회(辺境の店)와 **셋째·넷째를 공유**한다 -> 반드시 「의」「회」.
    #   이름은 대사(script_ko @라그란 놈이…)와 맞춰 「라그」.
    ("라그의회", 0x28, "라그의회",
     [(0x69, 0x6A, 0x79, 0x7A), (0x6B, 0x6C, 0x7B, 0x7C),
      (0x89, 0x8A, 0x99, 0x9A), (0x67, 0x68, 0x77, 0x78)]),   # 셋째·넷째는 만물의회와 공유
]

# 「もちきん」 상자 = 8x8 타일 넉 장 (같은 $28 뱅크). 소·지·금 + 빈 칸
MONEY_BANK, MONEY_TILES, MONEY_TEXT = 0x28, (0x03, 0x04, 0x05, 0x06), "소지금 "


def _mask(ch, size=GALMURI14_PX, px=16, bold=True):
    """한 글자를 px x px 이진 비트맵으로. **갈무리14 픽셀 폰트를 원래 크기로** 찍는다.

    ★큰 폰트를 축소하면 안 된다 - 획이 뭉개진다(맑은고딕 볼드로 해 보고 버렸다).
      갈무리14 는 14픽셀 전용 비트맵 폰트라 **안티앨리어싱만 끄면 픽셀이 정확히 떨어진다**
      (`ImageDraw.fontmode = "1"`). size 15 -> 14x14, size 16 -> 15x15.
    ★원본 한자는 획이 **2픽셀**이라 갈무리를 그냥 쓰면 너무 얇다.
      오른쪽으로 1픽셀 겹쳐 굵게 만든다(픽셀 폰트의 관용적인 볼드).
    """
    out = [[0] * px for _ in range(px)]
    if ch == " ":
        return out
    font = ImageFont.truetype(GALMURI14, size)
    im = Image.new("L", (size * 3, size * 3), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"                          # ★안티앨리어싱 끄기 - 안 끄면 회색이 섞인다
    d.text((size, size), ch, font=font, fill=255)
    bb = im.getbbox()
    if bb is None:
        return out
    im = im.crop(bb)
    w, h = im.size
    ox, oy = (px - w) // 2, (px - h) // 2
    for y in range(h):
        for x in range(w):
            if not im.getpixel((x, y)):
                continue
            if 0 <= oy + y < px and 0 <= ox + x < px:
                out[oy + y][ox + x] = 1
            if bold and 0 <= oy + y < px and 0 <= ox + x + 1 < px:
                out[oy + y][ox + x + 1] = 1
    return out


def _mask8(ch):
    """8x8 은 **프로젝트 자체 폰트(갈무리)** 를 쓴다 - 대사에 쓰는 것과 같은 글자꼴"""
    import galmuri8 as G
    if ch == " " or not G.has_glyph(ch):
        return [[0] * 8 for _ in range(8)]
    g = G.bitmap(ch)
    return [[1 if g[y][x] else 0 for x in range(8)] for y in range(8)]


def _put(rom, base, tile, block):
    """8x8 이진 블록을 타일에 굽는다. **두 평면 모두** 세워 흰색(색3)으로."""
    o = base + tile * 16
    for y in range(8):
        b = 0
        for x in range(8):
            if block[y][x]:
                b |= 1 << (7 - x)
        rom[o + y] = b
        rom[o + 8 + y] = b


def patch_rom(rom, chr_base):
    """rom(bytearray) 에 간판과 소지금을 굽는다. (간판글자수, 타일수) 를 돌려준다"""
    ntile = 0
    for tag, bank, text, blocks in SIGNS:
        base = chr_base + bank * 0x400
        assert len(text) == len(blocks) == 4, "간판 %s 는 4글자여야 한다" % tag
        for ch, (a, b, c, d) in zip(text, blocks):
            m = _mask(ch)
            for tile, ox, oy in ((a, 0, 0), (b, 8, 0), (c, 0, 8), (d, 8, 8)):
                _put(rom, base, tile, [[m[oy + y][ox + x] for x in range(8)]
                                       for y in range(8)])
                ntile += 1
    # 소지금 상자
    mbase = chr_base + MONEY_BANK * 0x400
    for ch, tile in zip(MONEY_TEXT, MONEY_TILES):
        _put(rom, mbase, tile, _mask8(ch))
        ntile += 1
    return len(SIGNS) * 4 + len(MONEY_TEXT), ntile


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "작업롬파일/mt1_kor5b_v34_협상결과.nes"
    rom = bytearray(open(src, "rb").read())
    chr_base = 16 + rom[4] * 16384
    print("글자 %d개 / 타일 %d개" % patch_rom(rom, chr_base))
    out = "작업롬파일/mt1_kor5b_vSIGN_x.nes"
    open(out, "wb").write(bytes(rom))
    print(out)
