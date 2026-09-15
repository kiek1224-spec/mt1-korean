#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""타이틀 화면 그리기 목록(세그먼트) 인코더/디코더.

★형식 (2026-09-06, 역어셈블로 확정 - 추측 아님)
  인터프리터: 뱅크$07 `$B7C6`~`$B812`.  화면표 `$B88C` + 화면id*4 -> 세그먼트표 주소.
  세그먼트표: 2바이트 포인터 **15개**.  세그먼트 i = 네임테이블 **행 2i, 2i+1** (정확히 64칸).
    `$EE`      = 세그먼트 끝
    `$FE nn`   = 빈칸($FF) nn 개
    그 밖      = 타일ID 리터럴 1칸
  펼친 결과는 버퍼 `$0588` 에 쌓이고 `JSR $C3DF` 가 한 번에 PPU 로 보낸다.

★예전에 여기서 크게 헤맸다: 이걸 "행6열8부터 시작하는 하나의 연속 스트림"으로 착각하고
  `$EE` 를 타일 데이터로 취급한 채 201바이트를 통째로 재인코딩했다가 타이틀이 박살났다.
  세그먼트 경계와 `$EE` 를 지키지 않으면 그 뒤가 전부 밀린다.

타이틀은 **화면1**(세그먼트표 `$B9BE`). 화면2(`$B9DC`)는 seg7 만 다르고 나머지를 공유한다.
"""
BANK = 7
SCREEN1_TBL = 0xB9BE
SCREEN2_TBL = 0xB9DC
NSEG = 15


def f(addr):
    """뱅크7이 $A000 창에 있을 때의 CPU주소 -> 파일오프셋"""
    assert 0xA000 <= addr < 0xC000, "뱅크7 창($A000~$BFFF) 밖이다: $%04X" % addr
    return 16 + BANK * 0x2000 + (addr - 0xA000)


def read_ptrs(rom, tbl=SCREEN1_TBL):
    o = f(tbl)
    return [rom[o + k * 2] | (rom[o + k * 2 + 1] << 8) for k in range(NSEG)]


def decode(rom, addr):
    """세그먼트 -> 64칸 타일ID 리스트"""
    o = f(addr)
    out = bytearray()
    while True:
        c = rom[o]
        if c == 0xEE:
            break
        if c == 0xFE:
            out += bytes([0xFF]) * rom[o + 1]
            o += 2
        else:
            out.append(c)
            o += 1
    assert len(out) == 64, "세그먼트 $%04X 가 %d칸이다 (64 이어야 함)" % (addr, len(out))
    return bytes(out)


def encode(cells64):
    """64칸 -> 최소 바이트열($EE 포함). 빈칸 3개 이상이면 $FE 가 이득."""
    assert len(cells64) == 64
    out = bytearray()
    i = 0
    while i < 64:
        if cells64[i] == 0xFF:
            j = i
            while j < 64 and cells64[j] == 0xFF:
                j += 1
            n = j - i
            if n >= 3:
                out += bytes([0xFE, n])
            else:
                out += bytes([0xFF]) * n
            i = j
        else:
            out.append(cells64[i])
            i += 1
    out.append(0xEE)
    return bytes(out)


def full_nametable(rom, tbl=SCREEN1_TBL):
    """15개 세그먼트를 펼쳐 960바이트 네임테이블로"""
    out = bytearray()
    for p in read_ptrs(rom, tbl):
        out += decode(rom, p)
    assert len(out) == 960
    return bytes(out)
