#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""여신전생 1 — 닌텐도 DS 컨셉 두 번째 화면.

실행에 필요한 것은 **이 파일과 ds_bridge.lua 두 개**, 그리고 여신전생1 롬 파일 하나다.
Mesen 에서 ds_bridge.lua 를 실행해 두면 이 창이 붙어서 **지금 있는 구역의 지도**를 크게 그리고
계단·엘리베이터·상자·아메지스트·정보·사람·가게·회복의 샘·여신상·고정 전투·텔레포트 표식과
**한글 범례·층 번호(지하 포함)·좌표**를 쓴다. 게임 화면에는 아무것도 겹치지 않는다.
★2026-10-02 이음매(레이어 $18)를 따라 롬에서 떨어진 구획을 이어 붙여 공략집 지도와 같은 층 모양으로 그린다.
★2026-10-03 오른쪽 패널: **MAG·마카·구슬 실시간 표시**와 **패스워드**(지금 상태로 만들기 · 복사 · 붙여넣은 패스워드 풀이 ·
  PASS WORD 화면 자동 입력 · 수첩 mt1_password_notes.json, 게임이 보여 준 패스워드 자동 기록). 계산은 「1-2. 패스워드」.
★2026-10-04 전투 중에는 지도 대신 **적 카드**(이름·종족·마릿수·마리별 HP·능력치·행동 비율·기본 보상)를 그린다.
  롬의 적 표에서 읽는다 — 「1-3. 적 악마 정보」. 브리지가 전투 깃발 $0690 과 적 RAM 을 같이 보낸다.
★2026-10-05 (사용자 보고 「벽인데 지나간다」「일방통행 구분」「로키 자리」) 벽을 경계마다 한 번, 게임 속 옆 칸끼리 비교해 그린다.
  한쪽 면만 막힌 경계는 **일방통행 화살표**(DungeonMap.wall_edges). 보스 칸은 처치 깃발 $065E(브리지 "bs")를 따라
  처치 전 ✕ / 처치 뒤 회색 ✕, 로키 (79,11)은 처치 전 ✕+작은 텔레포트 / 처치 뒤 텔레포트(_build_bosses).

    python mt1_ds_window.py [롬]                              # 창 띄우기 (롬 생략 시 작업롬파일의 최신 정상 빌드)
    python mt1_ds_window.py [롬] --check                      # 지도 계산이 기대 숫자를 내는지만 확인
    python mt1_ds_window.py --snapshot a.png --pos 5,5,1,0    # 창 없이 그림만 뽑기 (검증용)
    python mt1_ds_window.py --snapshot b.png --battle 146,3,20,5,13   # 전투 카드 그림 (종류 $92 헤케트 3마리)

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
INFO, SHOP, SPRING, STATUE, AMETHYST = "info", "shop", "spring", "statue", "amethyst"
JAKYOU = "jakyou"
KINDS = (UP, DOWN, ELEV, CHEST, AMETHYST, INFO, SHOP, SPRING, JAKYOU, STATUE, NPC, FIGHT, WARP, WARPTO)
# 레이어 $16 의 종류 값 -> 표식 (2026-10-02 공략집 dds.opatil.com 아이콘과 대조해 정했다.
#   값 7 = INFO 59곳, 13 = 아메지스트 8, 27 = 여신상 5, 28 = 회복의 샘, 4 가게 / 6 라그의 가게).
#   그 밖의 값은 사람·이벤트(대화 NPC). 디스패치 표는 고정뱅크 $F544 (값 x2).
#   ★2026-10-03 값 1 = 사교의 관(처리기 $F5E3 — 이 처리기로 가는 값은 1 하나뿐)을 따로 표시한다(사용자 보고).
L16_KIND = {32: CHEST, 7: INFO, 4: SHOP, 6: SHOP, 28: SPRING, 27: STATUE, 13: AMETHYST, 1: JAKYOU}
# ★2026-10-03 레이어 $16 은 Y 바이트 위 두 비트가 **조건**이다(조회 $E295 의 $E2E9~, 레이어 $16 일 때만):
#   0x40 = $07FF bit7 이 0 일 때만, 0x80 = $07FF bit7 이 1 일 때만 있는 칸. ★$07FF bit7 = 裏 시나리오(2026-10-04 공략집 裏 페이지와 대조) — 裏에서 다이달로스 탑의
#   가게·회복의 샘·사교의 관·상자 등이 자리를 옮긴다(156칸 중 25칸). 전에는 두 상태를 한 지도에 겹쳐 찍어
#   「없는 가게가 보인다」「사교의 관 자리에 다른 표식」이 났다(사용자 보고). 그래서 표식을 상태별로 따로 만들고
#   브리지가 보내는 "w"($07FF bit7)로 고른다. 숫자 확인(EXPECT)은 처음 상태 w=0 기준.
FLAG_W = 0x07FF
# 한글판·원판 모두 이 숫자가 나와야 한다 (automap.lua 와 대조 완료)
# ★2026-09-14 텔레포트 추가: 출발 47 / 도착 29 (38곳 중 8곳은 그 자체가 출발 칸, 1곳은 대화 칸).
# ★2026-10-02 공략집 대조로 고침: 올라가는 계단 = $08 출발 칸(전에는 $0A 도착 칸이라 (95,12)로 한 칸 어긋났다),
#   고정 전투를 텔레포트보다 먼저 찍는다(발할라 (79,11) 보스가 가려졌었다 -> 전투 48, 텔레포트 46),
#   대화 칸을 종류별로 나눴다, 구역은 이음매(레이어 $18)를 따라 잇는다.
#   이음매 74개(76항목 중 같은 칸 중복 1·특수 도착 (56,12) 1 제외)로 구역 220 -> 203, 자리 충돌 0.
#   이은 모양은 공략집 층 지도 49장과 칸 단위로 맞는다(참고자료/공략집대조/layout_check.py).
# ★2026-10-03 $07FF 조건을 따르게 되며 처음 상태(w=0) 숫자로 바꿨다(전에는 두 상태를 겹친 상자 25·INFO 66·가게 11·샘 3·NPC 34).
#   바뀐 상태(w=1)는 EXPECT_W1. 원판·한글판·영어판 세 롬이 같다.
EXPECT = {"comps": 203, "bigComps": 108, "seams": 74, "conflicts": 0, UP: 72, DOWN: 72, ELEV: 25,
          CHEST: 24, AMETHYST: 8, INFO: 67, SHOP: 10, SPRING: 2, JAKYOU: 1, STATUE: 5, NPC: 29, FIGHT: 48,
          WARP: 46, WARPTO: 29}
EXPECT_W1 = dict(EXPECT, **{CHEST: 22, AMETHYST: 6, INFO: 66, SHOP: 9, NPC: 28})

MAP_PRG = 0x14004      # 뱅크$0A 의 $8004
PTRTBL = 0x12AF5       # 뱅크$09 의 $AAF5 (블록 6 x 포인터 14)
DX = (-1, 0, 1, 0)     # 면 번호 0=서 1=남 2=동 3=북 (비트 자리 = 번호*2)
DY = (0, 1, 0, -1)
OPP = (2, 3, 0, 1)
SIDE_OF_DIR = {1: 3, 2: 2, 3: 1, 4: 0}    # 게임 방향 $0490 (1북 2동 3남 4서) -> 면 번호


