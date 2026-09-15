#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5c 검증: 슬롯 $C0~$CF 16칸 + 공백 $Dn + 창닫힘 리셋."""
import re, struct, sys
import mss
from nesboot import verify
from play import Runner
import build_step5b as B
import galmuri8 as G
ROM=B.OUT                      # 빌더가 쓴 버전 롬을 그대로 검사한다
def p(*a): print(*a); sys.stdout.flush()
fail=[]

# [1] 슬롯 범위가 라틴/가나를 침범하지 않는가
# ★슬롯 타일은 **연속이 아니다**($C0 을 건너뛴다). 반드시 B.TILES 로 검사할 것.
p("[1] 슬롯 타일 %d칸: %s" % (B.NSLOT, " ".join("$%02X"%t for t in B.TILES)))
if 0xC0 in B.TILES: fail.append("$C0 이 슬롯 표에 있다 (파서 제어코드)")
# 의도적으로 회수한 타일 - 대사/이름표 실측으로 미사용 확인된 것만
# 가나 $80~$99 는 사용자 결정으로 슬롯에 회수했다(전부 번역하면 안 쓰이는 글자).
# 라틴 $9A~$B3 와 기호 $B4~$BD 는 **보류** - 패스워드 화면과 상태바가 쓴다.
# $B6~$BC 는 종족명 합자 타일 - 이름을 한글로 바꾸면 안 쓰인다
RECLAIMED = set(range(0x80, 0x9A)) | set(range(0xB4, 0xBD)) | {0xBE, 0xBF}
for name,(lo,hi) in {"가나(회수)":(0x80,0x99),"라틴A~Z(보류)":(0x9A,0xB3),"기호/※(보류)":(0xB4,0xBF)}.items():
    ov=[t for t in B.TILES if lo<=t<=hi]
    bad_ov=[t for t in ov if t not in RECLAIMED]
    if bad_ov:
        p("    %-8s $%02X~$%02X  ★침범 %s" % (name, lo, hi, " ".join("$%02X"%t for t in bad_ov)))
        fail.append("%s 침범"%name)
    elif ov:
        p("    %-8s $%02X~$%02X  의도적 회수 %s (미사용 확인됨) ✔"
          % (name, lo, hi, " ".join("$%02X"%t for t in ov)))
    else:
        p("    %-8s $%02X~$%02X  침범 없음 ✔" % (name, lo, hi))

# [2] 메시지별 고유 음절 수가 16칸을 넘지 않는가
p("[2] 번역된 메시지별 고유 음절 수 (대사 풀 한도 %d)"%B.NDLG)
worst=[]
for a, enc, ids in B.records:
    worst.append((len(ids), a))
worst.sort(reverse=True)
for n,a in worst[:5]:
    p("    @%04X  %d칸" % (a, n))
p("    최대 %d칸 / 한도 %d칸  %s" % (worst[0][0], B.NDLG,
                                    "✔" if worst[0][0]<=B.NDLG else "★초과"))
if worst[0][0] > B.NDLG: fail.append("메시지 하나가 대사 풀 한도 초과")

# [3] 공백이 $Dn 으로 나가는가
a=0x8606; p2=B.phys(a)
enc=bytes(B.rom[p2:p2+11])
p("[3] @8606 인코딩: %s" % " ".join("%02X"%b for b in enc))
p("    선두가 $D1(빈칸1) 인가: %s" % ("예 ✔" if enc[0]==0xD1 else "★아니오"))
if enc[0]!=0xD1: fail.append("공백이 $D1 로 안 나감")

# [3d] ★제어 구조 보존 검사
#   $F0~$FF 는 게임 로직이다(분기·이름삽입·버튼대기·개행·페이지).
#   번역문의 인코딩이 원문과 **같은 제어코드 시퀀스(파라미터 포함)** 를 내야 한다.
#   $F8 이 파라미터를 3개 먹는다는 걸 모르고 4번째 바이트를 텍스트로 착각하면
#   여기서 걸린다. (실제로 export_script.py 가 그렇게 표시하고 있었다)
_src = open("mt1_m191_v3.nes", "rb").read()

def ctrl_seq(b):
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if c >= 0xF0 or c == 0xC0:      # $C0 도 게임 동작 제어코드(값 반감)라 포함
            k = B.PARAMS.get(c, 0)
            out.append((c,) + tuple(b[i + 1:i + 1 + k]))
            if c == 0xFB: break
            i += 1 + k
        else:
            i += 1
    return out

