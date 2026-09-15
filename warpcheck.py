#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""레이어 $08 / $0A 가 정말 **양방향 워프 쌍**인지 전수 대조한다.

가설: $08 의 (x,y) -> (x',y') 마다, $0A 에 (x',y') -> (x,y) 가 있다.
가설이 맞으면 '계단/통로표를 찾았다'고 말할 수 있고, 틀리면 말하면 안 된다.
"""
import sys

ROM = sys.argv[1]
d = open(ROM, "rb").read()
HDR, PRGN = 16, d[4] * 16384
DIROFF = [0x00, 0x1C, 0x38, 0x54, 0x70, 0x8C, 0xA8]
PTRBANK = 0x09


def ptr_at(idx):
    p = HDR + PTRBANK * 0x2000 + (0xAAF5 - 0xA000) + idx
    return d[p] | (d[p + 1] << 8)


def table(addr, stride=5, limit=64):
    if 0x8000 <= addr < 0xA000:   base, bank = 0x8000, 0x08
    elif 0xA000 <= addr < 0xC000: base, bank = 0xA000, 0x09
    else: return None
    off = HDR + bank * 0x2000 + (addr - base)
    out = []
    for i in range(limit):
        p = off + i * stride
        if p + stride > HDR + PRGN or d[p] == 0xFF:
            break
        out.append(tuple(d[p:p + stride]))
    return out


total_ok = total = 0
for b, doff in enumerate(DIROFF):
    A = table(ptr_at(doff + 0x08))
    B = table(ptr_at(doff + 0x0A))
    if A is None or B is None:
        print("블록 %d: 포인터가 범위 밖 - 건너뜀" % b); continue
    # $0A 를 (x,y) -> (x',y') 사전으로
    bmap = {}
    for e in B:
        bmap[(e[0], e[1] & 0x3F)] = (e[2], e[3])
    ok = 0
    for e in A:
        src = (e[0], e[1] & 0x3F)
        dst = (e[2], e[3])
        back = bmap.get(dst)
        if back == src:
            ok += 1
    total_ok += ok; total += len(A)
    print("블록 %d (오프셋 $%02X): $08 %2d개 / $0A %2d개 -> 왕복 일치 %2d/%2d %s"
          % (b, doff, len(A), len(B), ok, len(A),
             "✔" if ok == len(A) and len(A) > 0 else ("(빈 표)" if not A else "★불일치")))

print("-" * 66)
print("전체 왕복 일치 %d/%d" % (total_ok, total))
print("판정:", "양방향 워프표가 맞다 ✔" if total and total_ok == total
      else "★가설 기각 - 워프표라고 말하면 안 된다")
