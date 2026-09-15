#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사용자 세이브를 헤드리스 Mesen 에 얹어 **실제 화면**을 찍고, 몇 프레임 동안
CHR 뱅크 레지스터($8000/$8001)와 PPUCTRL($2000) 쓰기를 **스캔라인·PC 와 함께** 기록한다.

    python savestate_trace.py <롬> <세이브.mss> <출력.png> [프레임수] ["행,열,값;..."]

마지막 인자를 주면 매 프레임 네임테이블에 그 타일을 써 넣는다(값은 16진).
게임을 다시 몰지 않고 "이 코드가 이 화면의 CHR 페이지에서 어떻게 보이나"를 확인할 때 쓴다.

★2026-09-13 예/아니오 상자 깨짐을 이걸로 확정했다: 보물상자 화면은 vblank 에서 R2=$80 R3=$81 을
  쓰는데 한글 예/아니오 글리프는 $82/$83 페이지에만 있었다(자세한 건 mt1-hangul-memory.md).
★세이브는 PRG-RAM·CHR-RAM 을 통째로 담는다. 롬(PRG/CHR-ROM)은 새 것이 쓰이지만,
  훅·슬롯표(PRG-RAM)와 이미 올라간 글리프(CHR-RAM)는 **세이브를 만든 빌드의 것**이다.
"""
import os
import re
import shutil
import subprocess
import sys

WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORK)
import mtpaths
from PIL import Image

ROM, MSS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
FR = int(sys.argv[4]) if len(sys.argv) > 4 else 3
pokes = []
if len(sys.argv) > 5:
    pokes = [tuple(int(v, 16) if i == 2 else int(v) for i, v in enumerate(p.split(",")))
             for p in sys.argv[5].split(";") if p]
TMP = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "savestate_trace")   # ASCII 경로 (Lua io)
os.makedirs(TMP, exist_ok=True)
shutil.copyfile(MSS, os.path.join(TMP, "in.mss"))
W = TMP.replace("\\", "/")
poke_lua = "\n".join("  emu.write(0x2000 + %d * 32 + %d, %d, emu.memType.nesPpuMemory)" % (r, c, v)
                     for r, c, v in pokes)

lua = r'''
local WORK = "@@W@@"
local loaded, fr, done = false, 0, false
local function where()
  local ok, st = pcall(emu.getState)
  if not ok or not st then return -1 end
  return (st["ppu.scanline"] or -1) * 65536 + (st["cpu.pc"] or 0)
end
emu.addMemoryCallback(function()
  if loaded then return end
  local f = io.open(WORK .. "/in.mss", "rb"); local d = f:read("*all"); f:close()
  emu.loadSavestate(d)
  loaded = true
  print("@LOADED")
end, emu.callbackType.exec, 0x8000, 0xFFFF)
emu.addMemoryCallback(function(addr, val)
  if not loaded or done or fr < 1 then return end
  print(string.format("@W %04X %02X %d %d", addr, val, where(), fr))
end, emu.callbackType.write, 0x8000, 0x8001)
emu.addMemoryCallback(function(addr, val)
  if not loaded or done or fr < 1 then return end
  print(string.format("@P %04X %02X %d %d", addr, val, where(), fr))
end, emu.callbackType.write, 0x2000, 0x2000)
emu.addEventCallback(function()
  if not loaded or done then return end
@@POKE@@
  fr = fr + 1
  if fr >= @@FR@@ then
    local buf = emu.getScreenBuffer()
    local o = {}
    for i = 1, #buf do
      local v = buf[i]
      o[i] = string.char(math.floor(v / 65536) % 256, math.floor(v / 256) % 256, v % 256)
    end
    local f = io.open(WORK .. "/screen.raw", "wb"); f:write(table.concat(o)); f:close()
    print("@DONE")
    done = true
    emu.exit()
  end
end, emu.eventType.endFrame)
'''.replace("@@W@@", W).replace("@@FR@@", str(FR)).replace("@@POKE@@", poke_lua)
runner = os.path.join(TMP, "run.lua")
open(runner, "w", encoding="utf-8").write(lua)
raw = os.path.join(TMP, "screen.raw")
if os.path.exists(raw):
    os.remove(raw)

p = subprocess.run([mtpaths.MESEN_EXE, "--enableStdout", "--doNotSaveSettings",
                    "--testRunner", runner, os.path.abspath(ROM)],
                   capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
marks = [l for l in (p.stdout or "").splitlines() if l.startswith("@")]
print("표식:", [l for l in marks if not l.startswith(("@W", "@P"))])

sel, last_fr = None, None
for l in marks:
    m = re.match(r"@([WP]) ([0-9A-F]{4}) ([0-9A-F]{2}) (-?\d+) (\d+)", l)
    if not m:
        continue
    kind, addr, val = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
    packed, fr = int(m.group(4)), int(m.group(5))
    scan, pc = (packed >> 16, packed & 0xFFFF) if packed >= 0 else (-1, 0)
    if fr != last_fr:
        print("--- 프레임 %d" % fr)
        last_fr = fr
    if kind == "P":
        print("  sl%4d pc$%04X  PPUCTRL=%02X (BG 패턴표 $%d000)" % (scan, pc, val, (val >> 4) & 1))
    elif addr == 0x8000:
        sel = val & 7
    else:
        print("  sl%4d pc$%04X  R%d = %02X" % (scan, pc, sel if sel is not None else -1, val))

if os.path.exists(raw):
    im = Image.frombytes("RGB", (256, 240), open(raw, "rb").read()[:256 * 240 * 3])
    im.resize((768, 720), Image.NEAREST).save(OUT)
    print("화면:", OUT)
else:
    print("★화면을 못 뽑았다")
