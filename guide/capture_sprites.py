#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""도감용 악마 그림 — 헤드리스 Mesen 에서 적마다 전투를 띄워 게임이 그린 스프라이트를 덤프해 PNG 로 만든다.

    python 공략사이트/capture_sprites.py            # 덤프(약 5분) + 그림 -> 공략사이트/sprites/XX.png
    python 공략사이트/capture_sprites.py --render   # 이미 받은 덤프로 그림만 다시

방법 (2026-10-05):
  - 원판 롬 + 원판 필드 세이브(SaveStates 「Digital Devil Story - Megami Tensei (Japan)_2.mss」)를 임시폴더 사본 Mesen 에 얹는다
    (--testRunner 가 슬롯 11 을 덮어쓰므로 사본으로 돌린다, ds_selftest 와 같은 이유).
  - $0139 = 1 이면 다음 걸음에서 랜덤 전투가 반드시 난다(뱅크0D $BE6F). 걷기는 위/오른쪽 입력을 번갈아 준다.
  - 적을 다 고른 직후 뱅크0D $BDFE 에서 무리를 1개로 줄이고 종류 $0610 을 원하는 값(0x80|종류)으로 바꾼다.
  - 전투 시작 90·150·210 프레임에 OAM 256B + 팔레트 32B + PPU $0000-$1FFF + 스크린샷을 덤프한다(마지막 것을 쓴다).
  - 그림 = 3D 창 안 스프라이트 중 팔레트 3(달 아이콘·커서 = UI)을 뺀 것. 색은 스크린샷에서 그 자리 색을 배워 쓴다.
  - 루시퍼($E7)는 배경 타일로 그려져(고정 $E8EB -> $E952) 스크린샷의 창을 잘라 쓴다.
  - 헤카테($E5)는 라토스상으로 실체화하기 전에는 그려지지 않는다. 그래서 보스전($065F=2)으로 띄우고 라토스상 깃발 $056A bit2 를
    켠 뒤 명령을 A 로 확정시키면 뱅크0D $A614 -> $A646 -> $A74F 가 실체화 연출(고정 $E8EB)을 돌린다. $06A9 = 3 이 된 뒤에 덤프.
    그동안 파티 HP 는 999 로 붙잡아 둔다(안 그러면 확정 전에 전멸한다).
  - 베르제붑($DD)·포그($EC)는 그림 머리가 배경 팔레트($0784, 고정 $E7E8)로 가고 스프라이트는 빈 타일이다. 모습 대신 3D 화면
    팔레트를 바꿔 새까맣게(베르제붑) / 회색 안개처럼(포그) 만드는 연출이라 스크린샷의 창을 잘라 쓰고 설명을 붙인다.
  - Mesen 이 가끔 중간에 멈추면(같은 적이 다음엔 됨) 덤프가 없는 종류만 골라 다시 돈다.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, WORK)
import mtpaths  # noqa: E402
import mt1_ds_window as DW  # noqa: E402

TMP = os.path.join(os.environ.get("TEMP", r"C:\Temp"), "mt1_spr")          # Lua io 는 ASCII 경로만
OUT = os.path.join(HERE, "sprites")
ROM = os.path.join(WORK, "archive", "roms", "mt1_orig_jp.nes")
STATE = os.path.join(mtpaths.SAVEDIR, "Digital Devil Story - Megami Tensei (Japan)_2.mss")
NO_PICTURE = {}
FROM_SCREEN = {0xE7, 0xDD, 0xEC}
NOTES = {0xE5: "라토스상으로 실체화한 모습", 0xDD: "모습 없이 화면이 새까매짐", 0xEC: "모습 없이 화면이 안개처럼 흐려짐"}
VIEW = (16, 16, 176, 120)


def sandbox():
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


