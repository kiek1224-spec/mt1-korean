#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""롬 전체에서 **아직 번역 안 된 일본어**를 찾는다 (정적 분석).

왜 따로 만들었나
  - `scan_kana.py` 는 전체를 훑지만 **원본과 대조를 안 한다.** 정적 폰트가 가나 코드
    자리($24~$59, $64~$7F)에 살기 때문에 "가나 코드다"만 보면 우리 한글까지 다 걸린다.
  - `check_labels.py` 는 대조는 하지만 **라벨 주변 창만** 본다.
  -> 둘을 합친다: **원본과 한 바이트도 안 바뀐** 가나 런을 롬 전체에서 찾는다.
     안 바뀌었다 = 우리가 손을 안 댔다 = 원문 그대로다. 이게 진짜 신호다.

빼는 곳 (번역됐지만 원본 바이트가 그대로 남는 자리)
  - 뱅크 $0F~$1D : 우리 레코드/글리프 뱅크 (원본은 안 쓰는 빈 뱅크)
  - 이름표 A(악마/종족/특수아이템) B(아이템) : **이름 훅**이 런타임에 한글로 바꾼다.
    원본 문자열은 자리에 그대로 남아 있지만 화면엔 안 나온다.
  - 던전 패널 표 $BE24 (뱅크$05) : 전용 미니폰트, panel_ko.txt 가 따로 덮는다.
  - CHR (PRG 뒤쪽)

