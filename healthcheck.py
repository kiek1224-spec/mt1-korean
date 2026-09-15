#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""롬·빌더·데이터 종합 점검. 배치를 더 넣기 전에 한계선을 본다."""
import sys, zlib, io, re, os
sys.argv = [sys.argv[0]]
import build_step5b as B
import galmuri8 as G

def p(*a): print(*a); sys.stdout.flush()
warn = []

rom = open(B.OUT, "rb").read()
src = open("mt1_m191_v3.nes", "rb").read()

p("=" * 62)
p("1. 롬 무결성")
p("   파일 %d바이트  CRC32 %08X" % (len(rom), zlib.crc32(rom)))
hdr = rom[:16]
prg_kb, chr_kb = hdr[4] * 16, hdr[5] * 8
mapper = (hdr[6] >> 4) | (hdr[7] & 0xF0)
declared = 16 + prg_kb * 1024 + chr_kb * 1024
p("   헤더: PRG %dKB / CHR %dKB / 매퍼 %d" % (prg_kb, chr_kb, mapper))
p("   선언크기 %d vs 실제 %d  %s" % (declared, len(rom), "일치 ✔" if declared == len(rom) else "★불일치"))
if declared != len(rom): warn.append("헤더 선언크기 불일치")
# 매퍼195(CHR-RAM 4KB)는 슬롯 확장을 위한 **의도된** 전환이다 (MT1_M195=1, 에뮬 전용).
import os as _os
_want = 195 if _os.environ.get("MT1_M195", "0") == "1" else 191
if mapper != _want: warn.append("매퍼가 %d이 아님" % _want)

p("")
p("2. 패치 지점 (원본과 다른 곳이 의도한 곳뿐인가)")
sites = {
    "$C0BF NMI->업로더":      (B.fx(0xC0BF), 3),
    "$AF1E 메시지훅":          (B.B5 + (0xAF1E - 0xA000), 5),
    "$C12B NMI R7복원 대상":   (B.fx(0xC12B), 2),
    "$C689 분할 뱅크전환":     (B.fx(0xC689), 45),
    "$C959 뱅크셋13 R6":       (B.fx(0xC959), 1),
    "$C967 뱅크셋13 R7":       (B.fx(0xC967), 1),
}
for name, (off, n) in sites.items():
    p("   %-22s 원본 %s -> 현재 %s"
      % (name, src[off:off+min(n,4)].hex(" "), rom[off:off+min(n,4)].hex(" ")))
