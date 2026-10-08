#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""여신전생 1 (FC) 공략 페이지 — 롬에서 직접 읽어 HTML 한 장(index.html)을 만든다.

    python 공략사이트/make_guide.py [롬]      # 롬 생략 시 작업롬파일의 최신 정상 빌드 -> 공략사이트/index.html
    python 공략사이트/make_guide.py --check   # 표만 계산해 요약을 찍는다 (HTML 안 만듦)

지도·표식은 DS 창(mt1_ds_window.py)의 DungeonMap, 적 능력치는 EnemyBook 을 그대로 쓴다. 이름은 names_ko.txt.
이 파일이 새로 읽는 것은 **랜덤 전투 표·고정 전투 표**(아래)와 **상자·가게·장비 수치·합체·보상**(「상자·가게·장비·합체」 절),
**마법·버그**(「마법」 절, 2026-10-05)다 (원판 = 한글판 v52·v53 바이트 동일). ★$07FF bit7 = 裏 시나리오 (공략집 裏 다이달로스 페이지와 대조).

랜덤 전투 (뱅크$0C 가 $8000, 뱅크$0D 가 $A000 에 걸린 상태. 입구 = 고정뱅크 $F0DC -> 뱅크$0D $A004 -> $BDA4)
  - 걸음마다 고정뱅크 $F084~: $056E 가 0 이 아니면 없음. 안전 사각형 표 $EECE (4바이트 x 3: X 시작·끝, Y 시작·끝)
    안이면 없음. 세 번째 사각형은 $065E bit1(블록1 보스 = 메두사를 쓰러뜨림) 이 켜진 뒤에만 안전.
  - $BE10: 이 칸에 고정 전투(레이어 $14)가 있으면 그쪽. 없으면 들어온 쪽 면이 문($C988 = 3)이면 등급 6, 아니면 3.
  - $BE5A: 등급 -> 추첨 횟수 $92AD[등급] (3 -> 4번, 6 -> 1번). $BBEC 가 그 횟수만큼 난수를 뽑아 표 $9131 의
    0 칸에만 계속 걸리면 전투. 난수 $C76E = 표 $C77E[$0C & $7F] (0~15 가 8번씩), 뽑을 때마다 $0C 가 1 늘고
    매 프레임에도 는다 -> 문으로 들어선 걸음 = 64/128, 그 밖 걸음 = 연속 4번이 다 걸리는 자리 1/128.
  - 무리 수 $BEF9: 구역 z 의 마스크 두 바이트 $DA63[2z], $DA63[2z+1] 에서 난수/2 번째 2비트 칸 + 1.
  - 종류 $BF2D: 구역 z = (X/16) + (Y/16)*8 (롬 칸 좌표 $0780/$0781), 니블표 = 뱅크$0C ($BD54[2z]) 8바이트.
    난수 r -> 바이트 $BD94[r] (= r/2), 짝수면 위 니블·홀수면 아래 니블 -> 종류 = $BCF4[블록 $0782 * 16 + 니블].
    블록 $0782 = 층표($CB7D) 아래 니블 (특수 구역 14·15 는 3). 결국 무리마다 16칸 중 하나를 고르게 뽑는다.
  - 마릿수 $BF99: 적 레코드 [2] 아래 니블 v. F -> 1~4, 8 미만 -> v+1, 그 밖 -> v-9 ~ v-6 중 하나 (0~8 로 자름, 0 이면 그 무리는 없음).
고정 전투 (레이어 $14, 3바이트 [X][Y][코드 8~F])
  - 종류 = $DAA3[블록*8 + 코드-8] (1마리). 코드 F 는 보스: $065E 의 블록 비트가 켜지면(쓰러뜨리면) 다시 안 나온다.
    종류 $F0(프루시)는 $065E bit4(세트를 쓰러뜨림) 또는 $056B bit1 이 켜져 있으면 안 나온다.
검증 (2026-10-04): 헤드리스 Mesen 으로 무작위로 걸으며 게임이 이 루틴을 부를 때의 입력과 결과를 기록 —
  종류 285건·전투 판정 460건·무리 수 42건·마릿수 285건이 전부 계산과 같았다(위치·블록을 무작위로 바꿔 넣어
  107개 (구역, 블록) 조합 시험. 원판 1개·한글판 v52 세이브 4개, 기록·대조 도구는 세션 임시 폴더에서 썼다).
  1번 추첨은 29건 모두 들어온 쪽이 문, 걸은 위치 452곳의 블록은 모두 층표 아래 니블과 같았다.