사용:  python scan_left.py [최소가나수]
"""
import io
import sys

MIN = int(sys.argv[1]) if len(sys.argv) > 1 else 4
sys.argv = [sys.argv[0]]
import build_step5b as B
import decode_tbl as T

KANA = set(range(0x24, 0x58)) | set(range(0x64, 0x98))
DAK = {0x58, 0x59, 0x98, 0x99}
PUNCT = {0x5A, 0x5B, 0x5C, 0x5D, 0x62, 0x61}
SPACE = set(range(0xD0, 0xE0))      # $Dn = n칸 띄우기. **문장의 강한 신호**
# ★잡음 거르기. 이 게임은 맵/타일 데이터도 가나 코드 대역을 쓴다.
#   뱅크$0A 던전 데이터가 `ホルムヘムムヲ…` 처럼 수백 자씩 걸린다.
#   진짜 문장은 (1) 띄어쓰기 코드 $Dn 을 품고 (2) 같은 글자가 계속 반복되지 않는다.
REP_MAX = 0.34                      # 가장 잦은 글자가 이 비율을 넘으면 데이터로 본다
DISTINCT_MIN = 6                    # 서로 다른 글자 수 하한
HDR = 0x10
PRG = 0x40000

rom = open(B.OUT, "rb").read()
src = open(B.SRC, "rb").read()

# ---------------------------------------------------------------- 빼는 구간
skip = bytearray(HDR + PRG)


def mark(a, n):
    for i in range(max(a, 0), min(a + n, len(skip))):
        skip[i] = 1


for _b in range(0x0F, 0x1E):                       # 레코드/글리프 뱅크
    mark(HDR + _b * 0x2000, 0x2000)
for _tag, _ptoff, _cnt, _bank, _base, _e in B.NTABLES:
    if _tag == "C":                                # C(마법)는 제자리 치환을 했다 - 검사 대상
        continue
    mark(_ptoff, _cnt * 2)
    for _i in range(_cnt):
        _p = src[_ptoff + 2 * _i] | (src[_ptoff + 2 * _i + 1] << 8)
        _o = HDR + _bank * 0x2000 + (_p - _base)
        _l = 0
        while _l < 24 and src[_o + _l] != 0xFF:
            _l += 1
        mark(_o, _l + 1)
mark(0x0BE34, 23 * 5)                              # 던전 패널 표 (미니폰트)

# ★★번역문이 원문보다 짧으면 **종결자 뒤에 원문 꼬리가 남는다.** 화면엔 절대 안 나오는
#   죽은 바이트인데 가나 런으로는 걸린다. 빌더의 records 로 그 구간을 정확히 빼 준다.
#   (원문 길이는 **원본 바이트**로 다시 재야 한다 - B.rom 은 이미 번역문으로 덮여 있다)
# 죽은 꼬리 = [번역문 끝, **다음 메시지 시작**). 첫 종결자에서 끊으면 안 된다 -
# 메시지 안에도 $FF/$FE 가 들어 있어서 꼬리를 덜 잡고 오탐이 난다(2026-09-07 확인).
_ph = sorted(B.phys(_a) for _a, _e, _ in B.records)
_len = {B.phys(_a): len(_e) for _a, _e, _ in B.records}
_dead = 0
for _k, _q in enumerate(_ph):
    _stop = _ph[_k + 1] if _k + 1 < len(_ph) else _q + _len[_q]
    _n = _stop - (_q + _len[_q])
    if _n > 0:
        mark(_q + _len[_q], _n)
        _dead += _n
print("죽은 꼬리(번역문이 짧아 남은 원문) %d바이트를 검사에서 제외" % _dead)


def _texty(seg, ka):
    """데이터가 아니라 **문장**으로 보이는가."""
    if not any(c in SPACE for c in seg):        # 띄어쓰기가 없으면 문장이 아니다
        return False
    if len(set(ka)) < DISTINCT_MIN:
        return False
    top = max(ka.count(c) for c in set(ka))
    return top <= max(2, int(len(ka) * REP_MAX))


# ---------------------------------------------------------------- 훑기
runs = []
i = HDR
while i < HDR + PRG:
    if skip[i] or rom[i] != src[i] or rom[i] not in KANA:
        i += 1
        continue
    j = i
    while (j < HDR + PRG and not skip[j] and rom[j] == src[j]
           and (rom[j] in KANA or rom[j] in DAK or rom[j] in PUNCT or rom[j] in SPACE)):
        j += 1
    seg = bytes(rom[i:j])
    ka = [c for c in seg if c in KANA]
    if len(ka) >= MIN and _texty(seg, ka):
        runs.append((i, seg))
    i = max(j, i + 1)

# ---------------------------------------------------------------- 보고
from collections import Counter
cnt = Counter((a - HDR) // 0x2000 for a, _ in runs)
print("=" * 78)
print("원본과 **한 바이트도 안 바뀐** 가나 런 (>=%d글자) : %d곳" % (MIN, len(runs)))
print("뱅크별: " + "  ".join("$%02X:%d" % (b, n) for b, n in sorted(cnt.items())))
print("=" * 78)
# 알려진 메시지(252개) 구간 안인지 - 안이면 꼬리 계산 오차, 밖이면 **추출조차 안 된 문장**
spans = []
for _k, _q in enumerate(_ph):
    _stop = _ph[_k + 1] if _k + 1 < len(_ph) else _q + _len[_q]
    spans.append((_q, _stop))
spans.sort()


def _inside(x):
    for lo, hi in spans:
        if lo <= x < hi:
            return True
        if lo > x:
            break
    return False


MAPBANK = {0x0A}                     # 던전 맵 데이터 - 글자가 아니다 (육안 확인)
out = []
for a, seg in runs:
    b = (a - HDR) // 0x2000
    if b in MAPBANK:
        continue
    out.append((a, seg, _inside(a)))
print("\n지도데이터 뱅크($0A) 제외, 남은 %d곳" % len(out))
print("-" * 78)
for a, seg, ins in sorted(out, key=lambda x: (x[2], -len(x[1]))):
    b = (a - HDR) // 0x2000
    inb = (a - HDR) % 0x2000
    ctx = T.dec(rom[a - 6:a]) + " ▶" + T.dec(seg) + "◀ " + T.dec(rom[a + len(seg):a + len(seg) + 6])
    print("  [%s] 파일$%05X 뱅크$%02X $%04X  %2d자  %s"
          % ("메시지밖" if not ins else "메시지안", a, b, 0x8000 + inb, len(seg), ctx))
