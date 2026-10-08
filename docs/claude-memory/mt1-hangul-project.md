---
name: mt1-hangul-project
description: 여신전생1(NES) 한글화 프로젝트의 인계 문서 위치와 포맷 후 복구한 개발환경(Python/Mesen 경로)
metadata: 
  node_type: memory
  type: project
  originSessionId: 842dbf86-830e-42bd-a702-f8a424412b1c
  modified: 2026-10-05T11:55:42.805Z
---

여신전생1(디지털 데빌 스토리) NES 한글화. 작업폴더
`%USERPROFILE%\OneDrive\Desktop\작업\디지털 데빌스토리 여신전생 작업` (git 아님).

**인계 문서는 두 개다. 세션 시작 때 이 둘을 먼저 읽는다:**
- `mt1-hangul-memory.md` (작업폴더) — 설계·함정·인계. 위로 갈수록 최신.
- `작업롬파일/VERSIONS.md` — 버전별 CRC·빌드로그·상세.

★최신 롬 `작업롬파일/mt1_kor5b_v54_도망소지금상태목록.nes` CRC32 `E2091500` (2026-10-05, 검사 10종·락스텝 통과, 배포 전).
  v54 = 사용자 실플레이 보고 3건: 도망 문장 조사 は(`$18F7B`)·떨어진 「。」 일반 규칙, 소환 화면 소지금 상자(미니폰트 33/33 꽉 참 — 패널 예/아니오→네/아뇨로 칸 확보),
  9명 상태 목록(UI 훅 UISCAN 64→$70). 상태 목록 고침은 PRG-RAM 훅이라 옛 세이브스테이트엔 안 먹는다(리셋+패스워드). 상세는 인계 문서 맨 위 「★v54」.
  v53 `E6D0EAE8`(10-04) = 엔딩·상태창·사교의 관·가이아. 둘 다 IPS·배포 폴더·push 는 사용자 결정 대기.
v52 = 함정·워프 메시지 창 이스케이프 훅 + 라그 간판 + 「내 힘을」. v51 = 예/아니오 상자·상점·장로·엘리베이터.
UI 이스케이프 음절이 223/224종이라 새 번역은 기존 음절로 맞춰야 한다(자세한 건 인계 문서 「v52 에서 배운 것」).
사용자는 GitHub 배포를 준비 중이다(미완성·미검수 상태로 공개하고 다른 사람이 PR 로 고치게 할 생각).
배포 폴더 `Desktop\작업\mt1-korean` (make_release.py 로 생성, 2026-09-15). 결정: 코드 MIT + 번역문 CC BY-NC-SA,
`JP:` 원문 줄 포함, IPS 만. 배포 폴더 안에서 원판+base 패치로 v52 재현 빌드 성공.
GitHub: https://github.com/kiek1224-spec/mt1-korean — 2026-09-15 첫 커밋(비공개), 같은 날 사용자 요청으로 **공개(PUBLIC) 전환**.
  계정 `kiek1224-spec` 은 gh CLI 로 로그인돼 있고 git 커밋 이메일은 noreply 주소다.
  검수 현황(사용자, 2026-09-15): **마왕 로키까지 플레이하며 검수**, 이후 계속 검수 중. 검수가 오래 걸려 먼저 공개하는 것이 배포 목적.
  다음 버전은 배포처에 새 글로 올리거나 페이지의 「수정요청」을 넣어야 갱신된다(GitHub 커밋만으론 안 잡힘, 짐작).
  README 에 타이틀·automap.lua·DS 창 스크린샷(docs/images/)과 「AI(Claude)가 작성」 표기를 넣었다(사용자 요청).
  다음 버전 배포: 작업폴더에서 `make_release.py` -> 배포 폴더에서 커밋·push (README 등 손으로 쓴 파일은 배포 폴더에만 있다).
배포 패치: **IPS 만** (`make_ips.py`). 실제 파일명은 `작업롬파일/mt1_kor5b_v52.ips`(VERSIONS.md 477행의 긴 이름은 틀림),
  배포본 `mt1-korean/patch/MT1_Korean_v52.ips` 와 바이트 동일 — 2026-09-28 점검에서 둘 다 원판→`0F0383D4` 확인.
  `_FAILED.nes` 는 v52 와 CRC 같음(첫 빌드 오탐 격리본, 476행), 지워도 되는 찌꺼기. ★사용자 결정(2026-09-15): 「bps는 하지말아줘, ips는 잘되니까 그것만 배포」
  - BPS 를 권하거나 같이 만들지 말 것. (v52 BPS 는 만들어 봤지만 배포에서 뺀다)
★캐릭터 상태창에서 글자가 UI 창을 침범하는 오래된 문제는 **사용자 결정으로 그대로 둔다**(2026-09-15).
  먼저 고치자고 하지 말 것 - 배포 README 의 「알려진 문제」에만 적는다. 기록: VERSIONS.md 「알려진 문제」.
