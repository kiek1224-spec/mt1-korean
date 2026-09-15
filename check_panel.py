#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""던전 패널 / 전투 커맨드 박스 검사.

세 가지를 본다.
  [1] 번역한 엔트리가 **의도한 한글 글리프**를 가리키는가 (CHR 비트맵 대조)
  [2] 번역하지 않은 엔트리의 타일이 **원본과 한 바이트도 다르지 않은가**
      (미로 그래픽을 건드리지 않았다는 증명)
  [3] 5바이트 고정폭이 유지되고 남는 칸이 $FF 인가
"""
import sys
sys.argv = [sys.argv[0]]
import build_step5b as B
import galmuri8 as G

SRC = "mt1_m191_v3.nes"
v3 = open(SRC, "rb").read()
rom = open(B.OUT, "rb").read()
CHR0 = 16 + rom[4] * 16384


def tile(d, code):
    b, t = ((0x02, code) if code < 0x40 else (0x03, code - 0x40))
    o = CHR0 + b * 1024 + t * 16
    return bytes(d[o:o + 16])


if not B.PANEL:
    print("패널 꺼진 빌드 — 검사 건너뜀 (MT1_PANEL=1 로 빌드해야 의미가 있다)")
    raise SystemExit(0)

want = {}
for l in open("panel_ko.txt", encoding="utf-8"):
    l = l.rstrip()
    if not l.strip() or l.startswith("#"): continue
    i, jp, ko = l.split(chr(9))
    if ko != "-": want[int(i)] = ko

ent = [list(rom[B.PANTAB + i * B.PANW:B.PANTAB + (i + 1) * B.PANW]) for i in range(B.PANN)]
old = [list(v3[B.PANTAB + i * B.PANW:B.PANTAB + (i + 1) * B.PANW]) for i in range(B.PANN)]
bad = 0

print("%s  CRC32 %08X" % (B.OUT, __import__("zlib").crc32(rom)))
print("[1] 번역 엔트리 %d개" % len(want))
for i, ko in sorted(want.items()):
    codes = [c for c in ent[i] if c != 0xFF]
    got = ""
    for c in codes:
        g = tile(rom, c)
        hit = [ch for ch in ko if bytes(G.to_chr(G.bitmap(ch))) == g]
        got += hit[0] if hit else "?"
    ok = (got == ko) and len(codes) == len(ko)
    if not ok: bad += 1
    print("    idx%-2d %-6s -> %-6s %s  %s" % (i, ko, got, ok and "OK" or "★불일치",
                                               " ".join("$%02X" % c for c in ent[i])))

print("[2] 번역하지 않은 엔트리의 타일 원본 대조")
keep = sorted({c for i, e in enumerate(ent) if i not in want for c in e if c != 0xFF})
diff = [c for c in keep if tile(rom, c) != tile(v3, c)]
if diff:
    bad += 1
    print("    ★건드린 타일: %s" % " ".join("$%02X" % c for c in diff))
else:
    print("    잠근 타일 %d개 전부 원본과 동일 ✔" % len(keep))

print("[3] 고정폭 / 패딩")
for i, e in enumerate(ent):
    body = e
    while body and body[-1] == 0xFF: body = body[:-1]
    if 0xFF in body:
        bad += 1
        print("    ★idx%d 중간에 $FF: %s" % (i, " ".join("$%02X" % c for c in e)))
if not bad: print("    23엔트리 전부 5바이트 + 뒤쪽 $FF 패딩 ✔")

print("[4] 손대지 않은 엔트리가 원본 그대로인가")
untouched = [i for i in range(B.PANN) if i not in want]
moved = [i for i in untouched if ent[i] != old[i]]
if moved:
    bad += 1
    print("    ★바뀐 엔트리: %s" % moved)
else:
    print("    %d개 전부 원본과 동일 ✔" % len(untouched))

print()
print("=== 패널 검증 통과 ===" if not bad else "=== ★%d건 실패 ===" % bad)
sys.exit(1 if bad else 0)