LUA = r'''
local T = "@T@"
local kinds = {@KINDS@}
local waits = {90, 150, 210}
local h = io.open(T.."/state.mss", "rb"); local SD = h:read("*all"); h:close()
local log = io.open(T.."/log.txt", "a")
local M = emu.memType
local function rd(a) return emu.read(a, M.nesMemory) end
local function wr(a, v) emu.write(a, v, M.nesMemory) end
local idx, phase, wait, cur, mat = 0, "load", 0, nil, nil
local function dump(name)
  local t = {}
  for i = 0, 255 do t[#t+1] = string.char(emu.read(i, M.nesSpriteRam)) end
  for i = 0, 31 do t[#t+1] = string.char(emu.read(i, M.nesPaletteRam)) end
  for i = 0, 0x1FFF do t[#t+1] = string.char(emu.read(i, M.nesPpuMemory)) end
  local f = io.open(T.."/"..name..".bin", "wb"); f:write(table.concat(t)); f:close()
  local ok, png = pcall(emu.takeScreenshot)
  if ok and png then local g = io.open(T.."/"..name..".png", "wb"); g:write(png); g:close() end
end
emu.addMemoryCallback(function()           -- 적을 다 고른 직후: 1무리·원하는 종류로
  if cur and rd(0xBE00) == 0xBD and rd(0xBE01) == 0x0C then
    wr(0x060C, 1); wr(0x060D, 0); wr(0x060E, 0); wr(0x060F, 0)
    wr(0x0610, cur); wr(0x0611, 0); wr(0x0612, 0); wr(0x0613, 0)
    if cur == 0xE5 then wr(0x065F, 2); wr(0x056A, rd(0x056A) | 0x04) end   -- 헤카테: 보스전 + 라토스상
  end
end, emu.callbackType.exec, 0xBDFE, 0xBDFE)
emu.addEventCallback(function()            -- 걷기: 위/오른쪽을 번갈아
  if phase == "walk" then
    local b = ((wait // 90) % 2 == 1) and "right" or "up"
    if wait % 8 < 4 then emu.setInput({ [b] = true }, 0) end
  elseif phase == "battle" and cur == 0xE5 and wait > 60 and wait % 16 < 4 then
    emu.setInput({ a = true }, 0)                                         -- 명령을 골라 확정
  end
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()           -- NMI 마다 한 번
  if phase == "load" then
    idx = idx + 1
    if idx > #kinds then log:write("done\n"); log:close(); emu.exit() return end
    cur = kinds[idx]; emu.loadSavestate(SD); phase = "walk"; wait = 0; mat = nil
    return
  end
  wait = wait + 1
  if phase == "walk" then
    wr(0x0139, 1)
    if rd(0x0690) ~= 0 then phase = "battle"; wait = 0 end
    if wait > 1500 then log:write(string.format("FAIL %d\n", cur)); log:flush(); phase = "load" end
  elseif phase == "battle" and cur == 0xE5 then
    for _, a in ipairs({0x04B5, 0x04B7, 0x04C3, 0x04C5}) do wr(a, 0xE7); wr(a + 1, 0x03) end
    if mat == nil and rd(0x06A9) == 3 then mat = wait end
    for i = 1, 3 do if mat and wait == mat + 40 * i then dump(string.format("k%02X_%d", cur, i)) end end
    if mat and wait >= mat + 120 then log:write(string.format("ok %d\n", cur)); log:flush(); phase = "load" end
    if wait > 3000 then log:write(string.format("FAIL %d\n", cur)); log:flush(); phase = "load" end
  elseif phase == "battle" then
    for i, w in ipairs(waits) do
      if wait == w then dump(string.format("k%02X_%d", cur, i)) end
    end
    if wait >= waits[#waits] then log:write(string.format("ok %d\n", cur)); log:flush(); phase = "load" end
  end
end, emu.callbackType.exec, 0xC082, 0xC082)
'''


def kinds_of(book):
    return [0x80 | k for k in range(128) if book.record(k) is not None and any(book.record(k))]


