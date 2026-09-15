#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""원판 롬 -> 한글판 롬 IPS 패치를 만들고, **다시 적용해서 바이트 단위로 같은지** 확인한다.

    python make_ips.py <원판.nes> <한글판.nes> <출력.ips>

원판 기준 (2026-09-15 확인, 작업폴더의 원판 세 벌이 전부 같았다)
    Digital Devil Story - Megami Tensei (Japan).nes
    262,160바이트 / 파일 CRC32 682C4603 / 헤더 뺀 CRC32 5393D949 / 매퍼 76

IPS 규칙
  - 레코드 = [오프셋 3B][길이 2B][데이터], 길이 0 이면 RLE = [개수 2B][값 1B]. 끝은 "EOF".
  - 오프셋은 24비트, 길이는 16비트(65535)가 한계라 긴 구간은 쪼갠다.
  - 오프셋 $454F46 은 "EOF" 와 글자가 같아 쓰면 안 된다(우리 롬은 512KB 라 닿지 않지만 막아 둔다).
  - 한글판은 원판보다 **길다**(매퍼195, 512KB). 원판 끝 뒤는 전부 기록한다. IPS 는 파일을 줄이지 못하므로
    대상이 원판보다 짧으면 만들지 않는다.
  - ★iNES 헤더 16바이트는 **항상 통째로** 기록한다. 원판 덤프마다 헤더 뒤쪽 바이트가 다를 수 있어서,
    차이만 적으면 받은 사람의 롬에서 매퍼 번호가 어긋날 수 있다.
"""
import sys
import zlib

ORIG_CRC_NOHDR = 0x5393D949
EOF_OFS = 0x454F46
GAP = 6          # 이만큼 이하로 떨어진 차이는 한 레코드로 합친다 (레코드 머리 5바이트보다 싸다)
RLE_MIN = 9      # 같은 값이 이만큼 이상 이어지면 RLE 레코드로 뺀다


def _crc(b):
    return zlib.crc32(b) & 0xFFFFFFFF


def diff_runs(src, dst):
    """[시작, 끝) 목록 - dst 가 src 와 다른 구간 (src 끝 뒤는 전부 다름으로 친다)"""
    runs, i, n, ns = [], 0, len(dst), len(src)
    while i < n:
        if i < 16 or i >= ns or src[i] != dst[i]:
            j = i
            same = 0
            while j < n:
                if j < 16 or j >= ns or src[j] != dst[j]:
                    same = 0
                else:
                    same += 1
                    if same > GAP:
                        break
                j += 1
            # j 에서 같은 바이트가 GAP+1 개째가 되어 멈췄다 -> 같은 구간의 첫 칸 = j - same + 1
            # ★+1 을 빼먹으면 마지막 다른 바이트가 빠지고, 다음 바퀴가 그 자리에서 빈 구간만 만들며 멈추지 않는다.
            end = j - same + 1 if j < n else n
            runs.append((i, end))
            i = end
        else:
            i += 1
    return runs


def records(dst, runs):
    """(오프셋, 데이터) 또는 (오프셋, (개수, 값)) 로 쪼갠다"""
    out = []
    for s, e in runs:
        i = s
        lit = s
        while i < e:
            j = i
            while j < e and dst[j] == dst[i] and j - i < 0xFFFF:
                j += 1
            if j - i >= RLE_MIN:
                out.extend(_lits(dst, lit, i))
                out.append((i, (j - i, dst[i])))
                lit = j
            i = j if j > i else i + 1
        out.extend(_lits(dst, lit, e))
    return out


def _lits(dst, s, e):
    res = []
    while s < e:
        k = min(e, s + 0xFFFF)
        res.append((s, bytes(dst[s:k])))
        s = k
    return res


def build(src, dst):
    assert len(dst) >= len(src), "한글판이 원판보다 짧다 - IPS 는 파일을 줄일 수 없다"
    assert len(dst) <= 0xFFFFFF, "24비트 오프셋을 넘는다"
    recs = records(dst, diff_runs(src, dst))
    out = bytearray(b"PATCH")
    for ofs, body in recs:
        assert ofs != EOF_OFS, "오프셋 $454F46 은 IPS 에서 쓸 수 없다"
        out += ofs.to_bytes(3, "big")
        if isinstance(body, tuple):
            cnt, val = body
            out += b"\x00\x00" + cnt.to_bytes(2, "big") + bytes([val])
        else:
            out += len(body).to_bytes(2, "big") + body
    out += b"EOF"
    return bytes(out), recs


def apply(src, ips):
    """검증용 적용기 (만들기와 따로 짠다)"""
    assert ips[:5] == b"PATCH", "IPS 머리가 아니다"
    rom = bytearray(src)
    p = 5
    while True:
        tag = ips[p:p + 3]
        if tag == b"EOF" and p + 3 == len(ips):
            break
        ofs = int.from_bytes(tag, "big")
        size = int.from_bytes(ips[p + 3:p + 5], "big")
        p += 5
        if size == 0:
            cnt = int.from_bytes(ips[p:p + 2], "big")
            chunk = bytes([ips[p + 2]]) * cnt
            p += 3
        else:
            chunk = ips[p:p + size]
            p += size
        if ofs + len(chunk) > len(rom):
            rom.extend(b"\x00" * (ofs + len(chunk) - len(rom)))
        rom[ofs:ofs + len(chunk)] = chunk
    return bytes(rom)


def copied_from_source(src, recs, block=64):
    """패치 데이터 중 **원판에 그대로 있는** 64바이트 덩어리 (옮겨진 원본 데이터) - 한 값으로만 찬 덩어리는 뺀다"""
    body = src[16:]
    seen = set(body[i:i + block] for i in range(0, len(body) - block + 1))
    hit = 0
    for ofs, data in recs:
        if isinstance(data, tuple):
            continue
        for k in range(0, len(data) - block + 1, block):
            b = data[k:k + block]
            if len(set(b)) > 1 and b in seen:
                hit += 1
    return hit * block


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    src = open(sys.argv[1], "rb").read()
    dst = open(sys.argv[2], "rb").read()
    out_path = sys.argv[3]
    c0 = _crc(src[16:])
    print("원판   %s  %d바이트  CRC32(헤더 제외) %08X %s"
          % (sys.argv[1], len(src), c0, "✔" if c0 == ORIG_CRC_NOHDR else "★기준 원판(5393D949)이 아니다"))
    print("한글판 %s  %d바이트  CRC32 %08X" % (sys.argv[2], len(dst), _crc(dst)))
    ips, recs = build(src, dst)
    back = apply(src, ips)
    ok = back == dst
    nrle = sum(1 for _, b in recs if isinstance(b, tuple))
    print("IPS    %s  %d바이트 / 레코드 %d개 (RLE %d)" % (out_path, len(ips), len(recs), nrle))
    print("검증   원판 + IPS == 한글판 : %s  (결과 CRC32 %08X)" % ("일치 ✔" if ok else "★불일치", _crc(back)))
    print("참고   패치 안에 원판과 똑같은 64바이트 덩어리 %d KB" % (copied_from_source(src, recs) // 1024))
    if not ok:
        raise SystemExit(1)
    open(out_path, "wb").write(ips)


if __name__ == "__main__":
    main()
