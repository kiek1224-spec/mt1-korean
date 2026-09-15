#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesen 2.x 세이브 스테이트(.mss)를 읽어 **nesboot 상태로 밀어넣는다.**

이게 있으면 사용자가 특정 화면(상점 등)에서 저장한 상태로 **바로 점프**할 수 있다.
헤드리스로 게임을 처음부터 몰고 가는 것보다 훨씬 빠르고, 재현이 정확하다.

파일 구조 (실측)
    "MSS" + 버전/헤더  ...  zlib 스트림 2개
      1) 스크린샷 256x240x2 바이트
      2) 콘솔 상태: `키\\0` + uint32(LE) 길이 + 데이터  의 연속
"""
import re
import struct
import zlib


def streams(path):
    d = open(path, "rb").read()
    out = []
    i = 0
    while i < len(d) - 2:
        if d[i] == 0x78 and d[i + 1] in (0x01, 0x5E, 0x9C, 0xDA):
            try:
                o = zlib.decompressobj()
                data = o.decompress(d[i:])
                if len(data) > 256:
                    out.append((i, data))
                    i += len(d[i:]) - len(o.unused_data)
                    continue
            except Exception:
                pass
        i += 1
    return out


def parse(path):
    """상태 스트림을 {키: bytes} 로."""
    ss = streams(path)
    assert ss, "zlib 스트림을 못 찾음"
    st = max(ss, key=lambda t: len(t[1]))[1]          # 가장 큰 것이 상태
    if len(ss) > 1:
        st = ss[-1][1]                                 # 보통 마지막이 상태(앞은 스크린샷)
    out, i = {}, 0
    while i < len(st):
        j = st.find(b"\x00", i)
        if j < 0 or j - i < 3:
            break
        key = st[i:j]
        if not re.fullmatch(rb"[A-Za-z][A-Za-z0-9_.]*", key):
            i += 1
            continue
        if j + 5 > len(st):
            break
        n = struct.unpack_from("<I", st, j + 1)[0]
        if n > len(st):
            i = j + 1
            continue
        out[key.decode()] = st[j + 5:j + 5 + n]
        i = j + 5 + n
    return out


def _int(b):
    return int.from_bytes(b, "little") if b else 0


def refresh_prgram(n, copy_bytes=0x400, bank=0x0F):
    """★세이브의 PRG-RAM 을 **현재 롬의 부팅 이미지로 갈아끼운다.**

    우리 코드는 PRG-RAM($6000~)에 산다. 그래서 다른 빌드로 만든 세이브를 로드하면
    `mapper.workRam` 복원이 **그 빌드의 훅 코드를 그대로 되살린다** -> 새 빌드를 테스트한다고
    믿으면서 옛 코드를 돌리게 된다(실제로 그렇게 여러 번 헛짚었다).
    부팅 복사기가 하는 일(뱅크 $0F 앞부분 -> $6000)을 그대로 재현해 맞춘다.
    """
    off = 16 + bank * 0x2000
    n.prgram[0:copy_bytes] = n.prg[bank * 0x2000: bank * 0x2000 + copy_bytes]
    return copy_bytes


def reset_chrram(n, rom_path):
    """CHR-RAM 을 부팅 직후 상태(원본 CHR 뱅크6/7 복사본)로 되돌린다.
    세이브에는 옛 빌드가 올려둔 글리프가 남아 있어 그대로 두면 '한글이 나온다'고 오판한다."""
    d = open(rom_path, "rb").read()
    chr_off = 16 + d[4] * 16384
    for c in range(0x80, 0x100):
        bank = 6 if c < 0xC0 else 7
        src = chr_off + bank * 1024 + (c & 0x3F) * 16
        dst = (0x1000 + c * 16) - 0x1800
        if 0 <= dst <= len(n.chrram) - 16:
            n.chrram[dst:dst + 16] = d[src:src + 16]


def load(n, path, verbose=True):
    """nesboot NES 인스턴스에 상태를 적용한다.

    주의: PRG-RAM·CHR-RAM 도 복원된다. **다른 빌드의 세이브로 새 롬을 시험할 때는**
    반드시 `refresh_prgram(n)` / `reset_chrram(n, rom)` 을 이어서 호출할 것.
    """
    s = parse(path)

    def put(dst, key):
        v = s.get(key)
        if v is None:
            return 0
        m = min(len(dst), len(v))
        dst[:m] = v[:m]
        return m

    n.pc = _int(s["cpu.pc"])
    n.a = _int(s["cpu.a"])
    n.x = _int(s["cpu.x"])
    n.y = _int(s["cpu.y"])
    n.s = _int(s["cpu.sp"])
    n.p = _int(s["cpu.ps"])
    nram = put(n.ram, "memoryManager.internalRam")
    nchr = put(n.chrram, "mapper.chrRam")
    npgr = put(n.prgram, "mapper.workRam") or put(n.prgram, "mapper.saveRam")
    nvr = put(n.vram, "mapper.nametableRam")

    regs = s.get("mapper.registers", b"")
    for i in range(min(8, len(regs))):
        n.r[i] = regs[i]
    n.bsel = _int(s.get("mapper.reg8000", b"\x00"))
    n.prgmode = (n.bsel >> 6) & 1
    n.map_prg()

    ctrl = 0
    if _int(s.get("ppu.control.verticalWrite", b"\0")):
        ctrl |= 0x04
    if _int(s.get("ppu.control.spritePatternAddr", b"\0\0")):
        ctrl |= 0x08
    if _int(s.get("ppu.control.backgroundPatternAddr", b"\0\0")):
        ctrl |= 0x10
    if _int(s.get("ppu.control.largeSprites", b"\0")):
        ctrl |= 0x20
    if _int(s.get("ppu.control.nmiOnVerticalBlank", b"\0")):
        ctrl |= 0x80
    n.ppuctrl = ctrl
    n.vaddr = _int(s.get("ppu.videoRamAddr", b"\0\0")) & 0x3FFF

    if verbose:
        print("세이브 적용: PC=$%04X A=$%02X X=$%02X Y=$%02X SP=$%02X P=$%02X"
              % (n.pc, n.a, n.x, n.y, n.s, n.p))
        print("  내부RAM %dB / CHR-RAM %dB / PRG-RAM %dB / 네임테이블 %dB"
              % (nram, nchr, npgr, nvr))
        print("  R0~R7 = %s   reg8000=$%02X  PPUCTRL=$%02X"
              % (" ".join("$%02X" % x for x in n.r), n.bsel, n.ppuctrl))
    return s


def screenshot(path, out="mss_shot.png"):
    """저장 당시 화면(Mesen 이 넣어둔 썸네일)을 PNG 로."""
    from PIL import Image
    ss = streams(path)
    raw = ss[0][1]
    w, h = 256, 240
    if len(raw) < w * h * 2:
        return None
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            v = raw[(y * w + x) * 2] | (raw[(y * w + x) * 2 + 1] << 8)
            # Mesen 썸네일은 RGB555/565 계열 - 대략 뽑아본다
            px[x, y] = (((v >> 10) & 31) << 3, ((v >> 5) & 31) << 3, (v & 31) << 3)
    im.save(out)
    return out
