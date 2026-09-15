---
name: bizhawk-second-screen
description: "BizHawk 2.11.1로 롬 무수정 DS식 보조 스크린을 만드는 법 — 한글 출력이 되는 유일한 경로, C:\\BizHawk에 설치됨"
metadata: 
  node_type: memory
  type: project
  originSessionId: bcdb2bc2-3e25-47bd-8ef6-103582048e4b
  modified: 2026-09-13T06:17:38.357Z
---

2026-09-12에 검증 완료. FC/SFC 게임에 **닌텐도 DS 컨셉의 보조 스크린**을 롬 무수정으로
붙이는 경로는 **BizHawk**다. Mesen이 아니다.
★단, 2026-09-13 에 **Mesen 도 된다**는 게 확인됐다 — Mesen Lua 는 화면 밖 영역을 못 만들지만
LuaSocket 으로 위치를 보내고 **파이썬 tkinter 창**이 받아 그리면 된다(한글 OK). 여신전생1 은
사용자가 그 방식을 골랐다: [[mt1-ds-window]]. BizHawk 는 게임 **안쪽 메모리까지 고치는** 콘솔
(마리오 루이지·워프처럼)이 필요할 때의 길로 남긴다.

- 설치: `C:\BizHawk` (2.11.1, 공식 GitHub `TASEmulators/BizHawk`). Windows 빌드는
  **.NET Framework 4.8** 타겟이라 Win11에 기본 내장 — 추가 런타임 설치 불필요.
  VC++ 2022 x64는 이미 있었다.
- 검증 스크립트: `C:\BizHawk\Lua\ds_probe.lua` (마리오1 대상, T=배치전환, 1=목숨쓰기)
- 캡처 증거: `C:\BizHawk\layout_right.png`, `C:\BizHawk\layout_bottom.png`

**Why:** [[mt1-hangul-project]]의 자동지도(`automap.lua`)는 Mesen 전용인데, Mesen의
`emu.drawString`이 글자를 화면 왼쪽에 세로로 흘려서 **글자를 전부 포기하고 네모 표식으로
대체**해야 했다. BizHawk에서는 그 제약이 없다. 8x8 타일 폰트에 안 들어가는 긴 악마 이름·
설명을 보조 화면에 진짜 폰트로 쓸 수 있다는 뜻이라, 한글화의 타일 제약을 우회하는 길이다.

**How to apply:**
- `client.SetGameExtraPadding(l,t,r,b)` — 게임 화면 **밖에** 그릴 영역을 만든다. Mesen에 없는
  기능이고 이게 "두 번째 화면"의 전부다. 런타임에 다시 호출해 배치를 바꿔도 된다.
  오른쪽 패널(240x240)과 아래쪽 DS식 2단(256x200) 둘 다 동작 확인.
- `gui.drawText(x, y, s, 색, nil, 크기, "Malgun Gothic")` — **한글 그대로 나온다.**
  파일 UTF-8 리터럴도, 코드포인트로 조립한 문자열도 둘 다 정상.
- 색은 `0xAARRGGBB`. **알파를 빼면 투명이라 안 보인다.** `0xFF...`로 쓸 것.
- RAM은 `mainmemory.read_u8` / `write_u8`. 롬은 건드리지 않는다.
- `input.get()`으로 키, `input.getmouse()`로 커서(터치 대용).
- 루프는 `while true do ... emu.frameadvance() end`. Mesen의 `emu.addEventCallback`과 다르다.
- 패널 높이는 오른쪽 배치일 때 **240px가 상한**이다. 넘으면 아무 경고 없이 잘린다.

**★진짜 별도 창은 `forms` API 로 만든다 (2026-09-12 검증). 에뮬레이터 개조 불필요.**
`client.SetGameExtraPadding` 은 **같은 창 안**에 여백을 만드는 것이라 게임과 붙어 다닌다.
`forms.newform(w,h,title,onclose)` 은 **진짜 OS 창**을 띄운다 — 옮기고 키우고 다른 모니터로 보낸다.
- `forms.pictureBox(form,x,y,w,h)` 캔버스 + `forms.drawText/drawRectangle/drawImage/clear/refresh`.
  drawText 는 시스템 폰트라 한글이 나오고, **게임 해상도 256px 에 묶이지 않는다**(22pt도 가능).
- `forms.button(form, 캡션, 콜백, x,y,w,h)` 은 **진짜 윈도우 버튼**이다. 직접 그린 칸에
  마우스 좌표를 맞추던 일이 통째로 없어진다(`input.getmouse` 보정 불필요).
