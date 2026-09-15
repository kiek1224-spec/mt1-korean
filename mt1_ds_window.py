#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""여신전생 1 — 닌텐도 DS 컨셉 두 번째 화면.

실행에 필요한 것은 **이 파일과 ds_bridge.lua 두 개**, 그리고 여신전생1 롬 파일 하나다.
Mesen 에서 ds_bridge.lua 를 실행해 두면 이 창이 붙어서 **지금 있는 구역의 지도**를 크게 그리고
계단·엘리베이터·상자·NPC·고정 전투·텔레포트 표식과 **한글 범례·층 번호·좌표**를 쓴다.
게임 화면에는 아무것도 겹치지 않는다.

    python mt1_ds_window.py [롬]                              # 창 띄우기 (롬 생략 시 작업롬파일의 최신 정상 빌드)
    python mt1_ds_window.py [롬] --check                      # 지도 계산이 기대 숫자를 내는지만 확인
    python mt1_ds_window.py --snapshot a.png --pos 5,5,1,0    # 창 없이 그림만 뽑기 (검증용)

지도 데이터는 롬에서 직접 계산한다 — automap.lua 와 **같은 규칙**이고 숫자까지 대조했다.
규칙과 근거(레이어 뜻, 층표, 구역 나누기)는 automap.lua 머리말에 적어 두었다.
★Mesen 이 일시정지면 위치가 안 온다 — 창에 「멈춤」으로 표시한다.
★tkinter 는 파이썬 기본 포함이라 추가 설치가 없다. 그림 뽑기 모드만 Pillow 를 쓴다.
★2026-09-13 mt1map.py 를 이 파일로 합쳤다(사용자 요청: 실행 파일은 Lua 1 + 파이썬 1).
"""
import argparse
import json
import os
import queue
import socket
import sys
import threading
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))


def _latest_rom():
    """작업롬파일/ 에서 가장 최근의 **정상 빌드** (_FAILED·기준선 base 제외). 없으면 None.
    ★2026-09-15 전에는 v50 파일 이름이 박혀 있어서, 받은 사람은 롬을 꼭 인자로 줘야 했다."""
    d = os.path.join(HERE, "작업롬파일")
    if not os.path.isdir(d):
        return None
    c = [f for f in os.listdir(d) if f.startswith("mt1_kor5b_v") and f.endswith(".nes")
         and "_FAILED" not in f and "base" not in f]
    if not c:
        return None
    return os.path.join(d, max(c, key=lambda f: os.path.getmtime(os.path.join(d, f))))


DEFAULT_ROM = _latest_rom()
PORT = 9876


# ═════════════════════════════════════════════════════════════════════════════
# 1. 지도 데이터 (롬에서 계산)
# ═════════════════════════════════════════════════════════════════════════════
W, H, BLK = 128, 64, 8
BCOLS = W // BLK
UP, DOWN, ELEV, CHEST, NPC, FIGHT = "up", "down", "elev", "chest", "npc", "fight"
WARP, WARPTO = "warp", "warpTo"
KINDS = (UP, DOWN, ELEV, CHEST, NPC, FIGHT, WARP, WARPTO)
# 한글판·원판 모두 이 숫자가 나와야 한다 (automap.lua 와 대조 완료)
# ★2026-09-14 텔레포트 추가: 출발 47 / 도착 29 (38곳 중 8곳은 그 자체가 출발 칸, 1곳은 대화 칸).
#   텔레포트 칸과 겹치는 고정 전투 1곳을 텔레포트로 보여 주므로 전투 48 -> 47.
EXPECT = {"comps": 220, "bigComps": 122, UP: 72, DOWN: 72, ELEV: 25, CHEST: 25, NPC: 127, FIGHT: 47,
          WARP: 47, WARPTO: 29}

MAP_PRG = 0x14004      # 뱅크$0A 의 $8004
PTRTBL = 0x12AF5       # 뱅크$09 의 $AAF5 (블록 6 x 포인터 14)
DX = (-1, 0, 1, 0)     # 면 번호 0=서 1=남 2=동 3=북 (비트 자리 = 번호*2)
DY = (0, 1, 0, -1)
OPP = (2, 3, 0, 1)


class DungeonMap:
    def __init__(self, rom_path):
        d = open(rom_path, "rb").read()
        if d[:4] != b"NES\x1a":
            raise ValueError("NES 롬이 아니다: %s" % rom_path)
        self.prg_size = d[4] * 16384
        self.prg = d[16:16 + self.prg_size]
        self.cells = self.prg[MAP_PRG:MAP_PRG + W * H]
        # 층표: 고정뱅크 CPU $CB7D. 고정뱅크는 PRG 끝에서 두 번째 8KB 라 롬 크기에 따라 자리가 다르다.
        base = self.prg_size - 0x4000 + (0xCB7D - 0xC000)
        ft = self.prg[base:base + 128]
        self.floor_tbl = ft if (len(ft) == 128 and 0xFF not in ft) else None
        self._build_zones()
        self._build_marks()

    # ── 칸 ──────────────────────────────────────────────────────────────────
    def side(self, x, y, s):
        """0 뚫림 / 1 벽 / 3 문"""
        return (self.cells[y * W + x] >> (s * 2)) & 3

    @staticmethod
    def block_of(x, y):
        return (y // BLK) * BCOLS + x // BLK

    def floor_of(self, x, y):
        """(층, 탑). 층표를 못 찾았으면 None."""
        if self.floor_tbl is None:
            return None
        b = self.floor_tbl[self.block_of(x, y)]
        return b >> 4, b & 15

    # ── 구역 ────────────────────────────────────────────────────────────────
    def _build_zones(self):
        ok = lambda v: v == 0 or v == 3
        ft, cells = self.floor_tbl, self.cells
        comp = [-1] * (W * H)
        sizes, boxes, blocks = [], [], []
        for si in range(W * H):
            if comp[si] >= 0:
                continue
            cid = len(sizes)
            comp[si] = cid
            q = deque([si])
            n, x0, y0, x1, y1 = 0, W, H, -1, -1
            bl = set()
            while q:
                i = q.popleft()
                x, y = i % W, i // W
                n += 1
                x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
                bl.add(self.block_of(x, y))
                c = cells[i]
                for s in range(4):
                    nx, ny = x + DX[s], y + DY[s]
                    if not (0 <= nx < W and 0 <= ny < H):
                        continue
                    j = ny * W + nx
                    if comp[j] >= 0:
                        continue
                    # 양쪽 기록이 다 뚫림/문일 때만, 그리고 층표 바이트가 같은 블록끼리만
                    if not ok((c >> (s * 2)) & 3) or not ok((cells[j] >> (OPP[s] * 2)) & 3):
                        continue
                    if ft is not None and ft[self.block_of(x, y)] != ft[self.block_of(nx, ny)]:
                        continue
                    comp[j] = cid
                    q.append(j)
            sizes.append(n)
            boxes.append((x0 - x0 % BLK, y0 - y0 % BLK, (x1 // BLK + 1) * BLK, (y1 // BLK + 1) * BLK))
            blocks.append(bl)
        self.comp, self.comp_size, self.comp_box, self.comp_blocks = comp, sizes, boxes, blocks

    def zone_at(self, x, y):
        """(상자 (x0,y0,x1,y1) - x1·y1 은 끝+1, 구역에 속한 블록번호 집합)"""
        cid = self.comp[y * W + x]
        return self.comp_box[cid], self.comp_blocks[cid]

    # ── 표식 ────────────────────────────────────────────────────────────────
    def _rd(self, cpu):
        """뱅크$08/$09 (CPU $8000~$BFFF) 는 둘 다 PRG 주소 = CPU + $8000."""
        return self.prg[cpu + 0x8000]

    def _each(self, lid, stride, skip_len):
        """6블록의 레이어 lid 표. 끝은 $FF 또는 다음 포인터."""
        ptrs = [self.prg[PTRTBL + i * 2] | (self.prg[PTRTBL + i * 2 + 1] << 8) for i in range(6 * 14)]
        uniq = sorted(set(ptrs))
        for b in range(6):
            w = ptrs[b * 14 + (lid >> 1)]
            if not (0x8000 <= w < 0xC000):
                continue
            stop = next((u for u in uniq if u > w), w + 64)
            k = w + (1 + self._rd(w) if skip_len else 0)
            while k <= stop - stride and self._rd(k) != 0xFF:
                yield self._rd(k), self._rd(k + 1) & 0x3F, k
                k += stride

    def _build_marks(self):
        """겹치는 칸 우선순위 = automap.lua 와 같다: 상자·NPC -> 엘리베이터 -> 계단이 덮어쓰고,
        그 뒤 텔레포트 출발 -> 텔레포트 도착 -> 고정 전투 순서로 빈 칸에만."""
        m = {}
        inmap = lambda x, y: x < W and y < H
        for x, y, k in self._each(0x16, 6, False):
            if inmap(x, y) and (x, y) not in m:
                m[(x, y)] = CHEST if self._rd(k + 2) == 32 else NPC
        for x, y, k in self._each(0x10, 4, True):
            if inmap(x, y):
                m[(x, y)] = ELEV
        for x, y, k in self._each(0x0A, 5, False):
            tx, ty = self._rd(k + 2), self._rd(k + 3)
            if inmap(x, y):
                m[(x, y)] = DOWN
            if inmap(tx, ty) and m.get((tx, ty)) != DOWN:
                m[(tx, ty)] = UP
        # 텔레포트 [X][Y][도착X][도착Y][도착블록][도착층] - 고정뱅크 $FC3A 가 이 표로 순간이동시킨다
        warps = list(self._each(0x0E, 6, False))
        for x, y, k in warps:
            if inmap(x, y) and (x, y) not in m:
                m[(x, y)] = WARP
        for x, y, k in warps:
            tx, ty = self._rd(k + 2), self._rd(k + 3) & 0x3F
            if inmap(tx, ty) and (tx, ty) not in m:
                m[(tx, ty)] = WARPTO
        for x, y, k in self._each(0x14, 3, False):
            if inmap(x, y) and (x, y) not in m:
                m[(x, y)] = FIGHT
        self.marks = m

    def counts(self):
        c = {"comps": len(self.comp_size), "bigComps": sum(1 for n in self.comp_size if n >= 4)}
        for k in KINDS:
            c[k] = 0
        for v in self.marks.values():
            c[v] += 1
        return c


# ═════════════════════════════════════════════════════════════════════════════
# 2. 그리기
# ═════════════════════════════════════════════════════════════════════════════
WIN_W, WIN_H = 520, 700
MAP_X, MAP_Y, MAP_PX = 20, 70, 480
FONT = "Malgun Gothic"

BG, PANEL, ZONE_BG, EDGE = "#0a1622", "#0f2233", "#132b40", "#2c527a"
TXT, SUB = "#dbe8f2", "#7fb8dc"
C_WALL, C_DOOR, C_ME = "#e8e8f0", "#40b4ff", "#ff6040"
STYLE = {                       # automap.lua 와 같은 색·모양
    UP:    ("#ffe040", "fill"),
    DOWN:  ("#4070ff", "fill"),
    ELEV:  ("#40e080", "fill"),
    CHEST: ("#ff9020", "box"),
    NPC:   ("#ff70d0", "dot"),
    FIGHT: ("#ff3030", "cross"),
    WARP:   ("#b070ff", "diamond"),
    WARPTO: ("#b070ff", "odiamond"),
}
LEGEND = [(UP, "올라가는 계단"), (DOWN, "내려가는 계단"), (ELEV, "엘리베이터"),
          (CHEST, "보물상자"), (NPC, "대화 NPC"), (FIGHT, "고정 전투"),
          (WARP, "텔레포트"), (WARPTO, "텔레포트 도착")]


# 창(tkinter)과 그림 파일(Pillow)이 같은 그리기 코드를 쓰게 한다
class TkPainter:
    def __init__(self, canvas):
        self.c = canvas

    def clear(self, bg):
        self.c.delete("all")
        self.c.configure(bg=bg)

    def rect(self, x, y, w, h, fill=None, outline=None, width=1):
        self.c.create_rectangle(x, y, x + w, y + h, fill=fill or "", outline=outline or "",
                                width=width if outline else 0)

    def line(self, x1, y1, x2, y2, col, width=1):
        self.c.create_line(x1, y1, x2, y2, fill=col, width=width, capstyle="projecting")

    def oval(self, x, y, w, h, fill):
        self.c.create_oval(x, y, x + w, y + h, fill=fill, outline="")

    def poly(self, pts, fill):
        self.c.create_polygon(*[v for p in pts for v in p], fill=fill, outline="")

    def text(self, x, y, s, col, px, anchor="nw", bold=False):
        # 음수 크기 = 픽셀 단위 (그림 파일 쪽과 크기를 맞추려고)
        self.c.create_text(x, y, text=s, fill=col, anchor=anchor,
                           font=(FONT, -px, "bold" if bold else "normal"))


class PilPainter:
    ANCHOR = {"nw": "lt", "ne": "rt", "w": "lm", "e": "rm", "center": "mm"}

    def __init__(self, w, h):
        from PIL import Image, ImageDraw
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w, h))
        self.d = ImageDraw.Draw(self.img)
        self.fonts = {}

    def _font(self, px, bold):
        from PIL import ImageFont
        key = (px, bold)
        if key not in self.fonts:
            path = r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf"
            try:
                self.fonts[key] = ImageFont.truetype(path, px)
            except OSError:
                self.fonts[key] = ImageFont.load_default()
        return self.fonts[key]

    def clear(self, bg):
        self.d.rectangle([0, 0, self.w, self.h], fill=bg)

    def rect(self, x, y, w, h, fill=None, outline=None, width=1):
        self.d.rectangle([x, y, x + w, y + h], fill=fill, outline=outline, width=width)

    def line(self, x1, y1, x2, y2, col, width=1):
        self.d.line([x1, y1, x2, y2], fill=col, width=width)

    def oval(self, x, y, w, h, fill):
        self.d.ellipse([x, y, x + w, y + h], fill=fill)

    def poly(self, pts, fill):
        self.d.polygon([tuple(p) for p in pts], fill=fill)

    def text(self, x, y, s, col, px, anchor="nw", bold=False):
        self.d.text((x, y), s, fill=col, font=self._font(px, bold), anchor=self.ANCHOR[anchor])


def draw_mark(p, kind, x, y, cell):
    col, shape = STYLE[kind]
    ins = max(2, int(cell * 0.22))
    if shape == "fill":
        p.rect(x + ins, y + ins, cell - 2 * ins, cell - 2 * ins, fill=col)
    elif shape == "box":
        p.rect(x + ins, y + ins, cell - 2 * ins, cell - 2 * ins, outline=col, width=max(2, cell // 14))
    elif shape == "dot":
        r = max(3, int(cell * 0.17))
        p.oval(x + cell / 2 - r, y + cell / 2 - r, 2 * r, 2 * r, fill=col)
    elif shape in ("diamond", "odiamond"):
        cx, cy, r = x + cell / 2, y + cell / 2, cell / 2 - ins + 1
        pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        if shape == "diamond":
            p.poly(pts, fill=col)
        else:
            wd = max(2, cell // 14)
            for a, b in zip(pts, pts[1:] + pts[:1]):
                p.line(a[0], a[1], b[0], b[1], col, wd)
    else:
        wd = max(2, cell // 12)
        p.line(x + ins, y + ins, x + cell - ins, y + cell - ins, col, wd)
        p.line(x + cell - ins, y + ins, x + ins, y + cell - ins, col, wd)


def draw_player(p, x, y, cell, dx, dy):
    cx, cy = x + cell / 2, y + cell / 2
    r = cell * 0.36
    p.oval(cx - r, cy - r, 2 * r, 2 * r, fill=C_ME)
    if dx or dy:                                  # 게임이 실제로 더하는 dX/dY 쪽으로 삼각형
        t = r * 0.8
        tip = (cx + dx * t, cy + dy * t)
        base = (cx - dx * t * 0.55, cy - dy * t * 0.55)
        px, py = -dy * t * 0.7, dx * t * 0.7
        p.poly([tip, (base[0] + px, base[1] + py), (base[0] - px, base[1] - py)], fill="#ffffff")


def render(p, dmap, state, status):
    p.clear(BG)
    p.text(MAP_X, 16, "여신전생 자동지도", SUB, 14, "nw")

    status_txt = {"live": ("● Mesen 연결됨", "#4ade80"),
                  "stale": ("● Mesen 멈춤 — 일시정지 중이면 풀어 주세요", "#f0a63c"),
                  "wait": ("○ Mesen 연결 대기 중 — Script Window 에서 ds_bridge.lua 실행", "#8fb0c6")}[status]
    p.text(MAP_X, 42, status_txt[0], status_txt[1], 12, "nw")

    p.rect(MAP_X - 1, MAP_Y - 1, MAP_PX + 2, MAP_PX + 2, fill=PANEL, outline=EDGE, width=1)

    inside = state is not None and state["x"] < W and state["y"] < H
    if not inside:
        msg = "던전에 들어가면 지도가 나옵니다" if state is not None else "위치 정보를 기다리는 중"
        p.text(MAP_X + MAP_PX / 2, MAP_Y + MAP_PX / 2, msg, SUB, 16, "center")
    else:
        x, y, dx, dy = state["x"], state["y"], state["dx"], state["dy"]
        fl = dmap.floor_of(x, y)
        if fl is not None:
            p.text(WIN_W - MAP_X, 12, "특수 구역" if fl[0] == 0 else "%d층" % fl[0], TXT, 26, "ne", bold=True)

        (bx0, by0, bx1, by1), blocks = dmap.zone_at(x, y)
        zw, zh = bx1 - bx0, by1 - by0
        cell = min(MAP_PX // max(zw, zh), 56)
        ox = MAP_X + (MAP_PX - zw * cell) // 2
        oy = MAP_Y + (MAP_PX - zh * cell) // 2

        for b in blocks:                                    # 구역 바탕 (블록 단위)
            gx, gy = (b % BCOLS) * BLK, (b // BCOLS) * BLK
            p.rect(ox + (gx - bx0) * cell, oy + (gy - by0) * cell, BLK * cell, BLK * cell, fill=ZONE_BG)

        wd = max(2, cell // 12)
        for cy_ in range(by0, by1):
            for cx_ in range(bx0, bx1):
                if dmap.block_of(cx_, cy_) not in blocks:
                    continue
                X, Y = ox + (cx_ - bx0) * cell, oy + (cy_ - by0) * cell
                for s, seg in ((3, (X, Y, X + cell, Y)), (0, (X, Y, X, Y + cell)),
                               (1, (X, Y + cell, X + cell, Y + cell)), (2, (X + cell, Y, X + cell, Y + cell))):
                    v = dmap.side(cx_, cy_, s)
                    if v:
                        p.line(*seg, C_WALL if v == 1 else C_DOOR, wd)

        for (mx, my), kind in dmap.marks.items():
            if bx0 <= mx < bx1 and by0 <= my < by1 and dmap.block_of(mx, my) in blocks:
                draw_mark(p, kind, ox + (mx - bx0) * cell, oy + (my - by0) * cell, cell)

        draw_player(p, ox + (x - bx0) * cell, oy + (y - by0) * cell, cell, dx, dy)
        p.text(MAP_X, MAP_Y + MAP_PX + 14, "현재 위치 (%d, %d)" % (x, y), TXT, 14, "nw")
        p.text(WIN_W - MAP_X, MAP_Y + MAP_PX + 14, "구역 %d×%d" % (zw, zh), SUB, 14, "ne")

    # 범례
    ly = MAP_Y + MAP_PX + 48
    for i, (kind, label) in enumerate(LEGEND):
        col_x = MAP_X + (i % 3) * 164
        row_y = ly + (i // 3) * 30
        draw_mark(p, kind, col_x, row_y, 22)
        p.text(col_x + 28, row_y + 11, label, TXT, 13, "w")
    wx, wy = MAP_X + 2 * 164, ly + 2 * 30 + 11           # 범례 9번째 자리 (3열 x 3행의 마지막)
    p.line(wx, wy, wx + 24, wy, C_WALL, 2)
    p.text(wx + 30, wy, "벽", SUB, 12, "w")
    p.line(wx + 64, wy, wx + 88, wy, C_DOOR, 2)
    p.text(wx + 94, wy, "문", SUB, 12, "w")


# ═════════════════════════════════════════════════════════════════════════════
# 3. Mesen 연결과 창
# ═════════════════════════════════════════════════════════════════════════════
def net_loop(port, q, stop):
    """접속 -> 줄 단위 JSON 을 큐로. 끊기면 1초 뒤 다시 붙는다."""
    while not stop.is_set():
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1.0)
        except OSError:
            q.put(("link", False))
            time.sleep(1.0)
            continue
        q.put(("link", True))
        s.settimeout(1.0)
        buf = b""
        try:
            while not stop.is_set():
                try:
                    chunk = s.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        q.put(("state", json.loads(line)))
                    except ValueError:
                        pass
        except OSError:
            pass
        finally:
            s.close()
        q.put(("link", False))


def run_window(dmap, port):
    import tkinter as tk
    root = tk.Tk()
    root.title("여신전생 DS 지도")
    root.configure(bg=BG)
    root.resizable(False, False)
    canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg=BG, highlightthickness=0)
    canvas.pack()
    painter = TkPainter(canvas)

    q, stop = queue.Queue(), threading.Event()
    threading.Thread(target=net_loop, args=(port, q, stop), daemon=True).start()
    st = {"link": False, "state": None, "rx": 0.0, "sig": None}

    def poll():
        while True:
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                break
            if kind == "link":
                st["link"] = val
            else:
                st["state"], st["rx"] = val, time.time()
        if not st["link"]:
            status = "wait"
        elif time.time() - st["rx"] > 2.5:            # 브리지는 60프레임마다 한 번은 보낸다
            status = "stale"
        else:
            status = "live"
        sig = (status, json.dumps(st["state"], sort_keys=True))
        if sig != st["sig"]:                          # 바뀔 때만 다시 그린다
            render(painter, dmap, st["state"], status)
            st["sig"] = sig
        root.after(33, poll)

    def on_close():
        stop.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    poll()
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="여신전생 1 DS 컨셉 두 번째 화면")
    ap.add_argument("rom", nargs="?", default=DEFAULT_ROM, help="여신전생1 롬 (원판·한글판 지도 데이터 동일)")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--check", action="store_true", help="지도 계산이 기대 숫자를 내는지만 확인하고 끝낸다")
    ap.add_argument("--snapshot", help="창 대신 이 PNG 로 한 장 그리고 끝낸다")
    ap.add_argument("--pos", help="그림 뽑기용 위치 x,y[,dx,dy]")
    ap.add_argument("--status", default="live", choices=("live", "stale", "wait"))
    a = ap.parse_args()

    if not a.rom or not os.path.exists(a.rom):
        raise SystemExit("롬을 찾을 수 없다: %s\n-> python mt1_ds_window.py <롬 경로>"
                         "   (원판·영어판·한글판 아무거나 된다)" % a.rom)
    dmap = DungeonMap(a.rom)

    if a.check:
        c = dmap.counts()
        diff = {k: (c[k], EXPECT[k]) for k in EXPECT if c[k] != EXPECT[k]}
        print("%s\n   %s\n   %s" % (a.rom, " ".join("%s=%d" % (k, c[k]) for k in EXPECT),
                                  "기대값과 일치 ✔" if not diff else "★다름 %s" % diff))
        sys.exit(1 if diff else 0)

    if a.snapshot:
        state = None
        if a.pos:
            v = [int(t) for t in a.pos.split(",")] + [0, 0]
            state = {"x": v[0], "y": v[1], "dx": v[2], "dy": v[3]}
        p = PilPainter(WIN_W, WIN_H)
        render(p, dmap, state, a.status)
        p.img.save(a.snapshot)
        print("그림:", a.snapshot)
        return
    run_window(dmap, a.port)


if __name__ == "__main__":
    main()
