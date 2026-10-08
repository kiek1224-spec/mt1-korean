#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DS 두 번째 화면 자체검사 — 창을 화면에 띄우지 않고 전부 확인한다.

    python ds_selftest.py

  1) 지도 계산이 기대 숫자를 내는가 (automap.lua 와 같은 규칙)
  2) mt1_ds_window.py 의 tkinter 그리기가 여러 상태에서 도는가 (창은 숨긴 채)
  3) 창의 접속 코드(net_loop)가 헤드리스 Mesen 의 ds_bridge.lua 에 붙어 위치를 받는가
     (러너가 200프레임마다 X 를 바꿔 쓰고, 바뀐 X 를 여러 개 받아야 통과)
  4) 패스워드 계산: 게임이 실제로 받아 준 패스워드 두 개를 풀고 다시 만들기, 기준 경험치, 변조 거부
  5) 오른쪽 패널(창 숨김): MAG·마카·구슬 표시, 자동 입력 버튼·TYPE 명령, 불러온 뒤 확인, 지금 상태로 만들기
  6) 헤드리스 Mesen 끝에서 끝: 타이틀 -> PASS WORD -> 창이 TYPE -> 브리지가 대신 입력 -> 게임이 받고 RAM 이 같다
  7) 전투 정보: 적 표(롬)를 pareido CSV 와 대조 + 전투 세이브를 얹은 헤드리스 Mesen -> 브리지 "b"=1·종류·HP -> 전투 카드

★헤드리스 Mesen 은 임시폴더의 **사본**(mesen_sandbox)으로 돌린다. --testRunner 가 끝날 때 SaveStates 의 슬롯 11 을
  덮어써서, 원래 폴더로 돌리면 사용자의 「롬이름_11.mss」 자동 세이브가 시험 상태로 바뀐다(2026-10-04 실제로 덮였다).

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

def _sandbox_mesen():
    """원래 Mesen 폴더에서 실행 파일·설정만 임시폴더로 복사해 그 사본을 쓴다 (위 ★ 참고)"""
    src, dst = mtpaths.MESEN_DIR, os.path.join(os.environ.get("TEMP", r"C:\Temp"), "mesen_sandbox")
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src):
        if f.lower().endswith((".exe", ".dll", ".txt")) or f == "settings.json":
            s_, d_ = os.path.join(src, f), os.path.join(dst, f)
            if os.path.isfile(s_) and (not os.path.exists(d_) or os.path.getmtime(d_) < os.path.getmtime(s_)):
                shutil.copy2(s_, d_)
    if os.path.isdir(os.path.join(src, "Firmware")):
        shutil.copytree(os.path.join(src, "Firmware"), os.path.join(dst, "Firmware"), dirs_exist_ok=True)
    return os.path.join(dst, "Mesen.exe")


MESEN = _sandbox_mesen()
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
# $07FF bit7 조건(레이어 $16 Y 위 두 비트) — 2026-10-03 사용자 보고 자리(다이달로스 8층·7층)
c1 = dmap.counts(1)
diff1 = {k: (c1[k], DW.EXPECT_W1[k]) for k in DW.EXPECT_W1 if c1[k] != DW.EXPECT_W1[k]}
want_w = {0: {(7, 0): DW.JAKYOU, (9, 5): None, (13, 6): DW.INFO, (4, 5): DW.SHOP, (4, 1): DW.SPRING},
          1: {(7, 0): None, (9, 5): DW.SHOP, (13, 6): DW.JAKYOU, (4, 5): None, (22, 0): DW.SPRING}}
bad_w = [(w, xy, dmap.marks_w[w].get(xy)) for w, d in want_w.items() for xy, k in d.items() if dmap.marks_w[w].get(xy) != k]
print("   진행 상태별 표식 %s" % ("✔ (w=1 숫자 일치, 보고 자리 %d칸)" % sum(map(len, want_w.values()))
                          if not diff1 and not bad_w else "★ w=1 %s / 자리 %s" % (diff1, bad_w)))
