#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""롬에 남은 **가나 런**을 찾는다. 정적폰트/슬롯 회수 뒤라 이 자리는 전부 깨져 보인다.
사용: python scan_kana.py [롬] [최소길이]"""
import sys
import decode_tbl as T
rom = sys.argv[1] if len(sys.argv) > 1 else "mt1_kor5b.nes"
MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 4
d = open(rom, "rb").read()
prg = d[16:16 + d[4] * 16384]
KANA = set(range(0x24, 0x58)) | set(range(0x64, 0x98))
DAK = {0x58, 0x59, 0x98, 0x99}
runs, i = [], 0
while i < len(prg):
    if prg[i] in KANA:
        j = i
        while j < len(prg) and (prg[j] in KANA or (prg[j] in DAK and j > i)):
            j += 1
        if sum(1 for c in prg[i:j] if c in KANA) >= MIN:
            runs.append((i, prg[i:j]))
        i = j
    else:
        i += 1
from collections import Counter
cnt = Counter(a // 0x2000 for a, _ in runs)
print("총 %d개 런 (>=%d 가나)" % (len(runs), MIN))
print("뱅크별:", " ".join("$%02X:%d" % (b, n) for b, n in sorted(cnt.items())))
for a, seg in runs:
    b = a // 0x2000
    print("뱅크$%02X off$%04X 파일$%05X  %s" % (b, a & 0x1FFF, 16 + a, T.dec(seg)))
