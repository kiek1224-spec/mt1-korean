#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ui_ko.txt 의 제자리 치환 구간이 **코드가 절대주소로 참조하는 자리**를 덮는지 본다.

발견 경위: 첫 줄 `06EB2` 가 텍스트가 아니라 16비트 포인터 `$810E` 의 상위 바이트였다.
`$ABD9 LDA $AEA2` 가 그걸 읽어 `$C0/$C1` 포인터를 만들고, 그 포인터로 읽은 값을
`$AE12 STA $0216,Y` 로 **OAM 에 써서** 스프라이트가 깨졌다.
'텍스트처럼 보이는 바이트'는 증거가 못 된다 - $81 은 가나 「ほ」로 디코드된다.
"""
import io, sys
from mt1dis import OPS, SZ, ABS, ABX, ABY, Dis

ROM = sys.argv[1] if len(sys.argv) > 1 else "mt1_m191_v3.nes"
d = open(ROM, "rb").read()
prg = d[16:16 + d[4] * 16384]
# ★인덱스 없는 절대주소만 본다.
#   `LDA $xxxx,Y` 같은 인덱스 접근은 문자열을 한 글자씩 읽는 **정상 동작**이다.
#   위험한 것은 `LDA $xxxx` 처럼 **한 바이트를 값으로 읽는** 것 - 그게 포인터/플래그다.
ABSOPS = {op for op, (nm, md) in OPS.items() if md == ABS}
# ★참조 지점이 진짜 명령 시작인지 역어셈블러로 확인한다 (데이터 속 우연 제거)
_d = Dis(ROM); _d.load_bank_tables()
_base = _d.fixed_hi * 0x2000
_v = lambda o: _d.prg[_base + o] | (_d.prg[_base + o + 1] << 8)
_ent = [(_v(0x1FFC), 0, 1, ()), (_v(0x1FFA), 0, 1, ()), (0x8000, 0x0E, 1, ())]
if _v(0x1FFE) != 0xFFFF: _ent.append((_v(0x1FFE), 0, 1, ()))
_d.run(_ent)
CODE = _d.code
print("역어셈블 커버리지 %.1f%%" % (100 * sum(1 for x in CODE if x) / len(CODE)))

# 빌더가 남긴 **제자리 치환 구간 전체**(UI 문자열 + 라벨 + 패널)를 검사한다.
SRCLIST = "작업롬파일/patched_ranges.txt"
ent = []
for l in io.open(SRCLIST, encoding="utf-8"):
    l = l.rstrip()
    if not l.strip() or l.startswith("#"): continue
    a, c, t, k = l.split(chr(9))
    ent.append((int(a, 16), int(c), "%s %s" % (t, k)))

# 절대주소 참조를 전부 수집: (뱅크, 참조주소) -> 참조한 곳
refs = {}
for i in range(len(prg) - 2):
    op = prg[i]
    if op not in ABSOPS: continue
    tgt = prg[i + 1] | (prg[i + 2] << 8)
    if tgt < 0x8000: continue
    refs.setdefault(tgt, []).append(i)

bad = 0
print("%s 의 %d개 구간을 절대주소 참조와 대조 (%s)" % (SRCLIST, len(ent), ROM))
for a, c, k in ent:
    off = a - 16
    bank, boff = off // 0x2000, off % 0x2000
    # ★같은 뱅크 + 같은 창에서 참조하는 것만 센다.
    #   다른 뱅크에서 나온 3바이트 일치는 거의 전부 데이터 속 우연이다(90/100 오탐).
    #   진짜 버그($AEA2)는 뱅크$03 의 코드가 뱅크$03 의 자기 데이터를 부른 형태였다.
    # ★MMC3 의 마지막 두 뱅크는 **고정 창** $C000/$E000 이다. $8000/$A000 으로만 보면
    #   뱅크$1E/$1F 의 진짜 참조를 놓치고, 엉뚱한 자리를 짚어 오탐도 난다
    #   (2026-09-03: 뱅크$1F 의 텍스트를 `JSR $BA1B` 가 부른다고 잘못 잡았다 -
    #    그 JSR 은 $C864 로 뱅크를 바꾼 뒤의 다른 뱅크를 부르는 것이었다).
    nb = len(prg) // 0x2000
    # ★2026-09-13 고정 뱅크는 **창이 하나씩**이다: 끝에서 두 번째 = $C000, 마지막 = $E000.
    #   예전엔 둘 다에 $C000·$E000 을 모두 대 봐서, 뱅크$1F 의 엘리베이터 문자열($FC83)을 $DC83 으로도
    #   계산했고, 거기서 **뱅크$1E 를 부르는** `JSR $DC85` 와 우연히 겹쳐 오탐이 났다.
    #   진짜 참조는 코드에서 확인했다: 뱅크$1F 의 `LDA $FC83,X` 두 곳. 창을 좁혀도 진짜 참조는 그대로 잡힌다.
    wins = ((0xC000,) if bank == nb - 2 else (0xE000,) if bank == nb - 1 else (0x8000, 0xA000))
    hits = []
    for win in wins:
        for t in range(win + boff, win + boff + c):
            for src in refs.get(t, []):
                if src // 0x2000 != bank: continue
                if CODE[src] != 1: continue          # 명령 시작이 아니면 데이터 속 우연
                hits.append((t, src, win))
    if hits:
        bad += 1
        print("  ★파일$%05X 뱅크$%02X +%d  '%s'" % (a, bank, c, k))
        for t, src, win in hits[:6]:
            print("      $%04X 를 같은뱅크 $%04X 가 참조 (%s)"
                  % (t, win + (src % 0x2000),
                     " ".join("%02X" % x for x in prg[src:src + 3])))
print()
print("의심 구간 %d개 / %d개" % (bad, len(ent)))
sys.exit(1 if bad else 0)
