#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mesen 위치를 **한 곳에서** 푼다.

★왜 있는가 (2026-09-12): 스크립트 8곳에 Mesen 경로가 절대경로로 박혀 있었다.
  사용자가 PC 를 포맷하고 폴더를 옮기자 `make.py` 의 검사 9종과 락스텝이 통째로 멈췄다.
  경로는 **여기서만** 정하고 나머지는 이걸 import 한다. 다시는 박아 넣지 말 것.

찾는 순서:
  1. 환경변수 `MESEN_DIR` (강제 지정 - 다른 PC 나 임시 경로에 쓴다)
  2. 작업폴더의 **형제 폴더** `../Mesen_2.2.1_Windows`   <- 지금 쓰는 배치
  3. 알려진 옛 경로들 (혹시 되살아나면)
찾으면 `MESEN_DIR` / `MESEN_EXE` / `SAVEDIR` 를 채우고, 못 찾으면 그 자리에서 죽는다
(조용히 빈 경로로 진행하면 "Mesen 이 안 뜬다" 를 한참 쫓게 된다).
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDS = [
    os.environ.get("MESEN_DIR"),
    os.path.join(os.path.dirname(_HERE), "Mesen_2.2.1_Windows"),
    os.path.expanduser(r"~\OneDrive\Desktop\작업\Mesen_2.2.1_Windows"),
    os.path.expanduser(r"~\OneDrive\Desktop\새 폴더 (3)\Mesen_2.2.1_Windows"),
]

MESEN_DIR = None
for _c in _CANDS:
    if _c and os.path.isfile(os.path.join(_c, "Mesen.exe")):
        MESEN_DIR = os.path.abspath(_c)
        break
if MESEN_DIR is None:
    raise SystemExit(
        "★Mesen 을 못 찾았다. 찾아본 곳:\n  " +
        "\n  ".join(str(c) for c in _CANDS if c) +
        "\n-> 환경변수 MESEN_DIR 로 Mesen.exe 가 있는 폴더를 지정할 것.")

MESEN_EXE = os.path.join(MESEN_DIR, "Mesen.exe")
SAVEDIR = os.path.join(MESEN_DIR, "SaveStates")


def save(name):
    """세이브스테이트 파일의 전체 경로. 없으면 **바로** 알려준다."""
    p = os.path.join(SAVEDIR, name)
    if not os.path.isfile(p):
        raise SystemExit("★세이브스테이트가 없다: %s\n   (폴더: %s)" % (name, SAVEDIR))
    return p


if __name__ == "__main__":
    print("MESEN_DIR =", MESEN_DIR)
    print("MESEN_EXE =", MESEN_EXE)
    print("SAVEDIR   =", SAVEDIR,
          "(%d개 .mss)" % len([f for f in os.listdir(SAVEDIR) if f.endswith(".mss")]))