def orig_len(q):
    """★원문 길이는 **원본 파일**로 재야 한다.
       B.msg_len 은 이미 우리 인코딩이 덮인 B.rom 을 읽으므로 번역문의 길이가 나온다.
       그걸로 원문을 자르면 끝의 <FB> 가 잘려 엉뚱한 불일치가 무더기로 뜬다."""
    j = 0
    while j < 800:
        c = _src[q + j]
        if c in B.PARAMS:
            j += 1 + B.PARAMS[c]
            if c == 0xFB: return j
        else:
            j += 1
    return j

# [3b] 인코딩에 $C0 이 없는가 (파서 제어코드 - 실기에서 HP 를 깎는다)
# ★$C0 은 파서 제어코드(값 반감)라 **글리프로 쓰면 안 된다.** 다만 원문에 정상적으로
#   들어 있는 <C0> 도 있다(@915C). "없어야 한다"가 아니라 **원문과 개수가 같아야 한다**.
c0 = []
for a, enc, _ in B.records:
    q = B.phys(a)
    if _src[q:q + orig_len(q)].count(0xC0) != bytes(enc).count(0xC0):
        c0.append(a)
p("[3b] $C0 개수가 원문과 다른 메시지: %s"
  % (("★%s" % [hex(x) for x in c0]) if c0 else "없음 ✔"))
if c0: fail.append("$C0 개수 불일치")

# [3a] ★번역했는데 빌더가 **건너뛴** 메시지가 없는가
#      건너뛰면 그 대사는 조용히 일본어로 남는다. 실제로 @9A2B 이 라틴 바이트를
#      태그로 쓰는 바람에 "슬롯 범위와 충돌"로 빠졌는데 아무도 몰랐다.
import re as _re, io as _io
_ko = _io.open("script_ko.txt", encoding="utf-8").read().splitlines()
_n_tr, _cur = 0, None
for _l in _ko:
    _m = _re.match(r"^@([0-9A-Fa-f]{4})", _l)
    if _m: _cur = int(_m.group(1), 16)
    elif _l.startswith("KO:"):
        if _l[3:].strip(): _n_tr += 1
        _cur = None
p("[3a] 번역 %d개 중 빌더가 삽입한 것 %d개%s"
  % (_n_tr, len(B.records), "" if _n_tr == len(B.records) else "  ★%d개 건너뜀" % (_n_tr - len(B.records))))
if _n_tr != len(B.records):
    fail.append("번역했는데 삽입 안 된 메시지 %d개" % (_n_tr - len(B.records)))

# [3e] ★id 목록이 페이지 경계를 넘지 않는가
#   훅이 `LDA $A000,Y` 로 읽는데 Y 가 8비트다. 상위바이트는 시작할 때 한 번만
#   자기수정하므로 경계를 넘으면 Y 가 감겨 **페이지 앞쪽(글리프 영역)** 을 읽는다.
#   -> id 자리에 글리프 비트맵이 들어오고, 대사 뒷부분이 엉뚱한 한글로 나온다.
#   실기에서 이걸로 141개 중 13개가 깨지고 있었다(2026-08-31).
cross = [a for a, enc, ids in B.records
         if (B.where[a][0] & 0xFF) + 1 + 2 * len(ids) > 0x100]
p("[3e] id 목록이 페이지를 넘는 메시지: %s"
  % (("★%d개 %s" % (len(cross), [hex(x) for x in cross[:5]])) if cross else "없음 ✔"))
if cross: fail.append("id 목록 페이지 초과 %d개" % len(cross))

# [3c] 번역된 머리의 **꼬리공유 진입점**이 전부 룩업표에 있는가
#      빠지면 훅이 못 찾아 치환 없이 로컬 인덱스 코드가 그대로 그려진다(깨진 글자).
heads = {a for a, enc, ids in B.records}
missing_tails = [t for t, hd in B.head_of.items() if hd in heads and t not in B.where_all]
p("[3c] 번역된 머리의 꼬리 진입점 %d개 중 룩업표 누락: %s"
  % (sum(1 for t, hd in B.head_of.items() if hd in heads),
     ("★%s" % [hex(x) for x in missing_tails[:6]]) if missing_tails else "없음 ✔"))
if missing_tails: fail.append("꼬리공유 룩업 누락 %d건" % len(missing_tails))

bad_ctrl = []
for a, enc, ids in B.records:
    q = B.phys(a)
    o = ctrl_seq(_src[q:q + orig_len(q)])
    e = ctrl_seq(bytes(enc))
    if o != e:
        bad_ctrl.append((a, o, e))
