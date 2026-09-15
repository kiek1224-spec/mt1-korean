#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""롬 바이트를 **한글 기준**으로 디코드한다 (romdiff 보조).

build_step5b 의 인코딩 규칙을 그대로 뒤집는다:
  정적폰트 코드 1바이트 -> 음절      (static_font.txt)
  $BD <id>            -> {id}       (UI 이스케이프 - 음절은 빌드마다 번호가 바뀐다)
  $Dn                 -> 공백 n칸
  $9A~$B3             -> A~Z
  0~9                 -> 숫자,  $5A ! / $5B ? / $5C - / $5D ·
  $59                 -> 빈칸(정적 예약)
  $E0~$FF             -> <제어코드>
  그 밖               -> 가나(원문이 남은 자리) 또는 <XX>
"""
import os, sys
# ★경로를 하드코딩하지 않는다. 이 프로젝트는 옛 경로가 박힌 스크립트 8곳 때문에
#   PC 를 포맷한 뒤 툴체인이 통째로 멈춘 적이 있다(2026-09-12).
WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORK)
import decode_tbl as KANA

STATIC = {}
for _l in open(os.path.join(WORK, "static_font.txt"), encoding="utf-8"):
    _l = _l.rstrip()
    if not _l.strip() or _l.startswith("#"):
        continue
    _c, _ch = _l.split("\t")
    STATIC[int(_c, 16)] = _ch

PUNCT = {0x5A: "!", 0x5B: "?", 0x5C: "-", 0x5D: "·"}
for _i in range(10):
    PUNCT[_i] = "0123456789"[_i]


def dec(b):
    o, i = [], 0
    while i < len(b):
        c = b[i]; i += 1
        if c == 0xBD and i < len(b):
            o.append("{%d}" % b[i]); i += 1
        elif c == 0x59:
            o.append("_")
        elif c in STATIC:
            o.append(STATIC[c])
        elif c in PUNCT:
            o.append(PUNCT[c])
        elif 0x9A <= c <= 0xB3:
            o.append(chr(ord("A") + c - 0x9A))
        elif 0xD0 <= c <= 0xDF:
            o.append(" " * (c - 0xD0))
        elif c >= 0xE0:
            o.append("<%02X>" % c)
        else:
            k = KANA.CH.get(c)
            o.append(k if k else "<%02X>" % c)
    return "".join(o)
