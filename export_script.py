#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MT1 대사 스크립트를 **번역용 텍스트 파일**로 뽑는다. (안 A 1단계)

사용: python export_script.py [롬] [출력파일]
기본: mt1_m191_v3.nes -> script_jp.txt

## 제어코드 (뱅크$05 `$AF24` 디스패치를 역어셈블해 확정)
코드 뒤에 **파라미터 바이트**가 붙는 것이 있다. 이걸 모르면 파라미터를 글자로 오독한다.

| 코드 | 파라미터 | 핸들러 |
|---|---|---|
| `$C0` | 0 | `$AF82` (카운터 증가 후 계속) |
| `$F0` | 1 | `$AFEF` |
| `$F1` | 0 | `$AFF8` |
| `$F2` | 1 | `$B004` (`$068F` 에 더함) |
| `$F3` `$F4` `$FC` | 2 | `$AFC7` |
| `$F5` `$F6` `$F7` `$F8` | 2 | `$B017` |
| `$F9` | 0 | `$AFE6` (주인공 이름 삽입으로 보임 - `<F9>は` 형태로 자주 나옴) |
| `$FA` | 0 | `$AFD4` |
| `$FB` | 1 | `$AFBE` (메시지 끝) |

`$C0` 이상이면서 제어코드가 아닌 값은 **UI 타일 번호 그대로**다(공백·괘선 등).
번역할 때 **손대면 안 되는 것**: `<..>` 로 표시된 모든 태그.
"""
import sys
from collections import defaultdict

ROM = sys.argv[1] if len(sys.argv) > 1 else "mt1_m191_v3.nes"
OUT = sys.argv[2] if len(sys.argv) > 2 else "script_jp.txt"

# 파라미터 개수는 핸들러의 `INC $0658` 횟수로 읽고, **메시지 주소 인접 검산으로 확정**했다.
# ($FB 은 핸들러가 다음 바이트를 읽지만 인덱스를 진행시키지 않는다 -> 파라미터 0개.
#  1개로 가정하면 인접 맞물림이 233 -> 19 로 무너진다)
PARAMS = {0xC0: 0, 0xF0: 0, 0xF1: 0, 0xF2: 1, 0xF3: 2, 0xF4: 2,
          0xF5: 2, 0xF6: 2, 0xF7: 2, 0xF8: 2, 0xF9: 0, 0xFA: 0,
          0xFB: 0, 0xFC: 2}
END = {0xFB}

# 문자표 (font_sheet.png 로 타일을 직접 렌더해 확정한 것)
CH = {}
for i in range(10):
    CH[i] = "0123456789"[i]
for i, c in enumerate("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"):
    CH[0x24 + i] = c
for i, c in enumerate("ャュョッァィゥェォ"):
    CH[0x52 + i] = c
CH[0x58] = "゛"; CH[0x59] = "゜"; CH[0x5A] = "!"; CH[0x5B] = "?"
CH[0x5C] = "ー"; CH[0x5D] = "・"
for i, c in enumerate("あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"):
    CH[0x64 + i] = c
for i, c in enumerate("ぁぃゃゅょっ"):
    CH[0x92 + i] = c
CH[0x98] = "゛"; CH[0x99] = "゜"
for i in range(26):
    CH[0x9A + i] = chr(ord('A') + i)

d = open(ROM, "rb").read()
prg = d[16:16 + d[4] * 16384]
B4, B5 = 0x04 * 0x2000, 0x05 * 0x2000


def phys(a):
    if 0x8000 <= a < 0xA000:
        return B4 + (a - 0x8000)
    if 0xA000 <= a < 0xC000:
        return B5 + (a - 0xA000)
    return None


def rd16(p):
    return prg[p] | (prg[p + 1] << 8)


# ---------------------------------------------------------------- 포인터 훑기
# 표 길이를 "포인터처럼 보일 때까지" 로 잡으면 안 된다(이 프로젝트가 반복해서 당한 실수).
# 1차표의 **첫 포인터가 곧 표의 끝**이다: $8004 의 첫 값이 $8042 이므로 31엔트리.
# 그룹표들은 연속이므로 그룹 g 의 길이 = groups[g+1] - groups[g].
TBL = 0x8004
first0 = rd16(phys(TBL))
NG = (first0 - TBL) // 2
groups = [rd16(phys(TBL + i * 2)) for i in range(NG)]
assert all(0x8000 <= g < 0xC000 for g in groups), "1차표 포인터 범위 이상"

refs = defaultdict(list)          # 문자열 주소 -> [(그룹,번호)]
order = []
for gi, ga in enumerate(groups):
    if gi + 1 < len(groups):
        ge = groups[gi + 1]
    else:                          # 마지막 그룹은 포인터처럼 보이는 동안
        p, cnt = phys(ga), 0
        while cnt <= 256 and 0x8000 <= rd16(p) < 0xC000:
            p += 2; cnt += 1
        ge = ga + cnt * 2
    n = (ge - ga) // 2
    if n <= 0 or n > 256:
        continue
    for mi in range(n):
        ma = rd16(phys(ga + mi * 2))
        if phys(ma) is None:
            continue
        if ma not in refs:
            order.append(ma)
        refs[ma].append((gi, mi))


def parse(addr):
    """문자열 -> [('t',코드) | ('c',코드,[파라미터])]. 파라미터를 글자로 오독하지 않는다."""
    p = phys(addr)
    out = []
    i = 0
    while i < 512 and p + i < len(prg):
        b = prg[p + i]
        if b in PARAMS:
            np = PARAMS[b]
            out.append(("c", b, list(prg[p + i + 1:p + i + 1 + np])))
            i += 1 + np
            if b in END:
                break
        else:
            out.append(("t", b, []))
            i += 1
    return out, i


def render(toks):
    s = []
    for kind, b, par in toks:
        if kind == "c":
            s.append("<%02X%s>" % (b, "".join(" %02X" % x for x in par)))
        elif b in CH:
            s.append(CH[b])
        else:
            s.append("<%02X>" % b)          # UI 타일 등
    return "".join(s)


def glyph_codes(toks):
    """슬롯이 필요한 코드 = 제어코드도 UI타일($C0 이상)도 아닌 것"""
    return [b for k, b, _ in toks if k == "t" and b < 0xC0]


WIN = 88
lines = []
lines.append("# MT1 대사 스크립트 (원문)  롬: %s" % ROM)
lines.append("# 메시지 %d개 / 그룹 %d개" % (len(order), len(groups)))
lines.append("#")
lines.append("# 형식:  @주소 [그룹:번호 ...]")
lines.append("#        JP: 원문")
lines.append("#        KO: (여기에 번역을 쓰세요. 비어 있으면 미번역)")
lines.append("#")
lines.append("# <..> 는 제어코드/UI타일입니다. **순서와 개수를 그대로 유지**하세요.")
lines.append("#   <F9> = 주인공 이름 삽입,  <FB xx> = 메시지 끝,  <FC xx xx> = 다음 페이지")
lines.append("#   그 밖의 <xx> 는 아직 의미 미확정이니 손대지 마세요.")
lines.append("# 띄어쓰기: 원문의 <D1> 은 작은 점 모양의 일본어 단어 구분자입니다.")
lines.append("#          한글 번역문에서는 <D1> 대신 **그냥 공백**을 쓰세요(진짜 빈칸 $FF 로 들어갑니다).")
lines.append("# 제약: 한 화면(22열x4줄=88칸)에 **서로 다른 글자 63자 이하**")
lines.append("#       (원문 최대치는 46자였으므로 여유 있음. 초과하면 삽입 도구가 거부합니다)")
lines.append("")

# ---------------------------------------------------------------- 꼬리 공유 탐지
# 원본은 어떤 메시지의 **뒷부분을 그대로 다른 메시지로 재사용**한다(89건).
# 이걸 모르고 따로 번역해 넣으면 서로를 덮어쓴다.
spans = {}
for ma in order:
    toks, ln = parse(ma)
    spans[ma] = (ma, ma + ln, toks)
inside = {}
for a in order:
    for b in order:
        if b != a and spans[b][0] < a < spans[b][1]:
            inside[a] = b
            break

stat = []
for ma in order:
    _, _, toks = spans[ma]
    g = glyph_codes(toks)
    stat.append(len(set(g[:WIN])) if g else 0)
    tag = " ".join("%d:%d" % t for t in refs[ma][:6])
    if len(refs[ma]) > 6:
        tag += " +%d" % (len(refs[ma]) - 6)
    note = ""
    if ma in inside:
        note = "  ※꼬리공유: @%04X 의 뒷부분. 그쪽과 함께 번역해야 함" % inside[ma]
    lines.append("@%04X [%s]%s" % (ma, tag, note))
    lines.append("JP: " + render(toks))
    lines.append("KO: ")
    lines.append("")

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
stat.sort()
print("%s 로 저장" % OUT)
print("  메시지 %d개 (중복 주소 통합 전 참조 %d건), 그룹 %d개"
      % (len(order), sum(len(v) for v in refs.values()), len(groups)))
print("  파일 %d줄" % len(lines))
if stat:
    print("  화면당 고유 글자수: 중앙 %d / 최대 %d  (슬롯 63칸 대비 여유 %d)"
          % (stat[len(stat) // 2], stat[-1], 63 - stat[-1]))