def capture(kinds, mesen):
    os.makedirs(TMP, exist_ok=True)
    shutil.copyfile(ROM, os.path.join(TMP, "orig.nes"))
    shutil.copyfile(STATE, os.path.join(TMP, "state.mss"))
    for attempt in range(4):
        todo = [k for k in kinds if k not in NO_PICTURE and not os.path.exists(os.path.join(TMP, "k%02X_3.bin" % k))]
        if not todo:
            return
        print("덤프 %d종 (시도 %d)" % (len(todo), attempt + 1))
        lua = LUA.replace("@T@", TMP.replace("\\", "/")).replace("@KINDS@", ",".join(str(k) for k in todo))
        p = os.path.join(TMP, "capture.lua")
        open(p, "w", encoding="utf-8").write(lua)
        try:
            subprocess.run([mesen, "--enableStdout", "--doNotSaveSettings", "--testRunner", p, os.path.join(TMP, "orig.nes")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
        except subprocess.TimeoutExpired:
            print("  시간 초과 — 남은 것만 다시")


def load(name):
    b = open(os.path.join(TMP, name + ".bin"), "rb").read()
    return b[:256], b[256:288], b[288:]


def demon_sprites(oam):
    out = []
    for i in range(64):
        y, t, a, x = oam[4 * i:4 * i + 4]
        if y >= 0xEF or (a & 3) == 3:
            continue
        y += 1
        if VIEW[0] <= x + 4 < VIEW[2] and VIEW[1] <= y + 4 < VIEW[3]:
            out.append((x, y, t, a))
    return out


def tile(chr_, t, fx, fy):
    rows = []
    for r in range(8):
        lo, hi = chr_[t * 16 + r], chr_[t * 16 + 8 + r]
        row = [((lo >> (7 - c)) & 1) | (((hi >> (7 - c)) & 1) << 1) for c in range(8)]
        rows.append(row[::-1] if fx else row)
    return rows[::-1] if fy else rows


def pixels(img):
    return list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())


def save_indexed(img, path):
    """색이 몇 개뿐이라 팔레트 PNG(0번 = 투명)로 저장한다 — RGBA 의 1/3 크기"""
    from PIL import Image
    colors = sorted({p[:3] for p in pixels(img) if p[3]})
    pi = Image.new("P", img.size, 0)
    pi.putpalette([0, 0, 0] + [v for c in colors for v in c])
    look = {c: i + 1 for i, c in enumerate(colors)}
    pi.putdata([look[p[:3]] if p[3] else 0 for p in pixels(img)])
    pi.save(path, optimize=True, transparency=0)


def render_all(kinds):
    from PIL import Image
    # 색: 앞에 그려진 스프라이트 픽셀 자리의 스크린샷 색 (Mesen 기본 팔레트 그대로)
    votes = {}
    for k in kinds:
        for i in (1, 2, 3):
            n = "k%02X_%d" % (k, i)
            if not os.path.exists(os.path.join(TMP, n + ".png")):
                continue
            oam, pal, chr_ = load(n)
            shot = Image.open(os.path.join(TMP, n + ".png")).convert("RGB")
            for x, y, t, a in demon_sprites(oam)[:12]:
                if a & 0x20:
                    continue
                for r, row in enumerate(tile(chr_, t, a & 0x40, a & 0x80)):
                    for c, v in enumerate(row):
                        if v and x + c < 256 and y + r < 240:
                            d = votes.setdefault(pal[16 + 4 * (a & 3) + v] & 0x3F, {})
                            rgb = shot.getpixel((x + c, y + r))
                            d[rgb] = d.get(rgb, 0) + 1
    cmap = {i: max(d.items(), key=lambda t: t[1])[0] for i, d in votes.items()}
    os.makedirs(OUT, exist_ok=True)
    made, missing = {}, set()
    def draw(n):
        oam, pal, chr_ = load(n)
        sp = demon_sprites(oam)
        if not sp:
            return None
        x0, y0 = min(s[0] for s in sp), min(s[1] for s in sp)
        x1, y1 = max(s[0] for s in sp) + 8, max(s[1] for s in sp) + 8
        img = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        px = img.load()
        for x, y, t, a in reversed(sp):          # OAM 앞 번호가 위
            for r, row in enumerate(tile(chr_, t, a & 0x40, a & 0x80)):
                for c, v in enumerate(row):
                    if v:
                        idx = pal[16 + 4 * (a & 3) + v] & 0x3F
                        if idx not in cmap:
                            missing.add(idx)
                        px[x + c - x0, y + r - y0] = cmap.get(idx, NES_FALLBACK.get(idx, (255, 0, 255))) + (255,)
        return img if img.getbbox() else None

    for k in kinds:
        if k in NO_PICTURE:
            continue
        names = ["k%02X_%d" % (k, i) for i in (3, 2, 1) if os.path.exists(os.path.join(TMP, "k%02X_%d.bin" % (k, i)))]
        if not names:
            continue
        if k in FROM_SCREEN:
            img = Image.open(os.path.join(TMP, names[0] + ".png")).convert("RGBA").crop((16, 16, 176, 112))
        else:
            # 깜빡이거나 움직이는 악마가 있어(샤도우의 눈 등) 세 번의 덤프 중 그림이 가장 많은 것을 쓴다
            imgs = [im for im in (draw(n) for n in names) if im is not None]
            if not imgs:
                continue
            img = max(imgs, key=lambda im: sum(1 for p in pixels(im) if p[3]))
        save_indexed(img, os.path.join(OUT, "%02X.png" % (k & 0x7F)))
        made[k] = img.size
    json.dump({"%02X" % (k & 0x7F): v for k, v in NO_PICTURE.items()}, open(os.path.join(OUT, "none.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump({"%02X" % (k & 0x7F): v for k, v in NOTES.items()}, open(os.path.join(OUT, "notes.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    return made, missing, cmap


# 스크린샷에서 못 배운 색만 쓰는 대체값 (2C02 근사)
NES_FALLBACK = {0x01: (0, 30, 146), 0x02: (19, 0, 160), 0x03: (60, 0, 139), 0x05: (107, 0, 48), 0x06: (106, 18, 0),
                0x07: (79, 36, 0), 0x08: (49, 56, 0), 0x09: (0, 70, 0), 0x0A: (0, 72, 0), 0x0B: (0, 64, 16),
                0x0C: (0, 50, 77), 0x11: (13, 85, 232), 0x12: (65, 59, 255), 0x13: (125, 33, 255), 0x14: (165, 25, 193),
                0x15: (174, 31, 99), 0x16: (172, 50, 0), 0x17: (141, 84, 0), 0x18: (99, 103, 0), 0x19: (33, 124, 0),
                0x1A: (0, 128, 0), 0x1B: (0, 120, 60), 0x1C: (0, 100, 142), 0x21: (83, 160, 255), 0x22: (130, 136, 255),
                0x23: (180, 122, 255), 0x24: (240, 114, 255), 0x25: (251, 117, 191), 0x26: (251, 133, 92),
                0x27: (229, 162, 0), 0x28: (183, 180, 0), 0x29: (118, 196, 0), 0x2A: (70, 203, 40), 0x2B: (58, 195, 117),
                0x2C: (55, 175, 205), 0x30: (255, 255, 255), 0x31: (176, 216, 255), 0x32: (192, 196, 255),
                0x33: (219, 188, 255), 0x34: (251, 187, 255), 0x35: (253, 190, 225), 0x36: (253, 200, 179),
                0x37: (244, 214, 155), 0x38: (226, 222, 140), 0x39: (196, 232, 145), 0x3A: (174, 236, 171),
                0x3B: (171, 233, 205), 0x3C: (173, 223, 247), 0x00: (102, 102, 102), 0x10: (173, 173, 173),
                0x20: (236, 236, 236), 0x2D: (79, 79, 79), 0x3D: (184, 184, 184), 0x0F: (0, 0, 0), 0x1D: (0, 0, 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true", help="이미 받은 덤프로 그림만 다시 만든다")
    a = ap.parse_args()
    book = DW.EnemyBook(ROM)
    kinds = kinds_of(book)
    if not a.render:
        capture(kinds, sandbox())
    made, missing, cmap = render_all(kinds)
    lost = [k for k in kinds if k not in made and k not in NO_PICTURE]
    print("그림 %d종 -> %s  (색 %d개 배움%s)" % (len(made), OUT, len(cmap),
                                          ", 대체색 %s" % sorted("%02X" % i for i in missing) if missing else ""))
    print("그림 없음(의도): %s" % ", ".join(book.name(k) for k in NO_PICTURE))
    if lost:
        print("★덤프가 없거나 비어 못 만든 것: %s" % ", ".join("%02X %s" % (k, book.name(k)) for k in lost))


if __name__ == "__main__":
    main()