사용자 세이브스테이트는 `Desktop\작업\Mesen_2.2.1_Windows\SaveStates\` 에 있고, `savestate_trace.py` 로
헤드리스 재현이 된다 — 보고가 오면 추측 전에 그 세이브부터 얹어 볼 것.

**2026-09-12: 사용자가 PC 를 포맷해 개발환경이 날아갔다.**
- Python 재설치함: `%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe` (3.12.10).
  외부 패키지는 **Pillow 하나뿐**. `mss` 는 PyPI 패키지가 아니라 작업폴더의 로컬 모듈이니
  `pip install mss` 하면 안 된다.
- 스토어 스텁이 PATH 를 가로채면 "Python was not found" 가 난다 -> PATH 앞에 위 경로를 붙인다.
- Mesen 경로가 스크립트 8곳에 옛 경로로 박혀 있어 `make.py` 가 멈춰 있었다 -> **`mtpaths.py`
  를 만들어 고쳤다(완료).** 경로는 이제 거기서만 정한다. 스크립트에 다시 박아 넣지 말 것.
  `python mtpaths.py` 로 현재 해석 결과를 확인할 수 있다.
- 포맷으로 **잃은 데이터는 없다.** 롬·소스·세이브스테이트 469개 전부 OneDrive 에 남아 있었다.

2026-09-12 `make.py v51 --env MT1_M195=1` 로 검사 10종 + 압박시험 + 락스텝까지 전부 통과 확인.

**2026-09-12: 지도 패널을 BizHawk 별도 창으로 옮겼다** — `C:\BizHawk\Lua\mt1_panel.lua`.
Mesen 용 `automap.lua` 의 분석 자산을 그대로 쓰되 `forms.newform` 으로 **진짜 별도 창**에 크게
그린다. 옮긴 이유는 Mesen 의 `emu.drawString` 이 글자를 세로로 흘려 자동지도에서 글자를 전부
포기해야 했기 때문이고, BizHawk 에서는 **한글 라벨이 나온다**(이 층의 계단·통로 목록을
`15,8 → 23,0 (23칸)` 식으로 띄운다). 워프 144개/층넘음 85개가 automap 기록과 일치함을 확인.
- 악마 도감은 **아직 뼈대만**이다. 참고: pareido.jp/cyber-newtown/megaten-bestiary/
  동료 데이터표는 **파일 0x19E00 = PRG 도메인 0x19DF0**(헤더 16 차이), 8바이트 레코드로 보이고
  `byte[5]` 가 레벨이다(1,2,3…7,10,8,9,13…). 나머지는 니블 압축 같아 사이트 공개값과 대조해
  확정해야 한다. **원판 JP 와 한글 v50 이 이 구간에서 바이트 단위로 같다**(첫 차이 0x1A2D7).
- ★★**BizHawk 는 매퍼 195 를 못 돌린다.** 현재 롬 v50 이 매퍼195라 `Mapper195.ReadPpu` 에서
  `NullReferenceException` 으로 **에뮬레이터가 죽는다**(BizHawk 쪽 버그. 내 스크립트 문제 아님).
  quickerNES 가 195 를 지원 안 해 NesHawk 로 떨어지고, 거기서 터진다. 실측 결과:
  | 매퍼 | 결과 |
  |---|---|
  | 4 (MMC3) | ✅ 정상, **quickerNES**(빠른 코어) — `archive/roms/mt1_jp_mmc3.nes` 로 확인 |
  | 76 (원판/영어판) | ✅ 정상. 영어판은 PRG 256KB 로도 돈다 |
  | 191 (`mt1_kor5b.nes`) | ⚠️ 로드는 되나 **검은 화면** |
  | 195 (v50 현재) | ❌ 크래시 |
  -> BizHawk 로 놀려면 한글 롬을 **MMC3(매퍼4)로 다시 빌드**하는 게 답이다. 가장 널리
     검증된 매퍼고 빠른 코어까지 붙는다. Mesen 에서는 195 가 잘 도니 기존 작업엔 영향 없다.
- ★forms 그리기는 GDI+ 라 비싸다. 16x16 지도 한 장이 호출 1000번이 넘어서, 타이틀 화면처럼
  좌표가 매 프레임 요동치면 **에뮬레이터가 멈춘다.** 최소 재그리기 간격을 둘 것.

관련: [[mt1-hangul-romdiff-method]], [[bizhawk-second-screen]]

**2026-10-04 엔딩 캡처 검수**(사용자는 아직 엔딩을 못 봄 → 헤드리스로 대신 봄): `참고자료/엔딩캡처_2026-10-04/README.md`.
엔딩 진입 = 필드 세이브에서 `$C5AB` 에 끼어들어 `$0782=5`·`$065F=2` 넣고 `$E4ED`. 찾은 버그 둘: 엔딩 얼굴 장면 대사 깨짐(CHR 이 가나 글꼴로 덮임),
가이아 흥정 「でどうだい?」 미번역(뱅크1 `$ADDF`). 고칠지는 사용자 결정 전.
★**Mesen `--testRunner` 는 종료 때 SaveStates 의 슬롯 11 을 덮어쓴다** → 시험은 `%TEMP%\mesen_sandbox`(Mesen.exe+dll+settings.json+Firmware 복사본)로. [[mt1-ds-window]]