fail += bool(diff1 or bad_w)
# 일방통행·로키 칸 — 2026-10-05 사용자 보고 자리(발할라 (75,12) 둘레). 아래 7곳과 막힘은 헤드리스 Mesen 으로 잰 결과다:
#   (75,12)->동 통과·(76,12)->서 막힘, (76,13)->북 통과·(76,12)->남 막힘, (77,12)->서 통과·(76,12)->동 막힘, (75,8)->동 통과·(76,8)->서 막힘,
#   (76,12)<->(76,11) 양쪽 통과. 로키 (79,11): $065E bit2 꺼짐 = 보스전(종류 $E4), 켜짐 = (79,15) 로 순간이동.
ones = {(gx, gy, s) for gx, gy, s, k in dmap.wall_edges(dmap.zone_at(75, 12)[1]) if k == "one"}
want_one = {(75, 8, 2), (75, 12, 2), (76, 13, 3), (77, 12, 0), (77, 13, 1), (77, 13, 2), (77, 14, 0)}
boss_ok = (DW.mark_kind(dmap, 79, 11, DW.FIGHT, 3) == DW.BOSS_WARP and DW.mark_kind(dmap, 79, 11, DW.FIGHT, 7) == DW.WARP
           and DW.mark_kind(dmap, 31, 10, DW.FIGHT, 1) == DW.BOSS_DONE and len(dmap.bosses) == 6)
print("   일방통행·보스 %s" % ("✔ (발할라 실측 7곳, 로키 처치 전/후)" if ones == want_one and boss_ok
                         else "★ 일방 %s / 보스 %s" % (sorted(ones ^ want_one), boss_ok)))
fail += not (ones == want_one and boss_ok)

# ── 2) tkinter 그리기─────────────────────────────────────────────────────
import tkinter as tk
root = tk.Tk()
root.withdraw()
cv = tk.Canvas(root, width=DW.WIN_W, height=DW.WIN_H)
p = DW.TkPainter(cv)
cases = [(None, "wait"),
         ({"x": 5, "y": 5, "dx": 1, "dy": 0}, "live"),
         ({"x": 72, "y": 44, "dx": 0, "dy": -1}, "stale"),
         ({"x": 200, "y": 10, "dx": 0, "dy": 0}, "live"),
         ({"x": 28, "y": 10, "dx": 1, "dy": 0, "f": 1}, "live"),     # 이음매로 이은 층 (다이달로스 1층 24x8)
         ({"x": 33, "y": 29, "dx": 0, "dy": 1, "f": 9}, "live")]     # 지하 1층 (발할라 B1)
book = DW.load_book(ROM)
cases.append(({"x": 5, "y": 5, "dx": 1, "dy": 0, "b": 1, "eg": 0, "ek": [0x92, 0, 0, 0], "ec": [3, 0, 0, 0],
               "hp": [20, 0, 5, 13, 20, 20, 20, 20]}, "live"))                 # 전투 카드 (헤케트 3마리)
bad_tk = 0
for st, status in cases:
    try:
        DW.render(p, dmap, st, status, book)
        root.update_idletasks()
        if len(cv.find_all()) < 10:
            bad_tk += 1
    except Exception as e:
        print("   ★%s %s: %r" % (status, st, e))
        bad_tk += 1
root.destroy()
print("2) tk 그리기 %s" % ("%d가지 상태 ✔" % len(cases) if not bad_tk else "★%d건 실패" % bad_tk))
# 이음매: 다이달로스 1층은 롬에서 떨어진 구획 3개가 24x8 한 층으로 이어져야 한다 (공략집 지도와 같은 모양)
box, places, me = dmap.zone_at(28, 10)
ok_seam = (box[2] - box[0], box[3] - box[1]) == (24, 8) and len(places) == 3
print("   이음매 %s (다이달로스 1층 %dx%d, 구획 %d)" % ("✔" if ok_seam else "★", box[2] - box[0], box[3] - box[1], len(places)))
fail += not ok_seam
ok_fl = DW.floor_name(9) == "지하 1층" and DW.floor_name(10) == "지하 2층" and DW.floor_name(3) == "3층"
print("   층 이름 %s" % ("✔" if ok_fl else "★"))
fail += not ok_fl
fail += bool(bad_tk)

