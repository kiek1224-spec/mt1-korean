#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DS 두 번째 화면 자체검사 — 창을 화면에 띄우지 않고 전부 확인한다.

    python ds_selftest.py

  1) 지도 계산이 기대 숫자를 내는가 (automap.lua 와 같은 규칙)
  2) mt1_ds_window.py 의 tkinter 그리기가 여러 상태에서 도는가 (창은 숨긴 채)
  3) 창의 접속 코드(net_loop)가 헤드리스 Mesen 의 ds_bridge.lua 에 붙어 위치를 받는가
     (러너가 200프레임마다 X 를 바꿔 쓰고, 바뀐 X 를 여러 개 받아야 통과)

★Mesen 은 한글 경로의 Lua 를 io 로 못 읽는 문제가 있어 브리지를 임시폴더(ASCII)로 복사해 돌린다.
"""
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

WORK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORK)
import mtpaths
import mt1_ds_window as DW
from mt1_ds_window import DungeonMap, EXPECT

ROM = DW.DEFAULT_ROM                      # 작업롬파일의 최신 정상 빌드 (없으면 인자로 줄 것)
if len(sys.argv) > 1:
    ROM = sys.argv[1]
if not ROM or not os.path.exists(ROM):
    raise SystemExit("롬이 없다 -> python ds_selftest.py <롬 경로>")
fail = 0

# ── 1) 지도 데이터 ─────────────────────────────────────────────────────────
dmap = DungeonMap(ROM)
c = dmap.counts()
diff = {k: (c[k], EXPECT[k]) for k in EXPECT if c[k] != EXPECT[k]}
print("1) 지도 계산 %s" % ("기대값 일치 ✔" if not diff else "★다름 %s" % diff))
fail += bool(diff)

# ── 2) tkinter 그리기 ─────────────────────────────────────────────────────
import tkinter as tk
root = tk.Tk()
root.withdraw()
cv = tk.Canvas(root, width=DW.WIN_W, height=DW.WIN_H)
p = DW.TkPainter(cv)
cases = [(None, "wait"),
         ({"x": 5, "y": 5, "dx": 1, "dy": 0}, "live"),
         ({"x": 72, "y": 44, "dx": 0, "dy": -1}, "stale"),
         ({"x": 200, "y": 10, "dx": 0, "dy": 0}, "live")]
bad_tk = 0
for st, status in cases:
    try:
        DW.render(p, dmap, st, status)
        root.update_idletasks()
        if len(cv.find_all()) < 10:
            bad_tk += 1
    except Exception as e:
        print("   ★%s %s: %r" % (status, st, e))
        bad_tk += 1
root.destroy()
print("2) tk 그리기 %s" % ("4가지 상태 ✔" if not bad_tk else "★%d건 실패" % bad_tk))
fail += bool(bad_tk)

# ── 3) 창의 접속 코드 <-> 브리지 ────────────────────────────────────────────
TMP = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "ds_selftest")
os.makedirs(TMP, exist_ok=True)
subj = os.path.join(TMP, "bridge.lua")
shutil.copyfile(os.path.join(WORK, "ds_bridge.lua"), subj)
runner = os.path.join(TMP, "runner.lua")
open(runner, "w", encoding="utf-8").write('''
local f, e = loadfile([[%s]])
if not f then print("@ERR " .. tostring(e)) emu.exit() return end
local ok, e2 = pcall(f)
if not ok then print("@ERR " .. tostring(e2)) emu.exit() return end
local n, done = 0, false
emu.addEventCallback(function()
  if done then return end
  n = n + 1
  if n %% 200 == 0 then emu.write(0x0780, (n // 200) %% 100, emu.memType.nesMemory) end
  if n >= 30000 then done = true; emu.exit() end
end, emu.eventType.endFrame)
''' % subj.replace("\\", "/"))

proc = subprocess.Popen([mtpaths.MESEN_EXE, "--enableStdout", "--doNotSaveSettings",
                         "--testRunner", runner, ROM],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
q, stop = queue.Queue(), threading.Event()
threading.Thread(target=DW.net_loop, args=(DW.PORT, q, stop), daemon=True).start()
xs, linked = set(), False
t0 = time.time()
while time.time() - t0 < 40 and len(xs) < 5:
    try:
        kind, val = q.get(timeout=0.5)
    except queue.Empty:
        if proc.poll() is not None:
            break
        continue
    if kind == "link":
        linked = linked or val
    else:
        xs.add(val["x"])
stop.set()
try:
    proc.wait(timeout=120)
except subprocess.TimeoutExpired:
    proc.kill()
ok_net = linked and len(xs) >= 3
print("3) 브리지   %s" % ("접속·위치 수신 ✔ (X %s)" % sorted(xs) if ok_net else "★실패 (연결 %s, X %s)" % (linked, sorted(xs))))
fail += not ok_net

print("판정:", "통과 ✔" if fail == 0 else "★%d건 실패" % fail)
sys.exit(1 if fail else 0)
