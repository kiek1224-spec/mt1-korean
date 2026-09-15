#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★슬롯 타일 코드가 **게임 그래픽**과 충돌하는지 본다.

발견 경위 (2026-09-03): 악마 상태창 네임테이블을 덤프했더니 초록 상자 테두리가
`$C9`(15칸) `$CB`(8칸) 등으로 그려져 있었다. 그 코드들은 **우리 이름 슬롯 범위**다.
슬롯이 거기까지 차면 테두리가 한글로 덮인다.

★★2026-09-07 전면 개편. 예전 판은 **세 가지를 뭉뚱그려** 62종을 쏟아냈고,
  그래서 아무도 못 믿고 `make.py` 검사 목록에서 빠진 채 방치됐다.
  그 사이 합체 화면이 실제로 깨져 있었다(사용자 보고). 이제 셋으로 가른다:

    ① 진짜 그래픽   - 원본 폰트에 **글자가 아닌** 코드(상자·틀·장식). **이게 충돌이다.**
    ② 미번역 가나   - 원본 폰트에서 가나/라틴인 코드. 그래픽이 아니라 **아직 안 고친 일본어**다.
                      충돌이 아니라 **번역 할 일 목록**이다.
    ③ 타이틀 화면   - **CHR 뱅크가 다르다**(타이틀 전용). 번호가 겹쳐도 안 깨진다 -> 건너뛴다.

판정: 세이브스테이트를 물려 네임테이블을 훑고, **아직 아무 슬롯도 배정되지 않은**
슬롯 코드가 화면에 그려져 있으면 우리 글자가 아니다. 그 코드를 ①/②로 가른다.
①의 가장 앞 번호가 곧 '몇 칸까지 안전한가'다.
"""
import collections
import glob
import os
import sys

sys.argv = [sys.argv[0]]
import decode_tbl as T
import mss
import build_step5b as B
from play import Runner

import mtpaths                                          # ★경로는 mtpaths 에서만 정한다
SAVEDIR = mtpaths.SAVEDIR
# ★타이틀 세이브는 CHR 뱅크가 달라 판정 대상이 아니다. 파일이름 `_11` 이 타이틀이다.
SKIP_SUFFIX = ("_11.mss",)


def is_text(code):
    """원본 폰트에서 **글자**인 코드인가. decode_tbl 에 있으면 글자다."""
    return code in T.CH


# ★게임이 **그래픽**(상자 테두리·초상화 틀)으로 쓰는 슬롯 코드. 화면 검사로 확정한 목록이다.
GFX = {0xB4, 0xB5, 0xBE, 0xBF} | set(range(0xC1, 0xD0))
NEED_NAME = 24          # 이름 슬롯이 최소 이만큼은 그래픽과 안 겹쳐야 한다


def structural():
    """★세이브스테이트 없이 되는 검사. **이게 합격 기준**이다.

    화면 검사는 세이브스테이트에 담긴 **그 빌드의 SLOTTAB** 을 쓰므로, 슬롯 순서를 바꾼
    빌드에서는 옛 세이브로 재면 값이 어긋난다. 반면 풀 순서는 롬만 보면 알 수 있다.
    """
    d_bad = [c for c in B.TILES[:B.NDLG] if c in GFX]
    n_idx = [i for i, c in enumerate(B.TILES[B.NDLG:]) if c in GFX]
    n_first = n_idx[0] if n_idx else B.NNSLOT
    print("[구조] 대사풀 %d칸 중 그래픽코드 %d개 / 이름풀은 %d번째부터 그래픽코드 (총 %d칸)"
          % (B.NDLG, len(d_bad), n_first, B.NNSLOT))
    ok = not d_bad and n_first >= NEED_NAME
    if not ok:
        print("   ★그래픽 코드가 슬롯 풀 앞쪽에 있다. build_step5b.py 의 TILES 순서를 볼 것"
              " (GFX_CLASH 를 뒤로 보낸다)")
    return ok


def main():
    ok = structural()
    saves = [s for s in sorted(glob.glob(os.path.join(SAVEDIR, "mt1_kor5b_v*.mss")))
             if not s.endswith(SKIP_SUFFIX)]
    if not saves:
        print("세이브스테이트가 없다 - 화면 검사는 건너뜀")
        return 0 if ok else 1
    print("%s" % B.OUT)
    worst_d, worst_n, worst_sv = B.NDLG, B.NNSLOT, ""
    kana_all = collections.Counter()
    gfx_all = collections.Counter()
    for sv in saves:
        r = Runner(B.OUT)
        try:
            mss.load(r.n, sv, verbose=False)
            r.frames(4)
        except Exception as e:
            print("  %-34s 로드 실패 (%s)" % (os.path.basename(sv), e))
            continue
        n = r.n
        nx, nn = n.prgram[B.NEXT - 0x6000], n.prgram[B.NNEXT - 0x6000]
        live = set(B.TILES[:nx]) | set(B.TILES[B.NDLG:B.NDLG + nn])
        gfx, kana = set(), set()
        for i in range(0x800):
            c = n.vram[i]
            if c in B.TILES and c not in live:
                (kana if is_text(c) else gfx).add(c)
        for c in kana:
            kana_all[c] += 1
        for c in gfx:
            gfx_all[c] += 1
        di = [B.TILES.index(c) for c in gfx if B.TILES.index(c) < B.NDLG]
        ni = [B.TILES.index(c) - B.NDLG for c in gfx if B.TILES.index(c) >= B.NDLG]
        d0 = min(di) if di else B.NDLG
        n0 = min(ni) if ni else B.NNSLOT
        if (n0, d0) < (worst_n, worst_d):
            worst_sv = os.path.basename(sv)
        worst_d, worst_n = min(worst_d, d0), min(worst_n, n0)
        print("  %-34s 대사 %2d / 이름 %2d 까지 안전   (그래픽 %d종, 미번역가나 %d종)"
              % (os.path.basename(sv), d0, n0, len(gfx), len(kana)))

    print("\n① 진짜 그래픽과 겹치는 슬롯코드 %d종 (이게 충돌이다):" % len(gfx_all))
    print("   " + " ".join("%02X" % c for c in sorted(gfx_all)))
    print("② 미번역 가나로 화면에 뜬 코드 %d종 (충돌 아님 - 번역 할 일):" % len(kana_all))
    print("   " + " ".join("%02X(%s)" % (c, T.CH.get(c, "?")) for c in sorted(kana_all)))
    print("\n가장 빡빡한 화면: %s" % (worst_sv or "-"))
    print("  대사 %d칸 / 이름 %d칸을 넘기면 게임 그래픽이 한글로 덮인다." % (worst_d, worst_n))
    print("  현재 풀 크기: 대사 %d / 이름 %d" % (B.NDLG, B.NNSLOT))
    # ★★화면 검사는 **참고용**이다. 세이브스테이트가 그 빌드의 SLOTTAB 을 담고 있어서,
    #   슬롯 순서를 바꾼 빌드를 옛 세이브로 재면 값이 어긋난다. 합격 기준은 위의 구조 검사다.
    #   ★압박시험이 재는 것과도 다르다. 압박시험은 **슬롯 고갈**만 본다.
    #     여기서 걸리면 슬롯이 남아돌아도 화면이 깨진다 - 그걸 몰라서 v35~v41 을 통과시켰다.
    print("\n(화면 검사는 참고용 - 옛 세이브는 그 빌드의 슬롯표를 담고 있다)")
    print("%s" % ("통과" if ok else "★실패 - build_step5b.py 의 TILES 순서를 고칠 것"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
