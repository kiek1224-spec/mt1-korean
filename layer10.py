#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""레이어 $10 ($FCB7 이 조회하는 것) 을 뽑는다.

$FCB7 역어셈블 (2026-09-12):
    for i in 0..4:
        X = $EE9D[i] + $10
        포인터 = ($AAF5+X, +1)
        len  = (포인터)[0]                 <- **표 앞에 길이 바이트**
        표시작 = 포인터 + len + 1
        $E2BB 로 검색, 스트라이드 = 2 + 2 = 4
    엔트리 4바이트 = [X][Y|플래그(비트6-7)][v0][v1]
"""
import sys

ROM = sys.argv[1]
d = open(ROM, "rb").read()
HDR, PRGN = 16, d[4] * 16384


def prg(a):     # PRG 주소 -> 파일 오프셋
    return HDR + a


def fixed1F(cpu):
    return PRGN - 0x2000 + (cpu - 0xE000)


def ptr_at(idx):
    p = prg(9 * 0x2000 + (0xAAF5 - 0xA000) + idx)
    return d[p] | (d[p + 1] << 8)


def cpu_to_prg(cpu):
    if 0x8000 <= cpu < 0xA000: return 8 * 0x2000 + (cpu - 0x8000)
    if 0xA000 <= cpu < 0xC000: return 9 * 0x2000 + (cpu - 0xA000)
    return None


off5 = [d[prg(fixed1F(0xEE9D)) + i] for i in range(5)]
print("$EE9D 오프셋 5개:", " ".join("$%02X" % v for v in off5))
print()

grand = 0
for i, o in enumerate(off5):
    idx = o + 0x10
    cpu = ptr_at(idx)
    base = cpu_to_prg(cpu)
    if base is None:
        print("서브표 %d: idx=%3d ptr=$%04X  -> 범위 밖, 건너뜀" % (i, idx, cpu))
        continue
    ln = d[prg(base)]
    start = base + ln + 1
    ent = []
    for k in range(64):
        p = prg(start + k * 4)
        if p + 4 > HDR + PRGN or d[p] == 0xFF:
            break
        ent.append(tuple(d[p:p + 4]))
    grand += len(ent)
    print("서브표 %d: idx=%3d ptr=$%04X  길이바이트=%d  엔트리 %d개"
          % (i, idx, cpu, ln, len(ent)))
    for e in ent:
        x, yb, v0, v1 = e
        inr = "" if (x < 128 and (yb & 0x3F) < 64) else "  ※범위밖"
        print("      X=%3d Y=%2d flag=%d  v=%02X %02X%s"
              % (x, yb & 0x3F, yb >> 6, v0, v1, inr))
print("-" * 60)
print("합계 %d개" % grand)