# 의도하지 않은 차이 찾기 (PRG 영역만)
PRG0, PRGN = 0x10, prg_kb * 1024
diff = [i for i in range(PRG0, PRG0 + PRGN) if rom[i] != src[i]]
known = set()
for off, n in sites.values(): known.update(range(off, off + n))
# 데이터/메시지 영역은 당연히 다름 -> 뱅크 단위로 요약
banks = {}
for i in diff:
    banks.setdefault((i - PRG0) // 0x2000, 0)
    banks[(i - PRG0) // 0x2000] += 1
p("   원본과 다른 바이트: %d개, 뱅크별:" % len(diff))
for b in sorted(banks):
    tag = ""
    if b == B.LOOKBANK: tag = " (룩업표)"
    elif b in B.RECBANKS: tag = " (레코드)"
    elif b == 0x0E: tag = " (부팅복사기)"
    elif b == 0x0F: tag = " (PRG-RAM 이미지)"
    elif b in (0x1E, 0x1F): tag = " (고정뱅크: 패치)"
    elif b == 0x05: tag = " (메시지 텍스트)"
    p("      뱅크$%02X  %6d바이트%s" % (b, banks[b], tag))

p("")
p("3. PRG-RAM 배치 (겹침)")
regs = [("업로더", 0x6000, len(B.up)), ("SLOTTAB", B.SLOTTAB, B.NSLOT),
        ("TBL7", B.TBL7, B.NBSET), ("변수", B.SLOT, 8),
        ("훅", B.HOOK, len(B.hook)), ("RESIDL", B.RESIDL, B.NSLOT),
        ("RESIDH", B.RESIDH, B.NSLOT), ("MAP", B.MAP, B.LOCALMAX),
        ("글리프버퍼", B.SRCBASE, B.NSLOT * 16), ("텍스트버퍼", B.TEXT, 256),
        ("이름훅", B.NHOOK, len(B.nhook)), ("SETCNT", B.SETCNT, len(B.setcnt)),
        ("이름상주L", B.NRESL, B.NNSLOT), ("이름상주H", B.NRESH, B.NNSLOT),
        ("NBUF", B.NBUF, 16), ("모드표", B.NDSTL, 25), ("이름변수", B.NMODE, 10)]
regs.sort(key=lambda r: r[1])
prev_end, prev_name = 0, None
for name, a, n in regs:
    ov = "★%s와 겹침" % prev_name if a < prev_end else ""
    if ov: warn.append("%s 겹침" % name)
    p("   %-10s $%04X~$%04X (%d)  %s" % (name, a, a + n - 1, n, ov))
    prev_end, prev_name = a + n, name
p("   부팅 복사 범위 $6000~$%04X (COPY=%d)" % (0x6000 + B.COPY - 1, B.COPY))
for name, a, n in regs:
    if a < 0x6000 + B.COPY and a + n > 0x6000 + B.COPY:
        warn.append("%s 가 부팅복사 경계를 걸침" % name)

p("")
p("4. 용량 여유 (남은 %d개를 더 넣을 수 있는가)" % (342 - len(B.records)))
used_banks = sum(1 for b in B.RECBANKS if B.cur[b])
rec_bytes = sum(B.cur.values())
per_msg = rec_bytes / max(len(B.records), 1)
need = per_msg * 342
p("   레코드 %d바이트 / %d뱅크 사용 (총 %d뱅크 = %dKB)"
  % (rec_bytes, used_banks, len(B.RECBANKS), len(B.RECBANKS) * 8))
p("   메시지당 평균 %.0f바이트 -> 342개 예상 %.0fKB (%.1f뱅크)"
  % (per_msg, need / 1024, need / 0x2000))
if need > len(B.RECBANKS) * 0x2000 * 0.9:
    warn.append("레코드 뱅크 여유가 10%% 미만 (예상 %.1f/%d뱅크)" % (need / 0x2000, len(B.RECBANKS)))
p("   룩업표 %d바이트 / 4096  (엔트리 %d, 스트라이드 %d)"
  % (len(B.look), len(B.look) // B.ENTSZ, B.ENTSZ))
if len(B.look) > 4096 * 0.9: warn.append("룩업표 여유 10%% 미만")
p("   전역 음절 %d종 (상한 없음)   훅 %d바이트 / 여유 $%04X"
  % (len(B.glob), len(B.hook), B.RESIDL - (B.HOOK + len(B.hook))))

p("")
p("5. 번역 데이터")
maxu = max((len(i) for _, _, i in B.records), default=0)
p("   번역 %d / 342   최대 고유 음절 %d / 한도 %d" % (len(B.records), maxu, B.LOCALMAX))
tight = [(len(i), a) for a, _, i in B.records if len(i) >= B.LOCALMAX - 4]
if tight: p("   한도 근접(여유 4칸 이하): %s" % " ".join("@%04X(%d)" % (a, n) for n, a in sorted(tight, reverse=True)))
lines = io.open("script_ko.txt", encoding="utf-8").read().splitlines()
n_ko = sum(1 for l in lines if l.startswith("KO:") and l[3:].strip())
p("   script_ko.txt 번역줄 %d개 vs 빌더 삽입 %d개  %s"
  % (n_ko, len(B.records), "일치 ✔" if n_ko == len(B.records) else "★불일치"))
if n_ko != len(B.records): warn.append("번역줄과 삽입 개수 불일치")

p("")
p("=" * 62)
if warn:
    p("경고 %d건:" % len(warn))
    for w in warn: p("   ★ " + w)
else:
    p("경고 없음 ✔")

# ★어긋나면 종료코드로 알린다. 없으면 make.py 가 통과로 세어 버린다(2026-09-03 발각).
sys.exit(1 if warn else 0)