p("[3d] 제어 구조 보존 (번역 %d개): %s"
  % (len(B.records), ("★%d건 불일치" % len(bad_ctrl)) if bad_ctrl else "전부 일치 ✔"))
for a, o, e in bad_ctrl[:4]:
    p("    @%04X" % a)
    p("      원문: %s" % " ".join("<%s>" % " ".join("%02X" % x for x in t) for t in o))
    p("      번역: %s" % " ".join("<%s>" % " ".join("%02X" % x for x in t) for t in e))
if bad_ctrl: fail.append("제어 구조 불일치 %d건" % len(bad_ctrl))

# [4] 부팅
n0=verify(ROM, frames=600, verbose=False)
p("[4] 부팅 600프레임 통과, VRAM 쓰기 %d회 (v3=6147) %s"
  % (n0.vram_writes, "✔" if n0.vram_writes==6147 else "★다름"))
if n0.vram_writes!=6147: fail.append("VRAM 쓰기 %d"%n0.vram_writes)

# [5] 실게임 흐름: 창닫힘 리셋이 도는가 / 슬롯이 안 넘치는가
def parse_bin(path):
    st=open(path,"rb").read(); out,i={},0
    while i<len(st):
        j=st.find(b"\x00",i)
        if j<0 or j-i<3: break
        k=st[i:j]
        if not re.fullmatch(rb"[A-Za-z][A-Za-z0-9_.]*",k): i+=1; continue
        if j+5>len(st): break
        nn=struct.unpack_from("<I",st,j+1)[0]
        if nn>len(st): i=j+1; continue
        out[k.decode()]=st[j+5:j+5+nn]; i=j+5+nn
    return out
mss.parse=lambda path: parse_bin(path)
r=Runner(ROM); n=r.n
mss.load(n,"mss_state.bin",verbose=False)
mss.refresh_prgram(n,B.COPY); mss.reset_chrram(n,ROM)
r.fstart=n.cyc
p("[5] 상점 흐름")
# ★표본(프레임마다 NEXT 읽기)으로는 **새 창 리셋과 순환을 구분할 수 없다.**
#   둘 다 NEXT 를 0 으로 만들고, 그 직후 같은 훅 안에서 다시 배정되기 때문이다.
#   (실제로 이 구멍 때문에 멀쩡한 롬에 "순환/변질" 오진을 냈다.)
#   -> NEXT 에 대한 **쓰기를 직접 관측**한다. 순환은 NEXT 가 NSLOT 에 도달했을 때만
#      일어나므로, 0 을 쓰기 직전 값이 NSLOT 이면 순환, 그보다 작으면 새 창 리셋이다.
#   그리고 한 에폭(리셋과 리셋 사이) 안에서 배정은 **덧붙이기만** 하므로,
#   순환이 없으면 화면에 떠 있는 글자가 변질될 수 없다. 즉 검사는 "순환 0건"으로 환원된다.
NEXTADDR = B.NEXT
ev = []
_wr = n.wr
def wr(a, v, _o=_wr):
    if a == NEXTADDR:
        ev.append((n.prgram[NEXTADDR - 0x6000], v))
    _o(a, v)
n.wr = wr

hist = []
for i in range(16):
    r.press("a").frames(14)
    nx = n.prgram[B.NEXT - 0x6000]
    res = tuple(n.prgram[B.RESIDL - 0x6000 + k] | (n.prgram[B.RESIDH - 0x6000 + k] << 8)
                for k in range(B.NSLOT))
    ch = "".join(B.glob[g] if g < len(B.glob) else "?" for g in res[:nx])
    hist.append((nx, res))
    p("    A#%-2d NEXT=%2d  $BE/$BF=$%02X%02X  상주=[%s]"
      % (i + 1, nx, n.ram[0xBF], n.ram[0xBE], ch))
n.wr = _wr

wraps = [(a, b) for a, b in ev if b == 0 and a >= B.NSLOT]
resets = [(a, b) for a, b in ev if b == 0 and a < B.NSLOT]
peak = max([a for a, b in ev] + [h[0] for h in hist])
p("")
p("    NEXT 쓰기 %d회 / 새 창 리셋 %d회 / 순환 %d회" % (len(ev), len(resets), len(wraps)))
p("    최대 동시 사용 %d칸 / 한도 %d칸 %s"
  % (peak, B.NSLOT, "✔" if peak <= B.NSLOT else "★초과"))
