#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI 이스케이프 훅 검사: 롬의 UI 문자열을 버퍼에 올리고 $6C00 을 돌려
   $BD <id> 가 슬롯 타일로 압축 치환되는지, 결과가 의도한 한글인지 본다."""
import re
import sys, io
sys.argv = [sys.argv[0]]
from nesboot import verify
import build_step5b as B

# UI 훅이 꺼진 판에는 $6C00 이 아예 없다 (부팅복사 12페이지). 검사할 것이 없다.
if not B.UI_HOOK:
    print("UI 훅 꺼진 빌드 — 검사 건너뜀 (MT1_UIHOOK=1 로 빌드해야 의미가 있다)")
    raise SystemExit(0)

STATIC = {}
for l in io.open("static_font.txt", encoding="utf-8"):
    l = l.rstrip()
    if l.strip() and not l.startswith("#"):
        c, ch = l.split(chr(9)); STATIC[int(c, 16)] = ch
RET = 0x0300
n = verify(B.OUT, frames=600, verbose=False)
rom = open(B.OUT, "rb").read()

def render(cnt):
    o = ""
    for i in range(cnt):
        c = n.ram[0x0590 + i]
        # ★2026-09-07 $FE/$FB 에서도 멈춘다. 실제 렌더러($C13E)가 그러기 때문이다.
        #   안 멈추면 `<FE>` 로 끝나는 항목이 전부 거짓 실패로 뜬다(텔레포트 메뉴 등 5건).
        if c in (0xFF, 0xFE, 0xFB): break
        if c in B.TILES:
            k = B.TILES.index(c)
            g = n.prgram[B.RESIDL - 0x6000 + k] | (n.prgram[B.RESIDH - 0x6000 + k] << 8)
            o += B.glob[g] if g < len(B.glob) else "?%d" % g
        elif c in STATIC: o += STATIC[c]
        elif c == B.BLANK: o += ""
        elif 0xD0 <= c < 0xE0: o += " " * (c & 0xF)
        elif c < 0x0A: o += "0123456789"[c]
        elif c in (0x5A, 0x5B, 0x5C, 0x5D): o += "!?-·"[c - 0x5A]
        else: o += "<%02X>" % c
    return o

ent = []
for l in io.open("ui_ko.txt", encoding="utf-8"):
    l = l.rstrip()
    if not l.strip() or l.startswith("#"): continue
    a, ln, k = l.split(chr(9)); ent.append((int(a, 16), int(ln), k))

bad, maxuse = 0, 0
for off, ln, ko in ent:
    # ★2026-09-07 **문자열마다** 슬롯 색인을 되돌린다. 예전엔 루프 밖에서 한 번만 0으로
    #   두어 255개를 28칸에 연달아 밀어 넣었고, 풀이 감기면 앞 문자열의 타일이 뒤 글자로
    #   되읽혀 거짓 실패가 났다(「마즈르카」가 「마간르카」로 보였다).
    #   실기 메시지 훅도 창이 열릴 때마다 NEXT 를 0 으로 되돌리므로 이쪽이 실제와 맞다.
    #   문자열 사이 슬롯 압박은 **압박시험**이 따로 잰다.
    n.prgram[B.NEXT - 0x6000] = 0
    n.ram[0x14] = 4
    for i in range(64): n.ram[0x0590 + i] = 0xFF
    for i in range(ln): n.ram[0x0590 + i] = rom[off + i]
    n.push(((RET - 1) >> 8) & 0xFF); n.push((RET - 1) & 0xFF)
    n.pc = B.UIHOOK
    for _ in range(300000):
        if n.pc == RET: break
        n.step()
    else:
        print("  $%05X 훅이 안 끝남" % off); bad += 1; continue
    got = render(ln).rstrip()
    # ★끝에 붙인 종결자(`<FF>` 등)는 훅도 렌더러도 거기서 멈추는 게 **정상**이다.
    #   기대값에서도 떼고 비교한다 (안 떼면 `나카지마<FF>` 같은 항목이 거짓 실패를 낸다).
    # ★<59>(BLANK)는 **눈에 안 보이는 채움 타일**이다. 겹치는 진입점 때문에 꼬리 제어코드를
    #   구간 끝에 붙이려고 본문 뒤에 끼워 넣는데, 롬 디코더는 이걸 빈 문자로 읽으므로
    #   기대값에서도 빼야 한다(2026-09-03).
    # <Dn> 은 "빈 칸 n개" 제어코드다. 롬 디코더는 공백으로 펴서 읽으므로 기대값도 편다.
    want = re.sub(r"<D([0-9A-Fa-f])>", lambda m: " " * int(m.group(1), 16),
                  ko.rstrip().replace("<59>", ""))
    for _t in ("<FF>", "<FE>", "<FB>"):
        if want.endswith(_t): want = want[:-4]; break
    # 롬 디코더는 끝의 빈 칸을 버린다 - 양쪽 다 잘라서 비교
    maxuse = max(maxuse, n.prgram[B.NEXT - 0x6000])
    if got.rstrip() != want.rstrip():
        bad += 1
        if bad <= 8: print("  $%05X\n    나온것 「%s」\n    기대값 「%s」" % (off, got, want))
print("\nUI 문자열 %d개 검사: 어긋남 %d건" % (len(ent), bad))
print("대사 풀 최대 사용 %d칸 / %d칸 (문자열 하나 기준)" % (maxuse, B.NDLG))
# ★어긋나면 종료코드로 알린다. 없으면 make.py 가 "통과"로 세어 버린다(v14 에서 발각).
sys.exit(1 if bad else 0)
