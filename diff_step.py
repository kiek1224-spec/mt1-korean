#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""두 롬을 **명령 단위 락스텝**으로 돌려 처음 갈리는 지점을 찾는다."""
import sys
from play import Runner
from nesboot import CPF, SPR0_AT, VBL_AT
import mss

A = sys.argv[1] if len(sys.argv) > 1 else "작업롬파일/mt1_kor5b_v1_base.nes"
B = sys.argv[2] if len(sys.argv) > 2 else "작업롬파일/mt1_kor5b_v7_uistr_only.nes"
import mtpaths                                          # ★경로는 mtpaths 에서만 정한다
SAVE = mtpaths.save("mt1_kor5b_v1_base_1.mss")
ra, rb = Runner(A), Runner(B)
for r in (ra, rb):
    mss.load(r.n, SAVE, verbose=False)
    r.hold("up")


def tick(r):
    n = r.n
    pos = n.cyc - r.fstart
    if pos >= CPF:
        r.fstart += CPF; r.spr0 = r.vbl = False; n.ppustatus &= 0x3F
    elif not r.spr0 and pos >= SPR0_AT:
        n.ppustatus |= 0x40; r.spr0 = True
    elif not r.vbl and pos >= VBL_AT:
        n.ppustatus |= 0x80; r.vbl = True
        if n.ppuctrl & 0x80: n.nmi()
    n.step()


hist = []
for i in range(4_000_000):
    pa, pb = ra.n.pc, rb.n.pc
    if pa != pb:
        print("★%d번째 명령에서 PC 갈림: A=$%04X  B=$%04X" % (i, pa, pb))
        print("   직전 20개 PC:", " ".join("$%04X" % x for x in hist[-20:]))
        n = ra.n
        print("   A: 뱅크 $%02X/$%02X/$%02X/$%02X (R6=$%02X R7=$%02X) 프레임 %d"
              % (n.pb[0], n.pb[1], n.pb[2], n.pb[3], n.r[6], n.r[7], n.nmi_count))
        break
    if ra.n.a != rb.n.a or ra.n.x != rb.n.x or ra.n.y != rb.n.y:
        print("★%d번째 명령에서 레지스터 갈림 @ $%04X" % (i, pa))
        print("   A: A=%02X X=%02X Y=%02X   B: A=%02X X=%02X Y=%02X"
              % (ra.n.a, ra.n.x, ra.n.y, rb.n.a, rb.n.x, rb.n.y))
        print("   직전 24개 PC:", " ".join("$%04X" % x for x in hist[-24:]))
        n = ra.n
        print("   뱅크 $8000=$%02X $A000=$%02X  프레임 %d" % (n.pb[0], n.pb[1], n.nmi_count))
        break
    hist.append(pa)
    if len(hist) > 64: hist.pop(0)
    tick(ra); tick(rb)
else:
    print("갈림 없음")
