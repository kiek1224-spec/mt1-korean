#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이름 훅을 다섯 모드 전부로 직접 호출해 결과 버퍼를 한글로 되읽는다."""
import sys, os
os.environ["MT1_STATIC"] = "1"; sys.argv = [sys.argv[0]]
from nesboot import verify
import build_step5b as B

RET = 0x0300
REV = {c: ch for ch, c in B.STATIC.items()}
for ch, c in B.PUNCT.items(): REV.setdefault(c, ch)
REV[B.BLANK] = "_"

def decode(n, buf, cnt):
    out = ""
    for i in range(cnt):
        c = n.ram[buf + i]
        if c == 0xFF: break
        if c in B.TILES:
            k = B.TILES.index(c)
            if k >= B.NDLG:
                j = k - B.NDLG
                g = n.prgram[B.NRESL - 0x6000 + j] | (n.prgram[B.NRESH - 0x6000 + j] << 8)
            else:
                g = n.prgram[B.RESIDL - 0x6000 + k] | (n.prgram[B.RESIDH - 0x6000 + k] << 8)
            out += B.glob[g] if g < len(B.glob) else "?%d" % g
        elif c in REV: out += REV[c]
        elif 0xD0 <= c < 0xE0: out += " " * (c & 0xF)
        else: out += "<%02X>" % c
    return out

ko = {}
for l in open("names_ko.txt", encoding="utf-8"):
    l = l.rstrip()
    if l.strip() and not l.startswith("#"):
        k, v = l.split(chr(9)); ko[k] = v

n = verify(B.OUT, frames=600, verbose=False)
# 모드 -> (표태그, 개수, 뱅크셋, R6, R7)
SPEC = {0: ("A", 167, 12, 0x0C, 0x0D), 1: ("A", 167, 12, 0x0C, 0x0D), 2: ("A", 167, 12, 0x0C, 0x0D),
        3: ("C", 36, 10, 0x0A, 0x0B), 4: ("B", 64, 1, 0x01, 0x01)}
fail = 0
for mode in (0, 1, 2, 3, 4):
    tag, cnt, bset, r6, r7 = SPEC[mode]
    bad = []
    for i in range(cnt):
        n.ram[0x14] = bset; n.r[6], n.r[7] = r6, r7; n.map_prg()
        n.prgram[B.NNEXT - 0x6000] = 0; n.prgram[B.NCNT - 0x6000] = 0
        n.ram[0x0650] = 0; n.ram[0x0480] = 0; n.ram[0x0481] = 0
        for k in range(0x0588, 0x05B8): n.ram[k] = 0
        n.prgram[B.NMODE - 0x6000] = mode
        n.a = i; n.x = 0
        n.push(((RET - 1) >> 8) & 0xFF); n.push((RET - 1) & 0xFF)
        n.pc = B.NHOOK
        for _ in range(200000):
            if n.pc == RET: break
            n.step()
        else:
            bad.append((i, "훅이 끝나지 않음")); continue
        if mode == 1:   got = decode(n, 0x0588, 8)
        elif mode == 3: got = decode(n, 0x0588, 6)
        elif mode == 4: got = decode(n, 0x0590, n.a)
        elif mode == 0: got = decode(n, 0x0590, n.ram[0x0650])
        else:           got = decode(n, 0x0590, n.ram[0x0650] + 1)
        want = ko["%s%d" % (tag, i)]
        cap = {0: 8, 1: 8, 3: 6}.get(mode)
        exp = want[:cap] if cap else want
        if got.replace("_", "") != exp:
            bad.append((i, got, exp))
    fail += len(bad)
    print("모드 %d (%s표 %d개): 실패 %d %s" % (mode, tag, cnt, len(bad), bad[:4]))
print("\n총 실패 %d건" % fail)

# ★어긋나면 종료코드로 알린다. 없으면 make.py 가 통과로 세어 버린다(2026-09-03 발각).
sys.exit(1 if fail else 0)