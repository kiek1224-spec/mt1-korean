#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""빌드 -> 전체 검증 -> 기준선 락스텝 대조 -> VERSIONS.md 기록 을 한 번에.

    python make.py v11 보옥추가
    python make.py v12 진단 --env MT1_UIHOOK=0

**하나라도 실패하면 롬을 `_FAILED` 로 이름을 바꿔 격리한다.** 검증을 통과한 롬만
`작업롬파일/` 에 정상 이름으로 남으므로, 실기에 올릴 것을 고를 때 헷갈리지 않는다.

락스텝(`diff_step.py`)은 사용자 세이브스테이트를 기준선 롬과 새 롬에 **동시에** 물려
명령 단위로 돌린다. 갈리면 그 자리가 곧 원인이다 - 2026-09-03 에 이걸로
`ui_ko.txt` 첫 줄이 포인터를 덮은 것을 128585번째 명령에서 잡았다.
"""
import os
import subprocess
import sys
import time
import zlib

OUTDIR = "작업롬파일"
# 락스텝 기준선은 env 를 다 읽은 뒤에 고른다 (아래 BASE 참조)
LOG = os.path.join(OUTDIR, "VERSIONS.md")
MARK0, MARK1 = "<!-- BUILDLOG -->", "<!-- /BUILDLOG -->"

CHECKS = [
    ("check_uistr", "제자리 치환 구간이 코드가 읽는 자리를 덮는지"),
    ("check_5c",    "슬롯/인코딩/부팅/상점 종합"),
    ("check_ui",    "UI 문자열 100개"),
    ("check_panel", "던전 패널 글리프 + 잠금 타일"),
    ("check_labels", "라벨 주변에 번역 빠진 일본어가 남았는지"),
    ("check_ctrl",  "제어코드($Ex 프레임대기 등) 보존"),
    ("check_tails", "꼬리 89개 정렬"),
    ("check_slotclash", "슬롯 코드가 게임 그래픽과 겹치는지"),
    ("trace_name",  "이름 267개 5모드"),
    ("healthcheck", "롬·배치 점검"),
]

argv = [a for a in sys.argv[1:]]
env = dict(os.environ)
while "--env" in argv:
    i = argv.index("--env")
    k, v = argv[i + 1].split("=", 1)
    env[k] = v
    del argv[i:i + 2]
ver = argv[0] if argv else "v" + time.strftime("%m%d%H%M")
tag = argv[1] if len(argv) > 1 else ""
env["MT1_VER"], env["MT1_TAG"] = ver, tag
env["PYTHONIOENCODING"] = "utf-8"

# ★기준선은 **--env 까지 반영된 env** 로 골라야 한다. os.environ 을 보면 --env 가 안 잡혀
#   195 빌드를 191 기준선과 대조하게 되고, CHR 뱅크 쓰기에서 반드시 갈린다(2026-09-03).
BASE = os.path.join(OUTDIR, "mt1_kor5b_v26_m195_base.nes"
                    if env.get("MT1_M195", "0") == "1" else "mt1_kor5b_v1_base.nes")
name = "mt1_kor5b_%s%s.nes" % (ver, ("_" + tag) if tag else "")
rom = os.path.join(OUTDIR, name)
switches = " ".join("%s=%s" % (k, env[k]) for k in
                    ("MT1_UIHOOK", "MT1_UIPATCH", "MT1_PANEL", "MT1_LABELS", "MT1_STATIC")
                    if k in env)


def run(script, args=()):
    r = subprocess.run([sys.executable, script] + list(args), env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


print("=" * 62)
print(" 빌드 %s   %s" % (name, switches or "(기본 스위치)"))
print("=" * 62)
rc, out = run("build_step5b.py")
if rc != 0:
    print(out[-3000:])
    sys.exit("★빌드 실패")
for line in out.splitlines():
    if any(w in line for w in ("치환", "한글화", "구웠다", "패치", "CRC32", "★", "삽입")):
        print("  " + line)

crc = zlib.crc32(open(rom, "rb").read())
results = []
fail = 0

print()
print("검증")
for script, what in CHECKS:
    rc, out = run(script + ".py")
    tail = [l for l in out.splitlines() if l.strip()][-1:] or [""]
    ok = rc == 0
    if not ok: fail += 1
    print("  %-14s %-34s %s" % (script, what, "통과" if ok else "★실패"))
    if not ok:
        for l in out.splitlines()[-12:]:
            print("        " + l)
    results.append((script, ok))

print()
print("압박 시험 (참고용 - 빌드를 막지는 않는다)")
rc, out = run("stress_name.py")
for l in out.splitlines():
    if "회:" in l or "종족 20개" in l:
        mark = "  ★" if ("어긋남 0건" not in l and "합성최악" not in l) else "    "
        print(mark + l.strip())

print()
print("기준선 락스텝 대조 (%s)" % os.path.basename(BASE))
if not os.path.exists(BASE):
    print("  기준선 롬이 없다 - 건너뜀")
    lock = None
else:
    rc, out = run("diff_step.py", [BASE, rom])
    lock = ("갈림 없음" in out)
    if lock:
        print("  갈림 없음 - 기준선과 명령 단위로 완전히 동일하게 돈다")
    else:
        fail += 1
        print("  ★갈림 발생")
        for l in out.splitlines():
            if l.startswith("★") or "갈림" in l or l.startswith("   "):
                print("      " + l)

verdict = "통과" if not fail else "★%d건 실패" % fail
print()
print("=" * 62)
print(" %s  CRC32 %08X   %s" % (name, crc, verdict))
print("=" * 62)

if fail:
    bad = rom.replace(".nes", "_FAILED.nes")
    os.replace(rom, bad)
    print("검증에 걸려 %s 로 격리했다. 실기에 올리지 말 것." % os.path.basename(bad))

# --- VERSIONS.md 의 BUILDLOG 블록에 한 줄 추가
row = "| `%s` | `%08X` | %s | %s | %s |" % (
    ver + (("_" + tag) if tag else ""), crc, switches or "기본",
    verdict + ("" if lock is None else (" / 락스텝 " + ("일치" if lock else "갈림"))),
    time.strftime("%Y-%m-%d %H:%M"))
s = open(LOG, encoding="utf-8").read() if os.path.exists(LOG) else ""
if MARK0 not in s:
    s += ("\n## 자동 빌드 기록 (`make.py`)\n\n" + MARK0 +
          "\n| 버전 | CRC32 | 스위치 | 검증 | 시각 |\n|---|---|---|---|---|\n" + MARK1 + "\n")
s = s.replace(MARK1, row + "\n" + MARK1)
open(LOG, "w", encoding="utf-8", newline="\n").write(s)
print("%s 에 기록했다." % LOG)
sys.exit(1 if fail else 0)
