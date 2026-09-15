#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""던전 '칸 속성' 레이어표를 뽑는다.

조회 루틴 $E295 (역어셈블로 확정, 2026-09-12):
    X = $E28E[방향] + 레이어id          ($E28E = 00 1C 38 54 70 8C A8, 방향당 28바이트)
    포인터 = ($AAF5+X, $AAF5+X+1)        (뱅크 컨텍스트 8 -> R7 = 뱅크$09)
    그 포인터가 가리키는 표를 $FF 까지 훑는다
    엔트리 = [X][Y|플래그(비트6-7)][값...]   스트라이드 = 2 + Y인자
      $E295 를 Y=3 으로 부르면 스트라이드 5
"""
import sys

ROM = sys.argv[1]
d = open(ROM, "rb").read()
PRGN = d[4] * 16384
HDR = 16


def bankoff(bank, cpu, base):
    return HDR + bank * 0x2000 + (cpu - base)


PTRBANK = 0x09              # 컨텍스트 8 의 R7
DIROFF = [0x00, 0x1C, 0x38, 0x54, 0x70, 0x8C, 0xA8]


def ptr_at(idx):
    p = bankoff(PTRBANK, 0xAAF5, 0xA000) + idx
    return d[p] | (d[p + 1] << 8)


def read_table(addr, stride, limit=200):
    """addr 은 CPU 주소. $8000~$9FFF 면 R6(뱅크$08), $A000~ 면 R7(뱅크$09)."""
    if 0x8000 <= addr < 0xA000:
        base, bank = 0x8000, 0x08
    elif 0xA000 <= addr < 0xC000:
        base, bank = 0xA000, 0x09
    else:
        return None, "표 주소가 $8000~$BFFF 밖 ($%04X)" % addr
    off = bankoff(bank, addr, base)
    out = []
    for i in range(limit):
        p = off + i * stride
        if p + stride > HDR + PRGN:
            return out, "롬 끝"
        if d[p] == 0xFF:
            return out, "정상종료"
        out.append(d[p:p + stride])
    return out, "limit 도달"


LAYERS = [(0x08, "레이어$08", 5), (0x0A, "레이어$0A", 5),
          (0x16, "레이어$16", 5), (0x1A, "레이어$1A", 5)]

for dirn in range(4):
    print("=" * 74)
    print("방향 %d  (오프셋 $%02X)" % (dirn, DIROFF[dirn]))
    for lid, name, stride in LAYERS:
        idx = DIROFF[dirn] + lid
        a = ptr_at(idx)
        ent, why = read_table(a, stride)
        if ent is None:
            print("  %-9s idx=%3d  ptr=$%04X   %s" % (name, idx, a, why))
            continue
        print("  %-9s idx=%3d  ptr=$%04X   엔트리 %d개 (%s)"
              % (name, idx, a, len(ent), why))
        for e in ent[:12]:
            x = e[0]; yb = e[1]
            print("        X=%3d Y=%3d flag=%d  값 %s"
                  % (x, yb & 0x3F, yb >> 6, " ".join("%02X" % b for b in e[2:])))
        if len(ent) > 12:
            print("        ... 그 밖 %d개" % (len(ent) - 12))