- `pcall(forms.setproperty, form, "BackColor", "0xFF181828")` 으로 폼 바탕색도 바꿔진다.
- ★GDI+ 라 **매 프레임 다시 그리면 무겁다.** 내용 해시를 만들어 바뀔 때만 `refresh` 할 것.
- ★`local x = forms.button(..., function() ... x ... end, ...)` 는 클로저가 x 를 **전역(nil)**
  으로 본다. `local x` 를 먼저 선언하고 나중에 대입할 것.
- 게임 화면 **위에 겹쳐 그리는 건 여전히 `gui.*`** 몫이다. 둘을 같이 쓰면 된다.
- Citra 가 화면 둘인 건 3DS 하드웨어가 원래 2화면이라 프레임버퍼를 둘 그리는 것이다.
  NES 는 하나뿐이라 두 번째 화면을 만들어내야 하지만, 위 방법으로 충분하다.
- 예: `C:\BizHawk\Lua\ds_smb_window.lua` (마리오 조작 패널, 스테이지 32개 버튼).

**PRG 롬을 롬 파일 없이 패치하기 (2026-09-12 검증):**
BizHawk의 `PRG ROM` 메모리 도메인은 **쓰기가 된다**. 여기에 쓰면 메모리에 올라온 롬
이미지만 바뀌고 **디스크의 .nes 는 그대로다**(실행 전후 SHA256 동일 확인). 그래서 RAM에
없는 상수(물리값, 표, 텍스트)도 롬 무수정으로 바꿀 수 있다. 도메인 주소는 **헤더 16바이트를
제외한** 값이다(파일 오프셋 - 0x10). 이걸 단정하지 말고 원본 바이트와 대조해 보정값을
찾을 것 — `ds_luigi.lua`의 `findBase()`가 그 방식이다.
- NES 도메인 실측 목록: `WRAM` `CHR` `CIRAM (nametables)` `PRG ROM` `CHR VROM`
  `PALRAM` `OAM` `System Bus` `CPU registers`. **`PPU Bus` 는 없다**(팔레트는 `PALRAM`,
  0x00~0x1F, 스프라이트 팔레트0 = 0x10~0x13).
- 응용 예: SMB1에 로스트레벨 루이지 물리 이식 (`C:\BizHawk\Lua\ds_luigi.lua`). 값 출처는
  SMBpedia, 위치는 롬 바이트 대조로 확정. **Data Crystal의 SMB1 최대속도 값은 실제 롬과
  달랐다** — 웹 값을 그대로 믿지 말 것.

**함정:**
- **`input.get()` 은 에뮬 창에 포커스가 없어도 호스트 키보드를 읽는다.** 눌린 키를 파일이나
  로그로 남기면 사실상 키로거가 된다. 화면에만 띄울 것. (2026-09-12에 키 이름을 확인하려고
  파일로 남겼다가 사용자의 다른 작업 타이핑이 섞여 들어왔다. 바로 지우고 코드도 뺐다.)
- 스크립트 검증을 **합성 키 입력으로 하지 말 것.** 사용자가 다른 창을 쓰는 중이면 Windows가
  포커스 전환을 막아서 그 키가 **사용자가 쓰던 창으로 들어간다.** 대신 스크립트 맨 위에
  `START_AS` 같은 스위치를 두고 그걸 바꿔서 상태를 확인할 것.
- 에뮬레이터와 Lua 스크립트는 **ASCII 경로**에 둔다. 작업 폴더가 한글이라 Lua `io`가 죽는
  문제를 이미 겪었다(`mrun.py`가 임시폴더를 쓰는 이유). 롬 경로는 한글이어도 괜찮았다.
- 스크립트로 키 입력을 흉내 낼 땐 `SendKeys`가 **안 먹는다**(BizHawk가 메시지가 아니라
  하드웨어 상태를 폴링한다). `keybd_event`/`SendInput` 수준으로 넣어야 잡힌다.
- Mesen용 `automap.lua`는 BizHawk에서 한 줄도 안 돈다. API 이름이 전부 다르다
  (`emu.read`→`mainmemory.read_u8`, `emu.drawLine`→`gui.drawLine`, 콜백→프레임 루프).
- 마리오 RAM: 목숨 `$075A`는 **화면 표시보다 1 작다**(정상). `$075E`는 화면 코인이 아니라
  1UP 누적으로 보인다(화면 ×00일 때 2를 읽었다). 주소는 화면 값과 대조해 검증할 것.
