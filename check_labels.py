#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""라벨 블록에 **번역이 빠진 일본어**가 남아 있는지 본다.

발견 경위 (2026-09-03, 사용자 실기 보고):
능력치 라벨 5번째 줄이 사람 화면은 `う<FF>ん`(운)인데 **악마 화면만 `ぼうき`(ぼうぎょ, 방어)**
였다. `ui_words.txt` 는 가나 바이트열을 전역 치환하는 방식이라 문자열이 다르면 통째로 빠진다.
정적 폰트가 가나 타일을 먹었으므로 빠진 자리는 **엉뚱한 한글**로 뜬다.

방법: 이미 치환한 라벨 자리의 **주변 창**에서, **원본과 한 바이트도 안 바뀐 가나 런**을
찾는다. 정적 한글이 가나 코드 자리($24~$59, $64~$7F)에 살기 때문에 "가나 코드다"만으로는
전부 오탐이 된다 - **안 바뀌었다**가 진짜 신호다.
"""
import io
import sys
sys.argv = [sys.argv[0]]
import build_step5b as B
import decode_tbl as T

WIN = 0x50                      # 라벨 앞뒤로 훑을 범위
KANA = set(range(0x24, 0x58)) | set(range(0x64, 0x98))
DAK = {0x58, 0x59, 0x98, 0x99}

rom = open(B.OUT, "rb").read()
src = open(B.SRC, "rb").read()

rng = []
for l in io.open("작업롬파일/patched_ranges.txt", encoding="utf-8"):
    l = l.rstrip()
    if not l.strip() or l.startswith("#"): continue
    a, n, t, k = l.split(chr(9))
    if t.startswith("라벨"): rng.append((int(a, 16), int(n), k))

if not rng:
    print("라벨 치환 기록이 없다 (MT1_LABELS=1 로 빌드해야 의미가 있다)")
    raise SystemExit(0)

# 라벨 주변 창을 합쳐 중복 없이
spans = []
for a, n, _ in rng:
    lo, hi = max(0, a - WIN), a + n + WIN
    if spans and lo <= spans[-1][1]: spans[-1][1] = max(spans[-1][1], hi)
    else: spans.append([lo, hi])

KANA |= set(range(0xB4, 0xBD))       # 합자 카타카나(ジ ュ ン ゲ ェ 등)도 원문 그대로면 의심
bad = []
for lo, hi in spans:
    i = lo
    while i < hi:
        if rom[i] in KANA and rom[i] == src[i]:
            j = i
            while j < hi and rom[j] == src[j] and (rom[j] in KANA or (rom[j] in DAK and j > i)):
                j += 1
            if sum(1 for c in rom[i:j] if c in KANA) >= 2:
                bad.append((i, rom[i:j]))
            i = j
        else:
            i += 1

print("%s" % B.OUT)
print("라벨 치환 %d곳 / 검사 창 %d개" % (len(rng), len(spans)))
if bad:
    print("★라벨 주변에 남은 일본어 %d곳 - 화면에 엉뚱한 한글로 뜬다:" % len(bad))
    for a, seg in bad:
        print("   파일$%05X 뱅크$%02X  원문 그대로 남음: %s"
              % (a, (a - 16) // 0x2000, T.dec(seg)))
else:
    print("라벨 주변에 남은 일본어 없음 ✔")
sys.exit(1 if bad else 0)
