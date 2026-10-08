#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 배포판 폴더를 만든다 (2026-09-15).

    python make_release.py <원판(Japan).nes> <한글판 빌드.nes> <버전> [배포폴더]
    예) python make_release.py "원판.nes" 작업롬파일/mt1_kor5b_v52_함정창라그내힘.nes v52

기본 배포폴더 = 작업폴더 **옆** `../mt1-korean` (작업폴더 안에 두면 롬이 섞일 위험이 크다).

원칙
  - **화이트리스트만 복사한다.** 목록에 없는 파일은 절대 안 들어간다(롬·세이브·zip·로그·개인 메모).
    그래도 한 번 더: 확장자 .nes .fc .smc .mss .zip .bps 는 복사 단계에서 막는다.
  - 패치는 IPS 만 (사용자 결정: BPS 는 하지 않는다).
      patch/base_mt1_m191_v3.ips  원판 -> 빌드 기준 롬 (기여자가 빌드하려면 필요하다)
      patch/MT1_Korean_<버전>.ips  원판 -> 한글판
    둘 다 만든 뒤 원판에 **다시 적용해 바이트 일치**를 확인한다(make_ips.py).
  - 문서의 개인 경로(사용자 폴더)는 `%USERPROFILE%` 로 바꾸고, 마지막에 복사본 전체에서 사용자 이름을 다시 찾는다.
  - 기존 배포폴더에 README 등 손으로 쓴 파일이 있으면 **건드리지 않는다**(덮어쓰는 것은 목록의 파일뿐).
