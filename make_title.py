#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""타이틀 로고 한글화: "디지털 데빌 스토리 / 여신전생".

    python make_title.py            # 미리보기 PNG + 크기만 확인
    python make_title.py --emit     # build_step5b.py 에 넣을 헥스를 title_logo_data.py 로 저장

구조는 titleseg.py 참조(세그먼트 15개, 각 64칸, `$EE` 종료, `$FE nn` 빈칸).
바꾸는 것은 **seg3~seg6(행6~13)** 뿐이고, 그 네 개가 원래 차지한 191바이트 안에
다시 채워 넣는다(포인터표도 같이 고치므로 각 세그먼트 길이는 자유).

CHR: 패턴테이블1, 타일ID N 의 비트맵 = 파일 `$4D010 + N*16`.
     **로고 영역에서만 쓰이는 ID 87개**만 다시 그린다(화면1·2 전체를 훑어 충돌 0건 확인).
     0번부터 순서대로 잡으면 START/PASS WORD/저작권 문구를 덮어써서 깨진다 - 실제로 겪음.
"""
import os
import sys

import galmuri8 as G
import titleseg as TS
from PIL import Image, ImageDraw, ImageFont

BASE_ROM = "작업롬파일/mt1_kor5b_v31_DON그래픽.nes"
CHR_TILE0 = 0x4D010                      # 타일ID 0 의 비트맵 위치(파일오프셋)
LOGO_ROWS, LOGO_COLS = range(6, 14), range(4, 28)
MALGUN_BOLD = "C:/Windows/Fonts/malgunbd.ttf"

SUBTITLE = [("디", 2), ("지", 2), ("털", 2), (" ", 0), ("데", 2), ("빌", 2),
            (" ", 0), ("스", 1), ("토", 1), ("리", 1)]
SUB_ROW, SUB_COL = 6, 7
MAIN_TEXT = "여신전생"
MAIN_ROW, MAIN_COL, MAIN_W, MAIN_H = 8, 8, 16, 4
# ★글자별 크기 배율. 「여」(0번)의 ㅇ 이 세로로 길쭉해 찌그러져 보인다는 지적(2026-09-06)이 있어
#   그 글자만 줄인다. 1.0 이면 예전과 같다.
MAIN_SCALE = {}
# ★본문 전체 배율. 1.0 이면 상자를 꽉 채운다. 줄이면 여백이 늘고 **잉크가 닿는 칸이 줄어
#   타일도 덜 쓴다**(예산에 여유가 생긴다).
MAIN_FIT = 0.94
# ★★이진화 임계값. 높일수록 **획이 얇아진다.**
#   「여」의 ㅇ 은 획이 굵으면 안쪽 구멍이 가는 틈으로 뭉개져 원으로 안 읽힌다.
#   **글자를 줄여도 소용없다** - 획도 같이 줄어 비율이 그대로다(2026-09-06에 확인).
#   사용자 목업의 「여신전생」도 획이 얇아서 ㅇ 이 제대로 뚫려 있다. 크기가 아니라 이 값을 만질 것.
MAIN_THRESH = 185

# ★손으로 그린 본문 그림. 이 파일이 있으면 폰트 렌더 대신 그걸 쓴다.
#   `python title_edit.py` 로 현재 모습을 뽑아 편집한 뒤 덮어쓰면 된다.
MAIN_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_main.png")
C_BG, C_BODY, C_RING = (0, 0, 0), (0xBD, 0x3C, 0x30), (0xFF, 0xCE, 0xCE)


# ---------------------------------------------------------------- 안전 타일ID
def safe_ids(rom):
    """다시 그려도 되는 타일ID.

    두 종류를 합친다:
      1) 로고 영역(행6~13, 열4~27) **안에서만** 쓰이는 ID - 바깥과 겹치면 제외
      2) 화면1·2 **어디에도 안 쓰이는** ID - 타이틀 CHR 뱅크는 타이틀 전용이라 건드려도 안전하다
         (BG타일셋표 항목25 만 이 뱅크를 부른다 - 검증 완료)
    ★2번을 안 넣어서 예산이 87개로 묶여 있었다. 로고를 조금만 넓혀도 빌드가 멈췄다(2026-09-06).
    ★★단 `$EE`(세그먼트 끝)와 `$FE`(빈칸 반복)는 **세그먼트 제어코드**다. 타일ID 로 쓰면
      그리기 목록이 거기서 끊기거나 엉뚱하게 펼쳐진다. 반드시 뺀다. `$FF` 는 빈 칸이라 원래 제외.
    """
    inside, outside = set(), set()
    for tbl in (TS.SCREEN1_TBL, TS.SCREEN2_TBL):
        nt = TS.full_nametable(rom, tbl)
        for r in range(30):
            for c in range(32):
                v = nt[r * 32 + c]
                if v == 0xFF:
                    continue
                (inside if (r in LOGO_ROWS and c in LOGO_COLS) else outside).add(v)
    used = inside | outside | {0xFF}
    spare = {n for n in range(256) if n not in used}
    return sorted((inside - outside) | (spare - {0xEE, 0xFE}))


class Pool:
    """★같은 그림의 타일은 **ID 를 재사용**한다.

    안전 ID 는 87개뿐인데 자막 32(8글자x4) + 본문 56(14x4) = 88 이라 한 칸도 안 남는다.
    예전엔 본문 한 칸이 비어서 86 으로 겨우 맞았는데, 여백을 조금만 넓혀도 그 칸이 차면서
    빌드가 멈췄다(2026-09-06). 실제로는 빈 칸이나 단순한 획 조각이 여러 번 나오므로
    중복만 걷어내도 여유가 생긴다.
    """

    def __init__(self, ids):
        self.ids, self.n, self.tiles = ids, 0, {}
        self.seen = {}

    def alloc(self, chrbytes):
        key = bytes(chrbytes)
        if key in self.seen:
            return self.seen[key]
        assert self.n < len(self.ids), "안전 ID %d개를 다 썼다 - 로고를 줄일 것" % len(self.ids)
        tid = self.ids[self.n]
        self.n += 1
        self.tiles[tid] = chrbytes
        self.seen[key] = tid
        return tid


def pack2(block):
    """8x8 색인(0~3) -> NES 2bpp 16바이트"""
    out = bytearray(16)
    for y in range(8):
        lo = hi = 0
        for x in range(8):
            v = block[y][x]
            lo |= (v & 1) << (7 - x)
            hi |= ((v >> 1) & 1) << (7 - x)
        out[y], out[8 + y] = lo, hi
    return bytes(out)


# ---------------------------------------------------------------- 자막(갈무리14 + 밝은 테두리)
# ★★타이틀 배경 팔레트1 = `$0F 검정 | $1C 청록 | $04 자주 | $10 밝은회색` (팔레트 RAM 덤프로 확인.
#   원본과 우리 롬이 완전히 같다). 예전 판은 자주(값2)·청록(값1)만 쓰고 **밝은회색(값3)을 안 썼다.**
#   그래서 글자가 평면으로 보이고 검은 배경에 눌렸다("테두리가 없어서 촌스럽다" - 사용자, 2026-09-06).
#   -> 글자를 **밝은회색으로 한 바퀴 두른다.** 팔레트도 속성표도 그대로 두고 타일만 바꾸면 된다
#      (자주와 청록이 같은 팔레트 안에 있다).
# ★한쪽 모서리만 밝게 하면 안쪽 음영처럼 보이지 테두리로 안 읽힌다. **전체를 둘러야** 한다.
# ★글꼴은 갈무리14 를 **원래 크기(14x14)** 로 찍는다. 16x16 칸에 1픽셀 여백이 남아 거기에 테두리가 들어간다.
#   예전처럼 8x8 폰트를 2배로 늘리면 칸이 꽉 차서 **테두리 넣을 자리가 없다.**
GALMURI14 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "galmuri", "Galmuri14.ttf")
SUB_RING = 3                                  # 테두리 = 팔레트 색3($10 밝은회색)


def _sub_glyph(ch, body):
    """한 글자를 16x16 색인맵(0 배경 / body 본체 / SUB_RING 테두리)으로"""
    f = ImageFont.truetype(GALMURI14, 15)
    im = Image.new("L", (60, 60), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"                          # ★안티앨리어싱을 끄지 않으면 회색이 섞여 이진화가 지저분해진다
    d.text((15, 15), ch, font=f, fill=255)
    bb = im.getbbox()
    m = [[0] * 16 for _ in range(16)]
    if bb is None:
        return m
    im = im.crop(bb)
    w, h = im.size
    ox, oy = (16 - w) // 2, (16 - h) // 2
    for y in range(h):
        for x in range(w):
            if not im.getpixel((x, y)):
                continue
            for k in (0, 1):                  # 오른쪽으로 1픽셀 겹쳐 굵게 (픽셀 폰트 관용 볼드)
                if 0 <= oy + y < 16 and 0 <= ox + x + k < 16:
                    m[oy + y][ox + x + k] = 1
    out = [[0] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            if m[y][x]:
                out[y][x] = body
                continue
            if any(0 <= y + dy < 16 and 0 <= x + dx < 16 and m[y + dy][x + dx]
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                out[y][x] = SUB_RING
    return out


def subtitle(pool, cells):
    col = SUB_COL
    for ch, color in SUBTITLE:
        if ch == " ":
            col += 1
            continue
        g = _sub_glyph(ch, color)
        for qc in (0, 1):                   # 좌/우 절반
            top = [r[qc * 8:qc * 8 + 8] for r in g[0:8]]
            bot = [r[qc * 8:qc * 8 + 8] for r in g[8:16]]
            cells[SUB_ROW * 32 + col] = pool.alloc(pack2(top))
            cells[(SUB_ROW + 1) * 32 + col] = pool.alloc(pack2(bot))
            col += 1
    return col


def _load_main_png(W, H):
    """편집한 PNG 를 (본체마스크, 테두리마스크) 로 읽는다. 색은 가장 가까운 것으로 붙인다."""
    im = Image.open(MAIN_PNG).convert("RGB")
    assert im.size == (W, H),         "%s 는 %dx%d 이어야 한다 (지금 %dx%d). 크기를 바꾸면 상자와 안 맞는다" %         (os.path.basename(MAIN_PNG), W, H, im.size[0], im.size[1])
    body = [[0] * W for _ in range(H)]
    ring = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            c = im.getpixel((x, y))
            d = [(sum((a - b) ** 2 for a, b in zip(c, t)), i)
                 for i, t in enumerate((C_BG, C_BODY, C_RING))]
            k = min(d)[1]
            if k == 1: body[y][x] = 1
            elif k == 2: ring[y][x] = 1
    return body, ring


def _emit_main(pool, cells, mask, ring, W, H):
    """본체/테두리 마스크를 8x8 타일로 잘라 굽는다"""
    for tr in range(MAIN_H):
        for tc in range(MAIN_W):
            block = [[0] * 8 for _ in range(8)]
            ink = False
            for y in range(8):
                for x in range(8):
                    my, mx = tr * 8 + y, tc * 8 + x
                    if mask[my][mx]:
                        block[y][x] = 2; ink = True     # 채움(빨강)
                    elif ring[my][mx]:
                        block[y][x] = 3; ink = True     # 외곽선(살구)
            if ink:
                cells[(MAIN_ROW + tr) * 32 + MAIN_COL + tc] = pool.alloc(pack2(block))


# ---------------------------------------------------------------- 메인 타이틀(브러시체)
def main_title(pool, cells, shear=0.18, inset_x=2, inset_y=1):
    """★INSET 이 핵심이다. 예전엔 글자를 112x32 상자에 **정확히 꽉 채워** 그렸다:
         im.crop(...).resize((W, H))
       그러면 획이 상자 네 변에 닿아 **가장자리에서 잘리고**, 외곽선은 상자 밖으로 나갈
       자리가 없어 **그 변에서 끊긴다**(사용자 지적 2026-09-06: "테두리가 이어지지 않는다").
       -> 안쪽으로 들여 그려서 외곽선이 들어갈 여백을 남긴다. 모양·색은 그대로다.
    ★가로/세로 여백을 따로 준다. 가로 1픽셀로는 「여」의 ㅇ 왼쪽이 여전히 상자에 닿아 잘렸다
      (사용자 지적 2026-09-06). 세로까지 2로 늘리면 잉크가 닿는 타일이 늘어 **안전 ID 87개를
      초과해 빌드가 멈춘다.** 그래서 가로만 2, 세로는 1 로 둔다.
    """
    W, H = MAIN_W * 8, MAIN_H * 8
    # ★★손으로 그린 그림이 있으면 폰트 렌더 대신 **그걸 그대로 쓴다.**
    #   `python title_edit.py` 로 현재 모습을 PNG 로 뽑아, 그림판 등에서 픽셀을 고친 뒤
    #   같은 이름으로 덮어쓰면 된다. 색 세 가지만 쓴다(그 밖의 색은 가까운 쪽으로 붙인다):
    #     검정 #000000 = 배경 / #BD3C30 = 본체 / #FFCECE = 테두리
    if os.path.exists(MAIN_PNG):
        pm, pr = _load_main_png(W, H)
        _emit_main(pool, cells, pm, pr, W, H)
        return
    font = ImageFont.truetype(MALGUN_BOLD, 64)
    # ★네 글자를 **한 덩어리로** 그린다. 글자마다 따로 그려 같은 폭 칸에 맞추면
    #   「신전생」까지 넓어져 모양이 달라진다(2026-09-06에 해 보고 되돌렸다).
    im = Image.new("L", (W * 4, H * 4), 0)
    ImageDraw.Draw(im).text((W // 2, H // 2), MAIN_TEXT, font=font, fill=255)
    im = im.crop(im.getbbox())
    w, h = im.size
    im = im.transform((w + int(h * shear), h), Image.AFFINE,
                      (1, shear, 0, 0, 1, 0), resample=Image.BICUBIC, fillcolor=0)
    tw = max(1, int((W - inset_x * 2) * MAIN_FIT))
    th = max(1, int((H - inset_y * 2) * MAIN_FIT))
    im = im.crop(im.getbbox()).resize((tw, th), Image.LANCZOS)
    # ★그 다음 **첫 글자 구역만 잘라 축소해 다시 붙인다.** 「여」의 ㅇ 이 세로로 길쭉해
    #   찌그러져 보인다는 지적이 있었다. 이렇게 하면 나머지 세 글자는 픽셀 하나 안 바뀐다.
    s = MAIN_SCALE.get(0, 1.0)
    if s != 1.0:
        frac = font.getlength(MAIN_TEXT[0]) / font.getlength(MAIN_TEXT)
        xe = max(1, int(round(tw * frac)))
        head = im.crop((0, 0, xe, th))
        hw, hh = max(1, int(xe * s)), max(1, int(th * s))
        head = head.resize((hw, hh), Image.LANCZOS)
        ImageDraw.Draw(im).rectangle((0, 0, xe - 1, th - 1), fill=0)
        im.paste(head, ((xe - hw) // 2, (th - hh) // 2))
    pad = Image.new("L", (W, H), 0)
    pad.paste(im, ((W - tw) // 2, (H - th) // 2))
    im = pad
    mask = [[1 if im.getpixel((x, y)) >= MAIN_THRESH else 0 for x in range(W)] for y in range(H)]
    ring = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if mask[y][x]:
                continue
            if any(0 <= y + dy < H and 0 <= x + dx < W and mask[y + dy][x + dx]
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                ring[y][x] = 1
    _emit_main(pool, cells, mask, ring, W, H)


# ---------------------------------------------------------------- 조립
def build(rom):
    pool = Pool(safe_ids(rom))
    cells = {}
    subtitle(pool, cells)
    main_title(pool, cells)

    nt = bytearray(TS.full_nametable(rom))
    for r in LOGO_ROWS:                      # 안쪽만 비운다(좌우 체인 장식은 원본 유지)
        for c in LOGO_COLS:
            nt[r * 32 + c] = 0xFF
    for p, t in cells.items():
        nt[p] = t

    segs = {i: TS.encode(nt[i * 64:(i + 1) * 64]) for i in (3, 4, 5, 6)}
    return pool, nt, segs, cells


ATTR_ADDR = 0xBC85          # 화면1·2 가 공유하는 속성표 64바이트


def fix_attr(rom, cells):
    """★타일만 바꾸면 색이 샌다. 팔레트는 **16x16 픽셀(2x2타일) 단위**라
    자막이 원본보다 넓어지면 그 바깥은 원본 그룹3(회색)으로 찍힌다 - 실제로 겪음.
    새로 글자가 놓인 사분면마다 팔레트 그룹을 다시 칠한다."""
    o = TS.f(ATTR_ADDR)
    attr = bytearray(rom[o:o + 64])
    for pos in cells:
        r, c = pos // 32, pos % 32
        grp = 1 if r < MAIN_ROW else 2          # 자막=그룹1(보라/청록), 메인=그룹2(빨강)
        idx = (r // 4) * 8 + (c // 4)
        sh = (((r % 4) // 2) * 2 + ((c % 4) // 2)) * 2
        attr[idx] = (attr[idx] & ~(3 << sh)) | (grp << sh)
    rom[o:o + 64] = attr


def apply(rom_bytes, pool, segs, cells=None, chr_base=CHR_TILE0):
    rom = bytearray(rom_bytes)
    if cells:
        fix_attr(rom, cells)
    ptrs = TS.read_ptrs(rom)
    start, limit = ptrs[3], ptrs[7]
    total = sum(len(s) for s in segs.values())
    assert total <= limit - start, \
        "seg3~6 이 %d바이트인데 자리는 %d바이트뿐" % (total, limit - start)

    addr = start
    newptr = {}
    for i in (3, 4, 5, 6):
        newptr[i] = addr
        o = TS.f(addr)
        rom[o:o + len(segs[i])] = segs[i]
        addr += len(segs[i])
    # 포인터표는 화면1·2 둘 다 같은 세그먼트를 가리킨다 - 양쪽 다 고친다
    for tbl in (TS.SCREEN1_TBL, TS.SCREEN2_TBL):
        t = TS.f(tbl)
        for i, a in newptr.items():
            rom[t + i * 2] = a & 0xFF
            rom[t + i * 2 + 1] = a >> 8
    for tid, data in pool.tiles.items():
        o = chr_base + tid * 16
        rom[o:o + 16] = data
    return bytes(rom)


def patch_rom(rom):
    """build_step5b.py 가 부르는 진입점. bytearray 를 **제자리에서** 고친다.

    CHR 시작은 롬에서 직접 구한다(매퍼195 변환 뒤에도 앞 128KB 배치는 그대로라
    타일ID N -> CHR시작+$D000+N*16 이 191/195 양쪽에서 같다)."""
    pool, nt, segs, cells = build(rom)
    chr_s = 16 + rom[4] * 16384
    out = apply(bytes(rom), pool, segs, cells, chr_base=chr_s + 0xD000)
    rom[:] = out
    return pool.n, sum(len(s) for s in segs.values())


if __name__ == "__main__":
    rom = open(BASE_ROM, "rb").read()
    pool, nt, segs, cells = build(rom)
    ptrs = TS.read_ptrs(rom)
    room = ptrs[7] - ptrs[3]
    total = sum(len(s) for s in segs.values())
    print("타일 %d개 / 안전ID %d개" % (pool.n, len(pool.ids)))
    print("seg3~6 = %s  합계 %d / 자리 %d바이트" %
          ([len(segs[i]) for i in (3, 4, 5, 6)], total, room))
    assert total <= room
    if "--emit" in sys.argv:
        out = apply(rom, pool, segs, cells)
        dst = "작업롬파일/mt1_kor5b_v32_타이틀.nes"
        open(dst, "wb").write(out)
        import zlib
        print("%s  CRC32 %08X" % (dst, zlib.crc32(out) & 0xFFFFFFFF))
