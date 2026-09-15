#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""제자리 치환한 문자열이 **제어코드 구성을 그대로 보존했는지** 본다.

## 전투 제어코드 (2026-09-03, 역어셈블로 확정)
    $Dn  빈칸 n개          ($C213 -> 하위니블만큼 빈칸)
    $En  **n 프레임 대기**  ($C202 -> $C2C6 -> `JSR $C5A1` x n)
         $C5A1 은 NMI 가 `$08` 을 `$FF` 로 세울 때까지 도는 **한 프레임 대기**다.
         전투 문장 끝의 `<EF><E8><FE>` = 15프레임 + 8프레임 뜸 들이고 종료 = **연출 타이밍**
    $FD  개행   $FE  종료   $FF  버튼 대기
    셋 다 **추가 바이트를 안 먹는다.** 영어판도 이 코드들을 그대로 두었다.

    글자 쪽: `$62` = 「。」(일본어 마침표). 영어판은 `$61` = `.` 로 바꿨다.

지우거나 순서를 바꾸면 전투 연출이 어긋나거나 문장이 안 끝난다.
"""
import io
import sys
sys.argv = [sys.argv[0]]
import build_step5b as B

src = open(B.SRC, "rb").read()
rom = open(B.OUT, "rb").read()

# 일부러 끝에 종결자를 붙인 항목은 예외로 둔다 (파티 이름표)
ALLOW_TAIL_TERM = {0x0B068, 0x0B070, 0x0B07A}
# ★2026-09-15 함정·워프 메시지 창 표(고정뱅크 $D44A, 파일 $3D45A~$3D491)에서는 $FF 가 제어코드가 아니라
#   **빈칸 타일**이다. 복사 루틴 $D4C4 는 $FE(줄바꿈)·$FD(끝)만 보고 $FF 는 그대로 타일로 깐다.
#   번역문은 인코더가 줄 중간 $FF 를 막으므로 빈칸을 <59> 로 쓴다 -> 이 구간에서만 원본 $FF 를 빼고 비교한다.
#   (v52 첫 빌드 `0F0383D4` 가 이 검사 하나로 _FAILED 격리됐다. 롬 내용은 의도대로였다)
TRAP_FF_BLANK = range(0x3D45A, 0x3D492)


def ctrl(seg):
    # ★$Dn(빈칸 n개)은 제외한다. 한국어는 띄어쓰기가 달라서 당연히 바뀐다.
    #   구조를 바꾸는 것만 본다: $Ex(프레임 대기) / $Fx(개행·종료·버튼대기·파서 인자)
    return [c for c in seg if c >= 0xE0]


ent = []
for l in io.open("ui_ko.txt", encoding="utf-8"):
    l = l.rstrip()
    if not l.strip() or l.startswith("#"): continue
    a, c, k = l.split(chr(9))
    ent.append((int(a, 16), int(c), k))

bad = []
for a, n, ko in ent:
    o, w = ctrl(src[a:a + n]), ctrl(rom[a:a + n])
    if a in ALLOW_TAIL_TERM and w and w[-1] in (0xFB, 0xFE, 0xFF):
        w = w[:-1]
    if a in TRAP_FF_BLANK and a + n - 1 in TRAP_FF_BLANK:
        o = [c for c in o if c != 0xFF]
    if o != w:
        bad.append((a, ko, o, w))

print("%s" % B.OUT)
print("ui_ko %d개 제어코드 보존 검사" % len(ent))
if bad:
    print("★어긋난 곳 %d개 - 연출 타이밍이나 문장 끝이 깨진다:" % len(bad))
    for a, ko, o, w in bad:
        print("   $%05X '%s'" % (a, ko))
        print("      원본 %s" % (" ".join("$%02X" % c for c in o) or "(없음)"))
        print("      현재 %s" % (" ".join("$%02X" % c for c in w) or "(없음)"))
else:
    print("   전부 보존 ✔")
sys.exit(1 if bad else 0)