# ── 3) 창의 접속 코드 <-> 브리지 ────────────────────────────────────────────
TMP = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "ds_selftest")
TEST_PORT = 19876                         # 시험 전용 포트(실제 플레이용 9876 과 분리)
os.makedirs(TMP, exist_ok=True)
subj = os.path.join(TMP, "bridge.lua")
shutil.copyfile(os.path.join(WORK, "ds_bridge.lua"), subj)
runner = os.path.join(TMP, "runner.lua")
open(runner, "w", encoding="utf-8").write('''
DS_BRIDGE_PORT = %d   -- 사용자가 켜 둔 Mesen(9876)과 안 겹치게
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
''' % (TEST_PORT, subj.replace("\\", "/")))

proc = subprocess.Popen([MESEN, "--enableStdout", "--doNotSaveSettings",
                         "--testRunner", runner, ROM],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
q, stop = queue.Queue(), threading.Event()
threading.Thread(target=DW.net_loop, args=(TEST_PORT, q, stop), daemon=True).start()
xs, linked, has_f = set(), False, False
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
        has_f = "f" in val and "bs" in val          # 층, 보스 처치 깃발 $065E (2026-10-05)
stop.set()
try:
    proc.wait(timeout=120)
except subprocess.TimeoutExpired:
    proc.kill()
ok_net = linked and len(xs) >= 3 and has_f
print("3) 브리지   %s" % ("접속·위치·층·보스 깃발 수신 ✔ (X %s)" % sorted(xs) if ok_net
                         else "★실패 (연결 %s, X %s, 층·보스 깃발 %s)" % (linked, sorted(xs), has_f)))
fail += not ok_net

# ── 4) 패스워드 계산 ────────────────────────────────────────────────────────
# 웹판 끝에서 끝 시험(편의프로젝트 checks/check3_password.js)에서 게임이 실제로 받아 준 패스워드 두 개
PW_A = ("QUQNLT3E9SP2U3KEDRP6UTKECHL6CQ7", 0, {"naka": [10, 8, 9, 7, 6], "yumi": [6, 11, 7, 8, 8], "level": 1,
        "macca": 0, "exp": 0, "mag": 0, "orb": 0, "equip": [255] * 7, "demons": []})
PW_B = ("E3SH5EKQKR63UQ3W3QE1C3JWBUFHRWTEVX", 5, {"naka": [10, 8, 9, 7, 6], "yumi": [6, 11, 7, 8, 8], "level": 1,
        "macca": 12345, "exp": 15, "mag": 0, "orb": 0, "equip": [21, 41, 56, 50, 24, 44, 49], "demons": [33, 40]})
P = DW.Mt1Password(ROM)
bad_pw = []
for text, salt, want in (PW_A, PW_B):
    ok, st, s = P.decode(text)
    if not ok or any(st[k] != v for k, v in want.items()) or P.encode(st, salt) != text:
        bad_pw.append(text)
ok_lv = [DW.level_exp(v) for v in (2, 6, 10, 61)] == [20, 300, 1380, 361100]
flip = PW_A[0][:5] + ("0" if PW_A[0][5] != "0" else "1") + PW_A[0][6:]
ok_rej = not P.decode(flip)[0]
ok_pw = P.ok and not bad_pw and ok_lv and ok_rej
print("4) 패스워드 %s" % ("지원 판·풀기·다시 만들기·기준 경험치·변조 거부 ✔" if ok_pw
                        else "★실패 (지원 %s, 어긋남 %s, 경험치 %s, 거부 %s)" % (P.ok, bad_pw, ok_lv, ok_rej)))
fail += not ok_pw

# ── 5) 패널(창 숨김): 자원 표시·입력 화면·자동 입력 진행·불러온 뒤 확인 ─────────────
DW.Mt1Panel.NOTES = os.path.join(TMP, "notes_test.json")   # 사용자 수첩(작업폴더)과 섞이지 않게
if os.path.exists(DW.Mt1Panel.NOTES):
    os.remove(DW.Mt1Panel.NOTES)
root = tk.Tk()
root.withdraw()
sent = []
pn = DW.Mt1Panel(root, ROM, sent.append)
pn.on_state({"x": 5, "y": 5, "dx": 0, "dy": 0, "f": 1, "m": 4321, "g": 1234, "o": 7, "p": 1})
pn.var.set(PW_A[0]); root.update()
ok_res = [pn.res[k].cget("text") for k in ("g", "m", "o")] == ["1,234", "4,321", "7"]
ok_btn = str(pn.b_type.cget("state")) == "normal"
pn.type_in()
ok_cmd = bool(sent) and sent[-1].startswith("TYPE ") and sent[-1].count(":") == len(PW_A[0]) + 1
pn.on_pw({"pw": "accepted", "done": 31, "total": 31})
ram = bytearray(2048)                                     # 불러온 뒤 RAM 흉내: 상태 A
for i, v in enumerate(PW_A[2]["naka"]): ram[0x4B9 + i] = v
for i, v in enumerate(PW_A[2]["yumi"]): ram[0x4C9 + i] = v
ram[0x4B4] = 1
pn.on_ram(bytes(ram))
ok_load = pn.type_note.cget("text").startswith("불러왔습니다")
pn.make()
ok_make = pn.out.cget("text").replace(" ", "") == PW_A[0]
root.destroy()
ok_panel = ok_res and ok_btn and ok_cmd and ok_load and ok_make
print("5) 패널     %s" % ("자원 표시·자동 입력 버튼·TYPE 명령·불러온 뒤 확인·지금 상태로 만들기 ✔" if ok_panel
                        else "★실패 (자원 %s, 버튼 %s, 명령 %s, 확인 %s, 만들기 %s)" % (ok_res, ok_btn, ok_cmd, ok_load, ok_make)))
fail += not ok_panel

# ── 6) 헤드리스 Mesen 끝에서 끝: 타이틀 -> PASS WORD -> 창이 TYPE -> 브리지가 대신 입력 -> 게임이 받음 ──
runner6 = os.path.join(TMP, "runner_pw.lua")
open(runner6, "w", encoding="utf-8").write('''
DS_BRIDGE_PORT = %d   -- 사용자가 켜 둔 Mesen(9876)과 안 겹치게
local f, e = loadfile([[%s]])
if not f then print("@ERR " .. tostring(e)) emu.exit() return end
local ok, e2 = pcall(f)
if not ok then print("@ERR " .. tostring(e2)) emu.exit() return end
local n = 0
emu.addEventCallback(function() n = n + 1; if n >= 60000 then emu.exit() end end, emu.eventType.endFrame)
emu.addEventCallback(function()           -- 타이틀에서 아래(PASS WORD) -> START
  if n >= 400 and n < 408 then emu.setInput({ down = true }, 0) end
  if n >= 440 and n < 448 then emu.setInput({ start = true }, 0) end
end, emu.eventType.inputPolled)
''' % (TEST_PORT, subj.replace("\\", "/")))
proc = subprocess.Popen([MESEN, "--enableStdout", "--doNotSaveSettings", "--testRunner", runner6, ROM],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
q, out_q, stop = queue.Queue(), queue.Queue(), threading.Event()
threading.Thread(target=DW.net_loop, args=(TEST_PORT, q, stop, out_q), daemon=True).start()
r6 = {"screen": False, "typed": None, "ram": None, "res": False}
t0 = time.time()
while time.time() - t0 < 90:
    try:
        kind, val = q.get(timeout=0.5)
    except queue.Empty:
        if proc.poll() is not None:
            break
        continue
    if kind == "state":
        r6["res"] = r6["res"] or all(k in val for k in ("m", "g", "o", "p"))
        if val.get("p") == 1 and not r6["screen"]:
            r6["screen"] = True
            out_q.put("TYPE " + ",".join("%d:%d" % ct for ct in P.cells_for(PW_A[0])))
    elif kind == "pw" and val["pw"] not in ("typing", "submitted"):
        r6["typed"] = val
        out_q.put("RAM")
    elif kind == "ram" and r6["typed"]:
        r6["ram"] = val
        break
stop.set()
proc.kill()
got = P.read_state(r6["ram"]) if r6["ram"] else None
ok_e2e = (r6["typed"] or {}).get("pw") == "accepted" and got is not None and \
    all(got[k] == v for k, v in PW_A[2].items()) and r6["res"]
print("6) Mesen    %s" % ("PASS WORD 자동 입력 -> 게임이 받음 -> RAM == 패스워드 내용, 자원 값 수신 ✔ (%.0f초)" % (time.time() - t0)
                        if ok_e2e else "★실패 (입력 화면 %s, 결과 %s, 자원 %s, 상태 %s)" %
                        (r6["screen"], r6["typed"], r6["res"], got and {k: got[k] for k in PW_A[2]})))
fail += not ok_e2e

# ── 7) 전투 정보 ────────────────────────────────────────────────────────────
CSV = os.path.join(WORK, "참고자료", "pareido_aside_20260928", "mt1_demons.csv")
if os.path.exists(CSV):
    ok_tbl, bad_tbl, n_tbl = DW.check_enemies(DW.EnemyBook(ROM), CSV)
    print("7) 적 표    %s" % ("pareido CSV %d마리와 HP·능력치·경험치·마카·MAG·종족 일치 ✔" % n_tbl if ok_tbl
                             else "★%d마리 다름 %s" % (len(bad_tbl), bad_tbl[:3])))
    fail += not ok_tbl
else:
    print("7) 적 표    (pareido CSV 가 없어 대조 건너뜀)")
# 전투 세이브(사용자 v33 「전투프롬프트」, 헤케트 1마리 남음)를 그 세이브를 만든 롬에 얹어 브리지가 보내는 값을 본다
BSAVE = os.path.join(mtpaths.SAVEDIR, "mt1_kor5b_v33_전투프롬프트_1.mss")
BROM = os.path.join(WORK, "작업롬파일", "mt1_kor5b_v33_전투프롬프트.nes")
if os.path.exists(BSAVE) and os.path.exists(BROM):
    shutil.copyfile(BSAVE, os.path.join(TMP, "battle.mss"))
    runner7 = os.path.join(TMP, "runner_battle.lua")
    open(runner7, "w", encoding="utf-8").write('''
DS_BRIDGE_PORT = %d
local f, e = loadfile([[%s]])
if not f then print("@ERR " .. tostring(e)) emu.exit() return end
local ok, e2 = pcall(f)
if not ok then print("@ERR " .. tostring(e2)) emu.exit() return end
local loaded, n = false, 0
emu.addMemoryCallback(function()
  if loaded then return end
  local h = io.open([[%s]], "rb"); local d = h:read("*all"); h:close()
  pcall(function() emu.loadSavestate(d) end); loaded = true
end, emu.callbackType.exec, 0x8000, 0xFFFF)
emu.addEventCallback(function() n = n + 1; if n >= 3000 then emu.exit() end end, emu.eventType.endFrame)
''' % (TEST_PORT, subj.replace("\\", "/"), os.path.join(TMP, "battle.mss").replace("\\", "/")))
    proc = subprocess.Popen([MESEN, "--enableStdout", "--doNotSaveSettings", "--testRunner", runner7, BROM],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    q, stop = queue.Queue(), threading.Event()
    threading.Thread(target=DW.net_loop, args=(TEST_PORT, q, stop), daemon=True).start()
    got7, t0 = None, time.time()
    while time.time() - t0 < 60:
        try:
            kind, val = q.get(timeout=0.5)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        if kind == "state" and val.get("b") == 1:
            got7 = val
            break
    stop.set()
    proc.kill()
    ok7 = False
    if got7:
        g = got7["eg"] & 3
        info = book.info(got7["ek"][g]) if book else None
        alive = DW.alive_hp(got7["hp"], got7["ec"][g])
        pp = DW.PilPainter(DW.WIN_W, DW.WIN_H)
        DW.render(pp, dmap, got7, "live", book)
        pp.img.save(os.path.join(TMP, "battle_card.png"))
        ok7 = bool(info) and info["name"] == "헤케트" and info["hp"] == 20 and got7["ec"][g] == 1 and alive == [5]
        print("   전투 브리지 %s" % ("b=1 · %s(%s) %d마리 · 남은 HP %s/%d · 카드 %s ✔"
                                 % (info["name"], info["race"], got7["ec"][g], alive, info["hp"],
                                    os.path.join(TMP, "battle_card.png")) if ok7
                                 else "★ %s / %s" % (got7, info and info["name"])))
    else:
        print("   전투 브리지 ★전투 상태(b=1)를 못 받았다")
    fail += not ok7
else:
    print("   전투 브리지 (v33 전투 세이브·롬이 없어 건너뜀)")

print("판정:", "통과 ✔" if fail == 0 else "★%d건 실패" % fail)
sys.exit(1 if fail else 0)
