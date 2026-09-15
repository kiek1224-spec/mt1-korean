#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
헤드리스로 게임을 **실제로 조작**해서 화면을 뽑는다.

이게 없어서 지금까지 대사 화면 문제를 매번 사용자 실기에 의존해 발견했다
(여러 메시지가 한 화면에 겹치는 슬롯 충돌 같은 건 부팅만으로는 절대 안 보인다).

사용 예:
    from play import Runner
    r = Runner("mt1_kor5b.nes")
    r.frames(300)              # 타이틀까지
    r.press("start", 4); r.frames(60)
    r.shot("title.png")
"""
from nesboot import NES, CPF, SPR0_AT, VBL_AT
import screendump

BTN = {"a": 0, "b": 1, "select": 2, "start": 3,
       "up": 4, "down": 5, "left": 6, "right": 7}


class Runner:
    def __init__(s, rom):
        s.n = NES(rom)
        s.fstart = 0
        s.spr0 = s.vbl = False
        s.ins = 0

    def frames(s, k):
        n = s.n
        target = n.nmi_count + k
        guard = 0
        while n.nmi_count < target:
            pos = n.cyc - s.fstart
            if pos >= CPF:
                s.fstart += CPF
                s.spr0 = s.vbl = False
                n.ppustatus &= 0x3F
            elif not s.spr0 and pos >= SPR0_AT:
                n.ppustatus |= 0x40
                s.spr0 = True
            elif not s.vbl and pos >= VBL_AT:
                n.ppustatus |= 0x80
                s.vbl = True
                if n.ppuctrl & 0x80:
                    n.nmi()
            n.step()
            s.ins += 1
            guard += 1
            if guard > 30_000_000:
                raise RuntimeError("프레임이 진행되지 않음 (교착 의심)")
        return s

    def hold(s, *names):
        m = 0
        for x in names:
            m |= 1 << BTN[x]
        s.n.pad = m
        return s

    def press(s, name, dur=4, gap=6):
        """버튼을 dur 프레임 누르고 gap 프레임 뗀다 (게임이 눌림/뗌을 인식하도록)"""
        s.hold(name).frames(dur)
        s.hold().frames(gap)
        return s

    def shot(s, path, nt=0, scale=2):
        return screendump.dump(s.n, path, nt=nt, scale=scale)

    def tiles(s, rows=range(30), nt=0):
        return screendump.text(s.n, nt=nt, rows=rows)

    @property
    def info(s):
        n = s.n
        return ("프레임 %d  타일셋 $0D=%d $0E=%d  R2~R5=%s  $0B=%02X  $BE/$BF=$%02X%02X"
                % (n.nmi_count, n.ram[0x0D], n.ram[0x0E],
                   " ".join("$%02X" % x for x in n.r[2:6]),
                   n.ram[0x0B], n.ram[0x0BF], n.ram[0x0BE]))


if __name__ == "__main__":
    import sys
    rom = sys.argv[1] if len(sys.argv) > 1 else "mt1_kor5b.nes"
    r = Runner(rom)
    r.frames(240)
    print("부팅후 240f:", r.info)
    r.shot("shot_000.png")
    for i in range(1, 7):
        r.press("start", 6, 10)
        r.frames(60)
        r.shot("shot_%03d.png" % i)
        print("start x%d:" % i, r.info)
