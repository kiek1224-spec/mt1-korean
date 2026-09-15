#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""꼬리 진입점 89개를 **실제로 훅에 태워** 나오는 텍스트를 확인한다.
   꼬리는 머리 문장 중간을 가리키는 별도 진입점이라, 오프셋이 어긋나면 말이 중간부터 잘린다."""
import sys, io
sys.argv = [sys.argv[0]]
from nesboot import verify
import build_step5b as B

STATIC = {}
for l in io.open("static_font.txt", encoding="utf-8"):
    l = l.rstrip()
    if l.strip() and not l.startswith("#"):
        c, ch = l.split(chr(9)); STATIC[int(c, 16)] = ch
RET = 0x0300
n = verify(B.OUT, frames=600, verbose=False)
enc_of = {a: e for a, e, _ in B.records}
ids_of = {a: i for a, _, i in B.records}

# ★제어코드의 파라미터는 **글자가 아니다**. <F8 01 11 31> 의 31 은 메시지 id 인데,
#   정적 폰트를 줄여 $24~$7F 가 슬롯이 되자 두 렌더러가 이걸 서로 다르게 그려
#   멀쩡한 꼬리 31개가 어긋남으로 잡혔다(2026-09-03). 둘 다 PARAMS 로 건너뛴다.
def _walk(seq):
    """(바이트, 그려지는가) 를 순서대로"""
    i = 0
    while i < len(seq):
        c = seq[i]
        if c in B.PARAMS:
            for j in range(1 + B.PARAMS[c]):
                if i + j < len(seq): yield seq[i + j], False
            i += 1 + B.PARAMS[c]
            if c == 0xFB: return
        elif c >= 0xD0:
            yield c, False; i += 1
        else:
            yield c, True; i += 1


def render_enc(seq, ids):
    """인코딩(로컬 색인 $80+k)을 한글로"""
    o = ""
    for c, drawn in _walk(seq):
        if not drawn:
            if c == 0xFB: break
            o += " " * (c & 0xF) if 0xD0 <= c < 0xE0 else "<%02X>" % c
            continue
        if B.TILE0 <= c < B.TILE0 + B.LOCALMAX:
            k = c - B.TILE0
            o += B.glob[ids[k]] if k < len(ids) else "?"
        elif c in STATIC: o += STATIC[c]
        elif c < 0x0A: o += "0123456789"[c]
        elif c in (0x5A, 0x5B, 0x5C, 0x5D): o += "!?-·"[c - 0x5A]
        else: o += "<%02X>" % c
    return o

def render(seq, slots):
    o = ""
    for c, drawn in _walk(seq):
        if not drawn:
            if c == 0xFB: break
            o += " " * (c & 0xF) if 0xD0 <= c < 0xE0 else "<%02X>" % c
            continue
        if c in B.TILES:
            g = slots[B.TILES.index(c)]
            o += B.glob[g] if g < len(B.glob) else "?"
        elif c in STATIC: o += STATIC[c]
        elif c < 0x0A: o += "0123456789"[c]
        elif c in (0x5A, 0x5B, 0x5C, 0x5D): o += "!?-·"[c - 0x5A]
        else: o += "<%02X>" % c
    return o

def run(addr):
    n.ram[0x14] = 4          # 뱅크셋4 = R6:$04 / R7:$05 ($C8D5 가 이걸로 복원한다)
    n.r[6], n.r[7] = 0x04, 0x05; n.map_prg()
    n.ram[0xBE] = addr & 0xFF; n.ram[0xBF] = addr >> 8
    n.ram[0x0651] = 0x11
    n.prgram[B.NEXT - 0x6000] = 0
    n.prgram[B.LASTROW - 0x6000] = 0xFF
    n.push(((RET - 1) >> 8) & 0xFF); n.push((RET - 1) & 0xFF)
    n.pc = B.HOOK
    for _ in range(400000):
        if n.pc == RET: break
        n.step()
    else: return None
    slots = [n.prgram[B.RESIDL - 0x6000 + k] | (n.prgram[B.RESIDH - 0x6000 + k] << 8)
             for k in range(B.NSLOT)]
    txt = [n.ram[0x6700 - 0x6000 + i] if False else n.prgram[B.TEXT - 0x6000 + i] for i in range(200)]
    return render(txt, slots)

# 기대값: 머리 인코딩을 올바른 오프셋부터 자른 것
def expect(t, hd):
    e = enc_of[hd]
    look = B.look
    for i in range(0, len(look), B.ENTSZ):
        if look[i] | (look[i+1] << 8) == t:
            d = look[i+7]
            if d > 127: d -= 256
            off = (t - hd) + d
            return e[off:]
    return None

bad = 0
for t, hd in sorted(B.head_of.items()):
    if hd not in enc_of: continue
    got = run(t)
    exp = expect(t, hd)
    if got is None: print("  @%04X 훅이 안 끝남" % t); bad += 1; continue
    want = render_enc(exp, ids_of[hd])
    if got != want:
        bad += 1
        if bad <= 6: print("  @%04X(머리 @%04X)\n    나온것 %s\n    기대값 %s" % (t, hd, got[:40], want[:40]))
print("\n꼬리 %d개 검사: 어긋남 %d건" % (sum(1 for t, h in B.head_of.items() if h in enc_of), bad))
# 머리도 회귀 확인
hb = 0
for a, e, _ in B.records[:40]:
    got = run(a)
    if got != render_enc(e, ids_of[a]): hb += 1
print("머리 40개 회귀: 어긋남 %d건" % hb)

# ---------------------------------------------------------------- 원문 대조
# ★위의 검사는 **우리가 계산한 보정값을 우리가 기대값으로** 쓴다. 배관만 보는 셈이라
#   보정값 자체가 틀려도 통과한다(2026-09-03: $Dn 을 제어코드로 세어 꼬리가 한 코드씩
#   앞서 잡히던 버그를 못 잡았다). 그래서 **원문 쪽 제어코드 열**과 맞춰 본다.
#   꼬리부터 끝까지의 제어코드 열은 번역해도 1:1 보존되므로($Dn 만 예외) 완전히 같아야 한다.
def ctrlseq(get, n):
    out, j = [], 0
    while j < n:
        c = get(j)
        if 0xD0 <= c < 0xE0: j += 1                 # 여백은 번역하며 바뀐다 - 뺀다
        elif c in B.PARAMS:
            k = B.PARAMS[c]; out.append(tuple(get(j + x) for x in range(1 + k))); j += 1 + k
            if c == 0xFB: break
        elif c >= 0xE0: out.append((c,)); j += 1
        else: j += 1
    return out

cb = 0
for t, hd in sorted(B.head_of.items()):
    if hd not in enc_of: continue
    e = enc_of[hd]; off = t - hd; q = B.phys(hd)
    d = None
    for i in range(0, len(B.look), B.ENTSZ):
        if B.look[i] | (B.look[i + 1] << 8) == t:
            d = B.look[i + 7] - (256 if B.look[i + 7] > 127 else 0); break
    jp = ctrlseq(lambda j: B._orig[q + off + j], B.spans[hd][1] - t)
    ko = ctrlseq(lambda j: e[off + d + j], len(e) - off - d)
    if jp != ko:
        cb += 1
        if cb <= 6:
            print("  @%04X(머리 @%04X, 보정 %+d) 제어열 불일치" % (t, hd, d))
            print("    원문 %s" % " ".join("".join("%02X" % y for y in x) for x in jp[:7]))
            print("    한글 %s" % " ".join("".join("%02X" % y for y in x) for x in ko[:7]))
print("꼬리 원문 제어열 대조: 어긋남 %d건" % cb)
# ★어긋나면 종료코드로 알린다. 없으면 make.py 가 "통과"로 세어 버린다(2026-09-03 발각).
sys.exit(1 if (bad + hb + cb) else 0)