"""
import glob
import os
import shutil
import sys
import zlib

WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORK)
import make_ips

TEXT = ["script_ko.txt", "ui_ko.txt", "names_ko.txt", "ui_words.txt", "panel_ko.txt", "static_font.txt"]
BUILD = ["make.py", "build_step5b.py", "galmuri8.py", "decode_tbl.py", "mtpaths.py", "make_title.py",
         "titleseg.py", "title_main.png", "title_edit.py", "make_signs.py", "make_ips.py", "make_release.py"]
CHECK = ["check_uistr.py", "check_5c.py", "check_ui.py", "check_panel.py", "check_labels.py", "check_ctrl.py",
         "check_tails.py", "check_slotclash.py", "trace_name.py", "healthcheck.py", "stress_name.py",
         "diff_step.py", "mt1dis.py", "nesboot.py", "play.py", "screendump.py", "mss.py", "mss_state.bin"]
MAP = ["automap.lua", "ds_bridge.lua", "mt1_ds_window.py", "ds_selftest.py", "luacheck.py",
       "layers.py", "layer10.py", "warpcheck.py", "make_maps.py"]
TOOLS = ["savestate_trace.py", "scan_left.py", "scan_neighbors.py", "scan_kana.py", "kdec.py",
         "romdiff.py", "refaddr.py", "export_script.py"]
DIRS = {"galmuri": ["Galmuri14.ttf", "galmuriM_8x8.ttf", "galmuriM_8x8.png", "galmuriM_8x8.tbl"]}
DOCS = {"mt1-hangul-memory.md": "docs/mt1-hangul-memory.md",
        os.path.join("작업롬파일", "VERSIONS.md"): os.path.join("작업롬파일", "VERSIONS.md")}
MEMORY = ["mt1-hangul-project.md", "mt1-hangul-romdiff-method.md", "mt1-pareido-automap.md",
          "mt1-ds-window.md", "bizhawk-second-screen.md", "powershell-utf8-trap.md"]
# ★2026-10-08 롬 해석 공략 페이지(사용자 결정: 같이 올리되 롬에서 뽑은 악마 그림은 빼고). index.html 은 --no-sprites 로 새로 만든다.
GUIDE = {os.path.join("공략사이트", "make_guide.py"): os.path.join("guide", "make_guide.py"),
         os.path.join("공략사이트", "capture_sprites.py"): os.path.join("guide", "capture_sprites.py")}
# ★2026-10-08 Claude 메모 사본에서 빼는 줄(배포와 무관한 사적인 분석·구상). 줄에 이 말이 있으면 통째로 뺀다.
PRIVATE_MARKERS = ("lamu", "티카페", "유입", "retrodb", "대형공사", "타일 예산 제약", "참고 측정", "MT2(")
PUBLIC_IDS = ("kiek1224-spec",)          # 공개 GitHub 계정(저장소 주소) — 사용자 이름 검사에서 뺀다
BLOCK_EXT = (".nes", ".fc", ".smc", ".sfc", ".mss", ".zip", ".bps", ".7z")
BASE_ROM = "mt1_m191_v3.nes"


def _crc(b):
    return zlib.crc32(b) & 0xFFFFFFFF


def copy(src, dst):
    assert not src.lower().endswith(BLOCK_EXT), "막힌 확장자를 복사하려 했다: %s" % src
    assert os.path.isfile(src), "없는 파일: %s" % src
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)


def sanitize(path, home, user):
    s = open(path, encoding="utf-8").read()
    t = s.replace(home, "%USERPROFILE%").replace(home.replace("\\", "/"), "%USERPROFILE%")
    t = t.replace("C--Users-%s-" % user, "C--Users-<user>-")
    if t != s:
        open(path, "w", encoding="utf-8", newline="").write(t)
        return True
    return False


def ips(src, dst, out):
    patch, recs = make_ips.build(src, dst)
    assert make_ips.apply(src, patch) == dst, "IPS 재적용 불일치: %s" % out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(patch)
    return len(patch)


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    orig_p, kor_p, ver = sys.argv[1], sys.argv[2], sys.argv[3]
    out = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(WORK), "mt1-korean")
    orig = open(orig_p, "rb").read()
    assert _crc(orig[16:]) == make_ips.ORIG_CRC_NOHDR, "기준 원판(헤더 제외 5393D949)이 아니다"
    kor = open(kor_p, "rb").read()
    home = os.path.expanduser("~")
    user = os.path.basename(home)

    n = 0
    for f in TEXT + BUILD + CHECK + MAP + TOOLS:
        copy(os.path.join(WORK, f), os.path.join(out, f))
        n += 1
    for d, files in DIRS.items():
        for f in files:
            copy(os.path.join(WORK, d, f), os.path.join(out, d, f))
            n += 1
    for s, d in DOCS.items():
        copy(os.path.join(WORK, s), os.path.join(out, d))
        n += 1
    for s_, d_ in GUIDE.items():
        copy(os.path.join(WORK, s_), os.path.join(out, d_))
        n += 1
    gpage = os.path.join(out, "guide", "index.html")
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(WORK, "공략사이트", "make_guide.py"), kor_p, "--no-sprites", "--out", gpage],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0, "공략 페이지 생성 실패: " + r.stdout[-1500:] + r.stderr[-1500:]
    _g = open(gpage, encoding="utf-8").read()
    assert 'class="sprbox"' not in _g and "data:image/png;base64" in _g, "공략 페이지에 악마 그림이 들어갔거나 지도가 없다"
    print("공략 페이지 guide/index.html %.0f KB (악마 그림 없음)" % (len(_g.encode("utf-8")) / 1024.0))
    n += 1
    mem = glob.glob(os.path.join(home, ".claude", "projects", "*", "memory", "mt1-hangul-project.md"))
    assert mem, "Claude 메모리 폴더를 못 찾았다"
    memdir = os.path.dirname(mem[0])
    for f in MEMORY:
        copy(os.path.join(memdir, f), os.path.join(out, "docs", "claude-memory", f))
        n += 1
    for f in MEMORY:
        mp = os.path.join(out, "docs", "claude-memory", f)
        lines = open(mp, encoding="utf-8").read().split("\n")
        keep = [l for l in lines if not any(m in l for m in PRIVATE_MARKERS)]
        if len(keep) != len(lines):
            open(mp, "w", encoding="utf-8", newline="").write("\n".join(keep))
            print("메모 사본 %s: 사적인 줄 %d개 뺌" % (f, len(lines) - len(keep)))
    print("복사 %d개 -> %s" % (n, out))

    fixed = []
    for dp, dn, fn in os.walk(out):
        if ".git" in dp:
            continue
        for f in fn:
            if f.endswith((".md", ".txt", ".py", ".lua")):
                p = os.path.join(dp, f)
                try:
                    if sanitize(p, home, user):
                        fixed.append(os.path.relpath(p, out))
                except UnicodeDecodeError:
                    pass
    print("개인 경로 치환 %d개: %s" % (len(fixed), ", ".join(fixed) or "-"))

    base = open(os.path.join(WORK, BASE_ROM), "rb").read()
    b1 = ips(orig, base, os.path.join(out, "patch", "base_mt1_m191_v3.ips"))
    b2 = ips(orig, kor, os.path.join(out, "patch", "MT1_Korean_%s.ips" % ver))
    with open(os.path.join(out, "patch", "CHECKSUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("원판   Digital Devil Story - Megami Tensei (Japan).nes  %d bytes  CRC32 %08X (헤더 제외 %08X)\n"
                 % (len(orig), _crc(orig), _crc(orig[16:])))
        fh.write("MT1_Korean_%s.ips      -> %d bytes  CRC32 %08X\n" % (ver, len(kor), _crc(kor)))
        fh.write("base_mt1_m191_v3.ips  -> %s  %d bytes  CRC32 %08X (빌드 기준 롬, 플레이용 아님)\n"
                 % (BASE_ROM, len(base), _crc(base)))
    print("패치: base %d바이트 / 한글판 %s %d바이트 (둘 다 재적용 일치)" % (b1, ver, b2))

    bad = []
    for dp, dn, fn in os.walk(out):
        if ".git" in dp:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            if f.lower().endswith(BLOCK_EXT):
                bad.append("막힌 확장자 " + os.path.relpath(p, out))
                continue
            try:
                _t = open(p, "rb").read().decode("utf-8", "ignore").lower()
                for _pid in PUBLIC_IDS:
                    _t = _t.replace(_pid.lower(), "")
                if user.lower() in _t:
                    bad.append("사용자 이름 " + os.path.relpath(p, out))
            except OSError:
                pass
    if bad:
        print("★배포 금지 항목:")
        for b in bad:
            print("   " + b)
        raise SystemExit(1)
    print("최종 점검: 롬·세이브·zip 없음 / 사용자 이름 없음 ✔")


if __name__ == "__main__":
    main()
