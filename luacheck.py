#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""automap.lua 를 Mesen 헤드리스에 실제로 얹어 **문법 + 초기화 + 프레임 실행**까지 본다.

★한글 경로면 io/loadfile 이 죽으므로 ASCII 임시폴더로 복사해서 검사한다
  (이 프로젝트가 mrun.py 에서 이미 겪은 함정).
"""
import os
import re
import shutil
import subprocess
import sys

# ★2026-09-15 절대경로(개인 폴더)와 v50 롬 이름이 박혀 있던 것을 파일 위치 기준으로 바꿨다(배포 준비).
WORKDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORKDIR)
import mtpaths
import mt1_ds_window as _DW

TARGET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORKDIR, "automap.lua")
ROM = sys.argv[2] if len(sys.argv) > 2 else _DW.DEFAULT_ROM     # 작업롬파일의 최신 정상 빌드
if not ROM or not os.path.exists(ROM):
    raise SystemExit("롬이 없다 -> python luacheck.py <lua> <롬> [프레임]")
FRAMES = int(sys.argv[3]) if len(sys.argv) > 3 else 20

TMP = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "luacheck")
os.makedirs(TMP, exist_ok=True)
copy = os.path.join(TMP, "subject.lua")
shutil.copyfile(TARGET, copy)

harness = os.path.join(TMP, "harness.lua")
open(harness, "w", encoding="utf-8").write('''
local path = [[%s]]
local f, err = loadfile(path)
if not f then
  print("@SYNTAX FAIL " .. tostring(err))
  emu.exit(); return
end
print("@SYNTAX OK")
local ok, err2 = pcall(f)
if not ok then
  print("@INIT FAIL " .. tostring(err2))
  emu.exit(); return
end
print("@INIT OK")
-- 스크립트가 AUTOMAP_INFO 같은 진단 표를 남기면 같이 찍는다 (파이썬 계산과 대조용)
if type(AUTOMAP_INFO) == "table" then
  local ks = {}
  for k, v in pairs(AUTOMAP_INFO) do ks[#ks + 1] = k .. "=" .. tostring(v) end
  table.sort(ks)
  print("@INFO " .. table.concat(ks, " "))
end
-- ★emu.exit() 뒤에도 endFrame 콜백은 몇 번 더 돈다. 깃발로 한 번만 찍는다
--   (안 그러면 로그가 수십만 줄로 분다 - 2026-09-12 에 겪었다).
local n, done = 0, false
emu.addEventCallback(function()
  if done then return end
  n = n + 1
  if n >= %d then done = true; print("@FRAMES OK " .. n); emu.exit() end
end, emu.eventType.endFrame)
''' % (copy.replace("\\", "/"), FRAMES))

p = subprocess.run([mtpaths.MESEN_EXE, "--enableStdout", "--doNotSaveSettings",
                    "--testRunner", harness, os.path.abspath(ROM)],
                   capture_output=True, text=True, timeout=180,
                   encoding="utf-8", errors="replace")
out = p.stdout or ""
print("대상 :", TARGET)
print("롬   :", os.path.basename(ROM))
print("-" * 70)
marks = [l for l in out.splitlines() if l.startswith("@")]
errs = [l for l in out.splitlines()
        if re.search(r"error|Error|stack traceback|attempt to", l)]
for l in marks:
    print(" ", l)
if errs:
    print("\n★런타임 에러로 보이는 줄:")
    for l in errs[:20]:
        print("   ", l)
ok = any(l.startswith("@FRAMES OK") for l in marks) and not errs
print("-" * 70)
print("판정:", "통과 ✔" if ok else "★실패")
sys.exit(0 if ok else 1)