지역 이름·층 순서는 공략집(dds.opatil.com) 시나리오 페이지의 제목과 맞췄다(본문·그림은 가져오지 않음).
붉은 탑은 루시퍼(8층)에서 내려가는 계단을 거꾸로 따라가, 마즈르카 회랑의 특수 구역 층은 계단 연결로 정했다.
"""
import argparse
import base64
import html
import io
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mt1_ds_window as DW  # noqa: E402

# ── 지역 ────────────────────────────────────────────────────────────────────
AREAS = [  # (키, 이름, 원래 이름, 층 순서: 공략 진행 순서)
    ("daedalus", "다이달로스의 탑", "ダイダロスの塔", "down"),
    ("vien", "비엔 마을", "ビエンの街", "up"),
    ("valhalla", "발할라의 회랑", "ヴァルハラの回廊", "up"),
    ("mz_pass", "마즈르카 회랑 가는 길", "マズルカの回廊への通路", "up"),
    ("mazurka", "마즈르카의 회랑", "マズルカの回廊", "down"),
    ("fire_m", "불의 바다 (마즈르카 쪽)", "炎の腐海（マズルカ側）", "down"),
    ("fire_i", "불의 바다 (앙피니 쪽)", "炎の腐海（アンフィニ側）", "up"),
    ("infini", "앙피니 궁전", "アンフィニ宮殿", "down"),
    ("red", "붉은 탑", "赤の塔", "up"),
]
AREA_IDX = {a[0]: i for i, a in enumerate(AREAS)}
RED_CELLS = {(10, 7), (4, 6), (4, 7), (14, 6), (6, 6), (15, 4), (14, 5), (15, 5)}   # 붉은 탑 1~8층 구획


def area_of(dm, x, y):
    cx, cy = x // DW.BLK, y // DW.BLK
    t = dm.floor_tbl[cy * DW.BCOLS + cx] & 15
    if t in (0, 1, 2):
        return AREAS[t][0]
    if t in (14, 15):
        return "mazurka"
    if t == 3:
        return "mz_pass" if x < 96 else "mazurka"
    if t == 4:
        return "fire_m" if x >= 96 else "fire_i"
    return "red" if (cx, cy) in RED_CELLS else "infini"


def block_of_cell(dm, b):
    t = dm.floor_tbl[b] & 15
    return 3 if t >= 14 else t


def height(f):
    """층 값 -> 높이 (지하 1층 = -1)"""
    return 8 - f if f >= 9 else f


# ── 랜덤·고정 전투 표 ────────────────────────────────────────────────────────
class Encounters:
    def __init__(self, rom_path, book):
        d = open(rom_path, "rb").read()
        P = d[16:16 + d[4] * 16384]
        self.fixbase = len(P) - 0x4000
        self.P, self.book = P, book
        self.b0c, self.b0d = P[0x0C * 0x2000:0x0D * 0x2000], P[0x0D * 0x2000:0x0E * 0x2000]
        self.rand = [self.fx(0xC77E + i) for i in range(128)]
        zero = {i for i in range(16) if self.c(0x9131 + i) == 0}
        self.draws = {cls: self.c(0x92AD + cls) for cls in (3, 6)}
        self.rate = {cls: sum(1 for i in range(128) if all(self.rand[(i + j) & 127] in zero for j in range(n))) / 128.0
                     for cls, n in self.draws.items()}
        self.safe = []
        for i in range(3):
            x0, x1, y0, y1 = (self.fx(0xEECE + 4 * i + k) for k in range(4))
            self.safe.append((x0, x1, y0, y1, i == 2))     # 마지막 = 메두사를 쓰러뜨린 뒤에만 안전

    def fx(self, a):
        return self.P[self.fixbase + a - 0xC000]

    def c(self, a):
        return self.b0c[a - 0x8000]

    def d(self, a):
        return self.b0d[a - 0xA000]

    def kinds(self, block):
        return [self.d(0xBCF4 + block * 16 + i) for i in range(16)]

    def zone_nibbles(self, zone):
        ptr = self.d(0xBD54 + 2 * zone) | (self.d(0xBD55 + 2 * zone) << 8)
        out = []
        for i in range(8):
            b = self.c(ptr + i)
            out += [b >> 4, b & 15]
        return out

    def table(self, zone, block):
        """[(종류, 16칸 중 칸 수)] 많은 순"""
        ks = self.kinds(block)
        cnt = Counter(ks[n] for n in self.zone_nibbles(zone))
        return sorted(cnt.items(), key=lambda t: (-t[1], self.book.name(t[0])))

    def groups(self, zone):
        m0, m1 = self.fx(0xDA63 + 2 * zone), self.fx(0xDA64 + 2 * zone)
        out = Counter()
        for Y in range(8):
            a = (self.fx(0xDAD3 + Y) & m0) or (self.fx(0xDADB + Y) & m1)
            out[(a >> (2 * self.d(0xBEF1 + Y))) + 1] += 1
        return out                                          # 8칸 중

    def count_dist(self, kind):
        rec = self.book.record(kind)
        v = rec[2] & 15
        if v == 15:
            return Counter({1: 1, 2: 1, 3: 1, 4: 1})
        if v < 8:
            return Counter({v + 1: 4})
        out = Counter()
        for f in range(4):
            b = self.c(0x92A9 + f)
            out[min(8, max(0, (b - 256 if b > 127 else b) + v - 7))] += 1
        return out                                          # 4칸 중

    def fixed(self, dm):
        """[(블록, X, Y, 코드, 종류)]"""
        out = []
        for b in range(6):                                  # 블록마다 레이어 $14 포인터 (블록 6 x 포인터 14)
            i = DW.PTRTBL + (b * 14 + (0x14 >> 1)) * 2
            w = k = dm.prg[i] | (dm.prg[i + 1] << 8)
            while dm._rd(k) != 0xFF and k < w + 3 * 8:
                x, y, code = dm._rd(k), dm._rd(k + 1) & 0x3F, dm._rd(k + 2)
                if 8 <= code <= 15:
                    out.append((b, x, y, code, self.fx(0xDAA3 + b * 8 + code - 8)))
                k += 3
        return out

    def safe_at(self, x, y):
        """None / "always" / "medusa" """
        for x0, x1, y0, y1, cond in self.safe:
            if x0 <= x < x1 and y0 <= y < y1:
                return "medusa" if cond else "always"
        return None


# ── 상자·가게·장비·합체 (2026-10-04 역어셈블, 원판 = 한글판 바이트 동일) ──────────────
# 상자  지도 레이어 $16 값 32: [X][Y|조건][20][6C][?][번호]. 처리 고정뱅크 $F744 -> 뱅크1 $A72C.
#       내용 = 뱅크1 $A8D0[번호] (24칸): 0 = 500 마카 + 보옥 (마카 500 미만이고 장비가 하나도 없을 때만 열림, 열어도
#       닫힌 표시가 안 남아 다시 열 수 있다 = 공략집의 「두 번 열기」), $80 = 보옥 1개(최대 7), $30·$37 = 그 장비
#       (각각 $0562 나카지마 갑옷 칸·$0568 유미코 머리 칸에 바로 들어감), 그 밖 N = 레벨이 짝수면 레벨 x N 마카,
#       홀수면 대신 그 자리의 랜덤 전투($0139 로 강제). 열면 $013A~ 의 비트가 켜져 다시 안 열린다.
# 가게  레이어 $16 값 4 (값 6 = 라그의 가게, 거래 내용은 미해석). 뱅크0 $A911, 품목표 $AB9F 6바이트
#       [품목][종류 0 무기·1 갑옷·2 방패·3 투구][파는 블록 두 개: 니블-1, F 없음][장착 0 나카지마·1 유미코·2 둘 다]
#       [가격 아래][가격 위]. 블록 = $0782 (층표 아래 니블). 다이달로스 8층 8품목 가격이 공략집과 같다.
# 장비 수치  뱅크0B: 무기 $A078[코드-$14], 갑옷 $A40E[코드-$28], 방패 $A417[코드-$37], 투구 $A406[코드-$30].
#       물리 방어 굴림 수 = 機敏さ + 갑옷 + 방패 + 투구/4 - 4 x (구역+1) ($A4FF~, $A4F6 에 넣은 레벨은 $A43C 에서 덮여 안 쓰인다).
#       투구 값 전체는 적 마법을 받을 때의 방어 굴림($A65F, 아래 「마법」 절)에 들어간다.
#       각 표 0번 = 맨몸 값(무기 0·갑옷 8·방패 4·투구 4). 페이지는 맨몸 대비(표 값 - 0번)로 보이며, 공략집 수치와 23종 모두 같다.
# 합체  뱅크0 $A510: 그룹 = $A5C9[이름번호] (A2~A64, 종족을 레벨대로 2~3묶음으로 나눈 것),
#       목록 $A60A = 그룹 0~22 차례로 [상대 그룹][결과 이름번호]... FF. 두 그룹 중 큰 쪽 목록에서 작은 쪽을 찾고,
#       없으면 결과 $40 = 이름번호 64 드리아드(상성표에는 ※ 로 표시). 원판 사교의 관 캡처의 상성표 5줄 25칸과
#       결과(아피스+츠쿠요미=키마이라)가 같고, 공략집 역합체표 118조합 중 116개가 같다(2개는 공략집이 한 조합을 두 악마에 적음).
#       동료 레코드 뱅크0C $9E00 + (이름번호-2) x 8 (합류 처리 고정 $DBD7): [0] 강|지 [1] 공|속 (+5), [2] HP 하위,
#       [3] 위 니블 다섯째 능력치(+5)·아래 니블 HP 상위, [4] MP, [5] 마법 묶음, [6] 걸음마다 마그네타이트 x16 ($04E2 -> 뱅크7 $A3AD).
#       ★[6] 은 레벨이 아니다(2026-10-05 정정). 레벨 = 뱅크0B $A08D[이름번호] — 합체 거절 뱅크0 $A223: 나카지마 레벨 + 7 < 이 값이면
#       거절. 공략집 동료 데이터의 Lv(= 합체 가능한 나카지마 레벨)가 이 값 - 7 과 같고 걸음당 소비가 [6]/16 과 같다(魔神 3종 대조).
#       악마의 물리 공격은 상태 화면의 공격 대신 종족별 숨은 위력 뱅크0B $A0CE[이름번호] 를 굴린다($A1F3).
# 무기  맞히는 적 수 고정 $DAF5[무기-$14] = v -> 실제 1 + Bin(v-1) (뱅크0D $B05C). 보스의 물리 공격은 구역별 고정 $DB0A[구역].
# 라그의 가게  뱅크0 $A775 (한글판은 이 구간 코드가 달라 원판 기준): 자수정($0569 bit6)이 있어야 거래, 고르면 자수정이 없어진다.
#       품목 $13 용의 수염 = 파티 HP 전부 회복($DB5E), $14 벼락부름 = 파티 HP 절반(최소 1, 뱅크0 $BE18), $07 아레스의 목걸이
#       (이미 있으면 그 자리가 $3F 런던부츠 = 미콘 마을로, $F7B4), $12 하늘의 곡옥(받은 뒤에는 목록에서 빠짐).
# 보상  고정뱅크 $E458: 쓰러뜨린 적 한 마리마다 경험치·마카·MAG 에 레코드 [11]·[12]·[13] + 난수 0~1 을 더하고
#       전투가 끝나면 지급(뱅크0D $B6D5~). MAG 는 8191 에서 멈춘다.
def load_names():
    import re
    out = {"A": {}, "B": {}, "C": {}}
    for line in open(os.path.join(os.path.dirname(HERE), "names_ko.txt"), encoding="utf-8"):
        m = re.match(r"^([ABC])(\d+)\t(.*)$", line.rstrip("\n"))
        if m:
            out[m.group(1)][int(m.group(2))] = m.group(3)
    return out


EQUIP_KIND = ((0x15, 0x28, "무기", 0xA078, 0x14), (0x29, 0x30, "갑옷", 0xA40E, 0x28),
              (0x31, 0x37, "투구", 0xA406, 0x30), (0x38, 0x3E, "방패", 0xA417, 0x37))
WHO = ("나카지마", "유미코", "둘 다")
FUSION_DEFAULT = 0x40                                  # 목록에 없는 조합의 결과 = 이름번호 64 드리아드


class Extras:
    def __init__(self, rom, dm, names):
        d = open(rom, "rb").read()
        P = d[16:16 + d[4] * 16384]
        bank = lambda n, base: (lambda a: P[n * 0x2000 + a - base])
        b0, b1, b0b, b0c = bank(0, 0xA000), bank(1, 0xA000), bank(0x0B, 0xA000), bank(0x0C, 0x8000)
        fx = lambda a: P[len(P) - 0x4000 + a - 0xC000]
        self.names = names
        # 상자
        self.chest_val = [b1(0xA8D0 + i) for i in range(24)]
        self.chests, self.shops = [], []
        for x, y, k in dm._each(0x16, 6, False):
            kind, cond = dm._rd(k + 2), dm._rd(k + 1) & 0xC0
            if x >= DW.W or y >= DW.H:
                continue
            if kind == 32:
                self.chests.append((x, y, cond, dm._rd(k + 5)))
            elif kind in (4, 6):
                self.shops.append((x, y, cond, kind))
        # 가게 품목
        self.items, a = [], 0xAB9F
        while b0(a) != 0xFF:
            r = [b0(a + i) for i in range(6)]
            blocks = [n - 1 for n in (r[2] >> 4, r[2] & 15) if n != 15]
            self.items.append({"code": r[0], "cat": r[1], "blocks": blocks, "who": r[3], "price": r[4] | (r[5] << 8)})
            a += 6
        # 장비 수치와 장착 (패스워드 장비 목록 $AED1: 나카지마 무기·방패·갑옷·투구, 유미코 무기·갑옷·머리)
        pw = DW.Mt1Password(rom)
        nak = set(sum(pw.runs[0:4], [])) - {0xFF}
        yum = set(sum(pw.runs[4:7], [])) - {0xFF}
        self.equip = []
        for lo, hi, cat, tbl, base in EQUIP_KIND:
            for code in range(lo, hi + 1):
                who = 2 if (code in nak and code in yum) else (0 if code in nak else 1 if code in yum else None)
                self.equip.append({"code": code, "cat": cat, "value": b0b(tbl + code - base) - b0b(tbl), "who": who,
                                   "name": names["B"].get(code, "#%d" % code)})
        # 합체
        self.group = {a: b0(0xA5C9 + a) for a in range(2, 0x41) if b0(0xA5C9 + a) != 0xFF}
        self.lists, a = [], 0xA60A
        for _g in range(max(self.group.values()) + 1):
            L = {}
            while b0(a) != 0xFF:
                L[b0(a)] = b0(a + 1)
                a += 2
            a += 1
            self.lists.append(L)
        self.ally_level = {a: b0b(0xA08D + a) for a in self.group}
        self.ally_race = {a: b0c(0x8ECA + a - 2) for a in self.group}
        self.ally = {}
        for a in self.group:
            r = [b0c(0x9E00 + (a - 2) * 8 + i) for i in range(8)]
            self.ally[a] = {"hp": r[2] | (r[3] & 15) << 8, "mp": r[4], "set": r[5], "mag": r[6], "power": b0b(0xA0CE + a),
                            "stats": ((r[0] >> 4) + 5, (r[0] & 15) + 5, (r[1] >> 4) + 5, (r[1] & 15) + 5, (r[3] >> 4) + 5)}
        # 무기가 맞히는 적 수 (v -> 1 + Bin(v-1)), 보스 물리 공격의 대상 수
        self.reach = {code: fx(0xDAF5 + code - 0x14) for code in range(0x15, 0x29)}
        self.boss_reach = [fx(0xDB0A + b) for b in range(6)]

    def chest_text(self, idx):
        v = self.chest_val[idx]
        if v == 0:
            return "500 마카 + 보옥 (마카가 500 미만이고 장비가 없으면 다시 열림)"
        if v == 0x80:
            return "보옥 1개 (최대 7개)"
        if v in (0x30, 0x37):
            return "%s (바로 장착됨)" % self.names["B"].get(v, "#%d" % v)
        return "레벨 × %d 마카 — 레벨이 홀수면 대신 랜덤 전투" % v

    def fuse(self, a, b):
        ga, gb = self.group.get(a), self.group.get(b)
        if ga is None or gb is None:
            return None
        hi, lo = max(ga, gb), min(ga, gb)
        return self.lists[hi].get(lo, FUSION_DEFAULT)


# ── 마법 (2026-10-05 역어셈블, 원판 = 한글판 v53 표·계산 루틴 바이트 동일) ─────────────────────
# 뱅크0B($A000) 표: MP $A8FC[n] · 대상 $ABCE[n] · 종류 $B2F1[n] · 위력 $A004[n] · 속성 $A032[n] · 상태이상 비트 $B731[n-17]
#   대상: 위 니블 E = 상대 편(아래 니블 = 맞히는 수, 8 = 전부) · D1 아군 1명 · D8 아군 전체 · D0 죽은 아군 1명 · 00 없음
#   종류: 0 피해($B384) 1 상태이상($B6E0) 2 특수($B355) 3 회복($BA36) 4 보조($B8CE) 5 지도($BA55)
# 누가 쓰나: 유미코 = 단계 t (뱅크3 $BA01 = 계산기 프로그램 6: ⌊(레벨 + ⌊(나카지마 知 + 유미코 知 - 10)/2⌋)/5⌋, 고정 $F203 이
#   11 로 자름) -> 고정 $EEDA + 4t [이동 중 2바이트][전투 2바이트], 비트 7..0 = 뱅크0B $A7CF[0..15] 의 마법.
#   공략집의 습득 포인트(레벨+知 두 사람 합 >= 10(t+1))와 같은 식이다. 동료 = 동료 레코드 [5] -> $BFB2 + 3 x 묶음(FF 까지 3개).
# 성공 판정 뱅크0D $BBEC(n): n 번 뽑은 난수가 모두 $9131 의 0 칸이면 0. 상태이상은 0 이면 실패(n=2: 27/128),
#   리캄을 악마에게 쓰면 0 일 때 「사라졌다」(n=3: 11/128, 뱅크7 $A61D 로 동료 삭제).
# 피해 (Bin(x) = 동전 x 번 중 앞면, U3(x) = 0~2 를 x 번 더함, 달 $055A = 0 새달 ~ 8 보름, 구역 $0782)
#   아군->적 $A2A0: 공격 = max(0, Bin(N) - K) + Bin(위력), K = max(0, (강+지) - (공+속+운) + 4).
#     ★N = 2 x (RAM[$04B3+자리] + RAM[$04B4+자리]) — $A300 이 Y(시전자 기록) 대신 X(대열 자리)로 읽는 원판 버그.
#     적 방어 = 8 x 지' + U3(2 x 내성 + 강' + max(0, 달 - 달문턱)), 내성 = [15] & 7 ([15] & 속성 != 0 일 때), 문턱 = [4] 위 니블.
#     피해 = (공격 >= 방어 ? 공격 - 방어 : 0) + ⌊Bin(위력)/2⌋ (최대 255), 맞힌 적 모두 같은 값.
#   적->아군 $A581: 공격 = 위력 + Bin(강' + 4 x 지' + max(0, 달 - 달문턱)).
#     방어 = 기본 + Bin(지 + 운 + 투구 - 8 - 달) — 사람: 기본 = 레벨 (+2 x (구역+1) 테트라자 $0671), 투구 = $A406 표 값(맨머리 4)
#     악마: 기본 = 2 x 레벨($A08D), 투구 0. ★괄호 안이 음수면 0 으로 막지 않는다($A6A2, 8비트로 넘침 — 실측 미확인).
#     피해는 같은 꼴, 「방어」 중이면 절반.
#   메디·메디카 $BB32: 0~3 을 (대상 강 x 2 - 12 + 4 x (구역+1)) 번 더함. ★운을 더하려던 자리($BB4A)에 LDA 가 빠져 강을 두 번 쓴다.
# 버그 대조: 게임 카탈로그@Wiki(FC 女神転生) 「バグ関連」, 공략집 小ネタ(隊列と魔法威力·機敏さ·マグネタイト) — 셋 다 롬으로 원인 확인.
SPELL_JP = ("サイ", "サイコ", "サイキック", "サイクロン", "ボット", "ボットラー", "ボアットナ", "ガボアット", "ブリズ", "ブリザー",
            "ブリザトン", "カンデ", "カンデオン", "ハマ", "ハッケ", "ハキョウ", "マギ・オンカ", "ドルミン", "プリンパ", "ノップ",
            "マリンカリン", "グッスリト", "ハイパー", "テトラジャ", "エトナ", "キュマ", "メディ", "メディカ", "メディカル", "パッチ",
            "クリンク", "リカーム", "サバト", "スワードナ", "スタルト", "マッパー")    # 원판 뱅크0B $BE9A 이름표
ELEMENTS = ((0x02, "염동"), (0x10, "화염"), (0x04, "냉기"), (0x08, "전격"), (0x01, "파마"))
SPELL_KIND = ("공격", "상태이상", "특수", "회복", "보조", "지도")
STATUS_TXT = {0x08: "CLOSE — 「제정신을 잃었다」", 0x04: "CLOSE — 「제정신을 잃었다」", 0x02: "CLOSE — 「움직일 수 없다」",
              0x01: "CLOSE — 「움직일 수 없다」", 0x10: "SLEEP — 잠", 0x40: "마법 봉인"}
# 적 특수 공격 $C0~$CB (2026-10-05): 문구 = 뱅크0C $900A[코드&$3F] -> $9016 문자열, 피해 위력 = 뱅크0B $A026 (C0~C6),
#   피해형은 적 공격 마법과 같은 식($A581). C7~CA 는 지속 상태이상(뱅크0D $B1A5): 대상 기록 [0] 에 $B1A0 = 01 02 02 03 을
#   OR (독·마비·마비·돌), 이미 지속 상태이상이면 실패, 메두사($E3)는 반드시 성공, 그 밖은 $BBEC(2)=0 일 때만(27/128),
#   타바사상($06A9=1)이면 막힘. CB = 에너지 드레인($B2B1): 두 사람 레벨 -1·경험치를 그 레벨 시작값으로·최대 MP -1·
#   능력치 하나씩 -1, 테트라자($0671)로 막고 레벨 1 이면 효과 없음. 대상 수 $B03B: C7 이상 1명, 그 밖은 보스전이면 $DB0A[구역].
SPECIAL_ATK = {
    0xC0: ("불 뿜기 약", "불을 뿜었다"), 0xC1: ("불 뿜기 중", "불을 뿜었다"), 0xC2: ("불 뿜기 강", "불을 뿜었다"),
    0xC3: ("포효 약", "크게 포효했다"), 0xC4: ("포효 강", "크게 포효했다"), 0xC5: ("저주 약", "저주에 걸렸다"),
    0xC6: ("저주 강", "저주에 걸렸다"), 0xC7: ("독 뿌리기", "독을 뿌렸다"), 0xC8: ("노려보기", "노려본다"),
    0xC9: ("노래", "노래를 불렀다"), 0xCA: ("콘크리트", "콘크리트를 뿌렸다"), 0xCB: ("씩 웃기", "씩 웃었다"),
}
SPECIAL_EFFECT = {0xC7: "독(POISON)", 0xC8: "마비(PALSY) 「마비되어 버렸다」", 0xC9: "마비(PALSY) 「움직일 수 없게 됐다」",
                  0xCA: "돌(STONE). 메두사가 쓰면 반드시 걸리고, 타바사상이 있으면 「굳지 않았다」",
                  0xCB: "에너지 드레인: 나카지마·유미코 레벨 −1(경험치는 그 레벨의 시작값, 최대 MP −1, 능력치 하나씩 −1). "
                        "테트라자로 막고, 레벨 1 이면 효과 없음"}
SPECIAL_TXT = {
    16: "위력 0 — 롬에만 있고 유미코·동료·적 누구도 쓰지 않는다",
    22: "이 전투 동안 아군 물리 공격 +4×(구역+1)",
    23: "이 전투 동안 에너지 드레인을 막고 나카지마·유미코의 마법 방어 +2×(구역+1) (물리 방어는 그대로)",
    25: "MP 를 (대상 지력 − 4)만큼 빼앗음 (적 전용, 나카지마에게는 효과 없음)",
    26: "HP 회복: 0~3 을 (대상 강함×2 − 12 + 4×(구역+1))번 더한 양",
    27: "메디를 아군 전체에",
    28: "HP 를 최대까지 (루시퍼가 쓰는 것은 백룡의 구슬로 막는다)",
    29: "전투 중 상태이상(CLOSE·SLEEP·FREEZE·마법 봉인)을 풂",
    30: "독·마비를 풂, 돌은 1/2 확률 (죽음은 안 됨)",
    31: "죽은 사람을 HP 1 로 되살림. 악마에게 쓰면 11/128(약 9%) 확률로 「사라졌다」 — 동료에서 빠진다",
    32: "COMP 없이 동료를 부름 (파티가 가득 차면 실패)",
    33: "그 자리에서 패스워드를 보여 줌",
    34: "미콘 마을로 돌아감",
    35: "자동 지도를 켬 (새달에는 실패)",
}


def target_text(t):
    if t >> 4 == 0xE:
        return "상대 전부" if t & 15 >= 8 else "상대 %d" % (t & 15)
    return {0xD1: "아군 1", 0xD8: "아군 전체", 0xD0: "죽은 아군 1"}.get(t, "—")


class Magic:
    def __init__(self, rom, book, ex):
        d = open(rom, "rb").read()
        P = d[16:16 + d[4] * 16384]
        b0b = lambda a: P[0x0B * 0x2000 + a - 0xA000]
        b0c = lambda a: P[0x0C * 0x2000 + a - 0x8000]
        fx = lambda a: P[len(P) - 0x4000 + a - 0xC000]
        self.mp = [b0b(0xA8FC + n) for n in range(36)]
        self.target = [b0b(0xABCE + n) for n in range(36)]
        self.kind = [b0b(0xB2F1 + n) for n in range(36)]
        self.power = [b0b(0xA004 + n) if n < 17 else 0 for n in range(36)]
        self.attr = [b0b(0xA032 + n) for n in range(36)]
        self.status = {n: b0b(0xB731 + n - 17) for n in range(17, 25)}
        # 유미코: 단계마다 [이동 중][전투] 비트 -> 처음 켜지는 단계
        order = [b0b(0xA7CF + i) & 0x7F for i in range(16)]
        self.yumi = {}                                  # 마법 -> [단계, 이동 중, 전투]
        for t in range(12):
            field = fx(0xEEDA + 4 * t) << 8 | fx(0xEEDB + 4 * t)
            battle = fx(0xEEDC + 4 * t) << 8 | fx(0xEEDD + 4 * t)
            for i, n in enumerate(order):
                bit = 0x8000 >> i
                if (field | battle) & bit:
                    e = self.yumi.setdefault(n, [t, False, False])
                    e[1] |= bool(field & bit)
                    e[2] |= bool(battle & bit)
        # 동료 마법 묶음
        self.ally_spells = {}
        for a, al in ex.ally.items():
            sp = [b0b(0xBFB2 + 3 * al["set"] + i) for i in range(3)]
            sp = sp[:sp.index(0xFF)] if 0xFF in sp else sp
            self.ally_spells[a] = [x & 0x7F for x in sp]
        self.ally_users = defaultdict(list)
        for a, sp in sorted(self.ally_spells.items(), key=lambda t: -ex.ally_level[t[0]]):
            for n in sp:
                self.ally_users[n].append(a)
        # 적
        self.enemy_users = defaultdict(list)
        self.special_users = defaultdict(list)
        for k in range(128):
            info = book.info(k)
            if info is None or empty_record(book, k):
                continue
            for _name, w, code in info["actions"]:
                if 0x80 <= code < 0xC0 and w > 0 and k not in self.enemy_users[code & 0x7F]:
                    self.enemy_users[code & 0x7F].append(k)
                if code >= 0xC0 and w > 0 and k not in self.special_users[code]:
                    self.special_users[code].append(k)
        self.special_power = {0xC0 + i: b0b(0xA026 + i) for i in range(7)}
        # 성공 판정 (n 번 모두 0 칸이면 0)
        rand = [fx(0xC77E + i) for i in range(128)]
        zero = {i for i in range(16) if b0c(0x9131 + i) == 0}
        self.all_zero = {n: sum(1 for i in range(128) if all(rand[(i + j) & 127] in zero for j in range(n))) for n in (2, 3)}

    def element(self, n):
        a = self.attr[n]
        return next((name for bit, name in ELEMENTS if a == bit), "무속성")

    def effect(self, n):
        if n in SPECIAL_TXT:
            return SPECIAL_TXT[n]
        if self.kind[n] == 0:
            t = "위력 %d · %s" % (self.power[n], self.element(n))
            return t + (" · 맞고 살아남은 대상은 얼어붙는다(FREEZE)" if n in (8, 9, 10) else "")
        if self.kind[n] == 1:
            return "%s · 성공 %d/128 (이미 상태이상이면 실패, 보스전의 적에게는 안 걸림)" % (
                STATUS_TXT.get(self.status[n], "?"), 128 - self.all_zero[2])
        return ""


def resist_text(book, k):
    """도감용: 마법 내성과 달 문턱"""
    rec = book.record(k)
    mag, moon = rec[15] & 7, rec[4] >> 4
    els = [name for bit, name in ELEMENTS if rec[15] & bit] if mag else []
    bits = []
    if els:
        bits.append("내성 %s +%d" % ("·".join(els), 2 * mag))
    bits.append("달 %d/8~" % (moon + 1) if moon < 8 else "달 영향 없음")
    return " · ".join(bits)


def count_text(dist):
    ks = sorted(k for k, v in dist.items() if v)
    if len(ks) == 1:
        return "%d마리" % ks[0]
    return "%d~%d마리" % (ks[0], ks[-1])


def pct(a, b):
    v = 100.0 * a / b
    return ("%.1f%%" % v).replace(".0%", "%") if v < 10 else "%d%%" % round(v)


# ── 층 지도 고르기 ──────────────────────────────────────────────────────────
class Floor:
    def __init__(self, area, f):
        self.area, self.f = area, f
        self.comps, self.blocks = [], set()

    @property
    def key(self):
        a = AREAS[AREA_IDX[self.area]]
        h = height(self.f)
        return (AREA_IDX[self.area], -h if a[3] == "down" else h)

    @property
    def title(self):
        t = "%s %s" % (AREAS[AREA_IDX[self.area]][1], DW.floor_name(self.f))
        return t + (" (미콘 마을)" if (self.area, self.f) == ("daedalus", 8) else "")

    @property
    def anchor(self):
        return "%s-%s" % (self.area, ("b%d" % (self.f - 8)) if self.f >= 9 else str(self.f))


def special_floor(dm, cid, t):
    """특수 구역(층표 0)의 실제 층 — 계단 연결로 정했다 (mazurka 3·4·7·8층)"""
    if t == 14:
        return 7 if dm.comp[0 * DW.W + 96] == cid else 3
    return 4 if dm.comp[20 * DW.W + 84] == cid else 8


def build_floors(dm):
    """층 목록과 {구성요소: 층}. 작은 조각은 같은 구획을 이미 그린 큰 조각의 그림에 들어가므로 따로 안 그린다."""
    first = {}
    for i, cid in enumerate(dm.comp):
        first.setdefault(cid, i)
    floors, floor_of_comp = {}, {}
    for cid in sorted(first, key=lambda c: -dm.comp_size[c]):
        i = first[cid]
        x, y = i % DW.W, i // DW.W
        if dm.cells[i] == 0xFF:                         # 사방이 막힌 칸(지도 밖)
            continue
        ft = dm.floor_tbl[dm.block_of(x, y)]
        t, f = ft & 15, ft >> 4
        if t >= 14:
            f = special_floor(dm, cid, t)
        if f == 0:
            continue
        fl = floors.setdefault((area_of(dm, x, y), f), Floor(area_of(dm, x, y), f))
        floor_of_comp[cid] = fl
        blocks = {b for b, _ox, _oy in dm.comp_places[cid]}
        if blocks <= fl.blocks:
            continue
        fl.comps.append(cid)
        fl.blocks |= blocks
    return sorted(floors.values(), key=lambda fl: fl.key), floor_of_comp


# ── 지도 그림 ───────────────────────────────────────────────────────────────
TINT = ["#132b40", "#3a2440", "#1d3d2a", "#43361a"]
SAFE_TINT = "#33383d"                                   # 안전 구역 (tint 값 -1)


def draw_floor(dm, fl, w, fixed_nums, tint_of_block, chest_nums=None):
    """층의 구성요소마다 그림 하나, 폭 960 안에서 줄을 바꿔 가며 붙인다. fixed_nums = {(롬X, 롬Y): 번호}"""
    from PIL import Image
    imgs = []
    for cid in fl.comps:
        bx0, by0, bx1, by1 = dm.comp_box[cid]
        zw, zh = bx1 - bx0, by1 - by0
        cell = max(9, min(22, 600 // max(zw, zh)))
        pad = 8
        p = DW.PilPainter(zw * cell + 2 * pad, zh * cell + 2 * pad)
        p.clear(DW.PANEL)
        ox = oy = pad
        places = dm.comp_places[cid]
        for b, sx, sy in places:
            gx, gy = (b % DW.BCOLS) * DW.BLK + sx, (b // DW.BCOLS) * DW.BLK + sy
            p.rect(ox + (gx - bx0) * cell, oy + (gy - by0) * cell, DW.BLK * cell - 1, DW.BLK * cell - 1,
                   fill=SAFE_TINT if tint_of_block.get(b, 0) < 0 else TINT[tint_of_block.get(b, 0)])
        # 벽·문·일방통행 — 게임은 지금 칸의 앞 면만 보므로 마주 보는 두 면이 다르면 일방통행(DW.DungeonMap.wall_edges)
        DW.draw_walls(p, dm, places, bx0, by0, ox, oy, cell, max(2, cell // 10))
        by_block = dm.marks_by_block_w[w]
        for b, sx, sy in places:
            for mx, my, kind in by_block.get(b, ()):
                X, Y = ox + (mx + sx - bx0) * cell, oy + (my + sy - by0) * cell
                kind = DW.mark_kind(dm, mx, my, kind)       # 로키 칸: 보스 ✕ + 이기면 텔레포트
                DW.draw_mark(p, kind, X, Y, cell)
                n = fixed_nums.get((mx, my))
                if n is not None and kind in (DW.FIGHT, DW.BOSS_WARP):
                    p.text(X + cell - 1, Y, str(n), "#ffffff", max(10, cell * 2 // 3), "ne", bold=True)
                c = (chest_nums or {}).get((mx, my))
                if c is not None and kind == DW.CHEST:
                    p.text(X + cell - 1, Y, c, "#ffd08a", max(10, cell * 2 // 3), "ne", bold=True)
        imgs.append(p.img)
    rows, row, rw = [], [], 0                           # 폭 960 을 넘으면 줄을 바꾼다
    for im in sorted(imgs, key=lambda im: -im.width):
        if row and rw + 10 + im.width > 960:
            rows.append(row)
            row, rw = [], 0
        rw += (10 if row else 0) + im.width
        row.append(im)
    rows.append(row)
    W_ = max(sum(im.width for im in r) + 10 * (len(r) - 1) for r in rows)
    H_ = sum(max(im.height for im in r) for r in rows) + 10 * (len(rows) - 1)
    out = Image.new("RGB", (W_, H_), DW.BG)
    y = 0
    for r in rows:
        x = 0
        for im in r:
            out.paste(im, (x, y))
            x += im.width + 10
        y += max(im.height for im in r) + 10
    return out


def draw_legend():
    cols, cw, rh = 5, 150, 26
    items = list(DW.LEGEND) + [("wall", "벽"), ("door", "문"), ("oneway", "일방통행"), (DW.BOSS_WARP, "이기면 텔레포트")]
    rows = (len(items) + cols - 1) // cols
    p = DW.PilPainter(cols * cw + 8, rows * rh + 8)
    p.clear(DW.PANEL)
    for i, (kind, label) in enumerate(items):
        x, y = 6 + (i % cols) * cw, 4 + (i // cols) * rh
        if kind in ("wall", "door"):
            p.line(x + 2, y + 11, x + 20, y + 11, DW.C_WALL if kind == "wall" else DW.C_DOOR, 3)
        elif kind == "oneway":
            DW.draw_oneway(p, (x + 11, y + 1, x + 11, y + 21), 2, 22, 3)
        else:
            DW.draw_mark(p, kind, x, y, 22)
        p.text(x + 28, y + 11, label, DW.TXT, 13, "w")
    return p.img


def png_uri(img):
    buf = io.BytesIO()
    img.convert("P", palette=1, colors=48).save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ── 표 만들기 ───────────────────────────────────────────────────────────────
def build(rom):
    dm = DW.DungeonMap(rom)
    book = DW.EnemyBook(rom)
    enc = Encounters(rom, book)
    ex = Extras(rom, dm, load_names())
    floors, floor_of_comp = build_floors(dm)
    fixed = enc.fixed(dm)
    appear = defaultdict(list)                          # 종류 & $7F -> [(층, "r" 랜덤 / "f" 고정, 16칸 중 칸 수 / 코드)]
    for fl in floors:
        # 랜덤 전투: 구획(8x8)마다 (구역, 블록). 걸을 수 있는 칸 수로 무게
        part = Counter()
        safe = Counter()
        safe_blocks, cells = set(), 0
        for cid in fl.comps:
            for i in (j for j, c in enumerate(dm.comp) if c == cid):
                x, y = i % DW.W, i // DW.W
                b = dm.block_of(x, y)
                zone = (x >> 4) + (y >> 4) * 8
                s = enc.safe_at(x, y)
                part[(zone, block_of_cell(dm, b), s == "always")] += 1
                if s:
                    safe[s] += 1
                    if s == "always":
                        safe_blocks.add(b)
                cells += 1
        fl.parts = []
        for (zone, blk, always_safe), n in part.most_common():
            if always_safe:
                continue
            fl.parts.append({"zone": zone, "block": blk, "cells": n, "table": enc.table(zone, blk),
                             "groups": enc.groups(zone)})
        # 같은 출현표인 조각은 합친다
        merged = []
        for pt in fl.parts:
            same = next((m for m in merged if m["table"] == pt["table"] and m["groups"] == pt["groups"]), None)
            if same:
                same["cells"] += pt["cells"]
                same["zones"].append(pt["zone"])
            else:
                pt["zones"] = [pt["zone"]]
                merged.append(pt)
        fl.parts = merged
        fl.safe, fl.cells = safe, cells
        fl.tint = {b: -1 for b in safe_blocks} if fl.parts else {}
        for idx, pt in enumerate(fl.parts):
            for cid in fl.comps:
                for b, _sx, _sy in dm.comp_places[cid]:
                    bx, by = (b % DW.BCOLS) * DW.BLK, (b // DW.BCOLS) * DW.BLK
                    if (bx >> 4) + (by >> 4) * 8 in pt["zones"] and len(fl.parts) > 1 and b not in fl.tint:
                        fl.tint[b] = min(idx, len(TINT) - 1)
        for pt in fl.parts:
            for k, n in pt["table"]:
                appear[k & 0x7F].append((fl, "r", n))
        # 고정 전투
        fl.fixed = [f for f in fixed if floor_of_comp.get(dm.comp[f[2] * DW.W + f[1]]) is fl]
        for blk, x, y, code, kind in fl.fixed:
            appear[kind & 0x7F].append((fl, "f", code))
        fl.differs = any(dm.marks_by_block_w[0].get(b) != dm.marks_by_block_w[1].get(b) for b in fl.blocks)
        # 상자·가게 (조건: 0 늘, 0x40 표 시나리오만, 0x80 裏 시나리오만)
        at = lambda x, y: floor_of_comp.get(dm.comp[y * DW.W + x]) is fl
        fl.chests = [c for c in ex.chests if at(c[0], c[1])]
        fl.shops = [s for s in ex.shops if at(s[0], s[1])]
    ex.magic = Magic(rom, book, ex)
    return dm, book, enc, ex, floors, fixed, appear


# ── HTML ────────────────────────────────────────────────────────────────────
CSS = """
select{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--edge);background:var(--panel);color:var(--txt);max-width:100%}
:root{--bg:#0a1622;--panel:#0f2233;--card:#132b40;--edge:#2c527a;--txt:#dbe8f2;--sub:#7fb8dc;--acc:#ffb347;--bad:#ff6b6b;
--chip:#1b3a55;font-family:"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
@media (prefers-color-scheme:light){:root:not([data-theme=dark]){--bg:#f4f7fa;--panel:#ffffff;--card:#eef3f8;--edge:#b9cde0;
--txt:#14212d;--sub:#3d6a8c;--acc:#b25b00;--bad:#c62828;--chip:#dde8f2}}
:root[data-theme=dark]{--bg:#0a1622;--panel:#0f2233;--card:#132b40;--edge:#2c527a;--txt:#dbe8f2;--sub:#7fb8dc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-size:15px;line-height:1.55}
header{padding:20px 16px 8px;max-width:1100px;margin:auto}h1{margin:0;font-size:24px}header p{margin:6px 0 0;color:var(--sub);font-size:13px}
nav{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--edge)}
nav .in{max-width:1100px;margin:auto;display:flex;gap:4px;padding:6px 12px;overflow-x:auto}
nav button{background:none;border:0;color:var(--sub);font:inherit;padding:8px 12px;border-radius:8px;cursor:pointer;white-space:nowrap}
nav button.on{background:var(--chip);color:var(--txt);font-weight:bold}
main{max-width:1100px;margin:auto;padding:12px 16px 60px}section.tab{display:none}section.tab.on{display:block}
.toc{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 16px}.toc a{background:var(--chip);color:var(--txt);text-decoration:none;
padding:4px 10px;border-radius:999px;font-size:13px}
h2{font-size:20px;margin:28px 0 8px;border-left:4px solid var(--acc);padding-left:10px}h2 small{color:var(--sub);font-weight:normal;font-size:13px}
.floor{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:12px;margin:12px 0}
.floor h3{margin:0 0 8px;font-size:17px}.floor h3 a{color:inherit;text-decoration:none}
.map{overflow-x:auto;background:#0a1622;border-radius:8px;padding:6px;width:fit-content;max-width:100%}.map img{display:block;max-width:none;image-rendering:auto}
.map img[hidden]{display:none}
.cols{display:grid;grid-template-columns:1fr;gap:12px;margin-top:10px}@media(min-width:860px){.cols{grid-template-columns:1fr 1fr}}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:4px 6px;border-bottom:1px solid var(--edge);text-align:left;vertical-align:top}
th{color:var(--sub);font-weight:normal;font-size:12px}td.n{text-align:right;font-variant-numeric:tabular-nums}
a.k{color:var(--txt);text-decoration:underline dotted var(--sub)}.note{color:var(--sub);font-size:13px}.boss{color:var(--bad);font-weight:bold}
.chip{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:4px;border:1px solid var(--edge)}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--sub);margin:6px 0 0}
.tog{margin:6px 0;font-size:13px}.tog button{font:inherit;font-size:12px;background:var(--chip);color:var(--txt);border:1px solid var(--edge);
border-radius:6px;padding:3px 8px;cursor:pointer}.tog button.on{border-color:var(--acc);color:var(--acc)}
#q{width:100%;max-width:360px;font:inherit;padding:8px 10px;border-radius:8px;border:1px solid var(--edge);background:var(--panel);color:var(--txt)}
.dex{overflow-x:auto}.dex table{min-width:900px}.dex tr:target{background:var(--chip)}.dex td{white-space:nowrap}
.dex td.ap,.dex td.act{white-space:normal}.dex td.ap{font-size:12px;color:var(--sub);min-width:260px}.dex td.ap a{color:var(--sub)}
.dex td.act{min-width:170px}
.who{display:flex;align-items:center;gap:10px}.sprbox{flex:none;width:76px;min-height:52px;display:flex;align-items:center;
justify-content:center;background:#4b5a6a;border-radius:8px;padding:4px}.sprbox img{display:block;image-rendering:pixelated;max-width:68px}
.sprbox.none{font-size:11px;color:#dbe8f2;text-align:center;line-height:1.3;white-space:normal}
.sprbox{flex-direction:column}.sprbox small{font-size:10px;color:#dbe8f2;white-space:normal;text-align:center;line-height:1.25;margin-top:3px}
.bug{background:var(--panel);border:1px solid var(--edge);border-radius:12px;padding:12px 16px;margin:12px 0;max-width:860px}
.bug h3{margin:0 0 6px;font-size:16px}.bug p{margin:6px 0;line-height:1.75}.bug .src{font-size:12px;color:var(--sub);font-weight:normal}
.bug .why{font-size:13px;color:var(--sub);border-top:1px dashed var(--edge);padding-top:6px}
h2,.floor,.dex tr,.bug{scroll-margin-top:60px}
ul.rules li{margin:6px 0}code{background:var(--chip);padding:0 4px;border-radius:4px;font-size:13px}
.theme{margin-left:auto}
"""

JS = """
const tabs=[...document.querySelectorAll('nav [data-tab]')];
function show(id){tabs.forEach(b=>b.classList.toggle('on',b.dataset.tab==id));
document.querySelectorAll('section.tab').forEach(s=>s.classList.toggle('on',s.id==id));}
tabs.forEach(b=>b.onclick=()=>{show(b.dataset.tab);history.replaceState(null,'','#'+b.dataset.tab)});
function route(){const h=location.hash.slice(1);if(!h)return show('floors');
const el=document.getElementById(h);if(!el)return;const sec=el.closest('section.tab');if(sec)show(sec.id);
if(sec&&sec.id!=h)el.scrollIntoView();}
window.addEventListener('hashchange',route);route();
document.querySelectorAll('.tog button').forEach(b=>b.onclick=()=>{const f=b.closest('.floor');
f.querySelectorAll('.tog button').forEach(x=>x.classList.toggle('on',x==b));
f.querySelectorAll('.map img').forEach(im=>im.hidden=im.dataset.w!=b.dataset.w);});
const q=document.getElementById('q');if(q)q.oninput=()=>{const v=q.value.trim();
document.querySelectorAll('.dex tbody tr').forEach(tr=>tr.hidden=v&&!tr.textContent.includes(v));};
document.getElementById('theme').onclick=()=>{const r=document.documentElement;
const dark=matchMedia('(prefers-color-scheme: dark)').matches;const cur=r.dataset.theme||(dark?'dark':'light');
r.dataset.theme=cur=='dark'?'light':'dark';try{localStorage.setItem('mt1theme',r.dataset.theme)}catch(e){}};
try{const t=localStorage.getItem('mt1theme');if(t)document.documentElement.dataset.theme=t}catch(e){}
const fa=document.getElementById('fa'),fb=document.getElementById('fb'),fr=document.getElementById('fr');
if(fa){const by={};FU.d.forEach(x=>by[x[0]]=x);
const opts=FU.d.map(x=>'<option value="'+x[0]+'">'+x[1]+' ('+x[2]+' Lv'+x[3]+')</option>').join('');
fa.innerHTML=opts;fb.innerHTML=opts;fb.selectedIndex=1;
const calc=()=>{const A=by[fa.value],B=by[fb.value];const hi=Math.max(A[4],B[4]),lo=Math.min(A[4],B[4]);
const r0=FU.l[hi][lo],r=r0===undefined?FU.z:r0;const R=by[r];
fr.textContent='→ '+(R?R[1]+' ('+R[2]+' Lv'+R[3]+' · 나카지마 Lv'+Math.max(1,R[3]-7)+'부터)':'#'+r)+(r0===undefined?'  · 상성표 ※':'');};
fa.onchange=calc;fb.onchange=calc;calc();}
"""


def esc(s):
    return html.escape(str(s))


def kind_link(book, k):
    return '<a class="k" href="#d%02x">%s</a>' % (k & 0x7F, esc(book.name(k)))


def empty_record(book, k):
    rec = book.record(k)
    return rec is None or not any(rec)


def make_html(rom, dm, book, enc, ex, floors, fixed, appear):
    out = []
    w = out.append
    w('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<title>여신전생 1 롬 공략</title><style>%s</style></head><body>' % CSS)
    w('<header><h1>여신전생 1 (FC) 롬 해석 공략</h1>'
      '<p>지도·출현표·능력치를 전부 게임 롬에서 직접 읽어 만든 페이지입니다. 랜덤 전투 공식은 에뮬레이터 실측과 대조했습니다.</p></header>')
    w('<nav><div class="in"><button data-tab="floors">지역·층</button><button data-tab="dex">악마 도감</button>'
      '<button data-tab="fixed">고정 전투</button><button data-tab="equip">장비·가게</button>'
      '<button data-tab="fusion">합체·동료</button><button data-tab="magic">마법</button>'
      '<button data-tab="rules">규칙</button><button data-tab="bugs">버그</button>'
      '<button id="theme" class="theme" title="밝게/어둡게">◐</button></div></nav><main>')

    # 지역·층
    w('<section class="tab" id="floors"><div class="toc">')
    for a in AREAS:
        if any(fl.area == a[0] for fl in floors):
            w('<a href="#area-%s">%s</a>' % (a[0], esc(a[1])))
    w('</div>')
    w('<p><img alt="지도 범례" src="%s" style="max-width:100%%"></p>' % png_uri(draw_legend()))
    w('<p class="note">주황 화살표는 일방통행입니다. 화살표 쪽으로만 지나가고, 반대쪽에서는 벽처럼 막힙니다. '
      '게임은 지금 칸의 앞 면만 보고, 맞은편 칸의 기록은 보지 않습니다. 그래서 두 칸의 기록이 다른 경계는 '
      '한쪽에서만 지나갈 수 있습니다. '
      '발할라의 로키 자리는 이기기 전에는 보스전이고, 이긴 뒤에는 같은 칸이 텔레포트가 됩니다.</p>')
    cur = None
    for fl in floors:
        if fl.area != cur:
            cur = fl.area
            a = AREAS[AREA_IDX[cur]]
            w('<h2 id="area-%s">%s <small>%s</small></h2>' % (a[0], esc(a[1]), esc(a[2])))
        nums = {(x, y): i + 1 for i, (_b, x, y, _c, _k) in enumerate(fl.fixed)}
        cnums = {(x, y): chr(65 + i) for i, (x, y, _c, _i) in enumerate(fl.chests)}
        w('<div class="floor" id="%s"><h3><a href="#%s">%s</a></h3>' % (fl.anchor, fl.anchor, esc(fl.title)))
        if fl.differs:
            w('<div class="tog">표식: <button data-w="0" class="on">표 시나리오</button> '
              '<button data-w="1">裏 시나리오</button></div>')
        w('<div class="map">')
        for st in ((0, 1) if fl.differs else (0,)):
            img = draw_floor(dm, fl, st, nums, fl.tint, cnums)
            w('<img data-w="%d" %s alt="%s 지도" width="%d" height="%d" src="%s">'
              % (st, "hidden" if st else "", esc(fl.title), img.width, img.height, png_uri(img)))
        w('</div>')
        w('<div class="cols"><div>')
        if not fl.parts:
            w('<p class="note">랜덤 전투가 없는 층입니다.</p>')
        for idx, pt in enumerate(fl.parts):
            g = pt["groups"]
            gtxt = " · ".join("%d무리 %s" % (k, pct(v, 8)) for k, v in sorted(g.items()))
            head = "랜덤 전투"
            if len(fl.parts) > 1:
                head += ' <span class="chip" style="background:%s"></span>%s' % (TINT[min(idx, len(TINT) - 1)], "지도의 이 색 구역")
            w('<p><b>%s</b> <span class="note">무리 수: %s</span></p>' % (head, gtxt))
            w('<table><thead><tr><th>악마</th><th class="n">무리마다</th><th>마릿수</th><th class="n">HP</th>'
              '<th class="n">경험치</th></tr></thead><tbody>')
            for k, n in pt["table"]:
                info = book.info(k)
                w('<tr><td>%s</td><td class="n">%s</td><td>%s</td><td class="n">%d</td><td class="n">%d</td></tr>'
                  % (kind_link(book, k), pct(n, 16), count_text(enc.count_dist(k)), info["hp"], info["exp"]))
            w('</tbody></table>')
        if fl.safe.get("medusa"):
            w('<p class="note">%s 메두사를 쓰러뜨린 뒤에는 랜덤 전투가 없어집니다.</p>'
              % ("이 층은" if fl.safe["medusa"] >= fl.cells else "이 층의 일부는"))
        if fl.safe.get("always") and fl.parts:
            w('<p class="note"><span class="chip" style="background:%s"></span>회색 구역은 랜덤 전투가 없는 안전 구역입니다.</p>' % SAFE_TINT)
        w('</div><div>')
        if fl.fixed:
            w('<p><b>고정 전투</b> <span class="note">지도의 빨간 × 옆 번호</span></p><table><tbody>')
            for i, (blk, x, y, code, kind) in enumerate(fl.fixed):
                info = book.info(kind)
                tag = ' <span class="boss">보스</span>' if code == 15 else ""
                cond = ' <span class="note">(세트를 쓰러뜨리기 전에만)</span>' if kind == 0xF0 else ""
                if dm.bosses.get((x, y), (0, None))[1] == DW.WARP:     # 로키: 같은 칸에 텔레포트 표가 있다
                    cond = ' <span class="note">(이긴 뒤에는 이 칸이 텔레포트가 됨)</span>'
                if empty_record(book, kind):
                    w('<tr><td class="n">%d</td><td>%s <span class="note">(적 능력치가 비어 있음 — 전투가 아니라 '
                      '이벤트로 보임, 미확인)</span></td><td></td></tr>' % (i + 1, esc(book.name(kind))))
                    continue
                w('<tr><td class="n">%d</td><td>%s%s%s</td><td class="n">HP %d</td></tr>'
                  % (i + 1, kind_link(book, kind), tag, cond, info["hp"] if info else 0))
            w('</tbody></table>')
        if fl.chests:
            w('<p><b>보물상자</b> <span class="note">지도의 주황 상자 옆 글자</span></p><table><tbody>')
            for i, (x, y, cond, idx) in enumerate(fl.chests):
                when = {0x40: " <span class=\"note\">(표 시나리오만)</span>", 0x80: " <span class=\"note\">(裏 시나리오만)</span>"}.get(cond, "")
                w('<tr><td class="n">%s</td><td>%s%s</td></tr>' % (chr(65 + i), esc(ex.chest_text(idx)), when))
            w('</tbody></table>')
        for x, y, cond, kind in fl.shops:
            when = {0x40: " (표 시나리오만)", 0x80: " (裏 시나리오만)"}.get(cond, "")
            if kind == 6:
                B = ex.names["B"]
                w('<p><b>라그의 가게</b>%s <span class="note">돈은 받지 않고 「%s」 1개와 바꿔 준다. 없으면 그냥 돌려보내고, '
                  '무엇을 고르든 내준 것은 돌아오지 않는다.</span></p><table><tbody>' % (esc(when), esc(B[6])))
                for code, txt in ((0x13, "받는 순간 파티 전원의 HP 가 최대까지 회복"),
                                  (0x14, "받는 순간 벼락이 떨어져 파티 전원의 HP 가 절반(최소 1)"),
                                  (0x07, "획득. 이미 받았으면 이 자리가 「%s」로 바뀌고, 고르면 미콘 마을로 되돌아간다" % B[0x3F]),
                                  (0x12, "획득 (받은 뒤에는 목록에서 빠짐)")):
                    w('<tr><td>%s</td><td class="note">%s</td></tr>' % (esc(B.get(code, "?")), esc(txt)))
                w('</tbody></table>')
                continue
            blk = block_of_cell(dm, dm.block_of(x, y))
            sold = [it for it in ex.items if blk in it["blocks"]]
            w('<p><b>가게</b>%s <span class="note">지도의 노란 동전 · <a href="#equip">장비 표</a></span></p><table><tbody>' % esc(when))
            for it in sold:
                w('<tr><td>%s</td><td class="note">%s</td><td class="n">%d 마카</td></tr>'
                  % (esc(ex.names["B"].get(it["code"], "?")), WHO[it["who"]], it["price"]))
            w('</tbody></table>')
        w('</div></div></div>')
    w('</section>')

    # 도감
    w('<section class="tab" id="dex"><h2>악마 도감 <small>롬의 적 레코드 %d개</small></h2>'
      '<p><input id="q" placeholder="이름·종족·장소로 찾기"></p>'
      '<p class="note">HP 는 표 시나리오 값입니다(裏 시나리오에서는 게임이 두 배로 채웁니다). 경험치·마카·MAG 는 한 마리 기본값이고, '
      '실제로는 쓰러뜨린 한 마리마다 기본값에 0~1 을 더해 받습니다. 행동은 롬의 가중치 비율입니다. '
      '「내성 … +n」은 그 계열 공격 마법을 받을 때 방어가 평균 n 만큼 오른다는 뜻이고, 「달 n/8~」은 달이 그 위상보다 '
      '찰수록 공격·방어 굴림이 한 단계씩 늘어난다는 뜻입니다(<a href="#magic">마법</a> 탭 계산식). '
      '그림은 원판을 헤드리스 에뮬레이터에서 그 악마와 전투를 붙여, 게임이 그린 스프라이트를 그대로 뽑은 것입니다.</p>'
      '<div class="dex"><table><thead><tr>'
      '<th>이름</th><th>종족</th><th class="n">HP</th><th class="n">힘</th><th class="n">지</th><th class="n">공</th>'
      '<th class="n">속</th><th class="n">방</th><th class="n">경험치</th><th class="n">마카</th><th class="n">MAG</th>'
      '<th>마릿수</th><th>행동</th><th>마법 내성 · 달</th><th>나오는 곳</th></tr></thead><tbody>'
      % sum(1 for k in range(128) if not empty_record(book, k)))
    if not SPRITES:                                       # 검색창 바로 앞에 (표 머리까지 한 문자열이라 거기에 끼운다)
        out[-1] = out[-1].replace('<p><input id="q"', '<p class="note">배포판에는 악마 그림을 넣지 않았습니다(게임 그림이라서). '
                                  '원판 롬과 Mesen 원판 필드 세이브스테이트가 있으면 <code>python guide/capture_sprites.py</code> 로 그림을 뽑은 뒤 '
                                  '<code>python guide/make_guide.py</code> 를 다시 돌리면 들어갑니다.</p><p><input id="q"', 1)
    rows = []
    for k in range(128):
        info = book.info(k)
        if info is None or empty_record(book, k):
            continue
        rows.append((info["index"], k, info))
    name_count = Counter(info["name"] for _i, _k, info in rows)
    # capture_sprites.py 가 만든 그림 (없으면 이름만). ★배포판은 --no-sprites — 롬에서 뽑은 게임 그림을 공개 저장소에 싣지 않는다(2026-10-08 사용자 결정)
    spr_dir = os.path.join(HERE, "sprites") if SPRITES else os.path.join(HERE, "_no_sprites_")
    try:
        import json
        no_pic = json.load(open(os.path.join(spr_dir, "none.json"), encoding="utf-8"))
    except (OSError, ValueError):
        no_pic = {}
    try:
        spr_note = json.load(open(os.path.join(spr_dir, "notes.json"), encoding="utf-8"))
    except (OSError, ValueError):
        spr_note = {}

    def sprite_cell(k):
        p = os.path.join(spr_dir, "%02X.png" % k)
        if os.path.exists(p):
            from PIL import Image
            im = Image.open(p)
            note = spr_note.get("%02X" % k)
            return ('<span class="sprbox"><img alt="%s" width="%d" height="%d" src="data:image/png;base64,%s">%s</span>'
                    % (esc(note or ""), im.width, im.height, base64.b64encode(open(p, "rb").read()).decode(),
                       "<small>%s</small>" % esc(note) if note else ""))
        if "%02X" % k in no_pic:
            return '<span class="sprbox none">%s</span>' % esc(no_pic["%02X" % k])
        return ""
    for _i, k, info in sorted(rows):
        acts, merged, spell_of = [("일반 공격", info["normal"])], {}, {}
        for name, wt, c in info["actions"]:
            if c >= 0xC0 and c in SPECIAL_ATK:
                name = SPECIAL_ATK[c][0]
                spell_of[name] = "sx%02X" % c
            elif 0x80 <= c < 0xC0:
                spell_of[name] = "sp%d" % (c & 0x7F)
            merged[name] = merged.get(name, 0) + wt
        acts += sorted(merged.items(), key=lambda t: -t[1])
        tot = float(sum(wt for _n, wt in acts) or 1)
        atxt = ", ".join("%s %d%%" % ('<a class="k" href="#%s">%s</a>' % (spell_of[n], esc(n)) if n in spell_of else esc(n),
                                      round(100 * wt / tot)) for n, wt in acts if wt > 0)
        by_floor = {}
        for fl, how, v in appear.get(k, []):
            by_floor.setdefault(fl, []).append((how, v))
        places = []
        for fl, hs in by_floor.items():
            rs = sorted(v for h, v in hs if h == "r")
            fs = [v for h, v in hs if h == "f"]
            bits = []
            if rs:
                bits.append(pct(rs[0], 16) if rs[0] == rs[-1] else "%s~%s" % (pct(rs[0], 16)[:-1], pct(rs[-1], 16)))
            if fs:
                bits.append("보스" if 15 in fs else "고정")
            places.append('<a href="#%s">%s</a> %s' % (fl.anchor, esc(fl.title), " · ".join(bits)))
        dup = name_count[info["name"]] > 1
        w('<tr id="d%02x"><td><div class="who">%s<b>%s</b></div></td><td>%s</td><td class="n">%d</td><td class="n">%d</td><td class="n">%d</td>'
          '<td class="n">%d</td><td class="n">%d</td><td class="n">%d</td><td class="n">%d</td><td class="n">%d</td>'
          '<td class="n">%d</td><td>%s</td><td class="act">%s</td><td class="ap">%s</td><td class="ap">%s</td></tr>'
          % (k, sprite_cell(k), esc(info["name"]) + (' <span class="note">(#%d)</span>' % info["index"] if dup else ""), esc(info["race"]), info["hp"], info["str"], info["int"], info["atk"], info["spd"],
             info["def"], info["exp"], info["macca"], info["mag"], count_text(enc.count_dist(k)), atxt,
             esc(resist_text(book, k)), ", ".join(places) or "출현표·고정 전투에는 없음 (이벤트 전용일 수 있음)"))
    w('</tbody></table></div></section>')

    # 고정 전투
    w('<section class="tab" id="fixed"><h2>고정 전투 <small>%d곳</small></h2><table><thead><tr><th>장소</th><th>악마</th>'
      '<th class="n">HP</th><th>비고</th></tr></thead><tbody>' % len(fixed))
    where = {}
    for fl in floors:
        for f in fl.fixed:
            where[f] = fl
    for f in sorted(fixed, key=lambda f: (where[f].key if f in where else (99, 0), f[3])):
        blk, x, y, code, kind = f
        fl = where.get(f)
        info = book.info(kind)
        note = "보스 — 쓰러뜨리면 다시 안 나옴" if code == 15 else ""
        if kind == 0xF0:
            note = "세트를 쓰러뜨리기 전에만"
        empty = empty_record(book, kind)
        if empty:
            note = "적 능력치가 비어 있음 — 전투가 아니라 이벤트로 보임(미확인)"
        w('<tr><td>%s</td><td>%s</td><td class="n">%s</td><td>%s</td></tr>'
          % ('<a href="#%s">%s</a>' % (fl.anchor, esc(fl.title)) if fl else "(%d,%d)" % (x, y),
             esc(book.name(kind)) if empty else kind_link(book, kind), "" if empty else info["hp"], esc(note)))
    w('</tbody></table></section>')

    # 장비·가게
    shop_where = {}
    for fl in floors:
        for x, y, cond, kind in fl.shops:
            if kind == 4:
                shop_where.setdefault(block_of_cell(dm, dm.block_of(x, y)), fl)
    item_of = {it["code"]: it for it in ex.items}
    chest_of = {}
    for fl in floors:
        for x, y, cond, idx in fl.chests:
            if ex.chest_val[idx] in (0x30, 0x37):             # 장비 상자만 (10~50 은 마카 배수라 코드와 겹친다)
                chest_of.setdefault(ex.chest_val[idx], fl)
    w('<section class="tab" id="equip"><h2>장비 <small>롬의 수치표·가게 품목표</small></h2>'
      '<p class="note">수치는 롬 표 값에서 맨몸 값을 뺀 것입니다(무기는 공격, 나머지는 방어). '
      '물리 공격은 무기 값 + 15 번 동전을 던져 앞면 수를 더합니다. 물리 방어는 機敏さ + 갑옷 + 방패 + 투구÷4 − 4×(구역+1) 번 '
      '던진 앞면 수입니다(표 값 그대로, 맨몸 갑옷 8·방패 4·투구 4. 코드가 레벨을 넣었다가 바로 덮어써서 레벨은 안 들어감, '
      '뱅크0B <code>$A4F6</code>→<code>$A43C</code>). 적의 마법을 받을 때는 지력 + 운 + 투구 − 8 − 달 번을 던져 레벨에 '
      '더합니다 — 투구는 마법 방어에 ÷4 없이 통째로 들어갑니다. '
      '「맞히는 적」은 한 번 공격에 고른 무리에서 맞히는 수로, 최대 v 인 무기는 매번 1 + (v−1 번 중 앞면 수)마리입니다 '
      '(난무의 검 1~8마리 중 4~5마리가 55%%, 붉은 검·페르세우스의 검 1~4마리 중 2~3마리가 75%%). 같은 피해가 모두에게 들어갑니다. '
      '동료 악마는 늘 1마리, 보스의 물리 공격은 구역에 따라 파티 %s명입니다. '
      '「장착」은 가게 품목표의 장착자 칸으로, 가게는 고른 사람과 다르면 팔지 않습니다(뱅크0 <code>$A9CB</code>). '
      '그래서 공략집이 유미코용이라 적은 페르세우스의 검은 실제로는 나카지마 전용입니다. 새 장비를 사면 쓰던 것은 반값에 넘깁니다.</p>'
      % "·".join(str(v) for v in ex.boss_reach))
    for lo, hi, cat, _t, _b in EQUIP_KIND:
        w('<h2 id="eq-%s">%s</h2><div class="dex"><table style="min-width:640px"><thead><tr><th>이름</th><th class="n">수치</th>'
          '%s<th>장착</th><th class="n">가격</th><th>파는 곳 / 얻는 곳</th></tr></thead><tbody>'
          % (cat, cat, '<th>맞히는 적</th>' if cat == "무기" else ""))
        for e in (e for e in ex.equip if e["cat"] == cat):
            it = item_of.get(e["code"])
            where = []
            if it:
                for b in it["blocks"]:
                    fl = shop_where.get(b)
                    if fl:
                        where.append('<a href="#%s">%s 가게</a>' % (fl.anchor, "미콘 마을" if fl.area == "daedalus"
                                                                     else esc(AREAS[AREA_IDX[fl.area]][1])))
            if e["code"] in chest_of:
                fl = chest_of[e["code"]]
                where.append('<a href="#%s">%s 상자</a>' % (fl.anchor, esc(fl.title)))
            who = WHO[e["who"]] if e["who"] is not None else "—"
            v = ex.reach.get(e["code"], 1)
            reach = ("<td>%s</td>" % ("1" if v == 1 else "1~%d" % v)) if cat == "무기" else ""
            w('<tr><td>%s</td><td class="n">%d</td>%s<td>%s</td><td class="n">%s</td><td class="ap">%s</td></tr>'
              % (esc(e["name"]), e["value"], reach, who, it and "%d" % it["price"] or "", " · ".join(where) or "가게·상자에는 없음"))
        w('</tbody></table></div>')
    w('</section>')

    # 합체
    A = ex.names["A"]
    race_name = lambda a: A.get(147 + ex.ally_race[a], "?")
    members = defaultdict(list)
    for a, g in sorted(ex.group.items()):
        members[g].append(a)
    w('<section class="tab" id="fusion"><h2>합체 <small>사교의 관</small></h2>'
      '<p class="note">두 악마의 <b>그룹</b>(같은 종족을 레벨대로 2~3묶음으로 나눈 것)으로 결과가 정해집니다. '
      '아래 「만드는 법」에 없는 조합은 모두 <b>드리아드</b>가 되고 상성표에는 ※ 로 나옵니다. '
      '결과 악마의 레벨이 <b>나카지마 레벨 + 7</b> 보다 높으면 거절합니다(뱅크0 <code>$A223</code>). '
      '레벨은 게임 어디에도 표시되지 않는 롬의 표(<code>$A08D</code>) 값입니다.</p>'
      '<p><select id="fa"></select> + <select id="fb"></select></p><p id="fr" style="font-size:18px"></p>')
    w('<h2>그룹</h2><table><thead><tr><th>그룹</th><th>종족</th><th>악마 (레벨)</th></tr></thead><tbody>')
    for g in sorted(members):
        w('<tr><td class="n">%d</td><td>%s</td><td>%s</td></tr>' % (g, esc(race_name(members[g][0])), " · ".join(
            "%s (%d)" % (esc(A.get(a, "?")), ex.ally_level[a]) for a in members[g])))
    w('</tbody></table>')
    w('<h2>만드는 법 <small>결과 악마별</small></h2><div class="dex"><table style="min-width:640px"><thead><tr><th>결과</th>'
      '<th class="n">레벨</th><th>재료 (그룹 + 그룹)</th></tr></thead><tbody>')
    recipes = defaultdict(list)
    for hi, L in enumerate(ex.lists):
        for lo, res in L.items():
            recipes[res].append((hi, lo))
    gname = lambda g: "%s(%s)" % (race_name(members[g][0]), "·".join(A.get(a, "?") for a in members[g]))
    recipes[FUSION_DEFAULT] = recipes.get(FUSION_DEFAULT, [])
    for res in sorted(recipes, key=lambda r: (ex.ally_level.get(r, 0), r)):
        how = [esc("%s + %s" % (gname(hi), gname(lo))) for hi, lo in recipes[res]]
        if res == FUSION_DEFAULT:
            how.append("그 밖에 이 표에 없는 모든 조합 (상성표 ※)")
        w('<tr><td>%s</td><td class="n">%s</td><td class="ap">%s</td></tr>'
          % (esc(A.get(res, "#%d" % res)), ex.ally_level.get(res, ""), "<br>".join(how)))
    w('</tbody></table></div>')
    C = ex.names["C"]
    spell_link = lambda n: '<a class="k" href="#sp%d">%s</a>' % (n, esc(C.get(n, "#%d" % n)))

    def mag_text(c):
        if c == 0:
            return "0"
        return "%d" % (c // 16) if c >= 16 else "%d걸음에 1" % (-(-16 // c))
    w('<h2 id="allies">동료 능력 <small>롬의 동료 레코드 (적으로 나올 때와 다름)</small></h2>'
      '<p class="note">레벨은 합체 거절에 쓰는 값이고 「합체 가능」은 그 악마를 만들 수 있는 나카지마 레벨입니다. '
      '「물리 위력」은 악마가 일반 공격할 때 동전을 던지는 횟수로, 상태 화면의 공격 수치와 따로 정해진 숨은 값입니다 '
      '(공격이 비슷해도 실제 피해가 크게 다른 까닭). 마법은 전투 중에만 씁니다. '
      '「MAG/걸음」은 이 악마 혼자 데리고 다닐 때 걸음마다 드는 마그네타이트입니다 — 게임은 데리고 있는 악마의 값(롬 값)을 '
      '모두 더해 16으로 나눈 몫만큼 빼고 나머지는 버리며, 합이 16 미만이면 16이 될 때까지 쌓아 둡니다.</p>'
      '<div class="dex"><table style="min-width:980px"><thead><tr><th>악마</th><th>종족</th><th class="n">레벨</th>'
      '<th class="n">합체 가능</th><th class="n">HP</th><th class="n">MP</th><th class="n">강</th><th class="n">지</th>'
      '<th class="n">공</th><th class="n">속</th><th class="n">방</th><th class="n">물리 위력</th><th>MAG/걸음 (롬 값)</th>'
      '<th>마법</th></tr></thead><tbody>')
    for a in sorted(ex.ally, key=lambda a: (-ex.ally_level[a], a)):
        al, mg = ex.ally[a], ex.magic
        w('<tr><td><b>%s</b></td><td>%s</td><td class="n">%d</td><td class="n">%d</td><td class="n">%d</td><td class="n">%d</td>'
          '%s<td class="n">%d</td><td>%s <span class="note">(%d)</span></td><td class="ap">%s</td></tr>'
          % (esc(A.get(a, "?")), esc(race_name(a)), ex.ally_level[a], max(1, ex.ally_level[a] - 7), al["hp"], al["mp"],
             "".join('<td class="n">%d</td>' % s for s in al["stats"]), al["power"], mag_text(al["mag"]), al["mag"],
             " · ".join(spell_link(n) for n in mg.ally_spells[a]) or "—"))
    w('</tbody></table></div></section>')
    import json
    fusion_js = json.dumps({"d": [[a, A.get(a, "?"), race_name(a), ex.ally_level[a], g] for a, g in sorted(ex.group.items())],
                            "l": [{str(k): v for k, v in L.items()} for L in ex.lists], "z": FUSION_DEFAULT}, ensure_ascii=False)

    # 마법
    mg = ex.magic
    ok2, ok3 = 128 - mg.all_zero[2], mg.all_zero[3]
    w('<section class="tab" id="magic"><h2>마법 <small>롬의 마법 표 36개</small></h2>'
      '<p class="note">MP·대상·종류·위력·속성은 롬의 표 그대로입니다. 「상대 n」은 아군이 쓰면 고른 적 한 무리 안에서 최대 n마리, '
      '적이 쓰면 파티에서 무작위 n명입니다. 유미코 칸의 점수는 <b>레벨×2 + 나카지마 지력 + 유미코 지력</b>이 그 값 이상이면 '
      '배운다는 뜻이고(레벨은 두 사람이 같음), 「이동」·「전투」는 어디서 쓸 수 있는지입니다. 동료 악마의 마법은 전투 중에만 씁니다.</p>'
      '<div class="dex"><table style="min-width:1000px"><thead><tr><th>마법</th><th>원래 이름</th><th>종류</th>'
      '<th class="n">MP</th><th>대상</th><th>효과</th><th>유미코</th><th>동료 악마</th><th>쓰는 적</th></tr></thead><tbody>')
    for n in range(36):
        y = mg.yumi.get(n)
        ytxt = "%d점 · %s" % (10 * (y[0] + 1), "·".join(s for s, f in (("이동", y[1]), ("전투", y[2])) if f)) if y else ""
        allies = ", ".join(esc(A.get(a, "?")) for a in mg.ally_users.get(n, []))
        foes = ", ".join(kind_link(book, k) for k in mg.enemy_users.get(n, []))
        w('<tr id="sp%d"><td><b>%s</b></td><td>%s</td><td>%s</td><td class="n">%d</td><td>%s</td><td class="act">%s</td>'
          '<td>%s</td><td class="ap">%s</td><td class="ap">%s</td></tr>'
          % (n, esc(C.get(n, "#%d" % n)), esc(SPELL_JP[n]), SPELL_KIND[mg.kind[n]] if mg.kind[n] < 6 else "?", mg.mp[n],
             target_text(mg.target[n]), esc(mg.effect(n)), ytxt, allies or "—", foes or "—"))
    w('</tbody></table></div>')
    w('<h2 id="specials">적의 특수 공격 <small>도감 「행동」의 마법이 아닌 것</small></h2>'
      '<p class="note">피해형은 적 공격 마법과 같은 식으로 받는 쪽의 마법 방어(지력·운·투구)가 막습니다. 평소에는 1명, '
      '보스전에서는 구역에 따라 파티 %s명을 노립니다. 상태이상형은 1명에게 %d/128(약 %d%%) 확률로 걸리고, '
      '이미 독·마비·돌 중 하나에 걸려 있으면 실패합니다. 이 상태들은 전투가 끝나도 남아 크링크나 사교의 관에서 풉니다.</p>'
      '<div class="dex"><table style="min-width:820px"><thead><tr><th>특수 공격</th><th>화면 문구</th><th>효과</th>'
      '<th>쓰는 적</th></tr></thead><tbody>' % ("·".join(str(v) for v in ex.boss_reach), mg.all_zero[2],
                                             round(100.0 * mg.all_zero[2] / 128)))
    for code, (nm, msg) in sorted(SPECIAL_ATK.items()):
        eff = ("위력 %d" % mg.special_power[code]) if code in mg.special_power else SPECIAL_EFFECT.get(code, "")
        foes = ", ".join(kind_link(book, k) for k in mg.special_users.get(code, []))
        w('<tr id="sx%02X"><td><b>%s</b></td><td class="note">…%s</td><td class="act">%s</td><td class="ap">%s</td></tr>'
          % (code, esc(nm), esc(msg), esc(eff), foes or "—"))
    w('</tbody></table></div>')
    w('<h2>유미코가 배우는 순서</h2><table><thead><tr><th class="n">점수</th><th>마법</th><th>쓰는 곳</th></tr></thead><tbody>')
    for n, (t, f, b) in sorted(mg.yumi.items(), key=lambda t: t[1][0]):
        w('<tr><td class="n">%d</td><td>%s</td><td>%s</td></tr>'
          % (10 * (t + 1), spell_link(n), "·".join(s for s, ok in (("이동 중", f), ("전투", b)) if ok)))
    w('</tbody></table><p class="note">게임 계산: 단계 = ⌊(레벨 + ⌊(나카지마 지력 + 유미코 지력 − 10) ÷ 2⌋) ÷ 5⌋ '
      '(뱅크3 <code>$BA01</code>), 단계마다 고정 뱅크 <code>$EEDA</code> 의 표에서 쓸 수 있는 마법이 정해집니다. '
      '레벨이 깎이면(에너지 드레인) 다시 계산하므로 배운 마법을 잃을 수도 있습니다. 처음부터 12점 이상이라 맛파는 늘 씁니다.</p>')
    w('<h2>계산식 <small>롬 역어셈블</small></h2><ul class="rules">'
      '<li>기호: <b>동전(x)</b> = 동전 x번 중 앞면 수(평균 x/2), <b>주사위(x)</b> = 0·1·2 중 하나를 x번 더한 값(평균 x). '
      '<b>달</b> = 0(새달)~8(보름), 16걸음마다 한 칸씩 오르내림. <b>구역</b> = 0 다이달로스의 탑 · 1 비엔 마을 · 2 발할라의 회랑 · '
      '3 마즈르카 · 4 불의 바다 · 5 앙피니 궁전·붉은 탑. 적의 강\'·지\'는 도감 값 − 5, 「달 문턱」은 도감의 「달 n/8~」에서 1을 뺀 값.</li>'
      '<li><b>아군 → 적 공격 마법</b>: 공격 = 동전(N) − K (0 미만은 0) + 동전(위력). K = (강함+지력) − (공격+機敏さ+운) + 4 (0 미만은 0). '
      'N 은 원래 시전자의 (강함+지력)×2 였을 자리인데 <a href="#bugs">원판 버그</a>로 나카지마의 기록을 대열 자리에 따라 읽습니다: '
      '1번째 = 레벨×2, 2번째 = (레벨 + 현재 HP 아래 바이트)×2, 3번째 = (현재 HP 아래+위 바이트)×2, 4번째 = (현재 HP 위 + 최대 HP 아래)×2, '
      '5번째 = (최대 HP 아래+위)×2 — 256을 넘으면 넘친 만큼만 남습니다.<br>'
      '적 방어 = 지\'×8 + 주사위(내성×2 + 강\' + 달이 문턱을 넘은 칸 수). 피해 = (공격 − 방어, 0 미만은 0) + 동전(위력)÷2, 최대 255. '
      '맞힌 적은 모두 같은 피해를 받습니다.</li>'
      '<li><b>적 → 아군 공격 마법</b>: 공격 = 위력 + 동전(강\' + 지\'×4 + 달이 문턱을 넘은 칸 수). '
      '방어 = 기본 + 동전(지력 + 운 + 투구 − 8 − 달). 기본은 나카지마·유미코가 레벨(테트라자 중이면 +2×(구역+1)), 악마가 레벨×2. '
      '투구는 장비 표 값(맨머리 4, 악마 0). 피해 = (공격 − 방어, 0 미만은 0) + 동전(위력)÷2, 「방어」 중이면 절반. '
      '괄호 안이 음수가 되면 게임이 0으로 막지 않아 250 안팎으로 넘칩니다(<a href="#bugs">버그</a>, 실측 확인).</li>'
      '<li><b>상태이상</b>(도르민·프린파·놋프·마린카린·굿스리토·에토나): 능력치와 상관없이 %d/128(약 %d%%) 성공. '
      '이미 상태이상인 대상, 보스전의 적에게는 실패합니다. 냉기 계열(브리즈·브리자·브리자톤)은 피해를 입고 살아남은 대상을 '
      '덤으로 얼립니다(FREEZE, 판정 없음).</li>'
      '<li><b>전투 중 상태이상이 가는 시간</b>: CLOSE(움직일 수 없음·제정신을 잃음)와 SLEEP 은 그 캐릭터(적도 같음)의 차례가 올 때마다 '
      '행동하지 못하고, 그때마다 %d/128(약 %d%%) 확률로 풀립니다 — 평균 약 %.1f번의 차례를 쉬며, 풀린 차례도 쉽니다. '
      'FREEZE 는 그 라운드가 끝나면 저절로 풀리고, 마법 봉인은 행동은 하지만 주문을 「외우려 했지만 말할 수 없다」며 실패하고 '
      '전투가 끝나거나 팟치를 받을 때까지 갑니다(뱅크0D <code>$ACCA</code>·<code>$AD59</code>·<code>$AC60</code>).</li>'
      '<li><b>메디·메디카</b> 회복량 = 0~3 을 (대상의 강함×2 − 12 + 4×(구역+1))번 더한 값 — 시전자가 아니라 받는 쪽의 강함으로 정해집니다. '
      '원래는 강함+운이었을 자리에 <a href="#bugs">버그</a>로 강함이 두 번 들어갑니다.</li>'
      '<li><b>리캄</b>: 사람은 늘 HP 1 로 되살아납니다. 악마는 %d/128(약 %d%%) 확률로 「사라졌다」며 동료에서 빠집니다.</li>'
      '<li>하이퍼·테트라자의 효과는 그 전투가 끝나면 사라집니다. 테트라자는 에너지 드레인(레벨 1이면 원래 안 통함)을 막고 '
      '나카지마·유미코의 마법 방어만 올립니다.</li>'
      '</ul></section>' % (ok2, round(100.0 * ok2 / 128), mg.all_zero[2], round(100.0 * mg.all_zero[2] / 128),
                           128.0 / mg.all_zero[2], ok3, round(100.0 * ok3 / 128)))

    # 규칙
    w('<section class="tab" id="rules"><h2>랜덤 전투 규칙 <small>롬 역어셈블 + 에뮬레이터 실측</small></h2><ul class="rules">')
    w('<li><b>문으로 들어선 걸음</b>은 %s, <b>그 밖의 걸음</b>은 약 %s 확률로 전투가 납니다. '
      '게임은 걸음마다 난수를 문이면 %d번, 아니면 %d번 연달아 뽑아 전부 「꽝 없음」일 때만 전투를 겁니다.</li>'
      % (pct(enc.rate[6], 1), pct(enc.rate[3], 1), enc.draws[6], enc.draws[3]))
    w('<li>무리 수는 장소(16×16칸 구역)마다 정해진 비율로 1~4무리, <b>무리마다</b> 그 장소의 표 16칸 중 하나를 고르게 뽑습니다. '
      '그래서 표의 「무리마다」 확률은 16칸 중 그 악마가 차지한 칸 수입니다.</li>')
    w('<li>마릿수는 악마마다 정해져 있습니다: 1~4마리 중 무작위, 고정 수, 또는 「기준 −2 ~ +1」 범위(0이 나오면 그 무리는 빠짐).</li>')
    w('<li>안전 구역: 다이달로스의 탑 8층 전체와 발할라의 회랑 일부는 랜덤 전투가 없습니다. '
      '비엔 마을 2층 마을 구역은 메두사를 쓰러뜨린 뒤 안전해집니다.</li>')
    w('<li>고정 전투는 지도의 빨간 × 칸에 들어서면 일어나고 한 마리만 나옵니다. 보스는 쓰러뜨리면 다시 나오지 않습니다.</li>')
    w('<li>裏 시나리오(깃발 <code>$07FF</code> bit7)에서는 적의 최대 HP 가 두 배가 되고, 일부 시설·상자 자리가 바뀌거나 없어집니다 '
      '(지도 위 「裏 시나리오」 단추).</li>')
    w('<li>보상: 쓰러뜨린 적 한 마리마다 경험치·마카·MAG 를 도감의 기본값 + 0~1 만큼 모아 전투가 끝나면 받습니다. '
      'MAG 는 8191 에서 멈춥니다.</li>')
    w('<li>보물상자 「레벨 × N 마카」는 여는 순간 나카지마 레벨이 짝수일 때만 마카가 나오고, 홀수면 그 자리의 랜덤 전투가 납니다. '
      '「500 마카 + 보옥」 상자는 마카가 500 미만이고 장비가 하나도 없을 때 열리며, 열린 표시가 남지 않아 다시 열 수 있습니다.</li>')
    w('</ul><p class="note">검증: 헤드리스 Mesen 으로 무작위로 걸으며 게임이 출현 루틴을 부를 때의 입력과 결과를 기록해 '
      '악마 종류 285건·전투 판정 460건·무리 수 42건·마릿수 285건이 전부 위 계산과 같았습니다. '
      '가게 가격은 공략집의 다이달로스 8층 8품목과, 합체는 원판 사교의 관 화면(상성표 25칸·결과 키마이라)과 같습니다. '
      '원판과 한글판(v52·v53)의 표는 바이트까지 같습니다. '
      '지역 이름과 층 순서는 공개 공략집의 목차에 맞췄습니다.</p>')
    w('<h2>물리 공격 계산식 <small>뱅크0B <code>$A10F</code>·<code>$A41F</code></small></h2><ul class="rules">'
      '<li>기호는 <a href="#magic">마법</a> 탭과 같습니다(동전·주사위·달·구역, 적의 강\'·공\'·속\'·방\' = 도감 값 − 5).</li>'
      '<li><b>아군 → 적</b>: 기본 = 레벨(나카지마·유미코는 나카지마 레벨, 악마는 합체 레벨) + 하이퍼 중이면 4×(구역+1). '
      '앞몫 = 기본 + 동전(機敏さ + (공격−4)×2), 덜어 낼 몫 = 동전((공격−4)×2 − (지력+機敏さ+운−12), 0 미만은 0). '
      '앞몫이 덜어 낼 몫 이상이면 그 차이, 아니면 기본만 남깁니다. 여기에 동전(무기)을 더한 것이 공격입니다 — 무기는 사람이면 '
      '무기 표 값 + 15, 악마면 <a href="#allies">숨은 물리 위력</a>.<br>'
      '적 방어 = 방\'×8 + 동전(속\' + 달이 문턱을 넘은 칸 수). 피해 = (공격 − 방어, 0 미만은 0) + 동전(무기)÷2, 최대 255. '
      '무기가 맞히는 적 수만큼 같은 피해가 들어가고, 헤카테는 라토스상이 없으면 0 입니다.</li>'
      '<li><b>적 → 아군</b>: 공격 = 공\'×8 + 주사위(강\' + 속\' + 달이 문턱을 넘은 칸 수). '
      '방어는 나카지마·유미코가 동전(機敏さ + 갑옷 + 방패 + 투구÷4 − 4×(구역+1)), 악마가 동전(방어×8). '
      '피해 = (공격 − 방어, 0 미만은 0) + 동전(강\'×2)÷2, 최대 255. 「방어」 중이면 1/4 로 줄어듭니다(마법은 1/2). '
      '평소에는 1명, 보스는 구역에 따라 %s명을 칩니다.</li></ul>' % "·".join(str(v) for v in ex.boss_reach))
    B = ex.names["B"]
    w('<h2>보스전 아이템 <small>뱅크0D <code>$A646</code></small></h2><p class="note">아래 아이템은 쓰지 않아도 '
      '<b>가지고 있기만 하면</b> 그 보스전 첫머리에 나카지마가 저절로 사용합니다.</p><table><tbody>')
    for boss, item, txt in ((0xE3, 1, "돌로 만드는 공격을 막음"), (0xE4, 5, "로키의 주문이 들리지 않게 됨(마법 무효)"),
                            (0xE5, 10, "헤카테를 실체화 — 없으면 물리 공격이 0"),
                            (0xE6, 17, "세트의 물리 공격을 막음"), (0xE7, 16, "루시퍼의 메디카르(완전 회복)를 막음")):
        w('<tr><td>%s</td><td>%s</td><td class="note">%s</td></tr>' % (kind_link(book, boss), esc(B.get(item, "?")), esc(txt)))
    w('</tbody></table>')
    w('<p class="note">코드로만 확인한 것: 적의 물리 방어에서 버려지는 값, 물리 방어에 레벨이 안 들어가는 것(둘 다 버그 탭). '
      '나머지 버그·계산식은 롬 역어셈블에 더해 공략집 수치나 헤드리스 에뮬레이터 실측과 맞춰 봤습니다.</p>')
    w('<p class="note">만든 롬: %s</p></section>' % esc(os.path.basename(rom)))

    # 버그
    srcs = {"cat": '<a href="https://w.atwiki.jp/gcmatome/pages/7179.html">게임 카탈로그@Wiki</a>',
            "neta": '<a href="http://dds.opatil.com/dds1/data/neta.html">공략집 소네타</a>',
            "yakata": '<a href="https://8bit-yakata.sakura.ne.jp/wp/urawaza/dds/">8bit-yakata</a>',
            "rom": "롬 (이 페이지에서 처음 찾음)"}
    al = ex.ally
    trio = [a for a in al if A.get(a) in ("크리슈나", "가네샤", "원롱")]
    bugs = (
        ("아군 공격 마법의 위력이 대열 자리로 정해짐",
         "유미코·동료가 쓰는 공격 마법의 피해가 시전자의 강함·지력이 아니라 <b>서 있는 대열 자리</b>와 나카지마의 레벨·HP 에 따라 "
         "들쭉날쭉합니다. 자리 1 은 나카지마 레벨×2, 2 는 (레벨 + 현재 HP 아래 바이트)×2 처럼 읽혀 256 을 넘으면 넘친 만큼만 "
         "남습니다(<a href=\"#magic\">마법</a> 탭 계산식).",
         "뱅크0B <code>$A300</code>: 시전자 기록 오프셋(Y)으로 읽어야 할 <code>$04B3,Y</code>·<code>$04B4,Y</code> 를 "
         "자리 번호(X)로 읽는다.", ("cat", "neta")),
        ("동료의 행동 순서가 다음 칸 동료의 機敏さ",
         "전투 행동 순서에 동료 자신의 機敏さ 대신 동료 목록에서 <b>한 칸 아래 동료</b>의 값이 쓰입니다. 맨 아래 동료는 아래가 비어 "
         "0 − 4 = 252 가 되어 가장 먼저 움직입니다. 나카지마·유미코는 정상.",
         "뱅크0D <code>$B588</code>: 동료 번호에서 2를 빼야 하는데 1만 빼서 18바이트 다음 기록의 <code>$04DF</code> 를 읽는다.",
         ("cat", "neta")),
        ("크리슈나·가네샤·원롱을 함께 데리고 다니면 마그네타이트가 줄지 않음",
         "세 악마의 걸음당 값 %s 의 합이 정확히 256 이라 1바이트 덧셈이 0 이 됩니다. 서로 다른 동료 조합 중 합이 256 인 것은 이 "
         "셋뿐입니다(같은 악마 둘을 넣으면 크리슈나·크리슈나·바롱 같은 조합도 됨)." % "+".join(str(al[a]["mag"]) for a in trio),
         "뱅크7 <code>$A3B0</code>: 넘치면 255 로 막는 코드가 「넘쳤는데 결과가 0」인 경우를 건너뛴다.", ("neta", "yakata")),
        ("메디·메디카 회복량에 운이 빠짐",
         "회복량이 받는 쪽의 강함과 구역만으로 정해집니다(강함이 두 번 들어감).",
         "뱅크0B <code>$BB4A</code>: 다섯째 능력치 오프셋을 Y 에 읽고 <code>LDA</code> 없이 바로 빼서 강함 − 4 를 한 번 더 쓴다.", ("rom",)),
        ("적 마법을 받을 때 방어 굴림이 넘침",
         "지력 + 운 + 투구 − 8 이 달보다 작으면(보름 무렵의 약한 악마, 지력·운이 낮은 맨머리 나카지마) 방어 굴림 수가 음수가 되는데, "
         "게임이 0 으로 막지 않아 250 안팎이 됩니다 — 그러면 적 마법 피해가 크게 줄어듭니다. 실측: 지력·운 5·맨머리로 세트의 "
         "가보앗토를 맞으면 달 8 에서 굴림 수 254·방어 129·피해 약 82, 달 5 에서 굴림 수 1·방어 3·피해 약 205.",
         "뱅크0B <code>$A6A2</code>: 같은 루틴의 다른 뺄셈(<code>$A614</code>)에는 있는 0 막기가 여기에는 없다. "
         "헤드리스 Mesen 에서 <code>$A6A5</code>·<code>$A6BE</code> 를 기록해 확인.",
         ("rom",)),
        ("적의 물리 방어에 공격 수치가 빠짐",
         "아군이 적을 칠 때 적의 방어 굴림에 속도만 들어가고, 바로 앞에서 더한 공격 수치는 버려집니다. 같은 모양의 마법 방어 루틴은 "
         "더한 값을 저장합니다. 결과적으로 적의 물리 방어가 의도보다 낮을 것으로 보입니다.",
         "뱅크0B <code>$A23E</code>: <code>LDY</code> 대신 <code>LDX #0</code> 으로 레코드를 다시 읽고 더한 뒤 "
         "<code>STA</code> 없이 다음 값을 읽는다(마법 쪽 <code>$A3B3</code> 에는 <code>STA $069B</code> 가 있음). 코드상 판단.",
         ("rom",)),
        ("물리 방어에 레벨이 안 들어감",
         "아군의 물리 방어 계산이 레벨을 넣었다가 곧바로 굴림 결과로 덮어써서, 레벨이 올라도 물리 방어는 장비·機敏さ 로만 오릅니다 "
         "(마법 방어에는 레벨이 들어감).",
         "뱅크0B <code>$A4F6</code> 에서 <code>$069F</code> 에 레벨을 넣고, 돌아온 <code>$A43C</code> 가 굴림 값으로 덮는다. "
         "의도였는지는 알 수 없음.", ("rom",)),
        ("테트라자의 설명서 설명과 실제가 다름",
         "설명서에는 「방어력을 올린다」고만 되어 있지만 물리 방어는 오르지 않습니다. 실제로는 에너지 드레인을 막고 "
         "나카지마·유미코의 마법 방어만 +2×(구역+1) 올립니다. 유미코는 배우지 않습니다.",
         "뱅크0B <code>$B975</code> 가 <code>$0671</code> 을 켜고, 그 값을 읽는 곳은 마법 방어(<code>$A63D</code>)와 "
         "에너지 드레인(뱅크0D <code>$B2C3</code>)뿐.", ("cat",)),
        ("동료의 「공격」 수치와 실제 물리 피해가 따로 놂",
         "동료 악마의 물리 피해는 종족별 숨은 위력으로 굴립니다 — 공격 17 인 나가(위력 %d)와 공격 12 인 츠쿠요미(위력 %d)가 비슷하고, "
         "와이번(위력 %d)이 동료 중 손꼽히게 셉니다(<a href=\"#allies\">동료 능력</a> 표)."
         % tuple(next((al[a]["power"] for a in al if A.get(a) == nm), 0) for nm in ("나가", "츠쿠요미", "와이번")),
         "뱅크0B <code>$A1F3</code>: 악마는 무기 대신 <code>$A0CE</code>[이름번호] 를 쓴다.", ("cat",)),
        ("롬에만 있는 마법 「마기·온카」",
         "MP 9, 적 한 무리 전부를 노리는 위력 0 의 공격 마법이 있지만 유미코·동료·적 누구도 쓰지 않습니다.",
         "마법 16번: 위력 표 <code>$A004</code> 0, 대상 E8, 동료 묶음·적 레코드 어디에도 없음.", ("rom",)),
        ("500 마카 상자를 다시 열 수 있음",
         "미콘 마을의 첫 상자는 마카가 500 미만이고 장비가 하나도 없을 때 열리며 열린 표시가 남지 않습니다. "
         "마법으로 MP 를 쓰고 회복의 샘에 다녀오는 식으로 조건을 맞추면 다시 열립니다.",
         "뱅크1 <code>$A8D0</code> 0번 상자 처리.", ("neta",)),
        ("적 「바그」와 디버그 문구",
         "다이달로스의 탑의 적 「바그(バグ)」와 싸울 때 2P 컨트롤러의 ↙+A+B 를 누른 채 AUTO 를 고르면 「카부짱은 디버그를 시작했다」가 "
         "나온다고 알려져 있습니다.",
         "문구 조각은 롬에 있음(뱅크0C <code>$8DFF</code>·<code>$8E0C</code>). 조건은 확인하지 않음.", ("yakata",)),
        ("대열을 바꾼 턴의 행동 순서",
         "전투 중 「이치가에(いちがえ)」로 대열을 바꾸면, 그 라운드에는 바꾸기 전에 그 자리에 있던 캐릭터의 機敏さ 순서대로 "
         "움직입니다. 다음 라운드부터는 정상입니다.",
         "행동 순서표(뱅크0D <code>$B514</code>, 자리 번호로 저장)를 명령 입력(<code>$A30D</code>) 전에 만들고, 이치가에는 "
         "명령 입력 중에 대열만 바꾼다(<code>$A3AF</code> → 뱅크9 <code>$B8E3</code>). 실측: 나카지마 機敏 20·유미코 5 로 1라운드에 "
         "자리를 바꾸자 그 라운드엔 유미코가 먼저, 2라운드부터는 나카지마가 먼저 움직였다.", ("cat",)),
    )
    w('<section class="tab" id="bugs"><h2>버그 <small>인터넷에 알려진 것 + 롬에서 찾은 것</small></h2>'
      '<p class="note">「롬 원인」은 원판 롬을 역어셈블해 확인한 자리입니다(한글판 v53 도 같은 바이트). '
      '인터넷 출처는 내용을 확인하는 데만 썼고 문장은 옮기지 않았습니다.</p>')
    for i, (title, what, why, src) in enumerate(bugs):
        w('<div class="bug" id="bug%d"><h3>%s <span class="src">· %s</span></h3><p>%s</p><p class="why">롬 원인: %s</p></div>'
          % (i + 1, esc(title), " · ".join(srcs[s] for s in src)
             + ("" if "rom" in src or why.startswith("확인하지") else " + 롬"), what, why))
    w('</section>')
    w('</main><script>const FU=%s;%s</script></body></html>' % (fusion_js, JS))
    return "".join(out)


SPRITES = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", default=DW.DEFAULT_ROM)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "index.html"))
    ap.add_argument("--no-sprites", action="store_true", help="도감에 악마 그림을 넣지 않는다(배포판)")
    a = ap.parse_args()
    global SPRITES
    SPRITES = not a.no_sprites
    dm, book, enc, ex, floors, fixed, appear = build(a.rom)
    multi = [fl.title for fl in floors if len(fl.parts) > 1]
    print("층에 붙은 고정 전투 %d곳" % sum(len(fl.fixed) for fl in floors))
    print("층 %d개, 고정 전투 %d곳, 출현표가 둘 이상인 층 %d개 %s" % (len(floors), len(fixed), len(multi), multi))
    print("전투 확률: 문 %.4f / 걸음 %.4f (추첨 %s)" % (enc.rate[6], enc.rate[3], enc.draws))
    for fl in floors:
        print("  %-28s 구성요소 %d  출현표 %d  고정 %d%s" % (fl.title, len(fl.comps), len(fl.parts), len(fl.fixed),
                                                       "  표식 표·裏 다름" if fl.differs else ""))
    if a.check:
        return
    print("상자 %d개, 가게 %d곳, 가게 품목 %d, 장비 %d, 합체 그룹 %d / 조합 %d" % (
        len(ex.chests), len(ex.shops), len(ex.items), len(ex.equip), len(ex.lists), sum(len(L) for L in ex.lists)))
    print("층에 붙은 상자 %d, 가게 %d" % (sum(len(fl.chests) for fl in floors), sum(len(fl.shops) for fl in floors)))
    s = make_html(a.rom, dm, book, enc, ex, floors, fixed, appear)
    open(a.out, "w", encoding="utf-8").write(s)
    print("->", a.out, "%.0f KB" % (len(s.encode("utf-8")) / 1024.0))


if __name__ == "__main__":
    main()