def floor_name(f):
    """층 값 -> 글자. 게임 코드가 9 = 지하 1층, 10 = 지하 2층으로 쓴다
    (올라가는 계단 $FB11: 9 -> 1, 그 밖은 +1 / 내려가는 계단 $FBBB: 1 -> 9, 9 -> 10, 그 밖은 -1)."""
    if f == 0:
        return "특수 구역"
    return "지하 %d층" % (f - 8) if f >= 9 else "%d층" % f


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
        self._build_seams()
        self._build_zones()
        self._build_marks()
        self._build_bosses()
        self._edge_cache = {}

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

    # ── 이음매 ──────────────────────────────────────────────────────────────
    def _build_seams(self):
        """레이어 $18 = 이음매 7바이트 [X][Y|플래그][방향][도착X][도착Y][층][블록].
        고정뱅크 $F823 이 걸음 뒤 지금 칸을 이 표에서 찾고, 보는 방향($0490)이 같으면 위치를 (도착X,도착Y)로,
        층 $055D·블록 $0782 를 뒤 두 바이트로 바꾼다. 즉 롬 칸 (X,Y)에 그 방향으로 들어서는 걸음은
        실제로는 (도착X,도착Y)로 간다 - 게임 속 층은 8x8 구획을 이렇게 이어 붙인 모양이다(공략집 지도와 같다).
        ★도착이 (56,12) 면 $F873 이 던전 번호($0571)별 표로 바꿔치기한다 - 그런 항목은 지도 잇기에서 뺀다."""
        self.seams = {}
        for x, y, k in self._each(0x18, 7, False):
            d = self._rd(k + 2)
            tx, ty = self._rd(k + 3), self._rd(k + 4) & 0x3F
            if d in SIDE_OF_DIR and x < W and y < H and tx < W and ty < H and (tx, ty) != (0x38, 0x0C):
                self.seams.setdefault((x, y, SIDE_OF_DIR[d]), (tx, ty))

    # ── 구역 ────────────────────────────────────────────────────────────────
    def _build_zones(self):
        """걸어서 오갈 수 있는 칸을 묶고, 칸마다 **게임 속 자리**(lx, ly)를 정한다.
        롬에서 옆 칸이면 롬 좌표 그대로, 이음매를 건너면 건너간 쪽 구획을 통째로 옮겨 붙인다.
        같은 칸에 자리가 둘 나오면(이음매가 고리를 이루는 곳) 처음 자리를 쓰고 conflicts 로 센다."""
        ok = lambda v: v == 0 or v == 3
        ft, cells, seams = self.floor_tbl, self.cells, self.seams
        same_floor = (lambda a, b: True) if ft is None else (lambda a, b: ft[a] == ft[b])
        comp = [-1] * (W * H)
        lx, ly = [0] * (W * H), [0] * (W * H)
        sizes, places, boxes = [], [], []
        self.conflicts = 0
        for si in range(W * H):
            if comp[si] >= 0:
                continue
            cid = len(sizes)
            comp[si] = cid
            lx[si], ly[si] = si % W, si // W
            q = deque([si])
            n = 0
            pl = set()
            while q:
                i = q.popleft()
                x, y = i % W, i // W
                n += 1
                pl.add((self.block_of(x, y), lx[i] - x, ly[i] - y))
                c = cells[i]
                for s in range(4):
                    if not ok((c >> (s * 2)) & 3):
                        continue
                    nx, ny = x + DX[s], y + DY[s]
                    if not (0 <= nx < W and 0 <= ny < H):
                        continue
                    t = seams.get((nx, ny, s))
                    if t is not None:                      # 이음매: 들어서는 칸이 바뀐다
                        nx, ny = t
                    elif not ok((cells[ny * W + nx] >> (OPP[s] * 2)) & 3):
                        continue                           # 롬 옆 칸은 양쪽 기록이 다 뚫림/문일 때만
                    if not same_floor(self.block_of(x, y), self.block_of(nx, ny)):
                        continue                           # 층표 바이트가 다르면 다른 층(다른 던전으로 가는 이음매 포함)
                    j = ny * W + nx
                    px, py = lx[i] + DX[s], ly[i] + DY[s]
                    if comp[j] >= 0:
                        if comp[j] == cid and (lx[j], ly[j]) != (px, py):
                            self.conflicts += 1
                        continue
                    comp[j] = cid
                    lx[j], ly[j] = px, py
                    q.append(j)
            sizes.append(n)
            places.append(pl)
            boxes.append((min(ox + (b % BCOLS) * BLK for b, ox, oy in pl),
                          min(oy + (b // BCOLS) * BLK for b, ox, oy in pl),
                          max(ox + (b % BCOLS) * BLK for b, ox, oy in pl) + BLK,
                          max(oy + (b // BCOLS) * BLK for b, ox, oy in pl) + BLK))
        self.comp, self.comp_size, self.comp_box, self.comp_places = comp, sizes, boxes, places
        self.lx, self.ly = lx, ly

    def zone_at(self, x, y):
        """(상자 (x0,y0,x1,y1) - 게임 속 자리 기준, x1·y1 은 끝+1,
            구획 놓기 {(블록번호, 옮긴 X, 옮긴 Y)}, 이 칸의 게임 속 자리 (lx, ly))"""
        i = y * W + x
        cid = self.comp[i]
        return self.comp_box[cid], self.comp_places[cid], (self.lx[i], self.ly[i])

    # ── 표식 ────────────────────────────────────────────────────────────────
    def _rd(self, cpu):
        """뱅크$08/$09 (CPU $8000~$BFFF) 는 둘 다 PRG 주소 = CPU + $8000."""
        return self.prg[cpu + 0x8000]

    def _each(self, lid, stride, skip_len, with_block=False):
        """6블록의 레이어 lid 표. 끝은 $FF 또는 다음 포인터. with_block 이면 블록 세트 번호($0782)도 준다."""
        ptrs = [self.prg[PTRTBL + i * 2] | (self.prg[PTRTBL + i * 2 + 1] << 8) for i in range(6 * 14)]
        uniq = sorted(set(ptrs))
        for b in range(6):
            w = ptrs[b * 14 + (lid >> 1)]
            if not (0x8000 <= w < 0xC000):
                continue
            stop = next((u for u in uniq if u > w), w + 64)
            k = w + (1 + self._rd(w) if skip_len else 0)
            while k <= stop - stride and self._rd(k) != 0xFF:
                if with_block:
                    yield self._rd(k), self._rd(k + 1) & 0x3F, k, b
                else:
                    yield self._rd(k), self._rd(k + 1) & 0x3F, k
                k += stride

    def _build_marks(self):
        """$07FF bit7 상태(w = 0/1)마다 표식을 따로 만든다. self.marks 등은 처음 상태 w=0."""
        self.marks_w, self.marks_by_block_w = [], []
        for w in (0, 1):
            m = self._marks_for(w)
            by = {}
            for (x, y), kind in m.items():
                by.setdefault(self.block_of(x, y), []).append((x, y, kind))
            self.marks_w.append(m)
            self.marks_by_block_w.append(by)
        self.marks, self.marks_by_block = self.marks_w[0], self.marks_by_block_w[0]

    def _marks_for(self, w):
        """겹치는 칸 우선순위 = automap.lua 와 같다: 상자·대화 -> 엘리베이터 -> 계단이 덮어쓰고,
        그 뒤 고정 전투 -> 텔레포트 출발 -> 텔레포트 도착 순서로 빈 칸에만."""
        m = {}
        inmap = lambda x, y: x < W and y < H
        for x, y, k in self._each(0x16, 6, False):
            cond = self._rd(k + 1) & 0xC0                     # 0x40 = w 가 0 일 때만, 0x80 = w 가 1 일 때만 ($E2E9)
            if cond and (w != 0 if cond & 0x40 else w != 1):
                continue
            if inmap(x, y) and (x, y) not in m:
                m[(x, y)] = L16_KIND.get(self._rd(k + 2), NPC)
        for x, y, k in self._each(0x10, 4, True):
            if inmap(x, y):
                m[(x, y)] = ELEV
        # 계단은 **출발 칸**이 계단 자리다: $0A = 내려가는 계단($FB62, 층 -1), $08 = 올라가는 계단($FA30, 층 +1).
        # (도착 칸은 대개 반대쪽 계단 칸과 같지만 1곳은 그 옆 칸이다)
        for x, y, k in self._each(0x0A, 5, False):
            if inmap(x, y):
                m[(x, y)] = DOWN
        for x, y, k in self._each(0x08, 5, False):
            if inmap(x, y) and m.get((x, y)) != DOWN:
                m[(x, y)] = UP
        for x, y, k in self._each(0x14, 3, False):
            if inmap(x, y) and (x, y) not in m:
                m[(x, y)] = FIGHT
        # 텔레포트 [X][Y][도착X][도착Y][도착블록][도착층] - 고정뱅크 $FC3A 가 이 표로 순간이동시킨다
        warps = list(self._each(0x0E, 6, False))
        for x, y, k in warps:
            if inmap(x, y) and (x, y) not in m:
                m[(x, y)] = WARP
        for x, y, k in warps:
            tx, ty = self._rd(k + 2), self._rd(k + 3) & 0x3F
            if inmap(tx, ty) and (tx, ty) not in m:
                m[(tx, ty)] = WARPTO
        return m

    def counts(self, w=0):
        c = {"comps": len(self.comp_size), "bigComps": sum(1 for n in self.comp_size if n >= 4),
             "seams": len(self.seams), "conflicts": self.conflicts}
        for k in KINDS:
            c[k] = 0
        for v in self.marks_w[w].values():
            c[v] += 1
        return c

    # ── 보스 (2026-10-05 사용자 보고: 로키를 이기면 그 칸이 텔레포트가 된다) ──────────
    def _build_bosses(self):
        """고정 전투 값 15 = 블록 세트($0782)마다 하나 있는 보스 6곳.
        게임은 걸음마다 고정 전투(뱅크$0D $BE3F, 레이어 $14)를 텔레포트(고정뱅크 $FC3A)보다 **먼저** 본다.
        보스는 처치 깃발 $065E 의 블록 비트($9122[블록] = 1 << 블록)가 꺼져 있을 때만 싸운다($BEA3, 이기면 $E4E4 가 켠다).
        그래서 텔레포트 표가 같은 칸에 있는 (79,11) 로키 자리(겹치는 칸은 여기 하나)는 처치 전엔 보스전,
        처치 뒤엔 (79,15) 로 가는 텔레포트다 — 헤드리스 Mesen 으로 두 상태를 다 확인했다(종류 $E4 전투 / 순간이동).
        self.bosses = {(x, y): (블록, 처치 뒤 그 칸의 표식 또는 None)}"""
        warps = {(x, y) for x, y, k in self._each(0x0E, 6, False)}
        self.bosses = {}
        for x, y, k, b in self._each(0x14, 3, False, with_block=True):
            if self._rd(k + 2) == 15 and self.marks.get((x, y)) == FIGHT:
                self.bosses[(x, y)] = (b, WARP if (x, y) in warps else None)

    # ── 벽 (2026-10-05 사용자 보고: 벽으로 그려진 곳을 지나간다) ─────────────────
    def wall_edges(self, places):
        """구획 놓기(zone_at 의 places)를 게임 속 자리로 펼쳐 경계마다 하나씩 [(gx, gy, 면, 종류)].
        종류 'wall' 벽 / 'door' 문 / 'one' = 칸 (gx,gy) 에서 그 면 쪽으로만 지나가는 일방통행.
        ★게임은 **지금 칸의 앞 면만** 본다(고정뱅크 $EFEC -> 뱅크2 $A578: 0 뚫림·3 문이면 가고 1·2 면 막힘).
          맞은편 칸의 기록은 보지 않으므로 마주 보는 두 면이 다르면 한쪽으로만 지나간다(게임 속 배치 기준 260곳, 문 120 포함).
          전에는 두 칸의 면을 다 그려서 이런 곳이 벽으로 보였다. 이음매로 붙은 구획도 게임 속 옆 칸끼리 비교한다.
          헤드리스 Mesen 으로 (75,12)·(76,12) 둘레 10걸음을 재서 전부 이 판정과 같았다(공략집 화살표 1곳은 한 칸 어긋남)."""
        key = tuple(sorted(places))
        hit = self._edge_cache.get(key)
        if hit is not None:
            return hit
        pos = {}
        for b, sx, sy in places:
            rx, ry = (b % BCOLS) * BLK, (b // BCOLS) * BLK
            for cy in range(ry, ry + BLK):
                for cx in range(rx, rx + BLK):
                    pos.setdefault((cx + sx, cy + sy), (cx, cy))
        out = []
        for (gx, gy), (cx, cy) in pos.items():
            for s in range(4):
                a = self.side(cx, cy, s)
                nb = pos.get((gx + DX[s], gy + DY[s]))
                if nb is None:                        # 그림 밖과 맞닿은 면은 제 기록대로
                    if a:
                        out.append((gx, gy, s, "wall" if a == 1 else "door"))
                    continue
                if s in (0, 3):                       # 서·북 면은 옆 칸이 동·남 면으로 맡는다
                    continue
                b_ = self.side(nb[0], nb[1], OPP[s])
                pa, pb = a in (0, 3), b_ in (0, 3)
                if pa and pb:
                    if a == 3 or b_ == 3:
                        out.append((gx, gy, s, "door"))
                elif not pa and not pb:
                    out.append((gx, gy, s, "wall"))
                elif pa:
                    out.append((gx, gy, s, "one"))
                else:
                    out.append((gx + DX[s], gy + DY[s], OPP[s], "one"))
        self._edge_cache[key] = out
        return out


# ═════════════════════════════════════════════════════════════════════════════
# 1-2. 패스워드 (이 게임은 배터리 저장이 없어 31~39자 패스워드로 이어 한다)
# ═════════════════════════════════════════════════════════════════════════════
# 형식은 게임 프로그램에서 직접 읽었다 (PRG 뱅크 7 이 CPU $A000 에 올라온 상태, 원판 = 한글판 v52 바이트 동일):
#   조립 $AD9A — RAM $0635~$064D (25바이트). 능력치 $AFD9 · 마카 $B0C3 · 경험치 $B174 · MAG $B13D · 구슬 $B217
#               · 장비 $AE4A · 진행 깃발 $B2C7 · 동료 $B236 · 소금 $AE1B · 검사값·섞기 $B464 · 글자 $B562
#   풀기 $ADCC (빈칸 $BD 까지 센 길이 31 미만 거부) · 깃발 검사 $B31A · 입력 루프 $A731
#   표: 장비 목록 $AED1 · 검사값 $B51A · 길이 $B5A2 · 입력판 칸 -> 글자 $A9D8
#   레벨 기준 경험치 = 뱅크 3 계산기 프로그램 4 (상수 1·2·3·5·60), 벌금 = 프로그램 18 ((레벨+1) x 200)
#   상태 화면($B9F3~)에서 확인: 마카 $0550/1, 구슬 $0553, MAG $0554/5 (2026-10-03 값을 넣어 화면 대조)
# 웹판(편의프로젝트/web/games/mt1/password.js)과 같은 계산이다. pareido.jp 생성기는 단서로만 봤다(코드 미사용).
PW_CHARS = "0123456789ABCDEFGHJKLMNPQRSTUVWX"        # 5비트 값 0~31 (입력판의 Y 는 만들 때 쓰지 않는다)
PW_KNOWN_HASH = 0x2F24CF79                          # 패스워드 루틴 구간 FNV-1a (원판 = 한글판 v52, 영어판은 다름)
_RUN_OF_SLOT = (0, 2, 1, 3, 4, 5, 6)                 # 장비 칸 -> 롬 목록 번호
EQUIP_RAM = (0x561, 0x562, 0x563, 0x564, 0x565, 0x566, 0x568)
# 동료 6비트 값(번호-2, 빈칸 63)의 비트 자리: 칸마다 (바이트, 비트) x 비트0~5. 조립 $B650 이 쓰는 자리 그대로
_DEMON_BITS = (((18, 0), (18, 1), (18, 2), (19, 5), (19, 6), (19, 7)),
               ((20, 7), (19, 0), (19, 1), (19, 2), (19, 3), (19, 4)),
               ((20, 1), (20, 2), (20, 3), (20, 4), (20, 5), (20, 6)),
               ((21, 3), (21, 4), (21, 5), (21, 6), (21, 7), (20, 0)),
               ((21, 0), (21, 1), (21, 2), (22, 5), (22, 6), (22, 7)),
               ((23, 7), (22, 0), (22, 1), (22, 2), (22, 3), (22, 4)),
               ((23, 1), (23, 2), (23, 3), (23, 4), (23, 5), (23, 6)))


def level_exp(lv):
    """레벨 lv 의 기준 경험치 (3 으로 항상 나눠떨어진다)"""
    return (5 * (lv - 2) * (lv - 1) * lv + 60 * (lv - 1)) // 3


def _fnv(data, h=0x811C9DC5):
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


class Mt1Password:
    def __init__(self, rom_path):
        d = open(rom_path, "rb").read()
        prg = d[16:16 + d[4] * 16384]
        at7 = lambda cpu: 0xE000 + (cpu - 0xA000)
        h = 0x811C9DC5
        for a, b in ((at7(0xA700), at7(0xB600)), (0x7670, 0x7B00)):
            h = _fnv(prg[a:b], h)
        self.ok = len(prg) >= 0x10000 and h == PW_KNOWN_HASH
        self.hash = h
        self.runs, p = [], at7(0xAED1)
        for _ in range(7):
            n = prg[p]
            self.runs.append(list(prg[p + 1:p + 1 + n]))
            p += n + 1
        self.lengths = list(prg[at7(0xB5A2):at7(0xB5A2) + 8])
        self.grid = list(prg[at7(0xA9D8):at7(0xA9D8) + 34])
        self.crc_tbl = list(prg[at7(0xB51A):at7(0xB51A) + 32])

    # ── RAM(2KB) -> 상태 : 조립 루틴이 읽는 자리 그대로 ─────────────────
    @staticmethod
    def read_state(ram):
        r = ram
        demons = [r[0x4D3 + n * 18] for n in range(7) if (r[0x4D2 + n * 18] & 0xF0) and not (r[0x4D2 + n * 18] & 4)]
        return {"naka": [r[0x4B9 + i] for i in range(5)], "yumi": [r[0x4C9 + i] for i in range(5)],
                "level": r[0x4B4], "macca": r[0x550] | r[0x551] << 8,
                "exp": r[0x4BE] | r[0x4BF] << 8 | r[0x4C0] << 16, "s4c1": r[0x4C1],
                "orb": r[0x553], "mag": r[0x554] | r[0x555] << 8,
                "equip": [r[a] for a in EQUIP_RAM],
                "flags": {"f0134": r[0x134], "f065e": r[0x65E], "f056b": r[0x56B], "f056a": r[0x56A],
                          "f0569": r[0x569], "f0578": r[0x578], "f0579": r[0x579], "f07ff": r[0x7FF]},
                "demons": demons}

    @staticmethod
    def problem(st):
        """만들 수 없는 상태면 까닭(게임 시작 전 등)"""
        if any(not 5 <= v <= 20 for v in st["naka"]) or any(not 5 <= v <= 20 for v in st["yumi"][:4]):
            return "능력치가 범위 밖(모험을 시작한 뒤에 만들 수 있음)"
        lv = sum(st["naka"]) - 39
        if not 1 <= lv <= 61:
            return "레벨이 범위 밖"
        if st["level"] != lv:
            return "레벨(%d)과 능력치 합(%d)이 안 맞음" % (st["level"], lv)
        if not 0 <= st["exp"] - level_exp(st["level"]) <= 0x7FFF:
            return "경험치가 레벨 범위 밖"
        return None

    # ── 25바이트 <-> 글자 ────────────────────────────────────────────────
    def _crc(self, B):
        t, T = list(B[2:25]), self.crc_tbl
        for n in range(168):
            g, s = (n & 7) * 4, n >> 3
            if t[s] & T[g]:
                t[s] ^= T[g + 1]; t[s + 1] ^= T[g + 2]; t[s + 2] ^= T[g + 3]
        return t[21], t[22]

    @staticmethod
    def _swap_nibbles(B):
        """아래 니블 n <-> 위 니블 (n+k)&15 (서로 겹치지 않아 두 번 하면 제자리)"""
        k = B[1] >> 4
        lo = [B[2 + n] & 15 for n in range(16)]
        hi = [B[2 + n] >> 4 for n in range(16)]
        nlo, nhi = lo[:], hi[:]
        for n in range(16):
            m = (n + k) & 15
            nlo[n] = hi[m]; nhi[m] = lo[n]
        for n in range(16):
            B[2 + n] = nhi[n] << 4 | nlo[n]

    @staticmethod
    def _xor_key(B):
        key = (B[1] & 0xF0) | (B[0] & 0x0F)
        for i in range(2, 19):
            B[i] ^= key

    @staticmethod
    def _rotate(B, left):
        r = B[1] & 7
        if r:
            if not left:
                r = 8 - r
            for i in range(2, 25):
                B[i] = ((B[i] << r) | (B[i] >> (8 - r))) & 0xFF

    def encode(self, st, salt=0):
        B = [0] * 25
        for i in range(5):
            B[2 + i] = ((st["naka"][i] - 5) & 15) << 4 | ((st["yumi"][i] - 5) & 15)
        B[6] &= 0xF0                                            # 유미코 5번째 능력치는 넣지 않는다
        gold = st["macca"] & 0xFFFF
        if st["s4c1"] & 4:                                      # 게임은 이때 RAM 의 돈도 깎는다(여기선 안 건드림)
            gold = max(0, gold - (((st["level"] + 1) * 200) & 0xFFFF))
        B[7] = gold & 0xFF; B[6] |= (gold >> 8) & 0x0F; B[8] = (gold >> 8) & 0xF0
        d = (st["exp"] - level_exp(st["level"])) & 0xFFFFFF
        B[9] = d & 0xFF; B[8] |= (d >> 8) & 0x0F; B[10] = ((d >> 8) & 0x70) << 1
        mag = st["mag"]
        B[10] |= mag >> 8 & 0x1F; B[11] = mag & 0xFF; B[12] = ((mag >> 8 & 0x20) << 2) | ((st["orb"] & 7) << 4)
        k = [max(0, self.runs[_RUN_OF_SLOT[s]].index(i)) if i in self.runs[_RUN_OF_SLOT[s]] else 0
             for s, i in enumerate(st["equip"])]
        B[12] |= k[0] & 15
        B[13] = (k[1] & 7) << 5 | (k[2] & 7) << 2 | (k[3] & 7) >> 1
        B[14] = (k[3] & 1) << 7 | (k[4] & 7) << 4 | (k[5] & 3) << 2 | (k[6] & 7) >> 1
        f = st["flags"]
        B[15] = (k[6] & 1) << 7 | (f["f0134"] & 7) << 4 | (f["f065e"] & 0x10) >> 1 | (f["f056b"] & 7)
        B[16] = (f["f056a"] & 0xFE) | (1 if f["f07ff"] & 0x80 else 0)
        B[17] = f["f0569"] & 0xFF
        B[18] = (((f["f0578"] & 4) | f["f0579"]) & 0x0C) << 4 | 7
        for i in range(19, 25):
            B[i] = 0xFF                                         # 동료 자리는 1 로 채우고(빈칸 = 63) 있는 만큼 덮는다
        demons = st["demons"][:7]
        for n, ident in enumerate(demons):
            v = (ident - 2) & 0x3F
            for b, (i, bit) in enumerate(_DEMON_BITS[n]):
                B[i] = (B[i] & ~(1 << bit)) | (((v >> b) & 1) << bit)
        B[18] |= (salt & 7) << 3                                # 소금: 게임은 스택·제로페이지 XOR 로 정한다($AE1B)
        B[0], B[1] = self._crc(B)
        self._swap_nibbles(B); self._xor_key(B); self._rotate(B, True)
        out = []
        for c in range(40):                                     # 200비트를 앞에서부터 5비트씩
            v = 0
            for b in range(5):
                bit = c * 5 + b
                v = v << 1 | (B[bit >> 3] >> (7 - (bit & 7))) & 1
            out.append(PW_CHARS[v])
        return "".join(out)[:self.lengths[len(demons)]]

    @staticmethod
    def normalize(text):
        import unicodedata
        s = unicodedata.normalize("NFKC", text).upper()
        return "".join(ch for ch in s if ch not in " \t\r\n・·.-_")

    def decode(self, text):
        """(True, 상태, 글자) 또는 (False, 까닭, 글자)"""
        s = self.normalize(text)
        bad = sorted(set(ch for ch in s if ch not in PW_CHARS))
        if bad:
            hint = " (I·O·Z 는 없음 — 1·0·2 를 잘못 읽었을 수 있음)" if set(bad) & set("IOZY") else ""
            return False, "쓰지 않는 글자: %s%s" % ("".join(bad), hint), s
        if not 31 <= len(s) <= 40:
            return False, "길이 %d (31~40자여야 함)" % len(s), s
        B, full = [0] * 25, s.ljust(40, "X")
        for c in range(40):
            v = PW_CHARS.index(full[c])
            for b in range(5):
                bit = c * 5 + b
                if (v >> (4 - b)) & 1:
                    B[bit >> 3] |= 0x80 >> (bit & 7)
        if not any(B):
            return False, "검사값이 안 맞음", s
        self._rotate(B, False); self._xor_key(B); self._swap_nibbles(B)
        if self._crc(B) != (B[0], B[1]):
            return False, "검사값이 안 맞음(잘못 옮겨 적었을 수 있음)", s
        if not self._flags_ok(B):
            return False, "게임이 받지 않는 진행 깃발 조합", s
        hi = [B[2 + i] >> 4 for i in range(5)]
        lo = [B[2 + i] & 15 for i in range(4)]
        level = (sum(hi) - 14) & 0xFF
        k = [B[12] & 15, B[13] >> 5 & 7, B[13] >> 2 & 7, (B[13] & 3) << 1 | B[14] >> 7,
             B[14] >> 4 & 7, B[14] >> 2 & 3, (B[14] & 3) << 1 | B[15] >> 7]
        run = lambda s_, v: (self.runs[_RUN_OF_SLOT[s_]][v] if v < len(self.runs[_RUN_OF_SLOT[s_]]) else 0xFF)
        demons = []
        for n in range(7):
            v = sum(((B[i] >> bit) & 1) << b for b, (i, bit) in enumerate(_DEMON_BITS[n]))
            if v != 63:
                demons.append(v + 2)
        st = {"naka": [h + 5 for h in hi], "yumi": [l + 5 for l in lo] + [(sum(hi) - sum(lo) + 5) & 0xFF],
              "level": level, "macca": B[7] | ((B[8] & 0xF0) | (B[6] & 0x0F)) << 8,
              "exp": level_exp(level) + (B[9] | (((B[10] >> 1) & 0x70) | (B[8] & 0x0F)) << 8), "s4c1": 0,
              "orb": B[12] >> 4 & 7, "mag": B[11] | ((B[10] & 0x1F) | (B[12] >> 2 & 0x20)) << 8,
              "equip": [run(s_, v) for s_, v in enumerate(k)],
              "flags": {"f0134": B[15] >> 4 & 7, "f065e": (B[15] << 1) & 0x10, "f056b": B[15] & 7,
                        "f056a": B[16] & 0xFE, "f0569": B[17], "f0578": (B[18] >> 4) & 4,
                        "f0579": (B[18] >> 4) & 8, "f07ff": (B[16] & 1) << 7},
              "demons": demons}
        return True, st, s

    @staticmethod
    def _flags_ok(B):
        """풀기 $B31A 의 깃발 검사(게임이 거부하는 조합)"""
        a, b, hi = B[16], B[17], B[18] >> 4
        return not ((hi & 4) & b or (hi & 8) & (a & 0xFE)
                    or (a & 0x20 and (b & 0xB4) | (a & 0x16)) or (b & 1 and b >> 1 & 3)
                    or (a & 2 and b & 0x20) or (a & 0x10 and (a & 0x0C) | (b & 0x80)) or (a & 0x40 and b & 0x80))

    # ── 입력 화면 ────────────────────────────────────────────────────────
    def is_input_screen(self, ram):
        """입력 루프($A731)가 돌면 스택에 복귀주소 $A733 이 [33 A7] 로 남는다 (ds_bridge.lua 와 같은 규칙)"""
        if ram[0xC3] not in (0, 3) or ram[0xC2] > 16 or ram[0xC8] >= 40 or ram[0xC9] > 1:
            return False
        if any(ram[0x60C + i] not in self.grid for i in range(40)):
            return False
        return any(ram[a] == 0x33 and ram[a + 1] == 0xA7 for a in range(0x100, 0x1FF))

    def shown_password(self, ram):
        """게임이 보여 준(또는 방금 입력한) 패스워드: 길이 $0634 + 글자 $060C~ ($B562 가 채운다)"""
        n = ram[0x634]
        if not 31 <= n <= 40:
            return None
        s = ""
        for i in range(n):
            t = ram[0x60C + i]
            if t not in self.grid or self.grid.index(t) < 1:
                return None
            s += (PW_CHARS + "Y")[self.grid.index(t) - 1]
        return s if self.decode(s)[0] else None

    def cells_for(self, text):
        """자동 입력용 [(입력판 칸, 글자 번호)] — 끝에 빈칸 하나(풀기는 빈칸까지 센다)"""
        s = self.normalize(text)
        cells = [(PW_CHARS + "Y").index(ch) + 1 for ch in s]
        if len(cells) < 40:
            cells.append(0)
        return [(c, self.grid[c]) for c in cells]


# ═════════════════════════════════════════════════════════════════════════════
# 2. 그리기
# ═════════════════════════════════════════════════════════════════════════════
WIN_W, WIN_H = 520, 770
MAP_X, MAP_Y, MAP_PX = 20, 70, 480
FONT = "Malgun Gothic"

BG, PANEL, ZONE_BG, EDGE = "#0a1622", "#0f2233", "#132b40", "#2c527a"
TXT, SUB = "#dbe8f2", "#7fb8dc"
C_WALL, C_DOOR, C_ME = "#e8e8f0", "#40b4ff", "#ff6040"
C_ONEWAY = "#ffb020"            # 일방통행 화살표 (2026-10-05)
BOSS_DONE = "bossDone"          # 처치한 보스 (표식 개수 KINDS 에는 안 넣는다 — 그릴 때만 바꾼다)
BOSS_WARP = "bossWarp"          # 처치 전 로키: 보스 ✕ + 작은 텔레포트 마름모
STYLE = {                       # automap.lua 와 같은 색·모양
    UP:    ("#ffe040", "fill"),
    DOWN:  ("#4070ff", "fill"),
    ELEV:  ("#40e080", "fill"),
    CHEST: ("#ff9020", "box"),
    AMETHYST: ("#d070ff", "box"),
    INFO:  ("#8fd3ff", "dot"),
    NPC:   ("#ff70d0", "dot"),
    SHOP:  ("#ffc040", "coin"),
    SPRING: ("#40f0e0", "plus"),
    JAKYOU: ("#ff5c8a", "house"),
    STATUE: ("#f4f4f4", "tri"),
    FIGHT: ("#ff3030", "cross"),
    WARP:   ("#b070ff", "diamond"),
    WARPTO: ("#b070ff", "odiamond"),
    BOSS_DONE: ("#5f6b78", "cross"),
}
LEGEND = [(UP, "올라가는 계단"), (DOWN, "내려가는 계단"), (ELEV, "엘리베이터"),
          (CHEST, "보물상자"), (AMETHYST, "아메지스트"), (FIGHT, "고정 전투"),
          (INFO, "정보·글"), (NPC, "사람·이벤트"), (SHOP, "가게"),
          (SPRING, "회복의 샘"), (JAKYOU, "사교의 관"), (STATUE, "여신상"),
          (WARP, "텔레포트"), (WARPTO, "텔레포트 도착")]
LEG_COLS, LEG_W, LEG_H = 3, 164, 28
# 범례 마지막 줄 (그리는 법이 표식과 달라 따로): 일방통행 / 처치 전 로키(이기면 텔레포트) / 처치한 보스
LEGEND_EXTRA = [("oneway", "일방통행"), (BOSS_WARP, "이기면 텔레포트"), (BOSS_DONE, "처치한 보스")]


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
    if kind == BOSS_WARP:                                  # 보스 ✕ + 오른쪽 아래 작은 텔레포트
        draw_mark(p, FIGHT, x, y, cell)
        q = cell * 0.5
        draw_mark(p, WARP, x + cell - q, y + cell - q, q)
        return
    col, shape = STYLE[kind]
    ins = max(2, int(cell * 0.22))
    if shape == "fill":
        p.rect(x + ins, y + ins, cell - 2 * ins, cell - 2 * ins, fill=col)
    elif shape == "box":
        p.rect(x + ins, y + ins, cell - 2 * ins, cell - 2 * ins, outline=col, width=max(2, cell // 14))
    elif shape == "dot":
        r = max(3, int(cell * 0.17))
        p.oval(x + cell / 2 - r, y + cell / 2 - r, 2 * r, 2 * r, fill=col)
    elif shape == "coin":
        r = max(4, int(cell * 0.3))
        p.oval(x + cell / 2 - r, y + cell / 2 - r, 2 * r, 2 * r, fill=col)
    elif shape == "plus":
        wd = max(2, cell // 8)
        p.line(x + cell / 2, y + ins, x + cell / 2, y + cell - ins, col, wd)
        p.line(x + ins, y + cell / 2, x + cell - ins, y + cell / 2, col, wd)
    elif shape == "tri":
        p.poly([(x + cell / 2, y + ins), (x + cell - ins, y + cell - ins), (x + ins, y + cell - ins)], fill=col)
    elif shape == "house":                                 # 지붕 + 몸통 (사교의 관)
        mid = y + cell * 0.45
        p.poly([(x + cell / 2, y + ins), (x + cell - ins, mid), (x + cell - ins, y + cell - ins),
                (x + ins, y + cell - ins), (x + ins, mid)], fill=col)
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


def side_seg(X, Y, cell, s):
    """왼쪽 위가 (X, Y) 인 칸의 면 s (0 서 1 남 2 동 3 북) 선분"""
    return ((X, Y, X, Y + cell), (X, Y + cell, X + cell, Y + cell),
            (X + cell, Y, X + cell, Y + cell), (X, Y, X + cell, Y))[s]


def draw_oneway(p, seg, s, cell, wd):
    """일방통행 경계: 지나갈 수 있는 쪽(면 s 방향)으로 화살표. 선은 가늘게 — 반대쪽에서는 벽이다."""
    x1, y1, x2, y2 = seg
    p.line(x1, y1, x2, y2, C_ONEWAY, max(1, wd - 1))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ux, uy = DX[s], DY[s]
    h, hw = max(7, cell * 0.46), max(4, cell * 0.26)
    bx, by = mx - ux * h * 0.4, my - uy * h * 0.4
    p.poly([(mx + ux * h * 0.6, my + uy * h * 0.6), (bx - uy * hw, by + ux * hw), (bx + uy * hw, by - ux * hw)],
           fill=C_ONEWAY)


def draw_walls(p, dmap, places, bx0, by0, ox, oy, cell, wd):
    """벽·문을 먼저, 일방통행을 그 위에 (DungeonMap.wall_edges — 게임 속 옆 칸끼리 비교한 경계)."""
    ones = []
    for gx, gy, s, kind in dmap.wall_edges(places):
        seg = side_seg(ox + (gx - bx0) * cell, oy + (gy - by0) * cell, cell, s)
        if kind == "one":
            ones.append((seg, s))
        else:
            p.line(*seg, C_WALL if kind == "wall" else C_DOOR, wd)
    for seg, s in ones:
        draw_oneway(p, seg, s, cell, wd)


def mark_kind(dmap, x, y, kind, bs=None):
    """보스 칸은 처치 깃발 $065E(브리지 "bs")를 따라 바꿔 그린다. bs 가 None 이면(옛 브리지·공략 페이지) 처치 전.
    처치 뒤: 로키 칸은 텔레포트, 나머지는 회색 ✕. 처치 전 로키 칸은 ✕ + 작은 텔레포트."""
    boss = dmap.bosses.get((x, y))
    if boss is None:
        return kind
    blk, under = boss
    if bs is not None and bs & (1 << blk):
        return under or BOSS_DONE
    return BOSS_WARP if under else kind


def render(p, dmap, state, status, book=None):
    if book is not None and state is not None and state.get("b") == 1 and state.get("ek"):
        return render_battle(p, book, state, status)
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
        # 층: 게임의 현재 층 $055D(브리지가 "f" 로 보냄)를 먼저 쓴다. 층표가 0 인 특수 구역(마즈르카 3·4·7층)도
        # 게임은 계단·이음매·텔레포트로 층 값을 갖고 있다. 옛 브리지면 층표로.
        f = state.get("f")
        if not (isinstance(f, int) and 1 <= f <= 10):
            fl = dmap.floor_of(x, y)
            f = fl[0] if fl is not None else None
        if f is not None:
            p.text(WIN_W - MAP_X, 12, floor_name(f), TXT, 26, "ne", bold=True)

        (bx0, by0, bx1, by1), places, (lx, ly_) = dmap.zone_at(x, y)
        zw, zh = bx1 - bx0, by1 - by0
        cell = min(MAP_PX // max(zw, zh), 56)
        ox = MAP_X + (MAP_PX - zw * cell) // 2
        oy = MAP_Y + (MAP_PX - zh * cell) // 2

        # 구획(8x8 블록)마다 게임 속 자리로 옮겨 그린다 - 이음매로 이어진 층은 롬에서 떨어진 구획이 붙는다
        for b, sx, sy in places:
            gx, gy = (b % BCOLS) * BLK + sx, (b // BCOLS) * BLK + sy
            p.rect(ox + (gx - bx0) * cell, oy + (gy - by0) * cell, BLK * cell, BLK * cell, fill=ZONE_BG)

        draw_walls(p, dmap, places, bx0, by0, ox, oy, cell, max(2, cell // 12))

        # 표식은 지금 시나리오(表 0 / 裏 1 = $07FF bit7, 브리지의 "w")에 있는 칸만. 옛 브리지면 表(0)
        # 보스는 처치 깃발 $065E(브리지의 "bs")를 따른다 — mark_kind
        by_block = dmap.marks_by_block_w[1 if state.get("w") == 1 else 0]
        bs = state.get("bs") if isinstance(state.get("bs"), int) else None
        for b, sx, sy in places:
            for mx, my, kind in by_block.get(b, ()):
                draw_mark(p, mark_kind(dmap, mx, my, kind, bs), ox + (mx + sx - bx0) * cell, oy + (my + sy - by0) * cell, cell)

        draw_player(p, ox + (lx - bx0) * cell, oy + (ly_ - by0) * cell, cell, dx, dy)
        p.text(MAP_X, MAP_Y + MAP_PX + 14, "현재 위치 (%d, %d)" % (x, y), TXT, 14, "nw")
        p.text(WIN_W - MAP_X, MAP_Y + MAP_PX + 14, "구역 %d×%d" % (zw, zh), SUB, 14, "ne")

    # 범례 (3열, 마지막 칸에 벽·문)
    ly = MAP_Y + MAP_PX + 46
    for i, (kind, label) in enumerate(LEGEND):
        col_x = MAP_X + (i % LEG_COLS) * LEG_W
        row_y = ly + (i // LEG_COLS) * LEG_H
        draw_mark(p, kind, col_x, row_y, 22)
        p.text(col_x + 28, row_y + 11, label, TXT, 13, "w")
    n = len(LEGEND)
    wx, wy = MAP_X + (n % LEG_COLS) * LEG_W, ly + (n // LEG_COLS) * LEG_H + 11
    p.line(wx, wy, wx + 24, wy, C_WALL, 2)
    p.text(wx + 30, wy, "벽", SUB, 12, "w")
    p.line(wx + 64, wy, wx + 88, wy, C_DOOR, 2)
    p.text(wx + 94, wy, "문", SUB, 12, "w")
    for i, (kind, label) in enumerate(LEGEND_EXTRA):
        col_x, row_y = MAP_X + i * LEG_W, ly + (n // LEG_COLS + 1) * LEG_H
        if kind == "oneway":
            draw_oneway(p, (col_x + 11, row_y + 1, col_x + 11, row_y + 21), 2, 22, 3)
        else:
            draw_mark(p, kind, col_x, row_y, 22)
        p.text(col_x + 28, row_y + 11, label, TXT, 13, "w")


# ═════════════════════════════════════════════════════════════════════════════
# 1-3. 적 악마 정보 (전투 카드) — 2026-10-04
# ═════════════════════════════════════════════════════════════════════════════
# 롬 (원판·한글판 v52/v53 모두 같은 자리. 뱅크$0C 는 한글판이 이름표를 다시 써서 일부 다르지만 아래 표는 같다)
# - 적 레코드 포인터: 뱅크$0C `$8004` + (종류 & $7F) * 2  ->  16바이트 레코드 (게임이 `$CD31` 로 Y 번째를 읽는다)
# - 종족: 뱅크$0C `$8ECA` + (이름번호 - 2)  (게임 `$CD17`). 종족 이름 = 이름표 A[147 + 종족]
# - 레코드 16바이트
#     [0] 힘-5 <<4 | 지력-5        [1] 공격-5 <<4 | 속도-5      [2] 방어-5 <<4 | ?
#     [3] 최대HP 하위   [4] ? <<4 | 최대HP 상위 4비트
#     [5][6][7] 행동 (0 = 없음, $80+n = 마법 C[n], $C0+ = 특수·물리 공격)
#     [8] 일반공격 가중치 <<4 | 행동1 가중치   [9] 행동2 <<4 | 행동3     (보통 합계 16)
#     [11] 경험치  [12] 마카  [13] MAG   (기본값. 실제 전투 보상은 계산이 더 들어가는 듯 — 헤케트에서 다름을 봄)
# - 裏 시나리오($07FF bit7)면 게임이 최대 HP 를 두 배로 채운다 (뱅크$0D `$A298`).
# RAM (전투 중, 브리지가 보냄)
# - `$0690` 전투 중이면 1 (뱅크$0D `$A012` 시작 / `$A063` 끝) -> "b"
# - `$0652` 지금 그룹 "eg", `$060C+g` 그룹 g 마릿수 "ec", `$0610+g` 그룹 g 종류 "ek" (이름번호 = (종류 & $7F) + 32)
# - `$061C + 2i` 적 HP 8칸(16비트) "hp". 전투 시작 때 최대 HP 로 채우고 죽으면 0. 남은 적 = 앞에서부터 0 이 아닌 칸.
# pareido 앱에서 뽑은 CSV(참고자료/pareido_aside_20260928/mt1_demons.csv)와 114마리 전부 대조해 맞췄다(ds_selftest 7번).
# 그 앱의 코드는 쓰지 않았다 — 값 대조용으로만.
# 이름은 names_ko.txt 에서 옮겨 적었다(실행 파일을 Lua 1 + 파이썬 1 로 두려고 — 롬의 한글 이름은 슬롯 인코딩이라 직접 못 읽는다).
EN_NAMES = [            # 이름표 A32~A166 (적 악마·보스·종족)
    "트렌트", "케르베로스", "와이번", "케찰코아틀", "바실리스크", "바하라", "스톤카", "반다", "네코마타", "캔서",
    "웨어울프", "라미아", "길타브", "오리아스", "웨어캣", "세이렌", "레무리안", "소라스", "헤케트", "자이언트",
    "라케", "드워프", "펑거스", "비이", "요모츠시코메", "노움", "보글", "푸카", "포모리아", "엘프",
    "트롤", "고블린", "드리아드", "악마의목", "아바오아쿠", "폴터가이스트", "마이코니드로", "윌오위스프", "슬라임헤도로", "메가플라나리아",
    "윌오위스프", "그린슬라임", "핑크루퍼", "매드슬러그", "라핀스컬", "미라", "구울", "스켈레톤", "고스트", "좀비",
    "스킬라", "코카트리스", "서펜트", "탐즈", "타란텔라", "아피페", "바그", "바심", "킹트롤", "사이클롭스",
    "오니", "에킴", "오거", "가고일", "오크", "샤도우", "메피스토펠레스", "로아", "인큐버스", "서큐버스",
    "카임", "랑다", "타라가", "나아스", "알케니", "파라이", "하피", "하쿠마부도", "디바", "듀라한",
    "아쿠칼", "블랙나이트", "뱀파이어", "파라오", "티아마트", "히드라", "고르곤", "펜리스", "티폰", "만티코어",
    "발레푸르", "오르트로스", "누에", "베르제붑", "아수라", "조마", "베헤모스", "바알", "미노타우로스", "메두사",
    "로키", "헤카테", "세트", "루시퍼", "블롭", "트렌트", "메두사의그림자", "고블린", "포그", "샌드루퍼",
    "고스트이스마", "아바오아쿠", "프루시", "도돈고", "아스타로트", "마인", "신수", "귀신", "환마", "성수",
    "정령", "마수", "수인", "지령", "요정", "요괴", "악령", "환수", "사귀", "야마",
    "귀녀", "유귀", "요수", "사신", "마왕",
]
EN_MAGIC = [            # 이름표 C0~C35 (마법)
    "사이", "사이코", "사이킥", "사이클론", "봇토", "봇토라", "보앗토나", "가보앗토", "브리즈", "브리자",
    "브리자톤", "칸데", "칸데온", "하마", "핫케", "하쿄", "마기온카", "도르민", "프린파", "놋프",
    "마린카린", "굿스리토", "하이퍼", "테트라자", "에토나", "큐마", "메디", "메디카", "메디카르", "팟치",
    "크링크", "리캄", "사바트", "스워드나", "스타르트", "맛파",
]
EN_BANK, EN_PTR, EN_RACE, EN_RACE0 = 0x0C, 0x8004, 0x8ECA, 147


class EnemyBook:
    def __init__(self, rom_path):
        d = open(rom_path, "rb").read()
        if d[:4] != b"NES\x1a":
            raise ValueError("NES 롬이 아니다: %s" % rom_path)
        prg = d[16:16 + d[4] * 16384]
        self.bank = prg[EN_BANK * 0x2000:(EN_BANK + 1) * 0x2000]

    def _rd(self, cpu):
        return self.bank[cpu - 0x8000]

    @staticmethod
    def name_index(kind):
        return (kind & 0x7F) + 32

    @staticmethod
    def _a(idx):
        n = EN_NAMES[idx - 32] if 32 <= idx < 32 + len(EN_NAMES) else ""
        return n or "#%d" % idx

    def name(self, kind):
        return self._a(self.name_index(kind))

    def record(self, kind):
        k = kind & 0x7F
        p = self._rd(EN_PTR + 2 * k) | (self._rd(EN_PTR + 2 * k + 1) << 8)
        if not 0x8000 <= p <= 0x9FF0:
            return None
        return bytes(self.bank[p - 0x8000:p - 0x8000 + 16])

    def race(self, kind):
        return self._rd(EN_RACE + self.name_index(kind) - 2)

    def info(self, kind, late=False):
        """late = 裏 시나리오($07FF bit7) -> 최대 HP 두 배"""
        b = self.record(kind)
        if b is None:
            return None
        hp = ((b[4] & 0x0F) << 8) | b[3]
        acts = []
        for code, w in zip(b[5:8], (b[8] & 0x0F, b[9] >> 4, b[9] & 0x0F)):
            if code >= 0xC0:
                acts.append(("특수 공격", w, code))
            elif code >= 0x80:
                n = code - 0x80
                acts.append((EN_MAGIC[n] if n < len(EN_MAGIC) else "마법%d" % n, w, code))
        r = self.race(kind)
        return {"kind": kind, "index": self.name_index(kind), "name": self.name(kind),
                "race": self._a(EN_RACE0 + r) if 0 <= r < 20 else "종족%d" % r, "race_id": r,
                "hp": hp * (2 if late else 1), "hp_base": hp,
                "str": (b[0] >> 4) + 5, "int": (b[0] & 15) + 5, "atk": (b[1] >> 4) + 5,
                "spd": (b[1] & 15) + 5, "def": (b[2] >> 4) + 5,
                "exp": b[11], "macca": b[12], "mag": b[13], "normal": b[8] >> 4, "actions": acts, "raw": b}


def alive_hp(hps, count):
    """앞에서부터 HP 가 0 이 아닌 칸을 마릿수만큼 (게임의 「살아 있는 첫 칸」 찾기와 같은 순서)"""
    return [h for h in hps if h][:count]


def check_enemies(book, csv_path):
    """pareido 앱 추출 CSV 와 대조 -> (맞음 여부, 불일치 목록, 대조 마릿수)"""
    import csv
    rows = [r for r in csv.DictReader(open(csv_path, encoding="utf-8-sig"))
            if r["enemy_raw16_hex"] and r["enemy_hp(HP)"]]
    bad = []
    for r in rows:
        i = book.info(int(r["enemy_ram_id_hex"], 16))
        want = {"hp": int(r["enemy_hp(HP)"]), "str": int(r["enemy_str(強)"]), "int": int(r["enemy_int(知)"]),
                "atk": int(r["enemy_atk(攻)"]), "spd": int(r["enemy_spd(速)"]), "def": int(r["enemy_def(防)"]),
                "exp": int(r["enemy_exp(経験値)"]), "macca": int(r["enemy_macca(マッカ)"]),
                "mag": int(r["enemy_magnetite(マグネタイト)"]), "race_id": int(r["race_byte"]), "index": int(r["idx"])}
        got = {k: i[k] for k in want} if i else None
        if got != want:
            bad.append((r["name(名前)"], got, want))
    return not bad, bad, len(rows)


# ── 전투 카드 (2026-10-04, 사용자 「1에도 2처럼 전투가 나올 때 몬스터 정보」) ──────────────────────────────
# 전투 중($0690, 브리지 "b")에는 지도 자리에 지금 그룹의 적 정보를 그린다. 값은 전부 롬에서 읽는다(위 「1-3」).
# HP 는 게임처럼 「앞에서부터 0 이 아닌 칸」을 마릿수만큼. 裏 시나리오($07FF bit7, "w")면 최대 HP 두 배.
C_HP, C_HP_LOW, C_HP_BG, C_ACT = "#4ade80", "#f0a63c", "#22384d", "#c4b5fd"
STAT_LABELS = (("str", "힘"), ("int", "지력"), ("atk", "공격"), ("spd", "속도"), ("def", "방어"))


def render_battle(p, book, state, status):
    p.clear(BG)
    p.text(MAP_X, 16, "여신전생 전투 정보", SUB, 14, "nw")
    status_txt = {"live": ("● Mesen 연결됨", "#4ade80"),
                  "stale": ("● Mesen 멈춤 — 일시정지 중이면 풀어 주세요", "#f0a63c"),
                  "wait": ("○ Mesen 연결 대기 중 — Script Window 에서 ds_bridge.lua 실행", "#8fb0c6")}[status]
    p.text(MAP_X, 42, status_txt[0], status_txt[1], 12, "nw")
    p.rect(MAP_X - 1, MAP_Y - 1, MAP_PX + 2, MAP_PX + 2, fill=PANEL, outline=EDGE, width=1)

    ek, ec = state.get("ek") or [0] * 4, state.get("ec") or [0] * 4
    g = state.get("eg", 0) & 3
    kind, count = ek[g], ec[g]
    info = book.info(kind, late=state.get("w") == 1) if kind else None
    x0, y = MAP_X + 20, MAP_Y + 18
    if info is None:
        p.text(MAP_X + MAP_PX / 2, MAP_Y + MAP_PX / 2, "적 정보를 읽는 중", SUB, 16, "center")
        return
    p.text(x0, y, info["name"], TXT, 30, "nw", bold=True)
    p.text(WIN_W - MAP_X - 20, y + 6, "%d 마리" % count, TXT, 20, "ne", bold=True)
    y += 44
    p.text(x0, y, "%s  ·  최대 HP %d%s" % (info["race"], info["hp"], "  (裏 2배)" if state.get("w") == 1 else ""), SUB, 14, "nw")
    y += 34

    # 마리별 HP 막대
    hps = alive_hp(state.get("hp") or [], count)
    bar_w = MAP_PX - 40 - 110
    for i, h in enumerate(hps[:8]):
        frac = max(0.0, min(1.0, h / float(info["hp"] or 1)))
        p.text(x0, y + 9, "%d" % (i + 1), SUB, 13, "w")
        p.rect(x0 + 22, y, bar_w, 18, fill=C_HP_BG)
        if frac > 0:
            p.rect(x0 + 22, y, max(2, int(bar_w * frac)), 18, fill=C_HP if frac > 0.3 else C_HP_LOW)
        p.text(x0 + 22 + bar_w + 10, y + 9, "%d / %d" % (h, info["hp"]), TXT, 14, "w")
        y += 26
    if not hps:
        p.text(x0, y, "남은 적 없음", SUB, 14, "nw")
        y += 26
    y += 10

    # 능력치
    col_w = (MAP_PX - 40) / 5.0
    for i, (k, lab) in enumerate(STAT_LABELS):
        cx = x0 + col_w * i
        p.text(cx, y, lab, SUB, 13, "nw")
        p.text(cx, y + 18, "%d" % info[k], TXT, 22, "nw", bold=True)
    y += 58

    # 행동 비율. 레코드 가중치는 합이 16 이 되게 짜여 있지만 일반 공격만 쓰는 악마는 15 라 1/16 이 빈다
    # (그 1/16 에 게임이 무엇을 하는지는 미확인) -> 표에 있는 행동끼리의 비율로 보여 준다.
    p.text(x0, y, "행동 (비율)", SUB, 13, "nw")
    y += 22
    acts, merged = [("일반 공격", info["normal"])], {}
    for name, w, _code in info["actions"]:
        merged[name] = merged.get(name, 0) + w
    acts += sorted(merged.items(), key=lambda t: -t[1])
    total = float(sum(w for _n, w in acts) or 1)
    for name, w in acts:
        if w <= 0:
            continue
        p.text(x0 + 8, y, name, C_ACT if name != "일반 공격" else TXT, 15, "nw")
        p.text(WIN_W - MAP_X - 20, y, "%d%%" % round(100.0 * w / total), TXT, 15, "ne")
        y += 24
    y += 8

    # 보상 (한 마리)
    p.text(x0, y, "기본 보상 (한 마리)", SUB, 13, "nw")
    p.text(x0 + 8, y + 22, "경험치 %d    마카 %d    MAG %d" % (info["exp"], info["macca"], info["mag"]), TXT, 15, "nw")

    # 다른 무리
    others = [(ek[i], ec[i]) for i in range(4) if i != g and ec[i] > 0 and ek[i]]
    ly = MAP_Y + MAP_PX + 16
    if others:
        p.text(MAP_X, ly, "다른 무리: " + ", ".join("%s ×%d" % (book.name(k), c) for k, c in others), TXT, 14, "nw")
        ly += 26
    p.text(MAP_X, ly, "전투가 끝나면 지도로 돌아갑니다", SUB, 12, "nw")


# ═════════════════════════════════════════════════════════════════════════════
# 3. Mesen 연결과 창
# ═════════════════════════════════════════════════════════════════════════════
def net_loop(port, q, stop, out_q=None):
    """접속 -> 줄 단위 JSON 을 큐로. 끊기면 1초 뒤 다시 붙는다.
    받은 줄은 종류별로: 위치·자원 ("state", dict) / RAM ("ram", bytes) / 자동 입력 진행 ("pw", dict).
    out_q 에 넣은 문자열(RAM·TYPE·STOP 명령)은 한 줄씩 브리지로 보낸다."""
    while not stop.is_set():
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1.0)
        except OSError:
            q.put(("link", False))
            time.sleep(1.0)
            continue
        q.put(("link", True))
        s.settimeout(0.1)
        buf = b""
        try:
            while not stop.is_set():
                while out_q is not None and not out_q.empty():
                    s.sendall((out_q.get_nowait() + "\n").encode())
                try:
                    chunk = s.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if "ram" in msg:
                        q.put(("ram", bytes.fromhex(msg["ram"])))
                    elif "pw" in msg:
                        q.put(("pw", msg))
                    else:
                        q.put(("state", msg))
        except OSError:
            pass
        finally:
            s.close()
        q.put(("link", False))


class Mt1Panel:
    """오른쪽 패널: MAG·마카·구슬 실시간 + 패스워드(지금 상태로 만들기·복사·풀이·자동 입력·수첩).
    send(문자열) 로 브리지에 명령을 보낸다. 창(run_window)이 on_state·on_ram·on_pw·tick 을 불러 준다."""
    NOTES = os.path.join(HERE, "mt1_password_notes.json")
    MAX_NOTES = 40

    def __init__(self, parent, rom, send):
        import tkinter as tk
        self.tk, self.send = tk, send
        self.pw = Mt1Password(rom)
        self.ram, self.on_screen, self.typing, self.want, self.ticks = None, False, False, None, 0
        self.notes = self._load_notes()
        btn = dict(bg="#1b3a57", fg=TXT, activebackground="#2c527a", activeforeground=TXT, relief="flat",
                   font=(FONT, -14), padx=10, pady=4, cursor="hand2", disabledforeground="#4f6b82")
        lab = lambda p, text="", col=SUB, px=13, **kw: tk.Label(p, text=text, bg=BG, fg=col, font=(FONT, -px), **kw)
        f = self.frame = tk.Frame(parent, bg=BG, padx=16, pady=16)

        lab(f, "자원 (실시간)", TXT, 15).pack(anchor="w")
        res = tk.Frame(f, bg=BG); res.pack(fill="x", pady=(6, 12))
        self.res = {}
        for i, (key, name) in enumerate((("g", "MAG"), ("m", "마카"), ("o", "구슬"))):
            lab(res, name, SUB, 14).grid(row=i, column=0, sticky="w", padx=(0, 18))
            self.res[key] = lab(res, "—", TXT, 24, width=7, anchor="e")
            self.res[key].grid(row=i, column=1, sticky="e")

        lab(f, "패스워드", TXT, 15).pack(anchor="w", pady=(8, 0))
        lab(f, "배터리 저장이 없는 게임이라 패스워드로 이어 합니다. 미콘 마을 장로에게 가지 않아도 지금 상태로 만들 수 있고, "
               "입력 화면에서는 대신 칩니다.", wraplength=270, justify="left").pack(anchor="w", pady=(2, 8))
        row = tk.Frame(f, bg=BG); row.pack(fill="x")
        self.b_make = tk.Button(row, text="지금 상태로 만들기", command=self.make, **btn); self.b_make.pack(side="left")
        tk.Button(row, text="복사", command=self.copy, **btn).pack(side="left", padx=6)
        self.out = lab(f, "", "#8fd3ff", 15, wraplength=270, justify="left"); self.out.config(font=("Consolas", -16))
        self.out.pack(anchor="w", pady=(6, 0))
        self.make_note = lab(f, "", SUB, 12, wraplength=270, justify="left"); self.make_note.pack(anchor="w")

        lab(f, "넣을 패스워드", SUB, 12).pack(anchor="w", pady=(10, 2))
        self.var = tk.StringVar()
        tk.Entry(f, textvariable=self.var, bg=PANEL, fg=TXT, insertbackground=TXT, relief="flat",
                 font=("Consolas", -15), width=30).pack(fill="x", ipady=4)
        self.decoded = lab(f, "", SUB, 12, wraplength=270, justify="left"); self.decoded.pack(anchor="w")
        row = tk.Frame(f, bg=BG); row.pack(fill="x", pady=(6, 0))
        self.b_type = tk.Button(row, text="자동 입력", command=self.type_in, state="disabled", **btn)
        self.b_type.pack(side="left")
        self.type_note = lab(row, "타이틀에서 PASS WORD 를 고르면 켜집니다", SUB, 12, wraplength=170, justify="left")
        self.type_note.pack(side="left", padx=8)

        lab(f, "수첩 (고르면 위 칸에 들어갑니다)", TXT, 13).pack(anchor="w", pady=(14, 2))
        self.box = tk.Listbox(f, bg=PANEL, fg=TXT, selectbackground="#2c527a", relief="flat", height=9,
                              font=(FONT, -12), activestyle="none", highlightthickness=0)
        self.box.pack(fill="both", expand=True)
        self.box.bind("<<ListboxSelect>>", self._pick)
        self.var.trace_add("write", lambda *_: self._refresh())
        self._render_notes()
        if not self.pw.ok:
            self.b_make.config(state="disabled")
            self.make_note.config(text="이 롬의 패스워드 루틴은 아직 확인하지 않아서 패스워드 기능을 끕니다"
                                       "(원판·한글판 v52 확인). 자원 표시는 됩니다.", fg="#f0a63c")

    # ── 수첩 ───────────────────────────────────────────────────────────
    def _load_notes(self):
        try:
            return json.load(open(self.NOTES, encoding="utf-8"))
        except (OSError, ValueError):
            return []

    @staticmethod
    def _summary(st):
        return "Lv%d · 마카 %d · MAG %d · 동료 %d" % (st["level"], st["macca"], st["mag"], len(st["demons"]))

    def remember(self, text, source):
        ok, st, s = self.pw.decode(text)
        if not ok or any(n["pw"] == s for n in self.notes):
            return
        self.notes.insert(0, {"pw": s, "at": time.strftime("%m/%d %H:%M"), "from": source,
                              "sum": "Lv%d · 마카 %d · 동료 %d" % (st["level"], st["macca"], len(st["demons"]))})
        del self.notes[self.MAX_NOTES:]
        try:
            json.dump(self.notes, open(self.NOTES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except OSError:
            pass
        self._render_notes()

    def _render_notes(self):
        self.box.delete(0, "end")
        for n in self.notes:
            self.box.insert("end", "%s  %s · %s" % (n["at"], n["sum"], n["from"]))
        if not self.notes:
            self.box.insert("end", "아직 없습니다 — 만든 것과 게임이 보여 준 것이 저절로 남습니다")

    def _pick(self, _):
        sel = self.box.curselection()
        if sel and sel[0] < len(self.notes):
            self.var.set(self.notes[sel[0]]["pw"])

    # ── 버튼 ───────────────────────────────────────────────────────────
    @staticmethod
    def _group(s):
        return " ".join(s[i:i + 5] for i in range(0, len(s), 5))

    def make(self):
        if self.ram is None:
            self.make_note.config(text="게임 메모리를 아직 못 받았습니다(Mesen 이 돌고 있나요?)", fg="#f0a63c"); return
        st = self.pw.read_state(self.ram)
        why = self.pw.problem(st)
        if why:
            self.make_note.config(text="지금은 만들 수 없습니다 — " + why, fg="#f0a63c"); return
        text = self.pw.encode(st, 0)
        self.out.config(text=self._group(text))
        extra = " (게임 규칙대로 %d 를 뺐습니다)" % (((st["level"] + 1) * 200) & 0xFFFF) if st["s4c1"] & 4 else ""
        self.make_note.config(text=self._summary(st) + extra, fg="#4ade80")
        self.var.set(text)
        self.remember(text, "만들기")

    def copy(self):
        text = self.out.cget("text").replace(" ", "")
        if text:
            self.frame.clipboard_clear(); self.frame.clipboard_append(text)
            self.make_note.config(text="복사했습니다", fg="#4ade80")

    def type_in(self):
        ok, st, s = self.pw.decode(self.var.get())
        if not (ok and self.on_screen) or self.typing:
            return
        self.send("TYPE " + ",".join("%d:%d" % ct for ct in self.pw.cells_for(s)))
        self.typing, self.want = True, st
        self.type_note.config(text="입력 중 0/%d" % len(s), fg=SUB)
        self._refresh()

    def _refresh(self):
        text = self.var.get().strip()
        dec = self.pw.decode(text) if text and self.pw.ok else None
        if dec:
            self.decoded.config(text=(self._summary(dec[1]) + " · %d자" % len(dec[2])) if dec[0] else dec[1],
                                fg="#4ade80" if dec[0] else "#ff8a70")
        else:
            self.decoded.config(text="")
        on = bool(dec and dec[0]) and self.on_screen and not self.typing
        self.b_type.config(state="normal" if on else "disabled")

    # ── 창이 불러 주는 곳 ───────────────────────────────────────────────
    def on_state(self, state):
        for key, w in self.res.items():
            if key in state:
                w.config(text="{:,}".format(state[key]))
        was, self.on_screen = self.on_screen, state.get("p") == 1
        if was != self.on_screen:
            if not self.typing:
                self.type_note.config(text="입력 화면입니다" if self.on_screen else "타이틀에서 PASS WORD 를 고르면 켜집니다",
                                      fg=SUB)
            self._refresh()

    def on_ram(self, ram):
        self.ram = ram
        if not self.pw.ok:
            return
        shown = self.pw.shown_password(ram)              # 게임이 보여 준 패스워드(미콘 마을 장로) 자동 기록
        if shown:
            self.remember(shown, "게임 화면")
        if self.want is not None and not self.typing:    # 불러온 뒤 RAM 이 패스워드 내용과 같은지 한 번 확인
            now = self.pw.read_state(ram)
            same = all(now[k] == self.want[k] for k in ("level", "macca", "exp", "mag"))
            self.type_note.config(text=("불러왔습니다 — " + self._summary(now)) if same
                                  else "게임은 받았지만 상태가 예상과 다릅니다", fg="#4ade80" if same else "#ff8a70")
            self.want = None

    def on_pw(self, msg):
        state = msg.get("pw")
        if state in ("typing", "submitted"):
            self.type_note.config(text="입력 중 %d/%d" % (msg.get("done", 0), msg.get("total", 0)), fg=SUB)
            return
        self.typing = False
        if state != "accepted":
            self.want = None
        self.type_note.config(text={"accepted": "게임이 받아 줬습니다 — 확인 중…",
                                    "rejected": "게임이 받지 않았습니다(잘못된 패스워드)",
                                    "lost": "입력 화면을 벗어나 멈췄습니다",
                                    "stuck": "게임이 반응하지 않아 멈췄습니다",
                                    "stopped": "그만두었습니다"}.get(state, state),
                              fg="#4ade80" if state == "accepted" else "#ff8a70")
        self._refresh()

    def tick(self, linked):
        """창의 poll 마다(33ms). 0.5초마다 RAM 을 받아 둔다(만들기·자동 기록용)."""
        self.ticks += 1
        if linked and self.ticks % 15 == 0:
            self.send("RAM")


def load_book(rom):
    """적 정보 (롬이 없거나 모듈이 없으면 None -> 전투 중에도 지도를 그린다)"""
    if not rom:
        return None
    try:
        return EnemyBook(rom)
    except Exception as e:                      # 창은 계속 뜨게
        print("적 정보를 못 읽었다:", e)
        return None


def run_window(dmap, port, rom=None):
    import tkinter as tk
    root = tk.Tk()
    root.title("여신전생 DS 지도")
    root.configure(bg=BG)
    root.resizable(False, False)
    canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg=BG, highlightthickness=0)
    canvas.pack(side="left")
    painter = TkPainter(canvas)

    q, out_q, stop = queue.Queue(), queue.Queue(), threading.Event()
    threading.Thread(target=net_loop, args=(port, q, stop, out_q), daemon=True).start()
    st = {"link": False, "state": None, "rx": 0.0, "sig": None}
    book = load_book(rom)
    panel = None
    if rom:
        panel = Mt1Panel(root, rom, out_q.put)
        panel.frame.pack(side="left", fill="y")

    def poll():
        while True:
            try:
                kind, val = q.get_nowait()
            except queue.Empty:
                break
            if kind == "link":
                st["link"] = val
            elif kind == "state":
                st["state"], st["rx"] = val, time.time()
                if panel:
                    panel.on_state(val)
            elif panel and kind == "ram":
                panel.on_ram(val)
            elif panel and kind == "pw":
                panel.on_pw(val)
        if panel:
            panel.tick(st["link"])
        if not st["link"]:
            status = "wait"
        elif time.time() - st["rx"] > 2.5:            # 브리지는 60프레임마다 한 번은 보낸다
            status = "stale"
        else:
            status = "live"
        mapped = {k: v for k, v in (st["state"] or {}).items()
                  if k in ("x", "y", "dx", "dy", "f", "w", "bs", "b", "eg", "ek", "ec", "hp")}
        sig = (status, json.dumps(mapped if st["state"] else None, sort_keys=True))   # 자원 값만 바뀌면 지도는 그대로
        if sig != st["sig"]:                          # 바뀔 때만 다시 그린다
            render(painter, dmap, st["state"], status, book)
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
    ap.add_argument("--pos", help="그림 뽑기용 위치 x,y[,dx,dy[,층[,w[,bs]]]]  (층 = 게임의 $055D, 9·10 = 지하 / "
                                  "w = $07FF bit7 表 0·裏 1 / bs = 보스 처치 깃발 $065E)")
    ap.add_argument("--status", default="live", choices=("live", "stale", "wait"))
    ap.add_argument("--battle", help="그림 뽑기용 전투 상태 종류,마릿수[,HP...]  (종류 = $0610 값, 예: 146,3,20,5,0 은 헤케트 3마리)")
    a = ap.parse_args()

    if not a.rom or not os.path.exists(a.rom):
        raise SystemExit("롬을 찾을 수 없다: %s\n-> python mt1_ds_window.py <롬 경로>"
                         "   (원판·영어판·한글판 아무거나 된다)" % a.rom)
    dmap = DungeonMap(a.rom)

    if a.check:
        bad = 0
        for w, want in ((0, EXPECT), (1, EXPECT_W1)):
            c = dmap.counts(w)
            diff = {k: (c[k], want[k]) for k in want if c[k] != want[k]}
            print("%s  [$07FF bit7 = %d]\n   %s\n   %s" % (a.rom, w, " ".join("%s=%d" % (k, c[k]) for k in want),
                                                        "기대값과 일치 ✔" if not diff else "★다름 %s" % diff))
            bad += bool(diff)
        sys.exit(1 if bad else 0)

    if a.snapshot:
        state = None
        if a.pos:
            raw = [int(t) for t in a.pos.split(",")]
            v = raw + [0, 0]
            state = {"x": v[0], "y": v[1], "dx": v[2], "dy": v[3]}
            if len(raw) >= 5:
                state["f"] = raw[4]
            if len(raw) >= 6:
                state["w"] = raw[5]
            if len(raw) >= 7:
                state["bs"] = raw[6]
        if a.battle:
            v = [int(t) for t in a.battle.split(",")]
            state = dict(state or {"x": 255, "y": 255, "dx": 0, "dy": 0})
            state.update({"b": 1, "eg": 0, "ek": [v[0], 0, 0, 0], "ec": [v[1], 0, 0, 0],
                          "hp": (v[2:] + [0] * 8)[:8] if len(v) > 2 else [0] * 8})
        p = PilPainter(WIN_W, WIN_H)
        render(p, dmap, state, a.status, load_book(a.rom))
        p.img.save(a.snapshot)
        print("그림:", a.snapshot)
        return
    run_window(dmap, a.port, a.rom)


if __name__ == "__main__":
    main()
