#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""두 롬을 바이트 비교해 바뀐 구간을 뱅크별로 묶어 보여준다.
v42~v50 기록 복원용. 텍스트로 보이는 구간은 가나 디코드도 같이 낸다.

사용: python romdiff.py <이전롬> <이후롬> [-v]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decode_tbl as T


def load(p):
    d = open(p, "rb").read()
    prg_n, chr_n = d[4], d[5]
    prg = d[16:16 + prg_n * 16384]
    chrd = d[16 + prg_n * 16384:16 + prg_n * 16384 + chr_n * 8192]
    return d, prg, chrd, prg_n, chr_n


def runs(a, b, gap=16):
    """다른 바이트를 gap 이하 간격이면 한 덩어리로 묶는다."""
    out, cur = [], None
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            if cur and i - cur[1] <= gap:
                cur[1] = i + 1
            else:
                if cur: out.append(tuple(cur))
                cur = [i, i + 1]
    if cur: out.append(tuple(cur))
    if len(a) != len(b):
        out.append((n, max(len(a), len(b))))
    return out


def main():
    ap, bp = sys.argv[1], sys.argv[2]
    verbose = "-v" in sys.argv
    da, pa, ca, pna, cna = load(ap)
    db, pb, cb, pnb, cnb = load(bp)
    print("=" * 78)
    print(" %s  ->  %s" % (os.path.basename(ap), os.path.basename(bp)))
    print(" PRG %dKB->%dKB  CHR %dKB->%dKB  파일 %d->%d"
          % (pna * 16, pnb * 16, cna * 8, cnb * 8, len(da), len(db)))
    print("=" * 78)

    for label, xa, xb, banksz in (("PRG", pa, pb, 0x2000), ("CHR", ca, cb, 0x0400)):
        rs = runs(xa, xb)
        total = sum(e - s for s, e in rs)
        print("\n[%s] 바뀐 덩어리 %d개 / %d바이트" % (label, len(rs), total))
        if not rs:
            print("   (동일)")
            continue
        # 뱅크별 요약
        per = {}
        for s, e in rs:
            for i in range(s, e):
                per[i // banksz] = per.get(i // banksz, 0) + 1
        print("   뱅크별: " + "  ".join("$%02X:%d" % (k, v) for k, v in sorted(per.items())))
        for s, e in rs:
            if not verbose and e - s < 2:
                pass
            bank = s // banksz
            off = s % banksz
            head = "   $%02X:%04X 파일$%05X %4d바이트" % (bank, off, 16 + (0 if label == "PRG" else pnb * 16384) + s, e - s)
            seg_a, seg_b = xa[s:e], xb[s:e]
            if label == "PRG":
                import kdec
                print("%s\n       전: %s\n       후: %s"
                      % (head, kdec.dec(seg_a[:56]), kdec.dec(seg_b[:56])))
            else:
                print(head)


main()
