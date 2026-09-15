#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5b: 번역문 + **메시지별 동적 글리프셋**을 롬에 넣는다.

## 왜 필요한가
5a(정적 64자)는 메시지 13개만에 음절 79종으로 예산을 넘겼다. 실제 번역을 감당할 수 없다.
-> 메시지마다 **그 메시지가 쓰는 음절만** CHR-RAM 에 올린다(한 화면 최대 실측 45종, 슬롯 63칸).

## 구조
```
빌드타임
  전역 음절표   : 뱅크$10 offset $0000  (음절 id -> 16바이트 CHR)   최대 256종
  룩업표        : 뱅크$10 offset $1000  (메시지주소 2B + id목록 오프셋 2B) x N, $0000 종료
  id 목록       : 뱅크$11 offset $0000  ([개수][id...])
  번역문        : 원문 자리에 덮어쓰기, 음절은 코드 $80+슬롯

런타임
  $AF1E (5바이트) -> JSR $6100 / NOP / NOP     ; 메시지 시작 지점, **메인 스레드**
  $6100 : $0658=0 (원래 동작) / 룩업 / 뱅크셋13 진입 / 글리프를 $6200 으로 복사 / 복원
  $C0BF -> JSR $6000                            ; 4a 업로더 (한가한 프레임에만)
```
**뱅크 제약**: 메시지 엔진 `$AF24` 는 뱅크$05 = R7 창에 있다. R7 을 바꾸면 자기가 사라진다.
우리 코드는 PRG-RAM($6000) 이라 안전하고, 게임 트램폴린(`$C864`/`$C8D5`)으로 뱅크셋13 을
잠깐 빌렸다가 되돌린다. 뱅크셋13 은 게임이 안 쓰는 인덱스로 확인돼 있다.

