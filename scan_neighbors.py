#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ui_ko.txt 항목마다 **앞뒤로 붙어 남은 원문 조각**(원본과 한 바이트도 안 바뀐 가나)을 찾는다.

    python scan_neighbors.py <한글판 롬> [원본 롬=mt1_m191_v3.nes]

왜 따로 만들었나 (2026-09-15)
  `scan_left.py` 는 띄어쓰기($Dn)가 있어야 문장으로 보기 때문에 **짧은 낱말·조사**를 못 잡는다.
  v51 점검에서 남은 미번역이 거의 전부 "문장의 한쪽만 번역" 모양이었다
  (예: 「ナカジマたちは」+「힘이 넘쳤다」, 「[이름]は」+「가면에 담겼다」).
  -> 번역 항목의 **바로 앞/뒤**를 훑으면 1글자 조사까지 잡힌다.

규칙
  - 앞: 항목 시작에서 거꾸로, 뒤: 항목 끝에서 앞으로 최대 24바이트
  - 원본과 같고 글자/구두점/띄어쓰기/줄바꿈(FD) 인 바이트만 따라간다
  - 종결자(FE FF FB FC)나 바뀐 바이트(다른 번역 항목)를 만나면 멈춘다
★표 데이터가 우연히 가나 코드로 읽혀 걸리는 오탐이 섞인다. 원문 조각이 **연속 코드**거나
  앞 문맥이 숫자·제어코드뿐이면 데이터다. 판정 예시는 VERSIONS.md 「★미번역 점검」.
"""
import io
import os
import sys

WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORK)
import decode_tbl as T
import kdec as K

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
ROM = sys.argv[1]
SRC = sys.argv[2] if len(sys.argv) > 2 else os.path.join(WORK, "mt1_m191_v3.nes")
rom = open(ROM, "rb").read()
src = open(SRC, "rb").read()

KANA = set(range(0x24, 0x58)) | set(range(0x64, 0x98))
DAK = {0x58, 0x59, 0x98, 0x99}
PUNCT = {0x5A, 0x5B, 0x5C, 0x5D, 0x61, 0x62}
SPACE = set(range(0xD0, 0xE0))
OK = KANA | DAK | PUNCT | SPACE | {0xFD}
STOP = {0xFE, 0xFF, 0xFB, 0xFC}

ui = []
for ln in io.open(os.path.join(WORK, "ui_ko.txt"), encoding="utf-8"):
    if ln.startswith("#") or "\t" not in ln:
        continue
    p = ln.rstrip("\n").split("\t")
    try:
        ui.append((int(p[0], 16), int(p[1]), p[2] if len(p) > 2 else ""))
    except ValueError:
        pass


def walk(i, step, limit=24):
    got = []
    for _ in range(limit):
        if i < 0x10 or i >= min(len(rom), len(src)):
            break
        c = rom[i]
        if c in STOP or rom[i] != src[i] or c not in OK:
            break
        got.append(i)
        i += step
    return sorted(got)


hits = {}
for a, n, t in ui:            # ui_ko 주소 = 파일 오프셋
    for side, idx in (("앞", walk(a - 1, -1)), ("뒤", walk(a + n, 1))):
        k = sum(1 for i in idx if rom[i] in KANA)
        if k:
            hits.setdefault((idx[0], idx[-1] + 1), (side, a, t, k))

print("ui_ko 항목 %d개 / 앞뒤에 원문 가나가 남은 자리 %d곳" % (len(ui), len(hits)))
for (lo, hi), (side, a, t, k) in sorted(hits.items()):
    print("파일$%05X~$%05X 가나%d  [%s] 번역항목 %05X「%s」" % (lo, hi, k, side, a, t))
    print("    원문 조각 : %s" % T.dec(src[lo:hi]))
    print("    문맥(지금): %s ▶%s◀ %s" % (K.dec(rom[lo - 10:lo]), K.dec(rom[lo:hi]), K.dec(rom[hi:hi + 12])))
