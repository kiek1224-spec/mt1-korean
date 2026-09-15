#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이름 풀 압박: 한 화면에 여러 이름이 동시에 떠 있을 때 서로를 밀어내는지 본다.
   밀려나면 실기에서 '떠 있는 글자가 다른 글자로 변한다'."""
import sys, os, random
os.environ["MT1_STATIC"] = "1"; sys.argv = [sys.argv[0]]
from nesboot import verify
import build_step5b as B
RET = 0x0300
REV = {c: ch for ch, c in B.STATIC.items()}
for ch, c in B.PUNCT.items(): REV.setdefault(c, ch)
REV[B.BLANK] = ""
def render(n, codes):
    o = ""
    for c in codes:
        if c == 0xFF: break
        if c in B.TILES:
            k = B.TILES.index(c); j = k - B.NDLG
            g = (n.prgram[B.NRESL-0x6000+j] | (n.prgram[B.NRESH-0x6000+j] << 8)) if k >= B.NDLG \
                else (n.prgram[B.RESIDL-0x6000+k] | (n.prgram[B.RESIDH-0x6000+k] << 8))
            o += B.glob[g] if g < len(B.glob) else "?"
        else: o += REV.get(c, "<%02X>" % c)
    return o
ko = {}
for l in open("names_ko.txt", encoding="utf-8"):
    l = l.rstrip()
    if l.strip() and not l.startswith("#"):
        k, v = l.split(chr(9)); ko[k] = v
n = verify(B.OUT, frames=600, verbose=False)
SPEC = {1: (12, 0x0C, 0x0D), 3: (10, 0x0A, 0x0B), 4: (1, 0x01, 0x01)}
def screen(items):
    """items = [(모드, 태그, 색인)] 을 차례로 배정하고, 전부 끝난 뒤 다시 읽어 확인"""
    n.prgram[B.NNEXT-0x6000] = 0; n.prgram[B.NCNT-0x6000] = 0
    for k in range(0x0500, 0x0600): n.ram[k] = 0
    spots = []
    for pos, (mode, tag, i) in enumerate(items):
        bset, r6, r7 = SPEC[mode]
        n.ram[0x14] = bset; n.r[6], n.r[7] = r6, r7; n.map_prg()
        n.prgram[B.NMODE-0x6000] = mode
        n.ram[0x0480] = 1; n.ram[0x0481] = 0
        n.a = i; n.x = 0
        n.push(0x02); n.push(0xFF); n.pc = B.NHOOK
        for _ in range(200000):
            if n.pc == RET: break
            n.step()
        w = n.a if mode == 4 else ({3: 6}.get(mode, 8))   # 모드4 는 반환값이 쓴 칸수
        spots.append(([n.ram[0x0588 + k] for k in range(w)], tag, i, w))
        # 다음 이름은 다른 자리에 그린 셈 치고 버퍼만 옮겨 보관
    return spots
random.seed(11)
def trial(mix):
    items = []
    for mode, tag, cnt, k in mix:
        for i in random.sample(range(cnt), k): items.append((mode, tag, i))
    spots = screen(items)
    bad = 0
    for codes, tag, i, w in spots:
        cap = None if w == 12 else w        # 모드4 는 제한 없음
        want = ko["%s%d" % (tag, i)]
        if render(n, codes) != (want[:cap] if cap else want): bad += 1
    return bad, n.prgram[B.NCNT-0x6000]
for name, mix, rounds in (
        ("악마8", [(1,"A",147,8)], 400),
        ("악마8+종족8", [(1,"A",147,8),(1,"A",167,0)], 1),
        ("아이템8(목록만)", [(4,"B",64,8)], 400),
        ("아이템6+마법4", [(4,"B",64,6),(3,"C",36,4)], 400),
        ("악마8 + 아이템6", [(1,"A",147,8),(4,"B",64,6)], 400),
        # ★실제 게임에서 가능한 조합은 여기까지다. 아이템 목록과 마법 목록은 **다른 메뉴**라
        #   한 화면에 같이 뜨지 않는다. 아래 셋째 줄은 일부러 넘기는 합성 최악값이다.
        ("악마8 + 마법4", [(1,"A",147,8),(3,"C",36,4)], 400),
        ("악마8 + 아이템8", [(1,"A",147,8),(4,"B",64,8)], 400),
        ("[합성최악] 악마8+아이템6+마법4", [(1,"A",147,8),(4,"B",64,6),(3,"C",36,4)], 400)):
    worst = 0; bad = 0
    for _ in range(rounds):
        b, u = trial(mix); bad += b; worst = max(worst, u)
    print("%-24s %3d회: 최대 이름슬롯 %2d / %d칸, 어긋남 %d건" % (name, rounds, worst, B.NNSLOT, bad))
# 종족은 정적 폰트라 슬롯을 안 쓴다 - 따로 확인
r = screen([(1,"A",i) for i in range(147,167)])
print("종족 20개 전부: 이름슬롯 %d칸 사용 (0이면 전부 정적 ✔)" % n.prgram[B.NCNT-0x6000])