**업로더는 순환시킨다**(4a 와 동일). 타일셋이 25가 아닌 프레임에 쓴 바이트는 조용히 버려지므로,
한 번만 올리면 유실될 수 있다. 순환하면 저절로 복구된다.
"""
import os
import re
import sys
import zlib

import galmuri8 as G
from decode_tbl import CH as G_CH

KO_FILE = sys.argv[1] if len(sys.argv) > 1 else "script_ko.txt"
SRC = "mt1_m191_v3.nes"

# ---------------------------------------------------------------- 빌드 버전 (2026-09-03)
# 실기 확인이 여러 판을 오가므로 **결과물 이름에 버전을 박는다.**
# 사용: MT1_VER=v2 MT1_TAG=uihook python build_step5b.py
#   -> 작업롬파일/mt1_kor5b_v2_uihook.nes
# `작업롬파일/mt1_kor5b.nes` 와 `_v0_base.nes`(CRC 2212029A)는 사용자의 기준선이라 건드리지 않는다.
OUTDIR = "작업롬파일"
VERSION = os.environ.get("MT1_VER", "v1")
TAG = os.environ.get("MT1_TAG", "")
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "mt1_kor5b_%s%s.nes" % (VERSION, ("_" + TAG) if TAG else ""))
assert os.path.basename(OUT) not in ("mt1_kor5b.nes", "mt1_kor5b_v0_base.nes"), \
    "기준선 롬을 덮어쓰려 한다"

# ★UI 훅($C13E -> $6C00) 스위치. **기본 끔.**
#   켠 판(CRC 2F21163A)에서 던전 이동 중 상태창이 흔들리고 통로에 깨진 그림이 떴다.
#   ★2026-09-03 원인 규명 완료: 훅이 아니라 `ui_ko.txt` 첫 줄 주소가 한 바이트 앞이라
#   포인터 $810E 의 상위바이트를 덮은 것이었다. 고친 뒤 **기본 켬**으로 되돌렸다.
UI_HOOK = os.environ.get("MT1_UIHOOK", "1") == "1"

# ★직접 그려지는 라벨(ui_words.txt) 스위치. **기본 끔.**
#   뱅크 안에서 가나 바이트열을 찾아 **제자리 전역 치환**하는 방식이라,
#   코드/데이터가 우연히 같은 바이트를 가지면 조용히 망가진다
#   (인계문서: "롬 전체 바이트 치환 금지 - 2b 에서 데이터 뱅크를 훼손해 전투 중 그래픽이 깨졌음").
#   `check_uistr.py` 가 치환 구간을 매번 검사한다. 2026-09-03 부터 **기본 켬**.
LABELS = os.environ.get("MT1_LABELS", "1") == "1"

# ★던전 상단 사이드 패널 / 전투 커맨드 박스 (`panel_ko.txt`). **기본 끔.**
#   훅도 슬롯도 전역 치환도 쓰지 않는다 - CHR 전용 미니폰트 타일과
#   고정 주소의 5바이트 고정폭 표만 고친다. 2026-09-03 부터 **기본 켬**.
PANEL = os.environ.get("MT1_PANEL", "1") == "1"

# ★제자리 치환한 구간을 전부 기록한다. `check_uistr.py` 가 이 목록을 받아
#   "코드가 절대주소로 한 바이트를 읽는 자리를 덮었는가"를 검사한다.
#   (뱅크$03 $AEA2 가 포인터 상위바이트였는데 텍스트로 착각해 덮은 적이 있다)
INPLACE = []

# ★UI 문자열만 넣고 $C13E 훅은 **설치하지 않는** 진단 모드.
#   MT1_UIHOOK=1 MT1_UIPATCH=0 -> 문자열 제자리 치환은 하되 훅은 원본 유지.
#   훅이 범인인지 문자열 치환이 범인인지 한 판으로 가른다.
UI_PATCH = os.environ.get("MT1_UIPATCH", "1") == "1"
HDR = 0x10
fx = lambda a: HDR + 0x3C000 + (a - 0xC000)
bk = lambda n, o: HDR + n * 0x2000 + o

# ★슬롯을 히라가나를 피해 배치한다 (2026-08-31, 실기에서 발각된 문제의 해법)
# 대사 342개 중 **336개(98.2%)가 $80~$BD 코드를 쓴다**($98 탁점만 811회).
# 슬롯을 $80 부터 잡으면 번역 안 된 일본어가 우리 한글 글리프를 빌려 써서 전부 깨진다.
#   $80~$98 히라가나 へ~゛ / $9A~$9F 라틴 A~F  -> 건드리지 않음 (일본어 온전)
#   $A0~$BD 라틴 G~Z + 합자                    -> 한글 슬롯 30칸
# 메시지당 필요 슬롯 실측 최대 12칸이라 30칸으로 충분하다.
# $A0 은 페이지 정렬($A0*16=$A00)이라 업로더 주소계산은 상수 하나($18->$1A)만 바뀐다.
# 대가: 스테이터스 라틴 라벨(HIT-PTS 등)과 패스워드 화면이 깨진다. 대사 테스트엔 지장 없음.
# 전체 번역이 끝나면 $80~$BD 63칸으로 되돌리면 된다.
# ★슬롯 범위는 $C0~$CF 16칸.  $9A~$B3 은 라틴 A~Z 라서 절대 쓰면 안 된다
#   (던전 하단 상태바 CLASS/NAME/HIT-PTS/MP, 상태이상 이름, 패스워드 화면이 쓴다)
#   텍스트 엔진은 상위니블 $D/$E/$F 를 제어코드로 보므로($C202 분기) 그릴 수 있는
#   최대 코드가 $CF 다. 대사342+악마이름167 어디에도 안 쓰이는 자유 코드는
#   $92 $BD~$BF $C1~$CB $CE $CF 뿐이라, 쓸 수 있는 연속 구간은 $C1~$CF 가 유일하다.
#
# ★★$C0 은 **메시지 파서의 제어코드**다. 뱅크$05 $8F7E:
#     CMP #$C0 / BNE $8FA8
#     LSR $04B6 / ROR $04B5 / LDA #$01 / ADC $04B5 ...   ; 16비트 값을 반으로 깎고 +1
#     JSR $CD4F / JSR $D8C6 / INC $0658 / JMP $AF24
#   실기에서 이걸 글리프로 쓰자 **HP 30 -> 16 (=30>>1 +1) 로 깎이고 화면이 번쩍였다.**
#   블리터 디스패치($C15D/$C202)는 상위니블만 보므로 $C0 이 안전해 보이지만,
#   **파서($8F27~)가 먼저 가로챈다.** 디스패치는 파서와 블리터 **둘 다** 읽어야 한다.
# 슬롯 번호 -> 실제 타일 번호. **연속이 아니다** ($C0 은 파서 제어코드라 건너뛴다).
# ★가나 $80~$99 를 슬롯으로 회수했다(사용자 결정 2026-08-31).
#   대가: 아직 일본어인 대사·악마이름·메뉴에서 그 대역 글자가 한글로 보인다.
#   전부 번역하면 사라지는 문제라 감수한다.
# ★라틴 $9A~$B3 는 **보류**. 패스워드 화면이 A~Z 24자를 전부 쓰고,
#   상태바 CLASS/NAME/HIT-PTS/MP·상태이상 이름도 여기 있다. 건드리지 않는다.
# ★$B4~$BD 도 보류 ($BD 는 패스워드 빈칸 ※).
# ★$B6~$BC 는 원본이 **종족명을 5칸에 우겨넣으려고 만든 합자 타일**이다
#   ($B6$B7=ジュ $B8$B9=ジン $BA$BB=ゲン $BC=ェ). 이름을 한글로 바꾸면 쓸 일이 없어
#   슬롯으로 회수한다. $B4 는 「玉」 - あら玉/しず玉/ふる玉 세 아이템만 쓰던 것이라 같이 회수.
#   $BD(✕) 만 남긴다 (메뉴가 직접 그릴 수 있다).
M195 = os.environ.get("MT1_M195", "0") == "1"   # 매퍼195(CHR-RAM 4KB) 전환
# ★매퍼195 에서는 코드 $00~$FF 가 전부 CHR-RAM 이라, **정적 폰트에서 뺀 자리도 슬롯**이 된다.
#   191 에서는 그 자리가 CHR-ROM 이라 업로드가 그냥 버려지므로 절대 켜면 안 된다.
_STCODES = set()
for _l0 in open("static_font.txt", encoding="utf-8"):
    _l0 = _l0.rstrip()
    if _l0.strip() and not _l0.startswith("#"):
        _STCODES.add(int(_l0.split(chr(9))[0], 16))
FREED = [c for c in list(range(0x24, 0x5A)) + list(range(0x64, 0x80))
         if c not in _STCODES and c != 0x59]        # 0x59 = BLANK, 늘 예약
# ★★슬롯 **배정 순서**가 중요하다. 아래 18개는 게임이 **그래픽**(상자 테두리·초상화 틀)으로
#   쓰는 코드다. 슬롯이 거기까지 차면 테두리가 한글로 덮인다.
#   예전 순서는 이름 슬롯 풀이 **하필 이 구간에서 시작**해서($B6부터) 이름 슬롯을 10칸만 써도
#   바로 깨졌다. 합체·상태 화면이 그래서 망가져 있었다(2026-09-07 사용자 보고 -> check_slotclash).
#   -> **그래픽 코드를 풀 맨 뒤로** 보낸다. 앞쪽은 원본에서 가나였던 코드들이라
#      그래픽과 안 겹친다(미번역 일본어와 겹칠 뿐이고 그건 별개 문제다).
#   ★$B6~$BC 는 원본의 **합자 타일**(ジュ ジン ゲン ェ)이라 글자다 - 그래픽이 아니다.
GFX_CLASH = [0xB4, 0xB5, 0xBE, 0xBF] + list(range(0xC1, 0xD0))
# ★★2026-09-13 풀 맨 뒤로 보내는 것만으로는 **오래 플레이하면 결국 쓰인다.** 사용자 세이브 3개 전부에서
#   $B4~$CF 가 한글 글리프로 덮여 있었다(CHR-RAM 대조로 실측). 그중 **$CD 는 돈 기호**라 코드가
#   가격 앞에 직접 찍는다(뱅크0 $AAA4 `LDA #$CD`, 뱅크1 $AC65 문자열) -> 「옵495」「옵 1819」로 떴다.
#   돈 기호만큼은 풀에서 **아예 뺀다.** 이름 슬롯이 1칸 줄지만 압박시험 최악(40)보다 여유가 있다.
_POOL = (list(range(0x80, 0x9A)) + list(range(0xB4, 0xBD)) + [0xBE, 0xBF]
         + [c for c in range(0xC1, 0xD0) if c != 0xCD] + (FREED if M195 else []))
TILES = ([c for c in _POOL if c not in GFX_CLASH]
         + [c for c in _POOL if c in GFX_CLASH])
_TILESET = set(TILES)
NSLOT = len(TILES)                # 52 (191) / 84 (195) = 한 화면 동시 표시 가능한 서로 다른 글자 수
# 롬 인코딩용 로컬 인덱스 코드. **이 값은 우리 훅만 읽는 중간 코드**라
# 타일 번호와 무관하다. 스크립트에 리터럴로 등장하는 태그·PUNCT 와 안 겹치는
# 43바이트 연속 구간을 실측으로 골랐다($80~$AA).
TILE0 = 0x80
# ★로컬 색인 범위는 $80 ~ $80+LOCALMAX-1 이다. 이게 라틴($9A~$B3)까지 덮으면
#   훅이 라틴을 슬롯 색인으로 오해해 전부 한글 글리프로 바꿔 버린다
#   (실기 증상: "RUN DEMON" -> "러러러 러러러러러", 2026-09-02).
#   메시지당 실측 최대 로컬은 22개, 이름은 4개라 26칸이면 충분하다.
LOCALMAX = 26
assert TILE0 + LOCALMAX <= 0x9A, "로컬 색인 범위가 라틴($9A~)을 침범한다"
DSTHI = 0x10 + (TILE0 >> 4)      # 목적지 = $1000 + 타일*16 -> $1A00 + 슬롯*16
LOOKBANK = 0x10                  # 룩업표 (뱅크$10 오프셋 $1000 -> R6 로 매핑되어 CPU $9000)
# 메시지 레코드가 들어갈 (뱅크, 시작, 끝) 구간.
# ★342개 전체면 약 106KB 가 필요한데 $12~$1D 12뱅크(96KB)로는 모자란다(점검기가 잡음).
#   비어 있는 자리를 긁어 모은다:
#     $0F  앞 1KB 는 PRG-RAM 부팅 이미지 -> 그 뒤 7KB
#     $10  $1000~ 은 룩업표 -> 그 앞 4KB
#     $11  통째로 비어 있음
REC_REGIONS = ([(0x0F, 0x1B00 if (UI_HOOK and UI_PATCH) else 0x0C00, 0x2000),  # == COPY
                (0x10, 0x0E00, 0x1000),   # 앞 2.5KB 이름 진입표 + UI 음절표(0xA00~0xE00)
                (0x11, 0x0000, 0x2000)]
               + [(b, 0x0000, 0x2000) for b in range(0x12, 0x1E)])
RECBANKS = [b for b, _, _ in REC_REGIONS]
ENTSZ = 8                        # 룩업 엔트리 크기. **2의 거듭제곱이어야** X 8비트 페이지 처리가 깨끗하다
BSET = 13                        # 빌려 쓸 뱅크셋 인덱스
# ★음절 상한 없음. 글리프를 메시지 레코드에 직접 물렸다(2026-08-31).
#   예전엔 전역 음절표(뱅크$10 8KB)를 id 1바이트로 가리켜 **256종이 한계**였고,
#   67개 번역에 222종을 써서 바로 막혔다. 이제 id 는 상주 비교용 16비트 값일 뿐이다.
MAXSYL = 65535
# 한가한 프레임(블릿 없음)의 여유는 ~1,700사이클인데 4바이트(56사이클)만 쓰고 있었다.
# 글리프 하나(16바이트)를 한 프레임에 끝내면 체감 지연이 사라진다(약 180사이클).
# ★글리프 버퍼가 93*16=1488바이트로 커져 $6400~$67FF(1KB)에 안 들어간다.
#   부팅 복사 범위($6000~$79FF) **바깥**인 $7A00 으로 옮겼다 - 쓰기 전에 늘 채우므로 초기화 불필요.
# ★2026-09-07 $7A00 -> $7B00. 마법이름 36개를 제자리 치환에 넣자 이스케이프 음절이
#   195 -> 216종이 되어 글리프표($6D00~)가 $7A00 을 넘었다. 글리프 버퍼는 NSLOT*16=1264바이트라
#   $7B00 에서 시작해도 $7FF0 으로 PRG-RAM 안에 들어간다 (여유 16바이트).
SRCBASE, CHUNK = 0x7B00, 16      # 글리프 버퍼 (페이지 정렬 필수). NSLOT*16 바이트
SLOT, CHK, TMP, CNT = 0x60F0, 0x60F1, 0x60F2, 0x60F3
SLOTTAB = 0x6080                 # 슬롯->타일 변환표 (NSLOT 바이트) -> 84칸이면 $60D3 까지
TBL7 = 0x6070                    # ★뱅크셋 R7 표의 PRG-RAM 사본 (14바이트). SLOTTAB 이 커져 앞으로 옮겼다
NBSET = 14                       # 뱅크셋 개수 (0~13)
TMP2 = 0x60F7                    # id 상위바이트 비교용
NEXT, LCNT = 0x60F4, 0x60F5      # 다음 빈 슬롯 / 이 메시지의 로컬 음절 수
LASTROW = 0x60F6                 # 직전 메시지의 창 시작 행($0651) - 새 창 판정용
# ★43칸이 되면서 글리프 버퍼가 43*16=688바이트($6400~$66AF)로 커져
#   옛 RESID($6600)/MAP($6620) 자리를 삼킨다. 부팅 복사 범위($6000~$63FF) 안으로 옮겼다.
RESIDL = 0x6300                  # 슬롯별 상주 음절 id 하위 (NSLOT 바이트)
RESIDH = 0x6360                  # 상주 음절 id 상위  (93칸이라 $40 간격으로는 겹친다)
MAP = 0x63C0                     # 로컬 인덱스 -> 배정된 슬롯 (LOCALMAX 바이트)
TEXT = 0x6800                    # 치환된 메시지 텍스트 버퍼 (256바이트, 페이지 정렬)
HOOK = 0x6100
NHOOK = 0x6900                   # 이름 훅 (악마/아이템/마법 이름표)
# ★슬롯 풀을 둘로 나눈다. 메시지 훅은 새 창이 열리면 NEXT 를 0 으로 되돌리는데,
#   그때 **화면에 떠 있는 이름의 글리프**까지 덮어써 버린다(전투: 적 이름 + 대사 동시).
#   대사 0~NDLG-1 / 이름 NDLG~NSLOT-1 로 갈라 서로를 침범하지 못하게 한다.
#   실측 상한: 대사 한 메시지 22칸 / 악마8인 19칸 / 아이템6줄 18칸.
#   ★남은 위험: 전투에서 아이템 목록과 파티 이름이 **동시에** 보이면 31칸이 필요해
#     풀이 감긴다. 감겨도 다시 그리면 복구되지만 실기에서 확인할 것.
# ★대사 풀 24 / 이름 풀 28 (2026-09-03 재조정).
#   25/27 이던 것을 옮겼다. `악마8+아이템8`(실제 가능한 조합)에서 이름 풀이
#   27칸으로는 400회 중 9회 포화해 떠 있는 이름이 변질됐다. 28칸이면 1회로 줄고,
#   29칸으로 더 늘려도 1회 그대로라 여기가 무릎이다.
#   대사는 실측 최대 22칸이라 24 로도 여유 2칸이 남는다(check_5c [2] 가 지킨다).
# ★매퍼195(슬롯 93)에서는 대사 28 / 이름 65 로 나눈다.
#   실측(적대적 조합): 대사 한 메시지 최대 25, 악마8+아이템8 최대 53 -> 이름 여유 12칸.
NDLG = 28 if M195 else 24
NNSLOT = NSLOT - NDLG
# 글리프 버퍼가 $7500 으로 빠지면서 $6400~$67FF 가 비었다 - 이름 상주표를 그리로 옮긴다
# (부팅 복사 범위 안이라 0 으로 초기화된다)
NRESL, NRESH = 0x6400, 0x6480   # 이름 전용 상주표 (NNSLOT 바이트씩)
NBUF = 0x6B60                   # 번역결과 임시버퍼 16바이트
NMODE, NX, NLEN, NPAD = 0x6BF0, 0x6BF1, 0x6BF2, 0x6BF3
NT1, NT2, NNEXT, NCNT = 0x6BF4, 0x6BF5, 0x6BF6, 0x6BF7
NCAP, NFILL = 0x6BF8, 0x6BF9
# 모드별 매개변수 (0:$B94B 1:$B984 2:$B9AB 3:$BE68 마법 4:$BFC5 아이템)
NDSTL, NDSTH, NCAPT, NFILLT, NBASEH = 0x6BD0, 0x6BD5, 0x6BDA, 0x6BDF, 0x6BE4
MODE_DSTL  = [0x90, 0x88, 0x90, 0x88, 0x90]   # 모드4 는 $0480 을 보고 런타임에 다시 고른다
MODE_DSTH  = [0x05] * 5
MODE_CAP   = [8, 8, 0, 6, 0]                  # 0 = 무제한
MODE_FILL  = [0, 8, 0, 6, 0]                  # $FF 로 채울 칸수, 0 = 안 함
MODE_BASEH = [0x80, 0x80, 0x80, 0x88, 0x86]   # 진입표 상위바이트 (A/A/A/C/B)
SETCNT = 0x6B00                 # CNT = max(NEXT, NDLG+NCNT) 공용 서브루틴
#   PRG-RAM 배치: $6000 업로더 / $6080 SLOTTAB / $6070 TBL7 / $60F0 변수 (NSLOT=84 기준)
#   $6100 메시지훅 / $6300 RESIDL / $6340 RESIDH / $6380 MAP / $6400 글리프버퍼(800)
#   $6800 TEXT / $6900 이름훅 / $6AD0 SETCNT / $6B00 SETCNT / $6B20 이름상주표 / $6B60 NBUF / $6BF0 변수
BLANK = 0x59                     # 빈칸 타일 (정적 폰트에서 예약)
# ---------------------------------------------------------------- UI 이스케이프
# UI/시스템 문자열(스테이터스 라벨·레벨업·합체·회복…)은 대사 엔진도 이름 훅도 안 거치고
# 코드가 롬 주소를 직접 물고 텍스트 버퍼로 퍼 나른다(뱅크$0D 만 76곳, JSR $C13E 는 80곳).
# 그래서 **표시 진입점 $C13E 한 곳만** 훅해서 버퍼를 훑는다:
#   $BD <음절id>  (2바이트)  ->  배정된 슬롯 타일 1바이트  (뒤를 왼쪽으로 당겨 압축)
# $BD 는 원본의 ✕ 기호인데 번역문·이름표 어디에서도 안 쓰므로 표식으로 안전하다.
ESC = 0xBD
# ★2026-09-07 $6C00 -> $6600. 종결자 앞 빈칸 메우기가 들어가 훅이 232->262바이트가 됐고
#   옛 자리($6C00~$6CEF)는 240바이트뿐이었다. $6600~$67FF 는 통째로 비어 있다
#   ($6400 이름상주표는 $64B0 에서 끝나고 $6500 은 블록훅, $6800 은 TEXT).
UIHOOK = 0x6600
UIGLY = 0x6D00                   # ★PRG-RAM. 뱅크 전환 없이 읽는다 (아래 설명). 페이지 정렬 필수
# ★UI 음절에는 **연속된 전역 id** 를 준다. 그러면 id->전역id 표가 필요 없고
#   훅이 덧셈 한 번으로 끝난다(256바이트 절약, 훅도 짧아진다).
# ★글리프표가 PRG-RAM($6D00)로 옮겨간 뒤로는 상한이 뱅크가 아니라 **COPY** 로 정해진다.
#   $6D00 + UIMAX*16 <= COPY+$6000 이어야 한다. 96 -> 128 로 늘렸다(2026-09-03,
#   전투 문장을 다듬으면서 98종이 필요해졌다). COPY 도 같이 $1300 -> $1500.
# ★정적 폰트를 49칸으로 줄이자 이스케이프가 필요한 음절이 112 -> 135종이 됐다.
#   글리프표가 $6D00+160*16 = $7700 까지 쓰므로 COPY 도 $1700 으로 늘렸다.
# ★남은 미번역을 다 넣자 186종이 됐다. PRG-RAM 뒤쪽 $6D00~$7FFF 4864바이트를
#   글리프표 200*16=3200($6D00~$7980) + 글리프버퍼 84*16=1344($7A00~$7F40) 로 나눈다.
UIMAX = 224                      # id 1바이트. 글리프표 $6D00 ~ $6D00+UIMAX*16 = $7B00
UI_FILE = "ui_ko.txt"
NAME_FILE = "names_ko.txt"
# UI 훅을 켜면 글리프표($6D00~$7300)까지 PRG-RAM 으로 옮겨야 한다.
COPY = 0x1B00 if (UI_HOOK and UI_PATCH) else 0xC00  # 부팅 때 PRG-RAM 으로 옮길 바이트
assert REC_REGIONS[0] == (0x0F, COPY, 0x2000), "$0F 레코드 구간이 COPY 와 어긋남"
# (공백은 이제 슬롯을 쓴다. $FF 는 제어코드라 절대 쓰면 안 된다 - $C13E -> $C1CB 버튼대기)

# 5b 는 CHR 뱅크5(코드 $40~$7F)를 건드리지 않으므로 원본 문장부호·숫자 타일이 그대로 살아 있다.
# 번역문에서 이 글자들은 슬롯을 쓰지 않고 원래 코드로 바로 나간다.
PUNCT = {"!": 0x5A, "?": 0x5B, "ー": 0x5C, "·": 0x5D, "・": 0x5D, "-": 0x5C}
for _i in range(10):
    PUNCT["0123456789"[_i]] = _i

# ---------------------------------------------------------------- 정적 한글 폰트
# ★CHR-ROM 의 가나 타일자리($24~$59, $64~$7F = 82칸)를 고빈도 한글 음절로 덮는다.
#   여기 있는 음절은 **슬롯을 전혀 쓰지 않고** 원본 코드처럼 바로 나간다.
#   효과(실측): 메시지당 최대 동적 음절 39칸 -> 21칸, 이름은 하나당 최대 4칸.
#   대가: 롬에서 가나가 사라진다. 그래서 **남은 일본어(이름표·전투메시지)를 다 번역하기 전에는
#   켜면 안 된다.** STATIC_FONT 로 잠가 둔다.
#   ★기본 켬. 이름/아이템/마법 표가 이 폰트를 전제로 인코딩된다.
#   끄면 대사 한 개가 39음절을 요구해 대사 풀(25칸)을 넘긴다 -> 되돌릴 수 없다.
STATIC_FONT = __import__("os").environ.get("MT1_STATIC", "1") == "1"
STATIC = {}
_codes = []
for _l in open("static_font.txt", encoding="utf-8"):
    _l = _l.rstrip()
    if not _l.strip() or _l.startswith("#"): continue
    _c, _ch = _l.split(chr(9))
    _c = int(_c, 16)
    assert 0x24 <= _c < 0x5A or 0x64 <= _c < 0x80, "정적 코드 $%02X 가 허용 범위 밖" % _c
    assert _ch not in STATIC, "정적 폰트에 중복 음절: %s" % _ch
    STATIC[_ch] = _c; _codes.append(_c)
assert len(_codes) == len(set(_codes)), "정적 폰트 코드 중복"
assert not (set(STATIC) & set(PUNCT)), "정적 폰트가 PUNCT 와 겹친다"
if not STATIC_FONT:
    STATIC = {}

# ★제어코드별 파라미터 개수. **엔진 핸들러를 역어셈블해 실측한 값**(2026-08-31).
#   예전 표는 $F0 을 0개, $F5~$F8 을 2개로 잘못 잡고 있었다.
#     $F0 -> 뱅크$05 $AFEF : INY/LDA($BE),Y            = 1개
#     $F2 -> $B004        : INY/LDA($BE),Y            = 1개
#     $F3 $F4 -> $8FC7    : INY×2                     = 2개
#     $F5~$F8 -> $B017    : INY×3 (STA $0693 / TAX / TAY) = **3개**
#     $FC -> $AFC7        : INY×2                     = 2개
#     $F9 $FA -> INY 없음                             = 0개
#   $F8 이 3개라는 건 `<F8 01 22>カ` 의 「カ」가 **텍스트가 아니라 파라미터**라는 뜻이다.
#   모르고 번역하면 분기가 깨진다.
#   ($FB 도 핸들러가 1바이트를 더 먹지만, msg_len 은 $FB 에서 끝내므로 1바이트 보수적 -> 안전)
PARAMS = {0xC0: 0, 0xF0: 1, 0xF1: 0, 0xF2: 1, 0xF3: 2, 0xF4: 2,
          0xF5: 3, 0xF6: 3, 0xF7: 3, 0xF8: 3, 0xF9: 0, 0xFA: 0,
          0xFB: 0, 0xFC: 2}


class Asm:
    def __init__(s, org):
        s.org, s.b, s.lab, s.fix, s.fix16 = org, bytearray(), {}, [], []
    def L(s, n): s.lab[n] = s.org + len(s.b)
    def imm(s, op, v): s.b.extend((op, v & 0xFF))
    def zp(s, op, a): s.b.extend((op, a & 0xFF))
    def ab(s, op, a): s.b.extend((op, a & 0xFF, (a >> 8) & 0xFF))
    def raw(s, *v): s.b.extend(v)
    def rel(s, op, l): s.b.extend((op, 0)); s.fix.append((len(s.b) - 1, l))
    def ab_lab(s, op, l, dl): s.b.extend((op, 0, 0)); s.fix16.append((len(s.b) - 2, l, dl))
    def build(s):
        for pos, l in s.fix:
            dd = s.lab[l] - (s.org + pos + 1)
            assert -128 <= dd <= 127, ("분기 초과", l, dd)
            s.b[pos] = dd & 0xFF
        for pos, l, dl in s.fix16:
            a = s.lab[l] + dl
            s.b[pos], s.b[pos + 1] = a & 0xFF, (a >> 8) & 0xFF
        return bytes(s.b)


rom = bytearray(open(SRC, "rb").read())
assert zlib.crc32(bytes(rom)) == 0xE69ECD09
rom[8] = 0x01                                    # PRG-RAM 선언
B4, B5 = HDR + 0x04 * 0x2000, HDR + 0x05 * 0x2000


def phys(a):
    if 0x8000 <= a < 0xA000: return B4 + (a - 0x8000)
    if 0xA000 <= a < 0xC000: return B5 + (a - 0xA000)
    return None


def rd16(p): return rom[p] | (rom[p + 1] << 8)


def msg_len(a):
    p, j = phys(a), 0
    while j < 800:
        b = rom[p + j]
        if b in PARAMS:
            j += 1 + PARAMS[b]
            if b == 0xFB: return j
        else: j += 1
    return j


# ---------------------------------------------------------------- 원문 구조 + 꼬리공유
TBL = 0x8004
NG = (rd16(phys(TBL)) - TBL) // 2
groups = [rd16(phys(TBL + i * 2)) for i in range(NG)]
starts, seen = [], set()
for gi, ga in enumerate(groups):
    if gi + 1 < len(groups): ge = groups[gi + 1]
    else:
        p, c = phys(ga), 0
        while c <= 256 and 0x8000 <= rd16(p) < 0xC000: p += 2; c += 1
        ge = ga + c * 2
    for mi in range((ge - ga) // 2):
        ma = rd16(phys(ga + mi * 2))
        if phys(ma) is not None and ma not in seen:
            seen.add(ma); starts.append(ma)
spans = {a: (a, a + msg_len(a)) for a in starts}
shared = {a for a in starts if any(b != a and spans[b][0] < a < spans[b][1] for b in starts)}
# ★꼬리공유: 어떤 메시지(머리)의 span 한복판을 가리키는 별도 진입점.
#   머리를 번역하면 그 바이트가 우리 인코딩으로 덮이는데, 꼬리는 룩업표에 없어서
#   훅이 못 찾고 -> 치환 없이 -> **엔진이 로컬 인덱스 코드를 그대로 타일로 그린다**(깨진 글자).
#   그래서 꼬리에도 룩업 엔트리를 주되 **머리의 레코드를 가리키게** 한다.
#   머리의 MAP 전체가 만들어지므로 꼬리 구간의 인덱스도 정확히 치환된다.
#   (대가: 꼬리를 띄울 때도 머리의 음절을 전부 배정한다 - 머리를 띄우는 것과 같은 부담)
head_of = {}
for a in sorted(shared):
    cands = [b for b in starts if b not in shared and spans[b][0] < a < spans[b][1]]
    if cands:
        head_of[a] = max(cands)

# ---------------------------------------------------------------- 번역문
TAG = re.compile(r"<([0-9A-Fa-f]{2}(?: [0-9A-Fa-f]{2})*)>")


def tokenize(s):
    out, i = [], 0
    for m in TAG.finditer(s):
        if m.start() > i: out.append(("t", s[i:m.start()]))
        out.append(("c", [int(x, 16) for x in m.group(1).split()]))
        i = m.end()
    if i < len(s): out.append(("t", s[i:]))
    return out


entries, cur = [], None
for line in open(KO_FILE, encoding="utf-8").read().splitlines():
    m = re.match(r"^@([0-9A-Fa-f]{4})\b", line)
    if m: cur = int(m.group(1), 16); continue
    if line.startswith("KO:") and cur is not None:
        # ★.strip() 을 쓰면 안 된다. 파일 형식이 "KO:" + 구분자공백 + 본문인데,
        #   본문 자체가 공백으로 시작하는 줄(원문 <D1> 자리)이 많다.
        #   그 선두 공백은 **메뉴 커서가 앉을 칸**이라, 잘라먹으면 첫 글자가 커서에 덮인다.
        #   (실기 증상: 「무기」->「?기」, 「나카지마」->「?카지마」)
        ko = line[3:].rstrip()
        if ko[:1] == " ": ko = ko[1:]          # 구분자 한 칸만 제거
        if ko: entries.append((cur, ko))
        cur = None
print("번역된 메시지 %d개" % len(entries))

# 전역 음절표
glob, missing = [], set()
for _, ko in entries:
    for k, v in tokenize(ko):
        if k == "t":
            for ch in v:
                if "A" <= ch <= "Z": continue          # 라틴은 원본 타일
                if ch in PUNCT: continue               # 원본 타일로 나가므로 슬롯 불필요
                if ch in STATIC: continue              # 정적 폰트 -> 슬롯 불필요
                # ★공백은 슬롯을 쓰지 않는다. $Dx 가 "빈 칸 x개"를 그리는 제어코드다
                #   ($C217: 카운트=하위니블, $C21E 에서 타일 $FF 를 x번 블릿, $C255 DEC/BNE).
                #   원문의 <D1> 이 바로 그것. 예전엔 빈 글리프 슬롯을 잡았는데
                #   슬롯이 16칸뿐이라 그 한 칸이 아깝다. $FF 를 직접 쓰면 안 된다
                #   - 상위니블 $F 는 $C1CB(화살표+버튼대기)로 분기한다.
                if ch == " ": continue
                if not G.has_glyph(ch): missing.add(ch)
                elif ch not in glob: glob.append(ch)
if missing:
    print("★ 폰트에 없는 글자: %s" % " ".join(sorted(missing))); sys.exit(1)
if len(glob) > MAXSYL:
    print("★ 전역 음절 %d종 > 상한 %d (id 1바이트). 표를 2바이트로 늘려야 함"
          % (len(glob), MAXSYL)); sys.exit(1)
GID = {c: i for i, c in enumerate(glob)}
print("전역 음절 %d종 (상한 %d)" % (len(glob), MAXSYL))

# ---------------------------------------------------------------- 메시지별 인코딩
records, skipped = [], []
for a, ko in entries:
    if a in shared:
        skipped.append((a, "꼬리 공유")); continue
    local = []                                   # 이 메시지가 쓰는 음절 (등장 순)
    enc = []
    litpos = set()                               # 원문 태그에서 온 바이트의 위치
    for k, v in tokenize(ko):
        if k == "c":
            litpos.update(range(len(enc), len(enc) + len(v))); enc.extend(v)
        else:
            i = 0
            while i < len(v):
                ch = v[i]
                if ch == " ":                          # 연속 공백 -> $Dn 한 바이트
                    n = 0
                    while i < len(v) and v[i] == " " and n < 15: n += 1; i += 1
                    enc.append(0xD0 + n); continue
                i += 1
                if "A" <= ch <= "Z":                    # 라틴은 $9A~$B3 에 그대로 산다
                    enc.append(0x9A + ord(ch) - ord("A")); continue
                if ch in PUNCT: enc.append(PUNCT[ch]); continue
                if ch in STATIC: enc.append(STATIC[ch]); continue
                if ch not in local: local.append(ch)
                enc.append(TILE0 + local.index(ch))
    # 태그가 슬롯 타일 코드를 쓰면 우리 한글 글리프가 그 자리에 올라와 엉뚱하게 보인다
    # ★슬롯 타일은 연속이 아니다($B4~$BC, $C1~$CF 도 슬롯). 범위로 검사하면
    #   원문에서 그대로 가져온 <B4>(玉) <CC>(ォ) 같은 태그가 그물을 빠져나간다
    #   (2026-09-02 발각, 15개 메시지).
    # ★★그러나 **제어코드의 파라미터는 그려지지 않는다**. <F8 01 43 47> 의 43/47 은
    #   메시지 id 다. 태그 바이트를 통째로 검사하면 그것까지 충돌로 잡혀
    #   멀쩡한 메시지가 무더기로 빠진다(2026-09-03, 정적폰트를 줄여 $24~$7F 가
    #   슬롯이 되자 13개가 이렇게 탈락했다). 그래서 **실제로 그려지는 자리만** 본다.
    _drawn, _j = set(), 0
    while _j < len(enc):
        _c = enc[_j]
        if _c in PARAMS:
            _j += 1 + PARAMS[_c]
            if _c == 0xFB: break
        elif _c >= 0xD0:
            _j += 1                                  # 여백/프레임대기/개행/끝
        else:
            _drawn.add(_j); _j += 1
    clash = sorted({enc[i] for i in (_drawn & litpos) if enc[i] in _TILESET})
    if clash:
        skipped.append((a, "태그 %s 가 슬롯 타일과 충돌 - 번역문에서 없애야 한다"
                        % " ".join("<%02X>" % b for b in clash)))
        continue
    if len(local) > LOCALMAX:
        skipped.append((a, "고유 음절 %d > 롬 인코딩 상한 %d" % (len(local), LOCALMAX))); continue
    if 0xFB not in enc: enc.append(0xFB)
    if len(enc) > msg_len(a):
        skipped.append((a, "인코딩 %d > 원문 %d 바이트" % (len(enc), msg_len(a)))); continue
    records.append((a, enc, [GID[c] for c in local]))

# ★$C0 은 파서 제어코드(값을 반으로+1)라 **글리프로 쓰면 실기에서 HP 가 깎인다.**
#   슬롯 코드는 $80~$AA 라 $C0 이 슬롯으로 나올 일은 없지만, **원문에 정상적으로
#   들어 있는 <C0> 도 있다**(@915C). 그러니 "없어야 한다"가 아니라
#   **원문과 개수가 같아야 한다**로 검사한다.
_orig = open(SRC, "rb").read()
for a, enc, _ in records:
    q = phys(a)
    j = 0
    while j < 800:
        c = _orig[q + j]
        if c in PARAMS:
            j += 1 + PARAMS[c]
            if c == 0xFB: break
        else:
            j += 1
    want = _orig[q:q + j].count(0xC0)
    got = bytes(enc).count(0xC0)
    assert got == want, ("@%04X 의 $C0 개수가 원문과 다르다 (원문 %d, 번역 %d)"
                         % (a, want, got))
# ★★$FB 는 **파라미터 1바이트**를 갖는다. PARAMS 에 0 으로 적혀 있는 건 틀렸다.
#   엔진 $AFBE(뱅크$05): `INY / PHA / LDA ($BE),Y / TAX / PLA / JMP $B02A`
#   -> $FB **다음 바이트를 X 로 담아 호출자에게 돌려준다.**
#   그룹13(협상)에서 이 값이 결과코드다(실측 분포 0:32 1:6 2:56 3:30 $82:4).
#   0=전투속행, 나머지=동료/도망 등. 즉 「동료가 되었다」를 띄우고도 이 바이트가
#   0 이나 쓰레기면 **전투가 안 끝난다**(2026-09-06 런타임 추적으로 확정).
#
#   우리는 번역문을 원문 자리에 덮어쓰는데 한글이 대개 더 짧다. 그러면 $FB 가
#   앞당겨지고 그 뒤에는 지워지지 않은 **원문 텍스트 찌꺼기**가 남는다.
#   -> 원문의 결과코드를 새 $FB 뒤로 옮겨 적는다.
#   ★단 새 $FB 가 원문과 **같은 자리**면 손대지 않는다. 그 바이트는 이미 다음
#     메시지의 첫 바이트일 수 있고, 그 메시지가 머리면 번역문을 덮어써 버린다(실측 5곳).
def _fb_end(buf, base, cap):
    """buf[base..] 를 제어코드 규칙으로 훑어 $FB **다음** 오프셋을 돌려준다"""
    j = 0
    while j < cap:
        c = buf[base + j]
        j += 1 + PARAMS.get(c, 0)
        if c == 0xFB: return j
    return None


fb_moved = fb_same = 0
for a, enc, _ in records:
    p = phys(a); rom[p:p + len(enc)] = bytes(enc)
    _jo = _fb_end(_orig, p, 800)                 # 원문에서 결과코드가 있던 자리
    _jn = _fb_end(enc, 0, len(enc))              # 번역문에서 $FB 가 끝나는 자리
    if _jo is None or _jn is None: continue
    if _jn < _jo:
        rom[p + _jn] = _orig[p + _jo]; fb_moved += 1
    else:
        fb_same += 1
print("$FB 결과코드 이동 %d곳 (자리가 같아 그대로 둔 것 %d곳)" % (fb_moved, fb_same))

# ---------------------------------------------------------------- 확장 뱅크 데이터
# ★글리프를 메시지 레코드에 **직접 물린다.** 전역 음절표가 없으므로 음절 종수 상한도 없다.
#   메시지 하나의 레코드 = [개수] + id(2바이트)*n   +   글리프(16바이트)*n
#   둘 다 **같은 뱅크 안**에 둔다(훅이 R7 하나로 읽는다). 글리프는 16정렬.
#   id 는 글리프를 가리키는 색인이 아니라 **상주 여부를 비교하는 값**일 뿐이다.
recs = {b: bytearray(0x2000) for b in RECBANKS}
cur = {b: st for b, st, _ in REC_REGIONS}          # 구간마다 시작 위치가 다르다
lim = {b: en for b, _, en in REC_REGIONS}
look = bytearray()
where = {}
where_all = {}
placed = 0
for a, enc, ids in records:
    n = len(ids)
    idsz = 1 + 2 * n
    for b, _st, _en in REC_REGIONS:
        idoff = cur[b]
        # ★★id 목록은 **페이지 경계를 넘으면 안 된다.**
        #   훅이 `LDA $A000,Y` 로 읽는데 Y 가 8비트라 상위바이트를 시작할 때 한 번만
        #   자기수정하고 그 뒤엔 INY 만 한다. 경계를 넘으면 Y 가 감겨 **페이지 앞쪽
        #   (이전 레코드의 글리프 영역)** 을 읽고, id 자리에 글리프 비트맵이 들어온다.
        #   실기 증상: 대사 뒷부분이 엉뚱한 한글로 나오고 일부 글자는 색이 섞인다.
        #   (글리프 소스 gsrc 에는 자리올림 처리가 있는데 id 목록에만 빠져 있었다)
        #   어셈블리를 고치는 대신 **배치로 회피**한다 - 위험이 0 이다.
        if (idoff & 0xFF) + idsz > 0x100:
            idoff = (idoff + 0xFF) & ~0xFF         # 다음 페이지 머리로
        gloff = (idoff + idsz + 15) & ~15          # 글리프는 16정렬
        if gloff + 16 * n <= lim[b]:
            break
    else:
        print("★레코드 뱅크가 모자람 (%d뱅크로는 부족)" % len(RECBANKS)); sys.exit(1)
    assert (idoff & 0xFF) + idsz <= 0x100, "@%04X id 목록이 페이지를 넘음" % a
    recs[b][idoff] = n
    for k, gid in enumerate(ids):
        recs[b][idoff + 1 + 2 * k] = gid & 0xFF
        recs[b][idoff + 2 + 2 * k] = gid >> 8
        recs[b][gloff + 16 * k:gloff + 16 * k + 16] = G.to_chr(G.bitmap(glob[gid]))
    cur[b] = gloff + 16 * n
    look += bytes([a & 0xFF, a >> 8,
                   idoff & 0xFF, idoff >> 8,
                   gloff & 0xFF, gloff >> 8,
                   b, 0])
    where[a] = (idoff, gloff, b)
    where_all[a] = (idoff, gloff, b)
    placed += 1

# ---------------------------------------------------------------- 꼬리 정렬
# ★꼬리는 머리 문장 **중간을 가리키는 별도 진입점**이다. 오프셋이 일본어 기준이라
#   한글로 바꾸면 어긋난다(실측 89개 중 68개가 어긋났다 - 말이 중간부터 잘려 나온다).
#   제어코드 열은 원문과 1:1 로 보존되므로(검사 [3d]), **"몇 번째 제어코드 뒤, 텍스트 몇 글자째"**
#   를 좌표로 삼아 한글 쪽의 같은 자리를 찾는다. 그 차이를 엔트리 8번째 바이트에
#   **부호 있는 보정값**으로 싣고, 훅이 $BE/$BF 를 그만큼 당겨서 읽는다.
def _coords(get, n):
    """각 바이트 위치의 (제어코드 번호, 그 뒤 텍스트 글자수).

    ★$D0~$DF(빈 칸 n개)는 **세지 않는다**. 제어코드 열에서 번역하며 개수가 바뀌는 것은
      이것 하나뿐이다 - 글자 폭이 달라 여백을 다시 잡으니까(check_ctrl 도 $Dn 만 예외).
      이걸 세면 그 뒤 번호가 통째로 밀린다. 실측 증상: 꼬리가 한 코드씩 앞서 잡혀
      「예/아니오만 반복」「메시지가 안 뜸」「엉뚱한 문장」이 났다.
    ★$E0~$EF(n프레임 대기)는 반대로 **반드시** 센다. 예전엔 else 로 빠져 본문 글자로
      셌고, 그래서 그 뒤 글자수 좌표까지 어긋났다."""
    pos, ci, cs, j = {}, 0, 0, 0
    while j < n:
        pos[j] = (ci, cs)
        c = get(j)
        if 0xD0 <= c < 0xE0:
            j += 1                                   # 여백 - 좌표에 영향 없음
        elif c in PARAMS:
            k = PARAMS[c]; ci += 1; cs = 0; j += 1 + k
            if c == 0xFB: break
        elif c >= 0xE0:
            ci += 1; cs = 0; j += 1
        else:
            cs += 1; j += 1
    pos[j] = (ci, cs)
    return pos


# 번역된 머리의 꼬리들에도 같은 레코드를 가리키는 엔트리를 준다
tails = 0
tail_fix = 0
tail_miss = []
enc_of = {a: e for a, e, _ in records}
for t, hd in sorted(head_of.items()):
    if hd not in where:
        continue
    idoff, gloff, b = where[hd]
    e = enc_of[hd]; off = t - hd
    q = phys(hd)
    jp = _coords(lambda j: _orig[q + j], 400)
    ko = _coords(lambda j: e[j], len(e))
    d = 0
    if off in jp:
        hit = sorted(k for k, v in ko.items() if v == jp[off])
        hit = [k for k in hit if not (0xD0 <= e[k] < 0xE0)] or hit
        if hit:
            d = hit[0] - off
            if d: tail_fix += 1
        else:
            tail_miss.append(t)
    else:
        tail_miss.append(t)
    assert -128 <= d <= 127, "@%04X 꼬리 보정값 %d 가 부호바이트를 넘음" % (t, d)
    look += bytes([t & 0xFF, t >> 8,
                   idoff & 0xFF, idoff >> 8,
                   gloff & 0xFF, gloff >> 8,
                   b, d & 0xFF])
    tails += 1
    where_all[t] = (idoff, gloff, b)
# 종료 표시는 **주소 상위바이트 $FF**. 훅이 `LDA $9001,X / CMP #$FF` 로 검사한다.
look += bytes([0x00, 0xFF] + [0] * (ENTSZ - 2))
assert len(look) <= 0x1000, "룩업표 %d바이트가 4KB를 넘음" % len(look)
assert len(look) <= 0x1000, "룩업표가 예약 4KB를 넘음"
recs[LOOKBANK][0x1000:0x1000 + len(look)] = look       # 룩업표는 $10 의 $1000~ 에

# ---------------------------------------------------------------- 조사 타일 즉치값
# ★전투 문장의 조사 「〜は」「〜が」는 문자열이 아니라 **코드가 타일 번호를 직접 써 넣는다**
#   ($0590 = 전투 텍스트 버퍼). 우리는 그 타일 자리를 정적 한글로 재배정했으므로
#   화면에 「노움메 1마리」「나카지마 메 11포인트」처럼 엉뚱한 음절이 찍혔다.
#   한국어 주격/주제 조사(이·가 / 은·는)는 앞 음절 받침에 따라 달라져 타일 하나로 못 쓴다.
#   그래서 빈 타일($59)로 지운다 - 「노움 1마리」「나카지마 11포인트」로 읽힌다.
# ★★자리가 **8곳**이다. 예전엔 두 곳만 고쳐서 상점·장비 화면에 「나카지마 は」처럼
#   조사가 그대로 남아 있었다(사용자 보고 2026-09-07). 저장 형태가 `,X` 와 `,Y` 두 가지다.
#   `A9 7D` 를 전부 훑어 **텍스트 버퍼($0590)에 찍는 것만** 고른다.
PARTICLE = []
for _p in (0x008A7, 0x00B47, 0x027E1, 0x171F3, 0x179CA, 0x1B0DD, 0x1B898):
    # `STA $0590,X` / `STA $0590,Y` / 사이에 `LDY $0650` 이 끼는 형태까지 셋
    _st = rom[_p + 1:_p + 7]
    assert rom[_p - 1] == 0xA9 and rom[_p] == 0x7D and (
        _st[:3] in (bytes([0x9D, 0x90, 0x05]), bytes([0x99, 0x90, 0x05]))
        or _st == bytes([0xAC, 0x50, 0x06, 0x99, 0x90, 0x05])), \
        "$%05X 가 조사 「は」를 텍스트버퍼에 찍는 자리가 아니다" % (_p - 1)
    rom[_p] = BLANK; PARTICLE.append(_p)
# 「が」는 か($69) + 탁점($98) 두 타일이다. 앞 타일 쓰기를 통째로 NOP 하고 뒤만 빈칸으로.
_g = 0x1A2D7
assert rom[_g:_g + 6] == bytes([0xA9, 0x69, 0x9D, 0x90, 0x05, 0xE8]) and        rom[_g + 6:_g + 8] == bytes([0xA9, 0x98]), "$%05X 가 「が」 쓰기 자리가 아니다" % _g
rom[_g:_g + 6] = bytes([0xEA] * 6); rom[_g + 7] = BLANK; PARTICLE.append(_g)
# ★2026-09-13 상점 「いま おもちの ＿を」의 「を」도 코드가 직접 찍는다: 뱅크0 $AA97 `LDA #$90 / STA $0590,X`.
#   $90 은 동적 슬롯 자리라 화면에 엉뚱한 한글(「쌀」)이 떴다(사용자 보고). 롬 전체에서 이 한 곳뿐이다.
#   한국어 문장은 「지금 가진 [물건]」이라 조사가 필요 없다 -> 빈칸으로.
_wo = HDR + (0xAA97 - 0xA000) + 1
assert rom[_wo - 1:_wo + 4] == bytes([0xA9, 0x90, 0x9D, 0x90, 0x05]), "$%05X 가 「を」 쓰기 자리가 아니다" % (_wo - 1)
rom[_wo] = BLANK; PARTICLE.append(_wo)
print("코드가 직접 찍던 조사 타일 %d곳을 빈 칸으로" % len(PARTICLE))
# ★상점 가격 줄: 숫자 뒤 `INX`($AAD0) 가 한 칸을 띄워 「495 에 살게요」가 된다. 한국어는 붙여 쓰므로 지운다.
_ix = HDR + (0xAAD0 - 0xA000)
assert rom[_ix:_ix + 6] == bytes([0xE8, 0xA0, 0x00, 0xB9, 0x7A, 0xAB]), "$%05X 가 가격 뒤 INX 자리가 아니다" % _ix
rom[_ix] = 0xEA

# ---------------------------------------------------------------- 코드가 직접 찍는 「アクマ」
# ★2026-09-07. 전투에서 「(이름)의 공격!」의 이름 자리는 **이름표가 아니라 코드**가 찍는다.
#   뱅크$0D $B3DC:  LDA #$24 STA $0590 / LDA #$2B STA $0591 / LDA #$42 STA $0592
#                   LDA #$03 STA $0650          <- 「アクマ」 3글자 + 커서 3
#   그래서 화면에 「드안격의 공격!」처럼 떴다(코드 $24 $2B $42 가 정적 폰트로 재배정된 탓).
#   악·마 둘 다 정적이라 두 글자로 줄이고 셋째 쓰기는 NOP 로 지운다(코드 길이 그대로).
_ak = HDR + 0x0D * 0x2000 + (0xB3DC - 0xA000)
_akexp = bytes([0xA9, 0x24, 0x8D, 0x90, 0x05, 0xA9, 0x2B, 0x8D, 0x91, 0x05,
                0xA9, 0x42, 0x8D, 0x92, 0x05, 0xA9, 0x03, 0x8D, 0x50, 0x06])
assert bytes(rom[_ak:_ak + 20]) == _akexp, "$B3DC 가 「アクマ」 쓰기 자리가 아니다: %s" % rom[_ak:_ak + 20].hex()
rom[_ak + 1] = STATIC["악"]
rom[_ak + 6] = STATIC["마"]
rom[_ak + 10:_ak + 15] = bytes([0xEA] * 5)          # 셋째 글자 쓰기 삭제
rom[_ak + 16] = 0x02                                # 커서 3 -> 2
print("코드가 직접 찍던 「アクマ」 -> 「악마」 ($B3DC, 뱅크$0D)")

# ---------------------------------------------------------------- 이름표 A (악마/종족)
# 악마·종족 이름 167개는 **대사 엔진을 안 거친다.** 뱅크$0C 의 포인터표 $881A 에서
# 읽어 텍스트 버퍼($0588/$0590)로 복사하는 루틴 3곳이 초크포인트다:
#   $B94B(모드0, $0590 최대8칸)  $B984(모드1, $0588 8칸 $FF패딩)  $B9AB(모드2, 대사중 삽입)
# 셋 다 뱅크$0D($A000). 여기서 A=이름색인 인 지점을 통째로 우리 훅 호출로 바꾼다.
# 이름은 정적 폰트로 대부분 나가고, 남는 음절만 대사와 **같은 슬롯 풀**에서 동적 배정한다
# (실측: 이름 하나당 비정적 최대 4칸, 악마 8인 동시 표시 최악 16칸 / 43칸).
# 표 = (태그, 포인터표 파일오프셋, 개수, 뱅크, 그 뱅크의 CPU 베이스, 진입표 오프셋)
NTABLES = (("A", 0x1882A, 167, 12, 0x8000, 0x0000),   # 악마/종족   읽기: $B94B $B984 $B9AB
           ("B", 0x03F4F,  64,  1, 0xA000, 0x0600),   # 아이템/장비 읽기: $BFC5
           ("C", 0x17EAA,  36, 11, 0xA000, 0x0800))   # 마법        읽기: $BE68
NTBL = 0x8000                       # 진입표들이 놓이는 CPU 베이스 (뱅크셋13 의 R6)
nko = {}
for _line in open(NAME_FILE, encoding="utf-8"):
    _line = _line.rstrip()
    if not _line.strip() or _line.startswith("#"): continue
    _tag, _v = _line.split(chr(9))
    nko[_tag] = _v
nent = bytearray(0xA00)
ntot = 0
for tag, ptoff, ncnt, nbank, ncbase, eoff in NTABLES:
    assert (NTBL + eoff) & 0xFF == 0, "진입표는 페이지 정렬이어야 한다 (훅이 상위바이트만 더한다)"
    nfo = lambda cpu: HDR + nbank * 0x2000 + (cpu - ncbase)
    for i in range(ncnt):
        _p = _orig[ptoff + 2 * i] | (_orig[ptoff + 2 * i + 1] << 8)
        _o = nfo(_p); olen = 0
        while _orig[_o + olen] != 0xFF: olen += 1
        ko = nko.get("%s%d" % (tag, i))
        assert ko is not None, "번역이 빠진 이름: %s%d" % (tag, i)
        enc, loc = [], []
        for ch in ko:
            if ch in PUNCT: enc.append(PUNCT[ch]); continue
            if ch in STATIC: enc.append(STATIC[ch]); continue
            assert G.has_glyph(ch), "이름 %s%d: 폰트에 없는 글자 %s" % (tag, i, ch)
            if ch not in loc: loc.append(ch)
            enc.append(TILE0 + loc.index(ch))
        assert len(enc) <= 15, "이름 %s%d 인코딩 %d바이트 > 15" % (tag, i, len(enc))
        assert len(loc) <= NNSLOT, "이름 %s%d 동적음절 %d개 > 이름슬롯 %d" % (tag, i, len(loc), NNSLOT)
        pad = max(olen, len(enc))
        assert pad <= 15, "이름 %s%d 패딩폭 %d > 15" % (tag, i, pad)
        ids = []
        for ch in loc:
            if ch not in GID:
                GID[ch] = len(glob); glob.append(ch)
            ids.append(GID[ch])
        n = len(ids); idsz = 1 + 2 * n
        for b, _st, _en in REC_REGIONS:
            toff = cur[b]
            if (toff & 0xFF) + len(enc) > 0x100:
                toff = (toff + 0xFF) & ~0xFF
            idoff = toff + len(enc)
            if (idoff & 0xFF) + idsz > 0x100:
                idoff = (idoff + 0xFF) & ~0xFF
            gloff = (idoff + idsz + 15) & ~15
            if gloff + 16 * n <= lim[b]:
                break
        else:
            print("★이름 레코드 뱅크가 모자람"); sys.exit(1)
        recs[b][toff:toff + len(enc)] = bytes(enc)
        recs[b][idoff] = n
        for k, gid in enumerate(ids):
            recs[b][idoff + 1 + 2 * k] = gid & 0xFF
            recs[b][idoff + 2 + 2 * k] = gid >> 8
            recs[b][gloff + 16 * k:gloff + 16 * k + 16] = G.to_chr(G.bitmap(glob[gid]))
        cur[b] = gloff + 16 * n
        e = eoff + i * ENTSZ
        assert e + ENTSZ <= len(nent), "진입표 넘침 (%s%d)" % (tag, i)
        nent[e:e + ENTSZ] = bytes([toff & 0xFF, toff >> 8, idoff & 0xFF, idoff >> 8,
                                   gloff & 0xFF, gloff >> 8, b, (pad << 4) | len(enc)])
        ntot += 1
recs[LOOKBANK][0:len(nent)] = nent
print("이름표 %d개 삽입 (A%d B%d C%d, 진입표 %d바이트)"
      % (ntot, NTABLES[0][2], NTABLES[1][2], NTABLES[2][2], len(nent)))

# ---------------------------------------------------------------- UI/시스템 문자열 제자리 치환
uient = []
for _line in (open(UI_FILE, encoding="utf-8") if UI_HOOK else []):
    _line = _line.rstrip()
    if not _line.strip() or _line.startswith("#"): continue
    _a, _n, _k = _line.split(chr(9))
    uient.append((int(_a, 16), int(_n), _k))
uisyl = []                                   # 이스케이프가 필요한 음절 (id 순)
uilong = []
for _off, _n, _ko in uient:
    enc = []
    for k, v in tokenize(_ko):
        if k == "c":
            enc.extend(v); continue
        i = 0
        while i < len(v):
            ch = v[i]
            if ch == " ":
                m = 0
                while i < len(v) and v[i] == " " and m < 15: m += 1; i += 1
                enc.append(0xD0 + m); continue
            i += 1
            if ch in PUNCT: enc.append(PUNCT[ch]); continue
            if ch in STATIC: enc.append(STATIC[ch]); continue
            assert G.has_glyph(ch), "UI $%05X: 폰트에 없는 글자 %s" % (_off, ch)
            if ch not in uisyl: uisyl.append(ch)
            enc.extend([ESC, uisyl.index(ch)])
    # ★종결자는 **맨 끝 한 바이트만** 허용한다.
    #   중간에 있으면 훅이 거기서 멈춰 뒤쪽 이스케이프가 안 풀린다.
    #   끝에 있는 것은 정상 - `ナカジマたち`(7바이트) 자리에 `나카지마<FF>`(5바이트)를 넣으면
    #   남는 2바이트가 종결자 뒤라 죽은 바이트가 되어 **빈칸 패딩이 문장에 안 끼어든다**.
    assert not (set(enc[:-1]) & {0xFB, 0xFE, 0xFF}),         "UI $%05X 인코딩 중간에 종결자가 있다 - 훅이 거기서 멈춘다" % _off
    if len(enc) > _n:
        uilong.append((_off, _n, len(enc), _ko)); continue
    assert ESC not in enc[1::2] or True
    rom[_off:_off + _n] = bytes(enc) + bytes([BLANK] * (_n - len(enc)))
    INPLACE.append((_off, _n, "UI", _ko))
if uilong:
    print("★UI 길이 초과 %d개:" % len(uilong))
    for _o, _n, _l, _k in uilong[:6]: print("   $%05X %d>%d  %s" % (_o, _l, _n, _k))
    sys.exit(1)
# ---------------------------------------------------------------- ① 보스 칭호 (오프셋표)
# ★2026-09-07 정적 전수조사로 발견. 고정뱅크 $DA01~$DA3A(58바이트)에 6개가 <FE> 로 이어져 있고
#   **$D9FB 에 오프셋표 6바이트**가 따로 있다. 읽는 코드는 $DA49:
#       LDY $D9FB,X / LDA $DA01,Y / STA $0590,X   <- 대사 버퍼라 $C13E 훅이 이스케이프를 푼다
#   길이가 바뀌므로 ui_ko 로는 못 한다(주소가 밀린다). 여기서 직접 쓰고 표를 다시 만든다.
#   블록 바로 뒤 $DA3B 는 코드다 - **58바이트를 절대 넘으면 안 된다.**
def _enc_ko(text):
    """ui_ko 와 같은 규칙으로 인코딩 (정적 폰트 1바이트 / 그 밖 <BD><id> 2바이트 / 공백 $Dn)"""
    e, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch == " ":
            m = 0
            while i < len(text) and text[i] == " " and m < 15:
                m += 1; i += 1
            e.append(0xD0 + m); continue
        i += 1
        if ch in PUNCT: e.append(PUNCT[ch]); continue
        if ch in STATIC: e.append(STATIC[ch]); continue
        assert G.has_glyph(ch), "보스 칭호: 폰트에 없는 글자 %s" % ch
        if ch not in uisyl: uisyl.append(ch)
        e.extend([ESC, uisyl.index(ch)])
    return e


BOSS = ("마왕 미노타우로스", "마왕 메두사", "마왕 로키",
        "마왕 헤카테", "마왕 세트", "대마왕 루시퍼")
BOSS_TBL, BOSS_STR, BOSS_CAP = 0x3DA0B, 0x3DA11, 0x3A
assert bytes(rom[BOSS_TBL:BOSS_TBL + 6]) == bytes([0x00, 0x0B, 0x16, 0x1D, 0x26, 0x2D]),     "보스 오프셋표가 예상과 다르다: %s" % rom[BOSS_TBL:BOSS_TBL + 6].hex()
_bb, _boff = [], []
for _t in BOSS:
    _boff.append(len(_bb))
    _bb.extend(_enc_ko(_t))
    _bb.append(0xFE)
assert len(_bb) <= BOSS_CAP, "보스 칭호 %d바이트 > %d (뒤가 코드다)" % (len(_bb), BOSS_CAP)
rom[BOSS_STR:BOSS_STR + len(_bb)] = bytes(_bb)
rom[BOSS_TBL:BOSS_TBL + 6] = bytes(_boff)
INPLACE.append((BOSS_STR, len(_bb), "BOSS", " / ".join(BOSS)))
print("보스 칭호 6개 한글화 (%d/%d바이트, 오프셋표 %s)"
      % (len(_bb), BOSS_CAP, " ".join("%02X" % x for x in _boff)))

assert len(uisyl) <= UIMAX, "UI 음절 %d종 > 상한 %d" % (len(uisyl), UIMAX)
# UI 음절에 **연속된** 전역 id 를 준다 (이미 있어도 새로 붙인다 - 연속성이 우선)
UIBASE = len(glob)
uiglyph = []
if UI_PATCH:                      # 훅을 안 넣으면 글리프도 전역 id 도 필요 없다
    for _ch in uisyl:
        glob.append(_ch)
        uiglyph.append(bytes(G.to_chr(G.bitmap(_ch))))
    assert UIGLY - 0x6000 + 16 * len(uisyl) <= COPY, "UI 글리프표가 부팅복사 범위를 넘는다"
print("UI 문자열 %d개 치환, 이스케이프 음절 %d종" % (len(uient), len(uisyl)))

# ---------------------------------------------------------------- 치료 프롬프트 진입점
# ★회복의 샘 「누구를 치료할 것인가?」($00EEA)는 코드가 **문자열 +5 지점부터** 복사한다:
#     $000F7A  LDX #$00
#     $000F7C  LDA $AEDF,X      <- 여기 +5
#     $000F7F  STA $0590,X
#     $000F82  INX / CMP #$FE / BNE
#   원문 「よし゛ だれを ちりょう…」에서 「だれ」가 +5 였기 때문이다.
#   한글은 길이가 달라 +5 가 이스케이프 `BD nn`(누) **한복판**이 되어 「누」가 깨져 나왔다
#   (사용자 실기 보고 2026-09-06: 화면에 `0A 1E` 두 타일이 날것으로 떴다).
#   -> 오퍼랜드를 **문자열 맨 앞**으로 돌린다. 앞 5바이트를 아무도 안 읽던 상태였으므로
#      「좋다」를 빼고 21바이트를 문장 전체에 쓴다.
HEAL_LDA = 0x000F7C
assert rom[HEAL_LDA] == 0xBD and rom[HEAL_LDA + 1:HEAL_LDA + 3] == bytes([0xDF, 0xAE]) and \
       rom[HEAL_LDA + 3:HEAL_LDA + 6] == bytes([0x9D, 0x90, 0x05]), \
       "$%05X 가 치료 프롬프트 복사 루프가 아니다" % HEAL_LDA
rom[HEAL_LDA + 1:HEAL_LDA + 3] = bytes([0xDA, 0xAE])     # $AEDF -> $AEDA (문자열 시작)
print("치료 프롬프트 진입점 $AEDF -> $AEDA (문자열 앞에서부터 읽게)")

# ---------------------------------------------------------------- 직접 그려지는 라벨
# 스테이터스/레벨업 라벨은 **$C13E 를 안 거친다**(실기 확인: 이스케이프가 날것으로 나왔다).
# 그래서 이스케이프 없이 **라틴과 정적 폰트 음절만** 쓰고, 지정 뱅크의 모든 사본을 바꾼다.
_ENCJP = {}
for _c, _ch in G_CH.items(): _ENCJP.setdefault(_ch, _c)
_DAK = {"ガ":"カ゛","ギ":"キ゛","グ":"ク゛","ゲ":"ケ゛","ゴ":"コ゛","ザ":"サ゛","ジ":"シ゛","ズ":"ス゛",
        "ゼ":"セ゛","ゾ":"ソ゛","ダ":"タ゛","デ":"テ゛","ド":"ト゛","バ":"ハ゛","ビ":"ヒ゛","ブ":"フ゛",
        "ベ":"ヘ゛","ボ":"ホ゛","パ":"ハ゜","ピ":"ヒ゜","プ":"フ゜","ペ":"ヘ゜","ポ":"ホ゜",
        "が":"か゛","ぎ":"き゛","ぐ":"く゛","げ":"け゛","ご":"こ゛","ざ":"さ゛","じ":"し゛","ず":"す゛",
        "ぜ":"せ゛","ぞ":"そ゛","だ":"た゛","で":"て゛","ど":"と゛","ば":"は゛","び":"ひ゛","ぶ":"ふ゛",
        "べ":"へ゛","ぼ":"ほ゛","ぱ":"は゜","ぴ":"ひ゜","ぷ":"ふ゜","ぺ":"へ゜","ぽ":"ほ゜"}
def _jpbytes(w):
    # ★탁점/반탁점은 **가나 종류마다 코드가 다르다**: 가타카나 $58/$59, 히라가나 $98/$99.
    #   이걸 안 맞춰서 こうげき·きびんさ 가 안 바뀌었다(2026-09-02).
    o = []
    for ch in w:
        if ch == "玉": o.append(0xB4); continue
        exp = _DAK.get(ch, ch)
        base = _ENCJP[exp[0]]
        o.append(base)
        if len(exp) > 1:
            hira = 0x64 <= base <= 0x99
            o.append((0x98 if hira else 0x58) if exp[1] == "゛" else (0x99 if hira else 0x59))
    return bytes(o)
def _kobytes(w, where):
    o = []
    for ch in w:
        if "A" <= ch <= "Z": o.append(0x9A + ord(ch) - ord("A"))
        elif ch == " ": o.append(0xD1)
        elif ch in PUNCT: o.append(PUNCT[ch])
        elif ch in STATIC: o.append(STATIC[ch])
        else:
            raise SystemExit("★라벨 %s: '%s' 는 정적 폰트에 없다 (라벨엔 이스케이프를 못 쓴다)" % (where, ch))
    return bytes(o)
_nlab = 0
for _line in (open("ui_words.txt", encoding="utf-8") if LABELS else []):
    _line = _line.rstrip()
    if not _line.strip() or _line.startswith("#"): continue
    _bk, _jp, _ko = _line.split(chr(9))
    if _bk.startswith("@"):                      # 주소 지정 (한 글자짜리라 전역치환이 위험한 것)
        _off = int(_bk[1:], 16); _n = int(_jp)
        _rep = _kobytes(_ko, _bk)
        assert len(_rep) <= _n, "라벨 %s: %d > %d" % (_bk, len(_rep), _n)
        rom[_off:_off + _n] = _rep + bytes([BLANK] * (_n - len(_rep)))
        INPLACE.append((_off, _n, "라벨@", _ko))
        _nlab += 1
        continue
    _b = int(_bk, 16); _pat = _jpbytes(_jp); _rep = _kobytes(_ko, _jp)
    assert len(_rep) <= len(_pat), "라벨 %s -> %s : %d > %d 바이트" % (_jp, _ko, len(_rep), len(_pat))
    _lo, _hi = bk(_b, 0), bk(_b, 0x2000)
    _i = rom.find(_pat, _lo, _hi)
    while _i >= 0:
        rom[_i:_i + len(_pat)] = _rep + bytes([BLANK] * (len(_pat) - len(_rep)))
        INPLACE.append((_i, len(_pat), "라벨", "%s->%s" % (_jp, _ko)))
        _nlab += 1
        _i = rom.find(_pat, _i + len(_pat), _hi)
print("직접 그려지는 라벨 %d곳 치환" % _nlab)

# ---------------------------------------------------------------- 던전 패널 / 전투 박스
# 뱅크$05 CPU $BE24 (파일 $0BE34) 의 **5바이트 고정폭 23엔트리**.
# 메뉴 정의표 $BDD0 이 이 표를 5바이트 단위로 골라 $0588 버퍼에 깐다.
# 글자는 CHR 뱅크 $02($00~$3F) / $03($40~$7F) 에 구워진 **전용 미니폰트**로,
# 본문 폰트(CHR 뱅크4/5)와 비트맵이 별개다 -> 서로 간섭하지 않는다.
#
# ★기존 타일을 덮지 않는다. 번역하지 않는 엔트리가 쓰는 코드는 잠그고,
#   남은 빈 칸에만 한글을 굽는다. 그래서 미로 그래픽이 바뀔 수 없다.
PANTAB, PANN, PANW = bk(0x05, 0x1E24), 23, 5
if PANEL:
    _pan = {}
    for _l in open("panel_ko.txt", encoding="utf-8"):
        _l = _l.rstrip()
        if not _l.strip() or _l.startswith("#"): continue
        _i, _jp, _ko = _l.split(chr(9))
        if _ko != "-": _pan[int(_i)] = _ko
    _ent = [list(rom[PANTAB + _i * PANW:PANTAB + (_i + 1) * PANW]) for _i in range(PANN)]
    _lock = set()
    for _i, _e in enumerate(_ent):
        if _i not in _pan: _lock |= {c for c in _e if c != 0xFF}
    # 미니폰트 글자 영역. $1C(작은 M)와 $65~$7F(미로 패턴)는 처음부터 제외한다.
    _pool = [c for c in (list(range(0x3D, 0x40)) + list(range(0x40, 0x65))) if c not in _lock]
    # ★★2026-09-13 예/아니오 상자(블록 A·C)는 **두 폰트 페이지 세트에서 똑같이** 보여야 한다.
    #   상단 띠의 글자 코드($00~$7F)는 화면에 따라 R2/R3 = $82/$83(원래 02/03, 이 미니폰트)이거나
    #   $80/$81(원래 00/01)이다. 보물상자·NPC 선택지 화면은 $80/$81 을 쓴다
    #   (사용자 세이브를 헤드리스로 돌려 실측: vblank 에서 R2=$80 R3=$81).
    #   원판은 はい/いいえ 를 **두 세트 모두 같은 코드 $3D·$3E·$3F** 에 두어 어디서나 보였다.
    #   예전 한글판은 예·아·니·오 를 $44 $56 $57 $59 에 두었는데, 그 한글은 02/03 세트에만 있어서
    #   $80/$81 세트 화면에서는 **벽 조각·체크무늬**로 떴다(사용자 보고, 세이브로 재현).
    #   00/01 세트에는 빈 칸이 하나도 없어 네 번째 코드가 안전하다고 증명할 수 없다 -> 원판처럼 세 칸만 쓴다.
    #   세 글자로 자연스러운 「네 / 아뇨」를 $3D·$3E·$3F 에 먼저 배정하고 00 페이지에도 같이 굽는다.
    PROMPT_YES, PROMPT_NO = "네", "아뇨"
    _syl = []
    for _ch in PROMPT_YES + PROMPT_NO:
        if _ch not in _syl: _syl.append(_ch)
    for _i in sorted(_pan):
        for _ch in _pan[_i]:
            if _ch not in _syl: _syl.append(_ch)
    assert len(_syl) <= len(_pool), "패널 음절 %d종 > 빈 칸 %d개" % (len(_syl), len(_pool))
    _pcode = {_ch: _pool[_k] for _k, _ch in enumerate(_syl)}
    assert [_pcode[c] for c in PROMPT_YES + PROMPT_NO] == [0x3D, 0x3E, 0x3F], \
        "네/아뇨 가 $3D~$3F 에 못 들어갔다(잠긴 코드?): %s" % [hex(_pcode[c]) for c in PROMPT_YES + PROMPT_NO]
    _chrp = HDR + rom[4] * 16384
    for _ch, _c in _pcode.items():
        assert G.has_glyph(_ch), "패널 폰트에 없는 글자 %s" % _ch
        _b, _t = ((0x02, _c) if _c < 0x40 else (0x03, _c - 0x40))
        _o = _chrp + _b * 1024 + _t * 16
        rom[_o:_o + 16] = bytes(G.to_chr(G.bitmap(_ch)))
    # 00 페이지(원래 はいえ 자리)에도 같은 세 글자. 매퍼195 변환이 00/01 을 80/81 로 옮기므로 그쪽에도 간다.
    for _ch in PROMPT_YES + PROMPT_NO:
        _o = _chrp + 0x00 * 1024 + _pcode[_ch] * 16
        assert any(rom[_o:_o + 16]), "00 페이지 $%02X 가 비어 있다 - 원래 가나 자리가 아니다" % _pcode[_ch]
        rom[_o:_o + 16] = bytes(G.to_chr(G.bitmap(_ch)))
    for _i, _ko in sorted(_pan.items()):
        _enc = bytes(_pcode[_ch] for _ch in _ko)
        assert len(_enc) <= PANW, "패널 idx%d '%s' %d칸 > %d칸" % (_i, _ko, len(_enc), PANW)
        rom[PANTAB + _i * PANW:PANTAB + (_i + 1) * PANW] = _enc + bytes([0xFF] * (PANW - len(_enc)))
        INPLACE.append((PANTAB + _i * PANW, PANW, "패널", _ko))
    print("던전 패널/전투 박스 %d개 한글화 (음절 %d종 / 빈 칸 %d개, 잠근 타일 %d개)"
          % (len(_pan), len(_syl), len(_pool), len(_lock)))
else:
    print("던전 패널 꺼짐")

# ---------------------------------------------------------------- 전투 예/아니오 프롬프트 (2026-09-06)
# ★전투 협상의 「はい/いいえ」는 **패널 문자열표를 안 거친다.** 고정뱅크 `$D5B5` 에
#   9바이트 레코드로 **하드코딩**돼 있고, `$D640` 루틴이 그걸 버퍼 `$0580` 으로 복사한다.
#     레코드 = [열, 행, 폭, 높이, 0,0,0, 플래그, 타일]   플래그 $04 = 다음 네임테이블
#     블록 A(X=$00) 미니폰트 / B(X=$2E) **본문폰트** / C(X=$5C) 미니폰트
#   패널표만 번역하고 여기를 놓쳐서, 미니폰트를 한글로 갈아끼운 뒤
#   원본 코드 `3D 3E`(はい) `3E 3E 3F`(いいえ) 가 「컴프 / 프프상」으로 떴다.
#   -> 사용자가 보고한 「예/아니오를 눌러도 선택지만 반복」의 정체.
#   (원본 롬과 v31 의 네임테이블이 이 상자에서 바이트 단위로 같은 것을 확인해 확정)
# ★블록 B 는 본문 폰트라 정적 폰트에 없는 음절(예·아·니)을 못 쓴다 - 아직 손대지 않는다.
PROMPT = 0xD5B5
if PANEL:
    _pc = _pcode                                    # 패널 미니폰트 음절 -> 타일코드
    # ★블록 A·C 는 **미니폰트**(패널 전용), 블록 B 는 **본문 폰트**를 쓴다.
    #   B 는 대사 엔진도 UI 훅도 안 거쳐서 **정적 폰트 음절만** 쓸 수 있다.
    #   v33 때는 예·아·니가 정적 폰트에 없어 보류했는데, 2026-09-07 에 셋을 정적으로 올려 해결.
    #   원본 타일: A·C = `3D 3E 3E 3E 3F`(미니폰트) / B = `7D 65 65 65 67`(は い い い え)
    # ★2026-09-13 A·C 는 「네 / 아뇨」(미니폰트 $3D $3E $3F - 위 패널 절 설명). B 는 본문폰트라 그대로 「예 / 아니오」.
    _BLOCKS = (("A", 0x00, [_pc[c] for c in PROMPT_YES], [_pc[c] for c in PROMPT_NO],
                [0x3D, 0x3E, 0x3E, 0x3E, 0x3F]),
               ("B", 0x2E, [STATIC[c] for c in "예"], [STATIC[c] for c in "아니오"],
                [0x7D, 0x65, 0x65, 0x65, 0x67]),
               ("C", 0x5C, [_pc[c] for c in PROMPT_YES], [_pc[c] for c in PROMPT_NO],
                [0x3D, 0x3E, 0x3E, 0x3E, 0x3F]))
    for _blk, _base, _yes, _no, _want in _BLOCKS:
        _o = fx(PROMPT) + _base
        _recs = [list(rom[_o + k * 9:_o + k * 9 + 9]) for k in range(5)]
        assert rom[_o + 45] == 0xFF, "블록%s 가 5레코드가 아니다" % _blk
        assert [r[8] for r in _recs] == _want, \
            "블록%s 타일이 원본 はい/いいえ 가 아니다: %s" % (_blk, [hex(r[8]) for r in _recs])
        # ★$FF 를 타일로 쓰면 안 된다. 복사 루프가 **레코드의 모든 바이트**를 $FF 와
        #   비교해서 종료하므로($D656), 빈칸 용도로 넣으면 그 뒤 레코드가 통째로 잘린다.
        #   -> 쓸 글자 수만큼만 레코드를 쓰고 그다음 자리에 종료자를 둔다.
        #   위치는 원본 레코드 0(윗줄 첫 칸) 과 2~(아랫줄) 것을 그대로 쓴다.
        assert len(_yes) == 1 and 1 <= len(_no) <= 3, "블록%s 글자 수가 레코드 배치와 안 맞는다" % _blk
        _use = [_recs[0]] + _recs[2:2 + len(_no)]
        for _k, (_rec, _t) in enumerate(zip(_use, _yes + _no)):
            _rec[8] = _t
            rom[_o + _k * 9:_o + _k * 9 + 9] = bytes(_rec)
        rom[_o + 9 * len(_use)] = 0xFF           # 쓴 레코드 다음 자리 = 종료
        INPLACE.append((_o, 45, "전투프롬프트", "예/아니오(블록%s)" % _blk))
    print("전투/상점 예/아니오 프롬프트 3블록 전부 한글화 ($D5B5)")

# ---------------------------------------------------------------- 상태창 상자 테두리 제거
# ★슬롯 타일이 게임 그래픽과 겹치는 문제의 해법 (2026-09-03, 사용자 지시).
#   상태/목록 화면의 이중선 상자를 `$C9`(-) `$CB`(|) `$C8 $CA`(T) `$C1~$CF`(모서리)
#   `$F4 $F5 $F6 $F8`(귀퉁이) 로 그리는데, `$C1~$CF` 는 **우리 이름 슬롯 범위**다.
#   이름 슬롯이 12칸을 넘으면 테두리가 한글로 덮인다(실기 확인).
#   -> 테두리를 빈칸으로 바꿔 화면에서 없앤다. 그러면 슬롯 28칸을 전부 안전하게 쓴다.
#   ★초상화 테두리는 CHR-ROM 코드($13 $14 $15 등)라 여기 안 걸린다 - 그대로 남는다.
NOBOX = os.environ.get("MT1_NOBOX", "1") == "1"
# ★테두리 **선과 귀퉁이만** 지운다. $C1~$C7 $CC~$CF 는 블록 머리(`C2 D4 0E 08 C3`)나
#   글자(`$C4`=P, `$C5`=:)로도 쓰여서 싸잡아 지우면 레이아웃이 깨진다.
#   패턴: 위 `F5 C9 .. F4` / 옆 `F8 .. CB` / 중간 `C8 C9 .. CA` / 아래 `F6 F9 .. F7`
#
# ★★영어판을 그대로 따른다 (2026-09-03, 사용자가 두 화면 디자인이 다른 걸 발견).
#   영어판은 **사람 화면 두 블록만** 상자를 없애고(23개->0, 15개->0)
#   **악마 화면은 21개 그대로** 두었다. 이유가 명확하다:
#     - 사람 화면은 아이템 목록 + 마법 목록이 같이 떠서 이름이 많다 -> 타일이 모자란다
#     - 악마 화면은 마법 목록 하나뿐이라 여유가 있다
#   그리고 빈칸 타일($59)이 아니라 **$FF**(아무것도 안 그림)로 바꿨다.
#   레이아웃이 원래 $FF 로 빈 칸을 채우므로 그게 이 루틴의 '없음'이다.
# ★범위로 잡지 말 것. 처음에 `$0DAE0~$0DCE8` 식으로 뭉갰다가
#   블록2 의 **바닥 테두리 `$0DCE8`** 가 범위 밖이라 유미코 화면에만 초록 줄이 남았다
#   (2026-09-03 실기 보고). 그래서 **영어판이 실제로 지운 자리 41곳을 그대로** 박아 둔다.
#   뽑는 법:  v3 에서 상자코드이고 영어판에서 $FF 인 뱅크$06 주소 전부
BOXCLEAR = [
    0x0DAE6, 0x0DAE7, 0x0DAEA, 0x0DAFC, 0x0DB00, 0x0DB0B, 0x0DB0C, 0x0DB0F,
    0x0DB1B, 0x0DB1F, 0x0DB2A, 0x0DB2B, 0x0DB2E, 0x0DB3A, 0x0DB3E, 0x0DB49,
    0x0DB4A, 0x0DB4D, 0x0DB59, 0x0DB5D, 0x0DB68, 0x0DB69, 0x0DB6C, 0x0DC82,
    0x0DC83, 0x0DC86, 0x0DC9B, 0x0DC9F, 0x0DCAA, 0x0DCAB, 0x0DCAE, 0x0DCBA,
    0x0DCBE, 0x0DCC9, 0x0DCCA, 0x0DCCD, 0x0DCD9, 0x0DCDD, 0x0DCE8, 0x0DCE9,
    0x0DCEC]
BOXCODES = {0xC8, 0xC9, 0xCA, 0xCB, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9}
BOXSPANS = [(0x0DAE0, 0x0DB70), (0x0DC7C, 0x0DCF0)]      # check_slotclash 가 쓰는 참고 범위
if NOBOX:
    _nb = 0
    for _a in BOXCLEAR:
        assert rom[_a] in BOXCODES, "상자 목록 $%05X 가 상자코드가 아니다 ($%02X)" % (_a, rom[_a])
        rom[_a] = 0xFF; _nb += 1                # ★$59(빈칸타일)가 아니라 $FF(안 그림)
    print("사람 상태창 상자 테두리 %d칸 제거 (악마 화면은 영어판처럼 유지)" % _nb)
else:
    print("상자 테두리 유지")

# ★번역문·이름표가 $BD 를 쓰면 훅이 오인한다
for _a, _e, _ in records:
    assert ESC not in _e, "@%04X 인코딩에 $BD 가 들어 있다 (UI 이스케이프 표식과 충돌)" % _a

for b in RECBANKS:
    rom[bk(b, 0):bk(b, 0) + 0x2000] = bytes(recs[b])
LOOKEND = 0x91 + (len(look) >> 8)   # 룩업 스캔이 넘어서면 안 되는 상위바이트
used_banks = sum(1 for b in RECBANKS if cur[b])
rec_bytes = sum(cur.values())

# 뱅크셋 13 의 R6 을 룩업 뱅크로. R7 은 훅이 레코드 뱅크로 직접 바꾼다.
assert rom[fx(0xC959)] == 0x0C and rom[fx(0xC967)] == 0x0D
rom[fx(0xC959)] = LOOKBANK
rom[fx(0xC967)] = RECBANKS[0]

# ---------------------------------------------------------------- NMI 업로더 (4a)
c = Asm(0x6000)
c.zp(0xA5, 0x0B); c.imm(0x29, 0x01); c.rel(0xD0, "skip")
c.ab(0xAD, CNT); c.rel(0xF0, "skip")             # 올릴 게 없으면 끝
# ★목적지 타일은 **변환표**에서 얻는다 (슬롯 번호 != 타일 번호. $C0 을 건너뛰므로 불연속)
c.ab(0xAE, SLOT); c.ab(0xBD, SLOTTAB); c.ab(0x8D, TMP)    # TMP = 타일 번호
c.raw(0x4A, 0x4A, 0x4A, 0x4A)
c.raw(0x18); c.imm(0x69, 0x10); c.ab(0x8D, 0x2006)        # 목적지 상위 = $10 + (타일>>4)
# 글리프 소스는 **슬롯 기준**이라 표와 무관: SRCBASE + 슬롯*16
c.ab(0xAD, SLOT); c.raw(0x4A, 0x4A, 0x4A, 0x4A)
c.raw(0x18); c.imm(0x69, SRCBASE >> 8); c.ab_lab(0x8D, "ldsrc", 2)
c.ab(0xAD, SLOT); c.raw(0x0A, 0x0A, 0x0A, 0x0A); c.raw(0xAA)   # X = 슬롯*16 (소스 인덱스)
c.ab(0xAD, TMP); c.imm(0x29, 0x0F); c.raw(0x0A, 0x0A, 0x0A, 0x0A)
c.ab(0x8D, 0x2006); c.imm(0xA0, CHUNK)                    # 목적지 하위 = (타일&$0F)*16
c.L("ldsrc")
c.ab(0xBD, SRCBASE); c.ab(0x8D, 0x2007); c.raw(0xE8, 0x88); c.rel(0xD0, "ldsrc")
c.ab(0xEE, CHK); c.ab(0xAD, CHK); c.imm(0xC9, 16 // CHUNK); c.rel(0xD0, "skip")
c.imm(0xA9, 0x00); c.ab(0x8D, CHK)
c.ab(0xEE, SLOT); c.ab(0xAD, SLOT); c.ab(0xCD, CNT); c.rel(0xD0, "skip")
c.imm(0xA9, 0x00); c.ab(0x8D, SLOT)              # 순환 (자가복구)
c.L("skip")
c.ab(0x20, 0xC3DF); c.raw(0x60)
up = c.build()
LDSRC = c.lab["ldsrc"]
assert len(up) <= SLOT - 0x6000

# ---------------------------------------------------------------- 메시지 시작 훅
# 룩업표는 4바이트/엔트리이고 X 가 8비트라 한 페이지에 64개까지다.
# 페이지를 넘길 수 있게 참조 4곳의 상위바이트를 자기수정한다(PRG-RAM 이라 합법).
h = Asm(HOOK)
# === 런타임 슬롯 할당기 ===
# 메시지마다 슬롯을 0부터 재배정하면 한 화면의 앞 메시지 글자가 바뀐다(실기 확인).
# 그래서 (a) 상주 슬롯을 재사용하며 누적 배정하고,
#        (b) 원문을 PRG-RAM 으로 복사하면서 코드를 **배정된 슬롯**으로 치환한 뒤
#        (c) $BE/$BF 를 그 복사본으로 돌린다. 엔진의 ($BE),Y 가 그대로 동작한다.
# 전부 메인 스레드라 사이클 제약이 없다.
h.imm(0xA9, 0x00); h.ab(0x8D, 0x0658)            # 원래 동작

# --- 새 창 판정 -> 슬롯 반납 ($C0~$CF 16칸뿐이라 한 화면치만 담으면 된다)
# $0651 = 이 메시지가 쓰기 시작할 창의 행. 같은 창에 이어 붙으면 행이 **커지고**,
# 새 창이 열리면 위로 돌아가거나 같은 행에서 다시 시작한다(실측:
#   $8606 행$13 -> $8635 행$0F(새창) -> $8648 행$11(이어붙임) -> $8656 행$0F(새창)).
# 원래는 창 템플릿 복사 $D083 에 걸려 했으나, 그 루틴은 **전체 PRG 통틀어 호출처가
# $CF88 하나뿐인데 실제로 한 번도 실행되지 않는다**(계측 확인). $0651 에 쓰는 곳은
# 165군데라 그쪽도 못 건다. 그래서 훅 안에서 행 번호로 판정한다.
# 빗나가도 최악이 "예전과 같은 순환"이라 안전한 쪽으로 degrade 한다.
h.ab(0xAD, LASTROW); h.ab(0xCD, 0x0651)
h.rel(0x90, "samewin")                           # LASTROW < $0651 -> 이어붙임
h.imm(0xA9, 0x00); h.ab(0x8D, NEXT)              # 새 창 -> 슬롯 전부 반납
h.L("samewin")
h.ab(0xAD, 0x0651); h.ab(0x8D, LASTROW)

h.imm(0xA2, BSET); h.ab(0x20, 0xC864)            # 뱅크셋13 -> R6 = 룩업 뱅크($8000~$9FFF)
# 룩업표는 페이지를 넘으므로 참조 7곳의 상위바이트를 자기수정한다(PRG-RAM 이라 합법).
h.imm(0xA9, 0x90)
SELF = ("f1", "f2", "h1", "h2", "h3", "h4", "h5", "h6")
for lb_ in SELF:
    h.ab_lab(0x8D, lb_, 2)
h.imm(0xA2, 0x00)
h.L("find")
h.L("f1"); h.ab(0xBD, 0x9001)                    # 주소 상위
h.imm(0xC9, 0xFF); h.rel(0xF0, "none")           # $FF = 표 끝
h.zp(0xC5, 0xBF); h.rel(0xD0, "next")
h.L("f2"); h.ab(0xBD, 0x9000)                    # 주소 하위
h.zp(0xC5, 0xBE); h.rel(0xF0, "hit")
h.L("next")
h.raw(0x8A, 0x18); h.imm(0x69, ENTSZ); h.raw(0xAA)   # X += ENTSZ (2의 거듭제곱이라 깨끗히 감김)
h.rel(0xD0, "find")
for lb_ in SELF:
    h.ab_lab(0xEE, lb_, 2)
h.ab_lab(0xAD, "f1", 2)
h.imm(0xC9, LOOKEND)
h.rel(0x90, "find")
h.L("none")
h.ab(0x20, 0xC8D5); h.raw(0x60)                  # 번역 안 된 메시지 -> 아무것도 안 건드리고 반환

h.L("hit")
# --- R7 을 이 메시지의 레코드 뱅크로. 복원은 $C8D5 가 한다.
# --- 꼬리 보정: $BE/$BF 를 부호 있는 바이트만큼 옮긴다 (머리는 0이라 그냥 지나간다)
h.L("h6"); h.ab(0xBD, 0x9007)
h.rel(0xF0, "nod")
h.ab(0x8D, TMP)
h.raw(0x18); h.zp(0x65, 0xBE); h.zp(0x85, 0xBE)
h.imm(0xA9, 0x00); h.ab(0x2C, TMP); h.rel(0x10, "pos")
h.imm(0xA9, 0xFF)
h.L("pos")
h.zp(0x65, 0xBF); h.zp(0x85, 0xBF)
h.L("nod")
h.L("h1"); h.ab(0xBD, 0x9006)
# ★★R7 만 덮어쓰면 NMI 가 나가면서 되돌린다.
#   NMI 출구($C118~$C12D)가 `LDX $14 / LDA $C95A,X / STA $8001` 로 **뱅크셋 표에서
#   R7 을 다시 읽어 복원**하기 때문이다. 표는 ROM 이라 메시지마다 다른 값을 못 담는다.
#   -> 표를 PRG-RAM 사본으로 돌리고(아래 패치), 그 13번 항목도 같이 갱신한다.
#   그러면 NMI 가 복원해도 **올바른 레코드 뱅크**로 돌아온다.
#   (이걸 안 해서 훅 도중 NMI 가 끼면 이후 읽기가 엉뚱한 뱅크에서 나왔다.
#    글리프 16바이트 복사 중간에 걸리면 절반만 옳은 뱅크 = 글자 색이 섞여 보였다)
h.ab(0x8D, TBL7 + BSET)
h.imm(0xA0, 0x07); h.ab(0x8C, 0x8000); h.ab(0x8D, 0x8001)
# --- 글리프 소스 = $A000 + gloff  (로컬 하나 처리할 때마다 16씩 전진한다)
h.L("h2"); h.ab(0xBD, 0x9005)
h.raw(0x18); h.imm(0x69, 0xA0); h.ab_lab(0x8D, "gsrc", 2)
h.L("h3"); h.ab(0xBD, 0x9004)
h.ab_lab(0x8D, "gsrc", 1)
# --- id 목록 = $A000 + idoff
h.L("h4"); h.ab(0xBD, 0x9003)
h.raw(0x18); h.imm(0x69, 0xA0)
h.ab_lab(0x8D, "ldid", 2); h.ab_lab(0x8D, "ldid2", 2); h.ab_lab(0x8D, "ldid3", 2)
h.L("h5"); h.ab(0xBD, 0x9002)
h.raw(0xA8)
h.L("ldid"); h.ab(0xB9, 0xA000)                  # [개수]
h.ab(0x8D, LCNT)
h.imm(0xA2, 0x00)                                # X = 로컬 인덱스 k
h.L("each")
# 루프가 길어져 BEQ 로는 built 에 못 닿는다 -> 조건을 뒤집고 JMP 로 건넌다
h.ab(0xEC, LCNT)
h.rel(0xD0, "cont")
h.raw(0x4C, 0, 0); h.fix16.append((len(h.b) - 2, "built", 0))
h.L("cont")
h.raw(0xC8)
h.L("ldid2"); h.ab(0xB9, 0xA000); h.ab(0x8D, TMP)      # id 하위
h.raw(0xC8)
h.L("ldid3"); h.ab(0xB9, 0xA000); h.ab(0x8D, TMP2)     # id 상위
h.raw(0x98, 0x48)                                # TYA/PHA : id목록 위치 보존
h.imm(0xA0, 0x00)
h.L("srch")                                      # 이미 상주 중인 슬롯인지 (16비트 비교)
h.ab(0xCC, NEXT); h.rel(0xF0, "nofound")
h.ab(0xB9, RESIDL); h.ab(0xCD, TMP); h.rel(0xD0, "snext")
h.ab(0xB9, RESIDH); h.ab(0xCD, TMP2); h.rel(0xF0, "found")
h.L("snext")
h.raw(0xC8); h.rel(0xD0, "srch")
h.L("nofound")
h.ab(0xAD, NEXT); h.imm(0xC9, NDLG); h.rel(0x90, "ok")      # ★대사 풀은 0~NDLG-1
h.imm(0xA9, 0x00); h.ab(0x8D, NEXT)              # 꽉 차면 0부터 다시(가장 오래된 것부터 재활용)
h.L("ok")
h.ab(0xAC, NEXT)                                 # Y = 새 슬롯
h.ab(0xAD, TMP); h.ab(0x99, RESIDL)
h.ab(0xAD, TMP2); h.ab(0x99, RESIDH)
h.raw(0x98); h.raw(0x4A, 0x4A, 0x4A, 0x4A)
h.raw(0x18); h.imm(0x69, SRCBASE >> 8); h.ab_lab(0x8D, "gdst", 2)
h.raw(0x98); h.raw(0x0A, 0x0A, 0x0A, 0x0A)
h.ab_lab(0x8D, "gdst", 1)                        # 목적지 = SRCBASE + 슬롯*16
h.raw(0x98, 0x48)                                # 슬롯 번호 보존
h.imm(0xA0, 0x00)
h.L("gcopy")
h.L("gsrc"); h.ab(0xB9, 0xA000)                  # ★글리프를 레코드에서 바로 복사
h.L("gdst"); h.ab(0x99, SRCBASE)
h.raw(0xC8); h.imm(0xC0, 0x10); h.rel(0xD0, "gcopy")
h.raw(0x68, 0xA8)                                # Y = 슬롯 번호
h.ab(0xEE, NEXT)
h.L("found")
h.raw(0x98); h.ab(0x9D, MAP)                     # MAP[k] = 슬롯
# 글리프 소스를 다음 로컬로. **재사용이든 새 배정이든 항상** 16 전진해야 k 와 어긋나지 않는다.
h.ab_lab(0xAD, "gsrc", 1); h.raw(0x18); h.imm(0x69, 0x10); h.ab_lab(0x8D, "gsrc", 1)
h.rel(0x90, "nocarry")
h.ab_lab(0xEE, "gsrc", 2)
h.L("nocarry")
h.raw(0x68, 0xA8)                                # id목록 위치 복원
h.raw(0xE8)
h.raw(0x4C, 0, 0); h.fix16.append((len(h.b) - 2, "each", 0))

h.L("built")
h.ab(0x20, SETCNT)                               # CNT = max(대사, 이름) - 이름 슬롯도 올라가야 한다
h.imm(0xA9, 0x00); h.ab(0x8D, SLOT); h.ab(0x8D, CHK)
h.ab(0x20, 0xC8D5)                               # ★뱅크 복원 - 이제 원문($BE)을 읽을 수 있다

# --- 원문을 PRG-RAM 으로 복사하며 슬롯 코드 치환
h.imm(0xA0, 0x00)
h.L("cp")
h.zp(0xB1, 0xBE)                                 # LDA ($BE),Y
h.ab(0x8D, TMP)                                  # 원본 보관 (종료 판정용)
h.imm(0xC9, TILE0); h.rel(0x90, "keep")
h.imm(0xC9, (TILE0 + LOCALMAX) & 0xFF); h.rel(0xB0, "keep")
h.raw(0x38); h.imm(0xE9, TILE0); h.raw(0xAA)     # SEC/SBC/TAX : 로컬 인덱스
h.ab(0xBD, MAP)                                  # A = 배정된 슬롯
h.raw(0xAA); h.ab(0xBD, SLOTTAB)                 # -> 실제 타일 번호 (변환표 경유)
h.L("keep")
h.ab(0x99, TEXT)
h.ab(0xAD, TMP); h.imm(0xC9, 0xFB); h.rel(0xF0, "cpend")
h.raw(0xC8); h.rel(0xD0, "cp")
h.L("cpend")
# ★★$FB 는 **파라미터 1바이트를 갖는다.** 엔진 $AFBE(뱅크$05):
#     `INY / PHA / LDA ($BE),Y / TAX / PLA / RTS`  ->  그 바이트를 X 로 돌려주고
#     호출자 $AEDC 가 `TXA / RTS` 로 **전투 시스템에 협상 결과로 넘긴다**
#     (실측 분포 0:32 1:6 2:56 3:30 $82:4. 0 = 동료가 됨).
#   여기서 안 옮기면 $6800 버퍼에 남아 있던 **이전 메시지 찌꺼기**가 결과가 된다.
#   실기 증상: 「동료가 되었다」/「도망쳐 버렸다」를 띄우고도 **전투가 안 끝난다**
#   (2026-09-06 런타임 추적. 원문은 X=00, 우리는 X=5A 였다).
h.raw(0xC8); h.rel(0xF0, "cpdone")               # INY - 감기면 버퍼를 넘으니 포기
h.zp(0xB1, 0xBE); h.ab(0x99, TEXT)               # 파라미터도 복사본에 넣는다
h.L("cpdone")
h.imm(0xA9, TEXT & 0xFF); h.zp(0x85, 0xBE)
h.imm(0xA9, TEXT >> 8); h.zp(0x85, 0xBF)         # 엔진이 이제 복사본을 읽는다
h.raw(0x60)
hook = h.build()
assert HOOK + len(hook) <= RESIDL, "훅 %d바이트가 RESIDL($%04X)를 침범" % (len(hook), RESIDL)
assert RESIDL + NSLOT <= RESIDH and RESIDH + NSLOT <= MAP and MAP + LOCALMAX <= NRESL, "상주표/MAP 영역이 겹침 (NSLOT=%d)" % NSLOT
assert SRCBASE + NSLOT * 16 <= 0x8000, "글리프 버퍼(%d바이트)가 PRG-RAM 끝을 넘음" % (NSLOT * 16)
assert NRESL + NNSLOT <= NRESH and NRESH + NNSLOT <= 0x6500, "이름 상주표가 겹침"
assert SLOTTAB + NSLOT <= SLOT, "변환표가 변수 영역을 침범"

# ---------------------------------------------------------------- 이름 훅 (6502)
# 진입: A = 이름 색인, NMODE = 0/1/2, X = 목적지 오프셋(모드1)
# 나감: 모드0/2 는 $0590 에, 모드1 은 $0588 에 한글 코드를 채우고 원본과 같은 관례로 끝낸다.
nh = Asm(NHOOK)
nh.ab(0x8E, NX)                                   # 모드1 의 목적지 오프셋 보존
nh.zp(0x85, 0x12)                                 # $12 = 색인 (원본 루틴도 $12/$13 을 쓴다)
nh.imm(0xA9, 0x00); nh.zp(0x85, 0x13)
for _ in range(3):
    nh.zp(0x06, 0x12); nh.zp(0x26, 0x13)          # 색인 * 8
nh.ab(0xAE, NMODE); nh.zp(0xA5, 0x13); nh.raw(0x18)
nh.ab(0x7D, NBASEH); nh.zp(0x85, 0x13)      # 표 베이스는 모드마다 다르다
nh.imm(0xA2, BSET); nh.ab(0x20, 0xC864)           # 뱅크셋13 -> R6 = 이름 진입표 뱅크($8000)
# --- 엔트리 8바이트. ★$12/$13 을 덮기 전에 필요한 값을 전부 꺼내야 한다.
nh.imm(0xA0, 0x06); nh.zp(0xB1, 0x12)             # 레코드 뱅크
nh.ab(0x8D, TBL7 + BSET)                          # ★NMI 가 R7 을 되돌릴 때 볼 사본도 같이 갱신
nh.ab(0x8D, NT1)
nh.imm(0xA0, 0x07); nh.ab(0x8C, 0x8000)           # R7 선택
nh.ab(0xAD, NT1); nh.ab(0x8D, 0x8001)             # R7 = 레코드 뱅크 ($A000~)
nh.imm(0xA0, 0x07); nh.zp(0xB1, 0x12); nh.raw(0x48)
nh.imm(0x29, 0x0F); nh.ab(0x8D, NLEN)             # 낮은니블 = 인코딩 길이
nh.raw(0x68, 0x4A, 0x4A, 0x4A, 0x4A); nh.ab(0x8D, NPAD)   # 높은니블 = 원문 칸수
nh.imm(0xA0, 0x05); nh.zp(0xB1, 0x12); nh.raw(0x18); nh.imm(0x69, 0xA0)
nh.ab_lab(0x8D, "ngsrc", 2)
nh.imm(0xA0, 0x04); nh.zp(0xB1, 0x12); nh.ab_lab(0x8D, "ngsrc", 1)
nh.imm(0xA0, 0x00); nh.zp(0xB1, 0x12); nh.ab(0x8D, NT1)            # 텍스트 오프셋 하위
nh.imm(0xA0, 0x01); nh.zp(0xB1, 0x12); nh.raw(0x18); nh.imm(0x69, 0xA0)
nh.ab(0x8D, NT2)                                                   # 텍스트 상위(+$A0)
nh.imm(0xA0, 0x02); nh.zp(0xB1, 0x12); nh.raw(0xAA)                # X = id 하위
nh.imm(0xA0, 0x03); nh.zp(0xB1, 0x12); nh.raw(0x18); nh.imm(0x69, 0xA0)
nh.raw(0x48, 0x8A); nh.zp(0x85, 0x12); nh.raw(0x68); nh.zp(0x85, 0x13)   # $12/$13 = id 목록
# --- 슬롯 배정 (메시지 훅과 같은 상주표를 공유한다)
nh.imm(0xA0, 0x00)
nh.zp(0xB1, 0x12); nh.ab(0x8D, LCNT)
nh.imm(0xA2, 0x00)
nh.L("neach")
nh.ab(0xEC, LCNT); nh.rel(0xD0, "ncont")
nh.raw(0x4C, 0, 0); nh.fix16.append((len(nh.b) - 2, "nbuilt", 0))
nh.L("ncont")
nh.raw(0xC8); nh.zp(0xB1, 0x12); nh.ab(0x8D, TMP)
nh.raw(0xC8); nh.zp(0xB1, 0x12); nh.ab(0x8D, TMP2)
nh.raw(0x98, 0x48)
nh.imm(0xA0, 0x00)
nh.L("nsrch")
nh.ab(0xCC, NNEXT); nh.rel(0xF0, "nnofound")
nh.ab(0xB9, NRESL); nh.ab(0xCD, TMP); nh.rel(0xD0, "nsnext")
nh.ab(0xB9, NRESH); nh.ab(0xCD, TMP2); nh.rel(0xF0, "nfound")
nh.L("nsnext"); nh.raw(0xC8); nh.rel(0xD0, "nsrch")
nh.L("nnofound")
nh.ab(0xAD, NNEXT); nh.imm(0xC9, NNSLOT); nh.rel(0x90, "nok")
nh.imm(0xA9, 0x00); nh.ab(0x8D, NNEXT)
nh.L("nok")
nh.ab(0xAC, NNEXT)
nh.ab(0xAD, TMP); nh.ab(0x99, NRESL)
nh.ab(0xAD, TMP2); nh.ab(0x99, NRESH)
nh.raw(0x98, 0x18); nh.imm(0x69, NDLG)           # 실제 슬롯 = NDLG + 이름풀 색인
nh.raw(0x48, 0x4A, 0x4A, 0x4A, 0x4A)
nh.raw(0x18); nh.imm(0x69, SRCBASE >> 8); nh.ab_lab(0x8D, "ngdst", 2)
nh.raw(0x68, 0x0A, 0x0A, 0x0A, 0x0A); nh.ab_lab(0x8D, "ngdst", 1)
nh.imm(0xA0, 0x00)
nh.L("ngcopy")
nh.L("ngsrc"); nh.ab(0xB9, 0xA000)
nh.L("ngdst"); nh.ab(0x99, SRCBASE)
nh.raw(0xC8); nh.imm(0xC0, 0x10); nh.rel(0xD0, "ngcopy")
nh.ab(0xAC, NNEXT); nh.ab(0xEE, NNEXT)
nh.ab(0xAD, NNEXT); nh.ab(0xCD, NCNT); nh.rel(0x90, "nhw"); nh.ab(0x8D, NCNT)
nh.L("nhw")
nh.L("nfound")
nh.raw(0x98, 0x18); nh.imm(0x69, NDLG); nh.ab(0x9D, MAP)   # MAP 에는 실제 슬롯 번호를
nh.ab_lab(0xAD, "ngsrc", 1); nh.raw(0x18); nh.imm(0x69, 0x10)
nh.ab_lab(0x8D, "ngsrc", 1); nh.rel(0x90, "nnc"); nh.ab_lab(0xEE, "ngsrc", 2)
nh.L("nnc")
nh.raw(0x68, 0xA8, 0xE8)
nh.raw(0x4C, 0, 0); nh.fix16.append((len(nh.b) - 2, "neach", 0))
nh.L("nbuilt")
nh.ab(0x20, SETCNT)
# --- 텍스트를 슬롯 코드로 치환하며 NBUF 로
nh.ab(0xAD, NT1); nh.zp(0x85, 0x12)
nh.ab(0xAD, NT2); nh.zp(0x85, 0x13)
nh.imm(0xA0, 0x00)
nh.L("ntx")
nh.ab(0xCC, NLEN); nh.rel(0xF0, "ntxend")
nh.zp(0xB1, 0x12)
nh.imm(0xC9, TILE0); nh.rel(0x90, "nkeep")
nh.imm(0xC9, (TILE0 + LOCALMAX) & 0xFF); nh.rel(0xB0, "nkeep")
nh.raw(0x38); nh.imm(0xE9, TILE0); nh.raw(0xAA)
nh.ab(0xBD, MAP); nh.raw(0xAA); nh.ab(0xBD, SLOTTAB)
nh.L("nkeep")
nh.ab(0x99, NBUF)
nh.raw(0xC8); nh.rel(0xD0, "ntx")
nh.L("ntxend")
# --- 원문보다 짧으면 빈칸 타일로 덮는다 (모드2 = 문장 중 삽입이라 패딩 금지)
nh.ab(0xAD, NMODE); nh.imm(0xC9, 0x02); nh.rel(0xF0, "nemit")
nh.L("npl")
nh.ab(0xCC, NPAD); nh.rel(0xB0, "nemit")
nh.imm(0xA9, BLANK); nh.ab(0x99, NBUF)
nh.raw(0xC8); nh.rel(0xD0, "npl")
nh.L("nemit")
nh.raw(0x98); nh.ab(0x8D, NLEN)                   # NLEN = 최종 출력 길이
nh.ab(0x20, 0xC8D5)                               # 뱅크 복원 (호출자는 스왑 뱅크에 있다)
# --- 모드별 매개변수를 꺼낸다
nh.ab(0xAE, NMODE)
nh.ab(0xBD, NCAPT); nh.ab(0x8D, NCAP)
nh.ab(0xBD, NFILLT); nh.ab(0x8D, NFILL)
nh.ab(0xBD, NDSTH)
for _l in ("ndst", "ndst2", "ndst3"):
    nh.ab_lab(0x8D, _l, 2)
nh.ab(0xBD, NDSTL)
nh.imm(0xE0, 0x04); nh.rel(0xD0, "nds")           # 모드4 만 버퍼를 런타임에 고른다
nh.ab(0xAC, 0x0480); nh.rel(0xF0, "nds")          # $0480 == 0 -> $0590 (표의 기본값)
nh.imm(0xA9, 0x88)
nh.L("nds")
for _l in ("ndst", "ndst2", "ndst3"):
    nh.ab_lab(0x8D, _l, 1)
nh.ab(0xAE, NX); nh.imm(0xA0, 0x00)
nh.L("ncp")
nh.ab(0xCC, NLEN); nh.rel(0xF0, "ncpe")
nh.ab(0xAD, NCAP); nh.rel(0xF0, "nnocap")
nh.ab(0xCC, NCAP); nh.rel(0xF0, "ncpe")
nh.L("nnocap")
nh.ab(0xB9, NBUF)
nh.L("ndst"); nh.ab(0x9D, 0x0590)
nh.raw(0xE8, 0xC8); nh.rel(0xD0, "ncp")
nh.L("ncpe")
# --- 원본 관례대로 $FF 로 남은 칸 채우기 (모드1: 8칸, 모드3: 6칸)
nh.ab(0xAD, NFILL); nh.rel(0xF0, "nfd")
nh.imm(0xA9, 0xFF)
nh.L("nfl")
nh.ab(0xCC, NFILL); nh.rel(0xF0, "nfd")
nh.L("ndst2"); nh.ab(0x9D, 0x0588)
nh.raw(0xE8, 0xC8); nh.rel(0xD0, "nfl")
nh.L("nfd")
# --- 모드2 는 문장 중간 삽입이라 $FF 종결자를 쓴다 (원본과 같음)
nh.ab(0xAD, NMODE); nh.imm(0xC9, 0x02); nh.rel(0xD0, "ntn")
nh.imm(0xA9, 0xFF)
nh.L("ndst3"); nh.ab(0x9D, 0x0590)
nh.L("ntn")
# --- 종료 관례
nh.ab(0xAD, NMODE)
nh.imm(0xC9, 0x04); nh.rel(0xF0, "nex4")
nh.imm(0xC9, 0x02); nh.rel(0xF0, "nex02")
nh.imm(0xC9, 0x00); nh.rel(0xF0, "nex02")
nh.raw(0x60)                                      # 모드1/3 : 반환값 없음
nh.L("nex02")
nh.ab(0x8C, 0x0650); nh.raw(0x60)                 # 모드0/2 : $0650 = 쓴 칸수
nh.L("nex4")
nh.raw(0x8A, 0x38); nh.ab(0xED, 0x0481); nh.raw(0x60)   # 모드4 : A = 쓴 칸수
nhook = nh.build()

# ---------------------------------------------------------------- UI 이스케이프 훅
# $C13E(텍스트 버퍼 표시) 입구를 가로채 $0590 을 훑는다.
#   1차: $BD 가 있는지만 본다 -> 대사·이름은 없으므로 즉시 빠져나간다(비용 ~200사이클)
#   2차: $BD <id> 를 슬롯 타일 1바이트로 바꾸고 뒤를 왼쪽으로 당긴다(dst<=src 라 제자리 안전)
# 슬롯은 **대사 풀**에서 딴다. UI 문자열과 대사는 같은 창을 쓰므로 동시에 뜨지 않는다.
UISCAN = 64
UIID, UISX, UITILE, UISY = 0x67F0, 0x67F1, 0x67F2, 0x67F3
UITERM, UISRC = 0x67F4, 0x67F5     # 종결자 보관 / 종결자의 원본 색인
u = Asm(UIHOOK)
# ★두 패스 모두 **종결자에서 멈춘다.** 64칸을 무조건 훑으면 문자열 뒤의 게임 데이터
#   ($05AD~ 에 실제 값이 있다)까지 왼쪽으로 밀어 버린다. 실기에서 확인된 위험이다.
u.imm(0xA2, 0x00)
u.L("s0")
u.ab(0xBD, 0x0590); u.imm(0xC9, ESC); u.rel(0xF0, "found")
u.imm(0xC9, 0xFB); u.rel(0xF0, "none")
u.imm(0xC9, 0xFE); u.rel(0xF0, "none")
u.imm(0xC9, 0xFF); u.rel(0xF0, "none")
u.raw(0xE8); u.imm(0xE0, UISCAN); u.rel(0xD0, "s0")
u.L("none")
u.raw(0x4C, 0, 0); u.fix16.append((len(u.b) - 2, "exit", 0))
u.L("found")
# ★뱅크 전환을 하지 않는다. 글리프표가 PRG-RAM($6D00)에 있기 때문이다.
#   $C13E 는 뱅크 $00 $01 $03 $05 $07 $09 등 **27곳에서 JSR** 되는 지점이라,
#   여기서 $C864/$C8D5 로 PRG 뱅크를 갈아끼우는 것은 위험하다
#   (그 둘은 평범한 서브루틴이 아니라 스택에서 리턴주소를 꺼내고 옛 뱅크셋을
#    push 하는 짝 프로토콜이고, $1F 값에 따라 스크래치를 $15/$16/$17 과
#    $29/$2A/$2B 사이에서 갈아탄다).
u.imm(0xA2, 0x00); u.imm(0xA0, 0x00)
u.L("lp")
u.ab(0xBD, 0x0590); u.imm(0xC9, ESC); u.rel(0xD0, "put")
u.raw(0xE8); u.ab(0xBD, 0x0590)
u.ab_lab(0x20, "res", 0)
u.L("put")
u.ab(0x99, 0x0590)
u.imm(0xC9, 0xFB); u.rel(0xF0, "done")
u.imm(0xC9, 0xFE); u.rel(0xF0, "done")
u.imm(0xC9, 0xFF); u.rel(0xF0, "done")
u.raw(0xE8, 0xC8); u.imm(0xE0, UISCAN); u.rel(0xD0, "lp")
u.ab_lab(0x4C, "exit", 0)          # 종결자를 못 만난 채 64칸을 다 봤다 -> 패딩 없이 나간다
# ★★2026-09-07. 압축만 하고 끝내면 **꼬리가 남는다.**
#   뱅크$0D 는 뱅크$0C 의 문장을 **고정 길이로** 퍼 온다(8곳, 예: $AE18 이 $8FE5 에서 14바이트).
#   이스케이프 3개를 풀면 3바이트가 줄어 종결자가 3칸 앞으로 오고, 그 뒤에 원본 꼬리가
#   그대로 남는다. 실기에서 「뭔가 떨어져있다!」 다음에 **「다!」 두 글자만** 또 떴다(사용자 보고).
#   -> 종결자를 만나면 **줄어든 만큼 빈칸으로 메우고** 종결자를 원래 자리에 놓는다.
#      dst 가 src 를 넘지 않으므로 문자열 밖($05AD~ 게임 데이터)은 건드리지 않는다.
u.L("done")
u.ab(0x8D, UITERM)                 # 종결자 보관
u.raw(0x8A); u.ab(0x8D, UISRC)     # UISRC = X (종결자의 원본 색인)
u.L("pad")
u.ab(0xCC, UISRC); u.rel(0xF0, "padx")
u.imm(0xA9, BLANK); u.ab(0x99, 0x0590); u.raw(0xC8)
u.ab_lab(0x4C, "pad", 0)
u.L("padx")
u.ab(0xAD, UITERM); u.ab(0x99, 0x0590)
u.L("exit")
u.ab(0xAD, 0x068A); u.raw(0x60)                   # 원래 $C13E 의 첫 명령
# --- resolve: A = 음절 id -> A = 타일 코드 (X 보존)
u.L("res")
u.ab(0x8E, UISX); u.ab(0x8C, UISY)     # ★X(원본색인)와 Y(목적지색인)를 둘 다 보존해야 한다
u.ab(0x8D, UIID)
u.raw(0x18); u.imm(0x69, UIBASE & 0xFF); u.ab(0x8D, TMP)   # 전역id = UIBASE + id
u.imm(0xA9, 0x00); u.imm(0x69, UIBASE >> 8); u.ab(0x8D, TMP2)
u.imm(0xA0, 0x00)
u.L("sr")
u.ab(0xCC, NEXT); u.rel(0xF0, "nf")
u.ab(0xB9, RESIDL); u.ab(0xCD, TMP); u.rel(0xD0, "sn")
u.ab(0xB9, RESIDH); u.ab(0xCD, TMP2); u.rel(0xF0, "hit2")
u.L("sn"); u.raw(0xC8); u.rel(0xD0, "sr")
u.L("nf")
u.ab(0xAD, NEXT); u.imm(0xC9, NDLG); u.rel(0x90, "ok")
u.imm(0xA9, 0x00); u.ab(0x8D, NEXT)
u.L("ok")
u.ab(0xAC, NEXT)
u.ab(0xAD, TMP); u.ab(0x99, RESIDL)
u.ab(0xAD, TMP2); u.ab(0x99, RESIDH)
u.raw(0x98, 0x4A, 0x4A, 0x4A, 0x4A)
u.raw(0x18); u.imm(0x69, SRCBASE >> 8); u.ab_lab(0x8D, "gd", 2)
u.raw(0x98, 0x0A, 0x0A, 0x0A, 0x0A); u.ab_lab(0x8D, "gd", 1)
u.ab(0xAD, UIID); u.imm(0x29, 0x0F)
u.raw(0x0A, 0x0A, 0x0A, 0x0A); u.ab_lab(0x8D, "gs", 1)
u.ab(0xAD, UIID); u.raw(0x4A, 0x4A, 0x4A, 0x4A)
u.raw(0x18); u.imm(0x69, UIGLY >> 8); u.ab_lab(0x8D, "gs", 2)
u.raw(0x98, 0x48)
u.imm(0xA0, 0x00)
u.L("gc")
u.L("gs"); u.ab(0xB9, UIGLY)
u.L("gd"); u.ab(0x99, SRCBASE)
u.raw(0xC8); u.imm(0xC0, 0x10); u.rel(0xD0, "gc")
u.raw(0x68, 0xA8)
u.ab(0xEE, NEXT)
u.ab(0x20, SETCNT)
u.L("hit2")
u.raw(0x98, 0xAA); u.ab(0xBD, SLOTTAB); u.ab(0x8D, UITILE)
u.ab(0xAE, UISX); u.ab(0xAC, UISY); u.ab(0xAD, UITILE); u.raw(0x60)
uihook = u.build()
assert UIHOOK + len(uihook) <= UIID, "UI 훅 %d바이트가 변수 영역을 침범" % len(uihook)

# ---------------------------------------------------------------- 블록 업로드 이스케이프 훅
# ★2026-09-07. $C13E 훅은 **대사 버퍼 $0590** 만 훑는다. 그런데 사교의 관(합체)·악마
#   상세 화면은 $C13E 를 안 거치고 **블록 업로더**로 그린다:
#     $0580 열 / $0581 행 / $0582 폭 / $0583 높이 / $0584 세로쓰기 / $0587 네임테이블
#     $0588~ 이 타일 데이터  ->  $C3DF(즉시) 또는 $0B bit0 + NMI
#   그래서 CLASS 칸(종족 20개)과 「합체한 동료」 줄이 `✕5` `✕せ` 처럼 **날 이스케이프**로
#   떴다(사용자 보고 2026-09-07).
#
# ★★업로더를 통째로 훅하면 안 된다. $BD 는 원본에서 ✕ 기호라 **패스워드 화면이 진짜로**
#   쓴다(뱅크$00 $B38F/$B769 가 `LDA #$BD / STA $0588,X` 로 줄줄이 채운다).
#   실측(세이브스테이트 전수 + 조작 추적)으로 $BD 를 싣는 블록은 셋뿐이었다:
#     - 패스워드 ✕      : $C5AE 호출부 $A9D4, **W=1** (한 칸)
#     - 악마 초상화      : PC $A996, **세로쓰기(o=1) H=12**
#     - 우리 번역문      : W>=2, H=1, o=0
#   -> **개별 호출부만** 갈아끼운다. 아래 5곳은 전부 글자 줄이다.
#
# ★폭을 보존한다. 이스케이프는 2바이트 -> 1칸이라 그냥 당기면 표의 **다음 열이 밀린다**
#   (COMP 줄은 `# CLASS NAME 마법` 이 한 블록 26칸이다). 그래서 `$FF` 로 끊긴
#   **필드 안에서만** 당기고, 필드 끝에서 밀린 만큼 빈칸으로 갚는다.
BLKFIX = 0x6500                  # $6400~$64B2 는 이름 상주표, 그 뒤는 비어 있다
BF_W, BF_DEF = 0x65F0, 0x65F1    # 이 블록의 폭 / 이 필드에서 밀린 칸수
BF_END = 0x65F2                  # 꼬리 해석기가 볼 끝 색인
blkfix = b""
if UI_HOOK and UI_PATCH:
    NUI = len(uisyl)
    RES = u.lab["res"]                       # UI 훅의 「id -> 타일」 서브루틴 재사용
    f = Asm(BLKFIX)
    f.L("e1"); f.ab_lab(0x20, "fix", 0); f.ab(0x4C, 0xC3DF)   # 즉시 그리는 계열
    f.L("e2"); f.ab_lab(0x20, "fix", 0); f.ab(0x4C, 0xC5AE)   # NMI 예약 계열
    f.L("e3"); f.ab_lab(0x20, "fix", 0); f.ab(0x4C, 0xC603)   # 그리고 NMI 를 기다리는 계열
    f.L("fix")
    f.ab(0xAD, 0x0583); f.imm(0xC9, 0x01); f.rel(0xD0, "no")  # 한 줄짜리만
    f.ab(0xAD, 0x0584); f.rel(0xD0, "no")                     # 세로쓰기는 그래픽
    f.ab(0xAD, 0x0582); f.imm(0xC9, 0x02); f.rel(0x90, "no")  # 1칸이면 이스케이프 불가
    f.ab(0x8D, BF_W)
    f.imm(0xA2, 0x00)                        # 1차: $BD 가 하나도 없으면 즉시 귀환
    f.L("q")
    f.ab(0xBD, 0x0588); f.imm(0xC9, ESC); f.rel(0xF0, "go")
    f.raw(0xE8); f.ab(0xEC, BF_W); f.rel(0xD0, "q")
    f.L("no"); f.raw(0x60)
    f.L("go")                                # 2차: X=원본색인 Y=목적색인 (dst<=src 라 제자리 안전)
    f.imm(0xA2, 0x00); f.imm(0xA0, 0x00); f.imm(0xA9, 0x00); f.ab(0x8D, BF_DEF)
    f.L("lp")
    f.ab(0xEC, BF_W); f.rel(0xB0, "tail")
    f.ab(0xBD, 0x0588); f.raw(0xE8)
    f.imm(0xC9, ESC); f.rel(0xF0, "esc")
    f.imm(0xC9, 0xFF); f.rel(0xF0, "fend")
    f.L("put")
    f.ab(0x99, 0x0588); f.raw(0xC8); f.ab_lab(0x4C, "lp", 0)
    f.L("esc")
    f.ab(0xEC, BF_W); f.rel(0xB0, "escraw")  # $BD 가 마지막 바이트면 진짜 ✕ 다
    f.ab(0xBD, 0x0588)
    f.imm(0xC9, NUI); f.rel(0xB0, "escraw")  # id 가 범위 밖이면 진짜 ✕ 다
    f.raw(0xE8)
    f.ab(0x20, RES)
    f.ab(0xEE, BF_DEF)
    f.ab_lab(0x4C, "put", 0)
    f.L("escraw")
    f.imm(0xA9, ESC); f.ab_lab(0x4C, "put", 0)
    f.L("fend")                              # 필드 경계: 밀린 만큼 빈칸으로 갚고 $FF 를 넣는다
    f.ab(0xAD, BF_DEF); f.rel(0xF0, "ffonly")
    f.L("pad")
    f.imm(0xA9, BLANK); f.ab(0x99, 0x0588); f.raw(0xC8)
    f.ab(0xCE, BF_DEF); f.rel(0xD0, "pad")
    f.L("ffonly")
    f.imm(0xA9, 0xFF); f.ab_lab(0x4C, "put", 0)
    f.L("tail")                              # 줄 끝에서도 남은 만큼 갚는다
    f.ab(0xAD, BF_DEF); f.rel(0xF0, "fin")
    f.L("tpad")
    f.imm(0xA9, BLANK); f.ab(0x99, 0x0588); f.raw(0xC8)
    f.ab(0xCE, BF_DEF); f.rel(0xD0, "tpad")
    f.L("fin"); f.raw(0x60)
    # --- 꼬리 해석기: 대사 버퍼 $0590 에 **방금 덧붙인 구간만** 푼다.
    # 뱅크$0B $B1F8(마법 목록)은 이름을 $0590+$0650 에 이어 붙이고 $B216 에서 $0650 을 갱신한다.
    # 그 뒤 $C13E 를 부르지만 훅의 1차 훑기가 **앞선 종결자에서 멈춰** 여기까지 못 온다.
    # -> $B216 자리를 이 루틴으로 바꾼다. 원래 하던 `STX $0650` 도 여기서 대신 한다(줄어든 끝으로).
    f.L("tail0")
    f.ab(0x8E, BF_END); f.ab(0xAE, 0x0650); f.ab(0xAC, 0x0650)
    f.L("tl")
    f.ab(0xEC, BF_END); f.rel(0xB0, "tdone")
    f.ab(0xBD, 0x0590); f.raw(0xE8)
    f.imm(0xC9, ESC); f.rel(0xD0, "tput")
    f.ab(0xEC, BF_END); f.rel(0xB0, "traw")
    f.ab(0xBD, 0x0590)
    f.imm(0xC9, NUI); f.rel(0xB0, "traw")
    f.raw(0xE8)
    f.ab(0x20, RES)
    f.ab_lab(0x4C, "tput", 0)
    f.L("traw")
    f.imm(0xA9, ESC)
    f.L("tput")
    f.ab(0x99, 0x0590); f.raw(0xC8); f.ab_lab(0x4C, "tl", 0)
    f.L("tdone")
    f.ab(0x8C, 0x0650); f.raw(0x60)
    blkfix = f.build()
    assert BLKFIX + len(blkfix) <= BF_W, "블록훅 %d바이트가 변수 영역을 침범" % len(blkfix)

    # ------------------------------------------------------------ 함정·워프 메시지 창 훅 (2026-09-15)
    # 고정뱅크 $D499 가 표 $D44A 의 14바이트 레코드를 **높이 4 블록**(테두리/줄1/줄2/테두리, 폭 8)으로
    # $0588 에 깔고 `LDA #1 / ORA $0B / STA $0B / JSR $C603` 으로 NMI 업로드를 기다린다.
    # 위의 fix 는 높이 1 만 풀기 때문에 여기서는 이스케이프가 날것으로 떴다
    # (사용자 보고 「텔레포트 탈 때 번역 안 됨」, 강제 호출 화면 「※6렸다!」).
    # -> 행마다 [행 시작, 행 끝-1) 안에서만 당기고 줄어든 만큼 빈칸으로 갚는다. **행 끝 바이트(오른쪽 테두리)는 그대로.**
    # ★업로드 요청($0B bit0) **전에** 풀어야 한다. 요청 뒤에 풀면 그 사이 NMI 가 날 바이트를 올릴 수 있다.
    #   그래서 요청+대기 9바이트를 통째로 이 훅 호출로 바꾸고, 요청은 훅 안에서 한다.
    TRAPFIX = 0x6710                 # UI 훅($6600, 262바이트) 뒤 ~ UI 변수($67F0) 앞의 빈자리
    TF_H, TF_ROW = 0x65F3, 0x65F4    # 남은 행 수 / 이번 행 시작 색인 (BF_* 바로 뒤)
    r = Asm(TRAPFIX)
    r.ab_lab(0x20, "rows", 0)
    r.imm(0xA9, 0x01); r.zp(0x05, 0x0B); r.zp(0x85, 0x0B)      # 원래 하던 업로드 요청
    r.ab(0x4C, 0xC603)
    r.L("rows")
    r.ab(0xAD, 0x0584); r.rel(0xD0, "rx")                      # 세로쓰기는 그림
    r.ab(0xAD, 0x0582); r.imm(0xC9, 0x03); r.rel(0x90, "rx")   # 테두리 빼고 2칸도 안 되면 풀 게 없다
    r.ab(0xAD, 0x0583); r.rel(0xF0, "rx"); r.ab(0x8D, TF_H)
    r.imm(0xA9, 0x00); r.ab(0x8D, TF_ROW)
    r.L("row")
    r.ab(0xAD, TF_ROW); r.raw(0x18); r.ab(0x6D, 0x0582); r.ab(0x8D, BF_W)   # BF_W = 다음 행 시작
    r.raw(0x38); r.imm(0xE9, 0x01); r.ab(0x8D, BF_END)                     # BF_END = 행 끝 바이트(테두리)
    r.imm(0xA9, 0x00); r.ab(0x8D, BF_DEF)
    r.ab(0xAE, TF_ROW); r.ab(0xAC, TF_ROW)                     # X=원본색인 Y=목적색인 (dst<=src)
    r.L("lp")
    r.ab(0xEC, BF_END); r.rel(0xB0, "pad")
    r.ab(0xBD, 0x0588); r.raw(0xE8)
    r.imm(0xC9, ESC); r.rel(0xD0, "put")
    r.ab(0xEC, BF_END); r.rel(0xB0, "raw")                     # $BD 가 행 마지막 칸이면 진짜 ✕
    r.ab(0xBD, 0x0588); r.imm(0xC9, NUI); r.rel(0xB0, "raw")   # id 가 범위 밖이면 진짜 ✕
    r.raw(0xE8); r.ab(0x20, RES); r.ab(0xEE, BF_DEF)
    r.ab_lab(0x4C, "put", 0)
    r.L("raw"); r.imm(0xA9, ESC)
    r.L("put"); r.ab(0x99, 0x0588); r.raw(0xC8); r.ab_lab(0x4C, "lp", 0)
    r.L("pad")
    r.ab(0xAD, BF_DEF); r.rel(0xF0, "next")
    r.imm(0xA9, BLANK); r.ab(0x99, 0x0588); r.raw(0xC8)
    r.ab(0xCE, BF_DEF); r.ab_lab(0x4C, "pad", 0)
    r.L("next")
    r.ab(0xAD, BF_W); r.ab(0x8D, TF_ROW)
    r.ab(0xCE, TF_H); r.rel(0xD0, "row")
    r.L("rx"); r.raw(0x60)
    trapfix = r.build()
    assert UIHOOK + len(uihook) <= TRAPFIX and TRAPFIX + len(trapfix) <= UIID, \
        "함정 창 훅 %d바이트가 $%04X~$%04X 를 벗어난다" % (len(trapfix), TRAPFIX, UIID)

sc = Asm(SETCNT)
sc.ab(0xAD, NCNT); sc.raw(0x18); sc.imm(0x69, NDLG); sc.ab(0x8D, TMP)
sc.ab(0xAD, NEXT); sc.ab(0xCD, TMP); sc.rel(0xB0, "sok"); sc.ab(0xAD, TMP)
sc.L("sok")
sc.ab(0x8D, CNT)
sc.imm(0xA9, 0x00); sc.ab(0x8D, SLOT); sc.ab(0x8D, CHK)
sc.raw(0x60)
setcnt = sc.build()
assert NHOOK + len(nhook) <= SETCNT, "이름 훅 %d바이트가 SETCNT($%04X)를 침범" % (len(nhook), SETCNT)
assert SETCNT + len(setcnt) <= NBUF, "SETCNT 가 NBUF 를 침범"   # 이름 상주표는 $6400 으로 옮겼다
assert NBUF + 16 <= NMODE, "NBUF 가 변수 영역을 침범"
assert NRESL + NNSLOT <= NRESH and NRESH + NNSLOT <= NBUF, "이름 상주표가 겹침"
assert NDLG + NNSLOT == NSLOT
assert NNSLOT >= 20, "이름 슬롯 %d칸: 악마8+종족8 실측 17칸에 여유가 없다" % NNSLOT

# ---------------------------------------------------------------- PRG-RAM 이미지 + 부팅 복사기
img = bytearray(COPY)
img[:len(up)] = up
assert len(up) <= SLOTTAB - 0x6000, "업로더가 변환표를 침범"
img[SLOTTAB - 0x6000:SLOTTAB - 0x6000 + NSLOT] = bytes(TILES)
img[TBL7 - 0x6000:TBL7 - 0x6000 + NBSET] = rom[fx(0xC95A):fx(0xC95A) + NBSET]
assert TBL7 + NBSET <= SLOTTAB and SLOTTAB + NSLOT <= SLOT, "뱅크셋표/변환표/변수 영역이 겹침" 
img[SLOT - 0x6000] = 0; img[CHK - 0x6000] = 0; img[CNT - 0x6000] = 0
img[HOOK - 0x6000:HOOK - 0x6000 + len(hook)] = hook
img[NHOOK - 0x6000:NHOOK - 0x6000 + len(nhook)] = nhook
img[SETCNT - 0x6000:SETCNT - 0x6000 + len(setcnt)] = setcnt
if UI_HOOK and UI_PATCH:
    img[UIHOOK - 0x6000:UIHOOK - 0x6000 + len(uihook)] = uihook
    img[BLKFIX - 0x6000:BLKFIX - 0x6000 + len(blkfix)] = blkfix
    assert not any(img[TRAPFIX - 0x6000:TRAPFIX - 0x6000 + len(trapfix)]), "함정 창 훅 자리에 이미 뭔가 있다"
    img[TRAPFIX - 0x6000:TRAPFIX - 0x6000 + len(trapfix)] = trapfix
    for _i, _g in enumerate(uiglyph):       # UI 글리프표도 PRG-RAM 으로 (뱅크 전환 제거용)
        img[UIGLY - 0x6000 + 16 * _i:UIGLY - 0x6000 + 16 * _i + 16] = _g
for _base, _vals in ((NDSTL, MODE_DSTL), (NDSTH, MODE_DSTH), (NCAPT, MODE_CAP),
                     (NFILLT, MODE_FILL), (NBASEH, MODE_BASEH)):
    img[_base - 0x6000:_base - 0x6000 + 5] = bytes(_vals)
rom[bk(0x0F, 0):bk(0x0F, 0) + COPY] = bytes(img)

tail = bytes([0xA9, 0x10, 0x4C, 0x00, 0xC0])
base = bk(0x0E, 0)
pos = rom.find(tail, base, base + 0x200)
assert pos > 0
a = Asm(0x8000 + (pos - base))
a.imm(0xA9, 0x80); a.ab(0x8D, 0xA001)
a.imm(0xA9, 0x07); a.ab(0x8D, 0x8000)
a.imm(0xA9, 0x0F); a.ab(0x8D, 0x8001)
a.imm(0xA0, 0x00)
for p in range(COPY // 0x100):
    a.L("cp%d" % p)
    a.ab(0xB9, 0xA000 + p * 0x100); a.ab(0x99, 0x6000 + p * 0x100)
    a.raw(0xC8); a.rel(0xD0, "cp%d" % p)
boot = a.build()
assert rom[pos + len(tail):pos + len(tail) + len(boot)] == bytes([0xFF] * len(boot))
rom[pos:pos + len(boot)] = boot
rom[pos + len(boot):pos + len(boot) + len(tail)] = tail

# ---------------------------------------------------------------- 분할 뱅크전환 순서 (5c)
# 스프라이트0 분할에서 $C689 가 R2->R3->R4->R5 순서로 CHR 뱅크를 바꾼다.
# R5 는 맨 마지막이라 R2 보다 **약 38사이클(=0.33 스캔라인) 늦게** 적용된다.
# 타일 $C0~$FF 가 바로 R5 소관이라, 메시지 창 첫 글자줄의 **맨 윗 스캔라인**이
# 아직 상단 타일셋(CHR-ROM)으로 그려진다 -> 한글 위에 던전 벽 조각이 얹힌다.
# (실기: '누' 위에 가로막대가 얹혀 '두' 처럼 보이고, 분할이 흔들려 깜빡인다)
# 원본은 텍스트가 R4 범위($80~$BF)라 더 일찍 바뀌어 티가 안 났다.
#
# 고치는 법: **R4/R5 를 먼저 쓴다.** 뱅크 값은 그대로고 순서만 바꾼다.
# 바이트가 모자라는데, `SEC / SBC #$01`(3바이트)은 표를 2 당겨 `$C724,Y` 로 읽으면
# 없앨 수 있다 (Y=n*2 로 두면 $C724+n*2 == $C726+(n-1)*2). 그렇게 3바이트를 벌었다.
# 순서 선택: True = R4/R5 먼저(한글 깨끗, 일본어 $40~$7F 가 깨짐)
#            False = 원본 순서(일본어 깨끗, 한글 $C0~$CF 가 깨짐)
# 어느 쪽이든 **마지막에 쓰이는 레지스터 하나는 늦는다.** 근본 해법은 아래 "남은 일" 참조.
SPLIT_TEXT_FIRST = True

OLD_COMMON = bytes([
    0x38, 0xE9, 0x01, 0x0A, 0xA8,
    0xA2, 0x02, 0x8E, 0x00, 0x80, 0xB9, 0x26, 0xC7, 0x8D, 0x01, 0x80,
    0xE8, 0x8E, 0x00, 0x80, 0x09, 0x01, 0x8D, 0x01, 0x80,
    0xE8, 0x8E, 0x00, 0x80, 0xB9, 0x27, 0xC7, 0x8D, 0x01, 0x80,
    0xE8, 0x8E, 0x00, 0x80, 0x09, 0x01, 0x8D, 0x01, 0x80, 0x60])
# ★★$C6B5 는 반드시 RTS 로 남겨야 한다. $C668 과 $C66E 의 `BEQ $C6B5` 가 여기로 온다.
#   (남는 바이트를 끝에 패딩했다가 BEQ 가 리셋 스텁 $C6B6 으로 굴러떨어져 부팅이 깨졌다.
#    JSR/JMP 만 스캔하고 **상대분기를 안 봐서** 놓쳤다.)
#   그래서 패딩은 RTS **앞**에 둔다. 덤으로 총 사이클이 원본과 정확히 같아진다(62+4=66).
BODY = bytes([
    0x0A, 0xA8,                                          # ASL / TAY   (Y = n*2)
    0xA2, 0x04, 0x8E, 0x00, 0x80, 0xB9, 0x25, 0xC7, 0x8D, 0x01, 0x80,   # R4 = b
    0xE8, 0x8E, 0x00, 0x80, 0x09, 0x01, 0x8D, 0x01, 0x80,               # R5 = b|1
    0xA2, 0x02, 0x8E, 0x00, 0x80, 0xB9, 0x24, 0xC7, 0x8D, 0x01, 0x80,   # R2 = a
    0xE8, 0x8E, 0x00, 0x80, 0x09, 0x01, 0x8D, 0x01, 0x80])              # R3 = a|1
pad = len(OLD_COMMON) - 1 - len(BODY)
assert pad >= 0, "새 루틴이 원본보다 길다"
NEW_COMMON = BODY + bytes([0xEA] * pad) + bytes([0x60])   # NOP 패딩 + RTS
assert len(NEW_COMMON) == len(OLD_COMMON)
assert NEW_COMMON[-1] == 0x60, "$C6B5 가 RTS 여야 한다 ($C668/$C66E 의 BEQ 대상)"
assert bytes(rom[fx(0xC689):fx(0xC689) + len(OLD_COMMON)]) == OLD_COMMON,     "분할 뱅크전환 루틴이 예상과 다름"
if SPLIT_TEXT_FIRST:
    rom[fx(0xC689):fx(0xC689) + len(OLD_COMMON)] = NEW_COMMON

# ---------------------------------------------------------------- 패치 2곳
# NMI 출구가 R7 을 복원할 때 **PRG-RAM 사본**을 보게 한다 ($C12A: LDA $C95A,X)
assert bytes(rom[fx(0xC12A):fx(0xC12A) + 3]) == bytes([0xBD, 0x5A, 0xC9]),     "NMI 출구의 R7 복원 지점이 예상과 다름: %s" % rom[fx(0xC12A):fx(0xC12A) + 3].hex()
rom[fx(0xC12B):fx(0xC12B) + 2] = bytes([TBL7 & 0xFF, TBL7 >> 8])

assert bytes(rom[fx(0xC0BF):fx(0xC0BF) + 3]) == bytes([0x20, 0xDF, 0xC3])
rom[fx(0xC0BF):fx(0xC0BF) + 3] = bytes([0x20, 0x00, 0x60])        # NMI -> JSR $6000
AF1E = B5 + (0xAF1E - 0xA000)
assert bytes(rom[AF1E:AF1E + 5]) == bytes([0xA9, 0x00, 0x8D, 0x58, 0x06]), \
    "메시지 시작 지점이 예상과 다름: %s" % rom[AF1E:AF1E + 5].hex()
rom[AF1E:AF1E + 5] = bytes([0x20, HOOK & 0xFF, HOOK >> 8, 0xEA, 0xEA])   # JSR $6100 / NOP NOP

# ---------------------------------------------------------------- 정적 폰트를 CHR-ROM 에 굽는다
# 대화 타일셋은 CHR 뱅크 4($00~$3F) / 5($40~$7F). 뱅크 6,7 은 CHR-RAM 이라 손대지 않는다.
if STATIC_FONT:
    _chr = HDR + rom[4] * 16384
    assert len(rom) - _chr >= 0x20000, "CHR 블록이 없다"
    for _ch, _c in STATIC.items():
        _b = 4 if _c < 0x40 else 5
        _o = _chr + _b * 1024 + (_c & 0x3F) * 16
        rom[_o:_o + 16] = bytes(G.to_chr(G.bitmap(_ch)))
    # ★빈칸 타일을 실제로 비운다. 안 비우면 원래 있던 반탁점 「゜」이 남아
    #   이름 뒤 패딩이 전부 작은 동그라미로 보인다 (실기에서 발각, 2026-09-02).
    _bo = _chr + (4 if BLANK < 0x40 else 5) * 1024 + (BLANK & 0x3F) * 16
    rom[_bo:_bo + 16] = bytes(16)
    print("정적 폰트 %d칸을 CHR 뱅크4/5 에 구웠다" % len(STATIC))

# ---------------------------------------------------------------- 이름 루틴 3곳 갈아끼우기
# 각 지점에서 A = 이름 색인. 구간 안으로 들어오는 외부 분기가 없음을 확인했다.
_bkcpu = lambda bank, cpu, base: HDR + bank * 0x2000 + (cpu - base)
NPATCH = (
    (13, 0xB94B, 0xA000, bytes([0x0A, 0xAA, 0xBD, 0x1A, 0x88]), 37, 0,
     bytes([0xAE, 0x50, 0x06])),                              # LDX $0650
    (13, 0xB984, 0xA000, bytes([0x0A, 0xA8, 0xB9, 0x1A, 0x88]), 39, 1, b""),
    (13, 0xB9AB, 0xA000, bytes([0x29, 0x7F, 0x0A, 0xAA, 0xBD]), 38, 2,
     bytes([0x29, 0x7F, 0x18, 0x69, 0x20, 0xAE, 0x50, 0x06])),  # AND/+32/LDX $0650
    (11, 0xBE68, 0xA000, bytes([0x29, 0x7F, 0x0A, 0xAA, 0xBD]), 43, 3,
     bytes([0x29, 0x7F, 0xA2, 0x00])),                        # 마법: AND #$7F / LDX #0
    (1, 0xBFC5, 0xA000, bytes([0x0A, 0xA8, 0xB9, 0x3F, 0xBF]), 48, 4, b""),   # 아이템
)
for _bank, _cpu, _base, _want, _room, _mode, _pre in NPATCH:
    _o = _bkcpu(_bank, _cpu, _base)
    assert bytes(rom[_o:_o + 5]) == _want, ("이름 루틴 $%04X(뱅크$%02X) 가 예상과 다름: %s"
                                            % (_cpu, _bank, rom[_o:_o + 5].hex()))
    _code = _pre + bytes([0xA0, _mode, 0x8C, NMODE & 0xFF, NMODE >> 8,
                          0x20, NHOOK & 0xFF, NHOOK >> 8, 0x60])
    assert len(_code) <= _room, "$%04X 패치 %d바이트 > %d" % (_cpu, len(_code), _room)
    rom[_o:_o + len(_code)] = _code
print("이름 루틴 5곳 패치 -> JSR $%04X  (A:$B94B/$B984/$B9AB  C:$BE68  B:$BFC5)" % NHOOK)

# ---------------------------------------------------------------- $C13E 훅
assert bytes(rom[fx(0xC13E):fx(0xC13E) + 3]) == bytes([0xAD, 0x8A, 0x06]),     "텍스트 표시 진입점이 예상과 다름: %s" % rom[fx(0xC13E):fx(0xC13E) + 3].hex()
if UI_HOOK and UI_PATCH:
    rom[fx(0xC13E):fx(0xC13E) + 3] = bytes([0x20, UIHOOK & 0xFF, UIHOOK >> 8])
    print("UI 훅 %d바이트, $C13E -> JSR $%04X" % (len(uihook), UIHOOK))
elif UI_HOOK:
    print("★진단: UI 문자열만 넣고 $C13E 훅은 설치하지 않음")
else:
    print("UI 훅 꺼짐 ($C13E 원본 유지)")

# ---------------------------------------------------------------- 블록 그리기 호출부 5곳
# 전부 **글자 한 줄**을 그리는 자리다 (런타임 추적으로 확정, 2026-09-07).
#   $BCA3 = 뱅크$01 $BC7F 공용 필드 그리기 (높이 1 고정) - 악마 상세 CLASS/마법 칸
#   $A188 = 「합체한 동료 …」 줄        $A233 = 합체 화면 문장
#   $A474 = COMP 머리글 (CLASS NAME 1234567)   $A4FF = COMP 악마 한 줄
#   $AE93 $AF64 = 뱅크$0B 마법 목록 두 열 (둘 다 높이 1 고정)
#   $A9AA = 뱅크$0B 마법 이름 7칸 블록 ($C603 으로 NMI 를 기다린다)
#   $B216 = 뱅크$0B 마법 목록이 대사 버퍼에 이름을 덧붙인 **직후** (꼬리 해석기)
#   $B0BB = 뱅크$05 문자열 복사기의 끝 ($B0AA LDX $0650 ~ $B0BB STX $0650).
#           뱅크$0B $B216 과 **완전히 같은 모양**이라 꼬리 해석기를 그대로 쓴다.
#           텔레포트 목적지 메뉴가 이 경로로 그려진다.
#   $B5A3 = 뱅크$03 레벨업 화면 공용 줄 그리기 ($B10F/$B187/$B1C3 셋이 여기로 온다)
#           - 「레벨」「경험치」「다음 레벨까지」가 이스케이프로 떠 있었다(사용자 보고)
# 패스워드 ✕($A9D4, 한 칸)과 초상화(세로쓰기)는 **일부러 건드리지 않는다**.
# ★뱅크$05 $B89E 도 `JSR $C3DF` 자리지만 **안 건드린다.** 거기는 $0290 의 압축 데이터를
#   푸는 범용 해제기라 글자인지 그림인지 알 수 없다. 전투 주문 목록이 그 경로면
#   따로 확인하고 넣을 것.
BLK_SITES = ((1, 0xBCA3, bytes([0x20, 0xDF, 0xC3]), "e1"),
             (11, 0xAE93, bytes([0x20, 0xDF, 0xC3]), "e1"),
             (11, 0xAF64, bytes([0x20, 0xDF, 0xC3]), "e1"),
             (11, 0xA9AA, bytes([0x20, 0x03, 0xC6]), "e3"),
             (11, 0xB216, bytes([0x8E, 0x50, 0x06]), "tail0"),
             (3, 0xB5A3, bytes([0x20, 0xDF, 0xC3]), "e1"),
             (5, 0xB0BB, bytes([0x8E, 0x50, 0x06]), "tail0"),
             (0, 0xA188, bytes([0x20, 0xAE, 0xC5]), "e2"),
             (0, 0xA233, bytes([0x20, 0xAE, 0xC5]), "e2"),
             (0, 0xA474, bytes([0x20, 0xAE, 0xC5]), "e2"),
             (0, 0xA4FF, bytes([0x20, 0xAE, 0xC5]), "e2"))
if UI_HOOK and UI_PATCH:
    for _b, _cpu, _exp, _ent in BLK_SITES:
        _o = HDR + _b * 0x2000 + (_cpu - 0xA000)
        assert bytes(rom[_o:_o + 3]) == _exp,             "$%04X(뱅크$%02X)가 예상과 다름: %s" % (_cpu, _b, rom[_o:_o + 3].hex())
        _t = f.lab[_ent]
        rom[_o:_o + 3] = bytes([0x20, _t & 0xFF, _t >> 8])
    print("블록 그리기 %d곳 -> JSR $%04X (이스케이프 해석 %d바이트)"
          % (len(BLK_SITES), BLKFIX, len(blkfix)))
    # 함정·워프 메시지 창: 업로드 요청 + 대기 9바이트 -> JSR TRAPFIX + NOP 6 (위 「함정·워프 메시지 창 훅」)
    _tp = fx(0xD4F9)
    assert bytes(rom[_tp:_tp + 9]) == bytes([0xA9, 0x01, 0x05, 0x0B, 0x85, 0x0B, 0x20, 0x03, 0xC6]), \
        "함정 창 업로드 요청 자리가 예상과 다름: %s" % rom[_tp:_tp + 9].hex()
    rom[_tp:_tp + 9] = bytes([0x20, TRAPFIX & 0xFF, TRAPFIX >> 8, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA])
    print("함정·워프 메시지 창 $D4F9 -> JSR $%04X (줄별 이스케이프 해석 %d바이트)" % (TRAPFIX, len(trapfix)))

# ---------------------------------------------------------------- 매퍼195 (CHR-RAM 4KB)
# ★왜: 슬롯이 구조적으로 모자란다. 매퍼191 에서 그릴 수 있는 코드 $00~$CF 208칸은
#   정적 페이지($00~$7F, CHR-ROM 128칸) + RAM 페이지($80~$FF 중 $80~$CF 80칸)로 꽉 차 있고,
#   RAM 쪽 80칸은 라틴26 + $BD + $C0 + 슬롯52 로 한 칸도 안 남는다.
#   실측(적대적 조합): 이름 화면이 최대 50칸을 요구하는데 이름 풀은 28칸이다.
#   정적 폰트를 어떻게 다시 골라도 이름 최악은 40칸 밑으로 안 내려간다(측정 완료).
#   -> **용량을 늘리는 수밖에 없다.** 195 는 1KB CHR 뱅크 $00~$03 자체가 CHR-RAM 4KB 라
#      코드 $00~$FF 가 전부 RAM 이 된다. 정적 폰트 칸을 슬롯으로 풀 수 있다.
# ★대가: 매퍼가 바뀌어 실기 카트리지로는 못 굽는다. 에뮬 전용 (사용자 승인 2026-09-03).
if M195:
    _chr0 = HDR + rom[4] * 16384
    assert rom[5] == 0x10 and len(rom) - _chr0 == 128 * 1024, "CHR 128KB 가 아니다"
    assert ((rom[6] >> 4) | (rom[7] & 0xF0)) == 191, "매퍼191 롬이어야 한다"
    _old = bytes(rom[_chr0:])
    TBL_BG, NTS, TS25 = 0xC726, 36, 24
    _bg = [(rom[fx(TBL_BG) + i * 2], rom[fx(TBL_BG) + i * 2 + 1]) for i in range(NTS)]
    assert _bg[TS25] == (0x04, 0x80), "타일셋25 가 예상과 다르다: %s" % (_bg[TS25],)
    # 뱅크 $00~$03 을 비운다 ($80~$83 으로 이설). 스프라이트표는 원래 안 쓴다.
    _new = bytearray(_old) + bytearray(128 * 1024)
    for _s, _d in ((0x00, 0x80), (0x02, 0x82)):
        for _k in (0, 1):
            _new[(_d + _k) * 1024:(_d + _k) * 1024 + 1024] = _old[(_s + _k) * 1024:(_s + _k) * 1024 + 1024]
    for _i, (_a, _b) in enumerate(_bg):
        if _a in (0x00, 0x02): rom[fx(TBL_BG) + _i * 2] = _a + 0x80
    # 타일셋25: R2,R3 = RAM 2,3 (코드 $00~$7F) / R4,R5 = RAM 0,1 (코드 $80~$FF)
    rom[fx(TBL_BG) + TS25 * 2] = 0x02
    rom[fx(TBL_BG) + TS25 * 2 + 1] = 0x00
    # 기존 부팅 복사가 R4/R5 에 $80/$81 을 쓴다 - 191 에선 CHR-RAM 선택이지만
    # 195 에선 진짜 ROM 뱅크라 복사가 통째로 무시된다.
    _b0e = bk(0x0E, 0)
    assert rom[_b0e + 0x1E] == 0x80 and rom[_b0e + 0x28] == 0x81, "부팅 R4/R5 값이 예상과 다르다"
    rom[_b0e + 0x1E], rom[_b0e + 0x28] = 0x00, 0x01
    # 정적 페이지(옛 CHR 뱅크4,5)를 PRG 사본으로 두고 부팅 때 PPU $1000 에 올린다
    assert all(c == 0xFF for c in rom[_b0e + 0x1800:_b0e + 0x2000]), "뱅크$0E 뒤 2KB 가 비어 있지 않다"
    assert all(c == 0xFF for c in rom[_b0e + 0x0200:_b0e + 0x0240]), "$8200 자리가 비어 있지 않다"
    rom[_b0e + 0x1800:_b0e + 0x2000] = _old[4 * 1024:6 * 1024]
    _u = Asm(0x8200)
    for _r, _pg in ((0x02, 0x02), (0x03, 0x03)):                 # R2,R3 = RAM 2,3
        _u.imm(0xA9, _r); _u.ab(0x8D, 0x8000); _u.imm(0xA9, _pg); _u.ab(0x8D, 0x8001)
    _u.imm(0xA9, 0x10); _u.ab(0x8D, 0x2006); _u.imm(0xA9, 0x00); _u.ab(0x8D, 0x2006)
    _u.imm(0xA9, 0x00); _u.zp(0x85, 0x00); _u.imm(0xA9, 0x98); _u.zp(0x85, 0x01)
    _u.imm(0xA2, 0x08); _u.imm(0xA0, 0x00)
    _u.L("up1"); _u.zp(0xB1, 0x00); _u.ab(0x8D, 0x2007); _u.raw(0xC8); _u.rel(0xD0, "up1")
    _u.raw(0xE6, 0x01, 0xCA); _u.rel(0xD0, "up1")
    _u.imm(0xA9, 0x80); _u.ab(0x8D, 0xA001)                      # 원래 하던 일
    _u.raw(0x60)
    _up195 = _u.build()
    rom[_b0e + 0x0200:_b0e + 0x0200 + len(_up195)] = _up195
    assert bytes(rom[_b0e + 0x4F:_b0e + 0x54]) == bytes([0xA9, 0x80, 0x8D, 0x01, 0xA0]),         "부팅 후크 자리가 예상과 다르다"
    rom[_b0e + 0x4F:_b0e + 0x54] = bytes([0x20, 0x00, 0x82, 0xEA, 0xEA])   # JSR $8200
    rom = bytearray(bytes(rom[:_chr0]) + bytes(_new))
    rom[5] = 0x20                                                # CHR 256KB
    rom[6] = (rom[6] & 0x0F) | 0x30
    rom[7] = (rom[7] & 0x0F) | 0xC0                              # 매퍼 195
    print("매퍼195 전환: CHR 256KB, 코드 $00~$FF 전부 CHR-RAM, 정적폰트 2KB 부팅 업로드 %d바이트"
          % len(_up195))

# ---------------------------------------------------------------- DON 그래픽 -> "쾅!" (2026-09-04, 사용자 지시)
# 전투 시작 연출 "DON" 은 대사·이름 시스템과 무관한 **OAM 스프라이트**(패턴테이블0,
# 8x5=40칸, 타일 $C8~$EF)다. 화면 픽셀을 CHR-ROM 으로 역추적해 자리를 확정했다
# (mstate.py 로 세이브스테이트를 얹고 OAM/패턴 덤프 -> 타일별 바이트열을 CHR 에서 재검색).
# 글자가 실제로 들어간 15칸(타일 $D2~$D6/$DA~$DE/$E2~$E6, 5x3타일=40x24px)만 바꾸고
# 나머지 25칸(불꽃 스파이크 테두리)은 원본 그대로 둔다 - 매퍼191/195 공통으로 CHR 앞 128KB
# 배치가 같아서(M195 는 뒤에 늘어나는 128KB만 새로 쓴다) 이 오프셋은 두 매퍼에서 동일하다.
_chr_s = HDR + rom[4] * 16384
_kwang = bytes.fromhex(
    "870707070f0f0f0700fbfbfbf0f7f3fbffffffffffffffff00ffffff00fffffff7f7f7f7f7f7f7f7"
    "03ebebebebebebebd1c0c0c1c1c1fdfda0bfbfbebebe82fa010000f8f8f8f8f800ffff07f7f7f7f7"
    "07001f1f1f1f1f00f8ffe0efefefe0ffff7dffffffffff3f00ba38ffffff00c7f7f7ffffffffffff"
    "ebeb03fbfbfb03f8fdfdfdc1c1c1c1c1fafa82bebebebe3ef8f8f8f8f8f8f8f8f7f7f7f7f7f7f7f7"
    "0000010101010090fffffefefefeff0ffffffffcfcffffff1f7f78f3f3787f1fffffff0f0fffffff"
    "ffff07f3f307ffffc1c1e0e1e1e1c1c63ebe9fdede9ebe01f8f8f0f8f8f8f8f0f7070f67f7f76700")
assert len(_kwang) == 240, "쾅! 타일 데이터 길이가 240바이트가 아니다"
for _i, _n in enumerate((0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE,
                          0xE2, 0xE3, 0xE4, 0xE5, 0xE6)):
    _o = _chr_s + 0x15480 + (_n - 0xC8) * 0x10
    rom[_o:_o + 16] = _kwang[_i * 16:_i * 16 + 16]
print("DON 스프라이트 15칸 -> \"쾅!\" (%d바이트)" % len(_kwang))

# ---------------------------------------------------------------- 타이틀 로고 (2026-09-06)
# "デジタルデビル物語 / 女神転生" -> "디지털 데빌 스토리 / 여신전생".
# 타이틀은 뱅크$07 의 **그리기 목록**(세그먼트 15개, 각 64칸=2줄, `$EE` 종료,
# `$FE nn` 빈칸)으로 그려진다 - 자세한 형식과 함정은 titleseg.py / make_title.py 참조.
# ★여기서 크게 헤맸다: 이걸 "하나의 연속 스트림"으로 착각하고 `$EE` 를 무시한 채
#   201바이트를 재인코딩했다가 타이틀이 박살났다. 세그먼트 경계를 반드시 지킬 것.
import make_title as _MT
_ntile, _nbyte = _MT.patch_rom(rom)
print("타이틀 로고 한글화: 타일 %d개 / 세그먼트 %d바이트" % (_ntile, _nbyte))

# ---------------------------------------------------------------- 시설 간판 (2026-09-06)
# 邪教の館 -> 사교의관 / 回復の泉 -> 치료의샘 / 辺境の店 -> 만물의회, もちきん -> 소지금.
# 간판은 **배경 네임테이블 타일**이다(스프라이트 아님). 한 글자 = 2x2 타일, 흰색 단색.
# ★CHR 뱅크가 한 프레임에 두 번 바뀐다(MMC3 IRQ 분할) - 상단용은 **vblank 에서** 들어간다.
#   프레임 끝에서 패턴테이블을 뜨면 폰트 뱅크가 잡혀 엉뚱한 그림이 나온다.
# ★치료의샘과 만물의회는 **셋째 글자 타일을 공유**한다(원문이 둘 다 「の」였다).
#   그래서 셋째 글자가 서로 달라지는 이름은 못 쓴다. 자세한 건 make_signs.py.
import make_signs as _MS
_nch, _ntl = _MS.patch_rom(rom, HDR + rom[4] * 16384)
print("시설 간판·소지금 한글화: 글자 %d개 / 타일 %d개" % (_nch, _ntl))

out = bytes(rom)
open(OUT, "wb").write(out)
with open(os.path.join(OUTDIR, "patched_ranges.txt"), "w", encoding="utf-8") as _f:
    _f.write("# 빌더가 **제자리 치환**한 구간. check_uistr.py 가 읽는다\n")
    _f.write("# 파일오프셋<TAB>바이트수<TAB>종류<TAB>내용\n")
    for _o, _n2, _t, _k in sorted(INPLACE):
        _f.write("%05X\t%d\t%s\t%s\n" % (_o, _n2, _t, _k))
print("제자리 치환 %d곳 -> %s/patched_ranges.txt" % (len(INPLACE), OUTDIR))
print()
print("삽입 %d개 / 건너뜀 %d개" % (len(records), len(skipped)))
for a_, why in skipped[:6]:
    print("   @%04X  %s" % (a_, why))
print("업로더 %d바이트 / 메시지훅 %d바이트 / 부팅복사기 %d바이트" % (len(up), len(hook), len(boot)))
print("꼬리 정렬 보정 %d개%s" % (tail_fix, "" if not tail_miss else
      "  ★자리를 못 찾은 꼬리 %d개: %s" % (len(tail_miss),
       " ".join("$%04X" % x for x in tail_miss))))
print("룩업표 %d엔트리(머리 %d + 꼬리 %d, %d바이트) / 레코드 %d바이트, 뱅크 %d개 (%s~)"
      % (placed + tails, placed, tails, len(look), rec_bytes, used_banks, "$%02X" % RECBANKS[0]))
print("패치: $C0BF -> JSR $6000,  $AF1E -> JSR $%04X + NOP NOP" % HOOK)
print()
print("%s  CRC32 %08X" % (OUT, zlib.crc32(out)))
