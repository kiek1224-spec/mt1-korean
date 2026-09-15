#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nesboot 상태에서 **화면(배경 네임테이블)을 그림으로 뽑는다.**

지금까지 병목은 실기 확인을 사용자에게 매번 부탁해야 하는 것이었다.
컨트롤러 입력(nesboot) + 이 화면 덤프가 있으면 대사 화면까지 직접 몰고 가서 눈으로 볼 수 있다.

한계(알고 쓸 것)
  - 스프라이트는 안 그린다. 배경만.
  - 팔레트를 추적하지 않으므로 **색 인덱스를 회색조로** 표시한다.
  - 스프라이트0 분할로 화면 위/아래가 다른 CHR 뱅크를 쓰는 경우, 덤프는 **현재 레지스터 상태**
    하나만 쓴다. 대사창(하단)을 보려면 분할 이후 상태에서 뜨는 게 맞다.
"""
from PIL import Image

PAL = [(16, 16, 20), (95, 95, 105), (170, 170, 180), (255, 255, 255)]


def chr_byte(n, a):
    """PPU 주소 a($0000-$1FFF)의 CHR 바이트를 현재 뱅크 매핑대로 읽는다."""
    a &= 0x1FFF
    if a < 0x0800:
        bank = (n.r[0] & 0xFE) | ((a >> 10) & 1)
    elif a < 0x1000:
        bank = (n.r[1] & 0xFE) | ((a >> 10) & 1)
    else:
        bank = n.r[2 + ((a - 0x1000) >> 10)]
    if n.mapper == 195:
        ram = bank < 4
        idx = ((bank & 3) << 10) | (a & 0x3FF)
    else:
        ram = bool(bank & 0x80)
        idx = ((bank & 1) << 10) | (a & 0x3FF)
    if ram:
        return n.chrram[idx % len(n.chrram)]
    off = bank * 0x400 + (a & 0x3FF)
    return n.chr[off % len(n.chr)] if n.chr else 0


def dump(n, path, nt=0, scale=2):
    """네임테이블 nt(0~3) 를 PNG 로. BG 패턴테이블은 PPUCTRL 비트4 로 정한다."""
    base = 0x1000 if (n.ppuctrl & 0x10) else 0x0000
    im = Image.new("RGB", (256 * scale, 240 * scale), PAL[0])
    px = im.load()
    ntoff = (nt & 3) * 0x400
    for ty in range(30):
        for tx in range(32):
            code = n.vram[(ntoff + ty * 32 + tx) & 0xFFF]
            ta = base + code * 16
            for r in range(8):
                p0 = chr_byte(n, ta + r)
                p1 = chr_byte(n, ta + r + 8)
                for c in range(8):
                    v = ((p0 >> (7 - c)) & 1) | (((p1 >> (7 - c)) & 1) << 1)
                    col = PAL[v]
                    X, Y = (tx * 8 + c) * scale, (ty * 8 + r) * scale
                    for dy in range(scale):
                        for dx in range(scale):
                            px[X + dx, Y + dy] = col
    im.save(path)
    return path


def text(n, nt=0, rows=range(30)):
    """네임테이블 타일번호를 16진으로. 어떤 코드가 찍혔는지 볼 때."""
    out = []
    ntoff = (nt & 3) * 0x400
    for ty in rows:
        row = n.vram[ntoff + ty * 32:ntoff + ty * 32 + 32]
        out.append("%2d: %s" % (ty, " ".join("%02X" % b for b in row)))
    return "\n".join(out)