p("    여유 %d칸" % (B.NSLOT - peak))
if wraps:
    p("    ★순환 발생 - 화면에 떠 있는 글자가 덮인다: %s" % wraps[:5])
    fail.append("슬롯 %d칸 초과로 순환 %d회" % (B.NSLOT, len(wraps)))
else:
    p("    순환 없음 -> 떠 있는 글자 변질 불가 ✔")

# [7] ★업로드가 텍스트 그리기를 따라잡는가 (경주 검사)
#   [6] 은 "충분히 기다린 뒤" 한 번만 대조하므로 **경주 자체를 못 본다.**
#   ★단 "빠를수록 좋다"는 아니다. CHR-RAM 타일은 나중에 올라와도 **화면이 저절로 고쳐진다**
#     (네임테이블은 타일 번호만 갖는다). 실측: 글자는 3프레임에 1칸씩 그려지는데
#     업로드는 12칸을 5프레임에 끝낸다 - 경주에서 업로드가 이미 이기고 있다.
#   그러니 검사할 것은 속도가 아니라 **끝내 전부 도달하는가**다.
#   (한때 지연이 원인이라 보고 게이트를 걷어냈다가 vblank 를 넘겨 화면을 깨뜨렸다.
#    게이트는 충돌 방지가 아니라 **vblank 예산 보호**다. 절대 건드리지 말 것.)
MAXLAG = 40

def uploaded_cnt():
    nx = n.prgram[B.NEXT - 0x6000]
    ok = 0
    for k in range(nx):
        gid = (n.prgram[B.RESIDL - 0x6000 + k]
               | (n.prgram[B.RESIDH - 0x6000 + k] << 8))
        if gid >= len(B.glob): continue
        want = bytes(G.to_chr(G.bitmap(B.glob[gid])))
        t = B.TILES[k]; off = (0x1000 + t * 16) - 0x1800
        if bytes(n.chrram[off:off + 16]) == want: ok += 1
    return ok, nx

p("[7] 업로드 지연 (슬롯 배정 -> 전부 CHR-RAM 도달)")
r2 = Runner(ROM); n2 = r2.n
mss.load(n2, "mss_state.bin", verbose=False)
mss.refresh_prgram(n2, B.COPY); mss.reset_chrram(n2, ROM)
r2.fstart = n2.cyc
_n_save = n
n = n2
worst, seen = 0, 0
prev_nx = 0
for _ in range(120):
    r2.frames(2)
    ok, nx = uploaded_cnt()
    if nx and nx != prev_nx:                      # 새로 배정된 순간
        start = n2.nmi_count
        for _w in range(40):
            ok, nx2 = uploaded_cnt()
            if ok == nx2: break
            r2.frames(1)
        lag = n2.nmi_count - start
        worst = max(worst, lag); seen += 1
        p("    슬롯 %2d칸 배정 -> %d프레임 만에 완료" % (nx2, lag))
        prev_nx = nx2
n = _n_save
p("    최악 지연 %d프레임 / 한도 %d %s   (지연 자체는 무해 - 끝내 도달하면 화면이 고쳐진다)"
  % (worst, MAXLAG, "✔" if worst <= MAXLAG else "★미완료 의심"))
if worst > MAXLAG:
    fail.append("업로드가 %d프레임 안에 완료되지 않음" % MAXLAG)

# [6] CHR-RAM 이 실제로 맞는 타일에 올라갔는가 (TILE0 가 16정렬이 아니라 목적지 계산이 바뀌었다)
nx=n.prgram[B.NEXT-0x6000]
p("[6] CHR-RAM 대조 (슬롯 %d칸)"%nx)
okc=badc=0
for k in range(nx):
    gid=n.prgram[B.RESIDL-0x6000+k] | (n.prgram[B.RESIDH-0x6000+k]<<8)
    ch=B.glob[gid] if gid<len(B.glob) else "?"
    want=bytes(G.to_chr(G.bitmap(ch)))
    tile=B.TILES[k]; off=(0x1000+tile*16)-0x1800
    got=bytes(n.chrram[off:off+16])
    if got==want: okc+=1
    else:
        badc+=1
        p("    ★슬롯%d 타일$%02X '%s' CHR 불일치"%(k,tile,ch))
p("    일치 %d / 불일치 %d %s"%(okc,badc,"✔" if badc==0 else ""))
if badc: fail.append("CHR-RAM 업로드 목적지 어긋남 %d칸"%badc)

p("")
if fail:
    p("=== 실패 %d건 ==="%len(fail))
    for f in fail: p("  - "+f)
    sys.exit(1)
p("=== 5c 검증 통과 ===")
