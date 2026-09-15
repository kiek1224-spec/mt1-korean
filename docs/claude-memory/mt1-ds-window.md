---
name: mt1-ds-window
description: "여신전생1 DS 컨셉 두 번째 화면 — Mesen 브리지(TCP 9876) + 파이썬 tkinter 창으로 결정, 파일·검증법"
metadata: 
  node_type: memory
  type: project
  originSessionId: 842dbf86-830e-42bd-a702-f8a424412b1c
  modified: 2026-09-13T07:00:18.916Z
---

2026-09-13, 사용자가 사이트(pareido.jp)를 보고 **닌텐도 DS 컨셉**을 원했고, 두 안 중
**"Mesen + 별도 창"** 을 골랐다(BizHawk 이사는 안 함). 게임 화면은 깨끗하게 두고
두 번째 창에 구역 지도·표식·한글 범례·층 번호를 그린다.

작업폴더: **실행은 `ds_bridge.lua`(Mesen, 포트 9876) + `mt1_ds_window.py`(tkinter 창, 지도 계산 포함) 두 개**와
롬 파일 하나. `ds_selftest.py` 는 검사 전용. 원래 따로 있던 `mt1map.py` 는 사용자 요청으로 창 파일에 합쳤다
(기대 숫자 확인: `python mt1_ds_window.py [롬] --check`).
사용자는 **나중에 안드로이드에서도 실험**해 볼 생각이다 — 그때 Mesen·tkinter 둘 다 안드로이드에 없다는 점부터 볼 것.
자세한 표는 작업폴더 `mt1-hangul-memory.md` 「DS 컨셉 두 번째 화면」 절.

**Why:** Mesen 은 `emu.drawString` 이 깨져 화면에 글자를 못 쓰고, 지도가 게임을 가렸다.
별도 창이면 한글이 되고 겹침도 없다. 사용자는 Mesen 을 계속 쓰고 싶어 한다.

**How to apply:**
- 검증은 `python ds_selftest.py` 부터. 헤드리스 Mesen 에서도 LuaSocket 이 돌아 종단 테스트가 자동으로 된다
- 창 레이아웃은 `--snapshot` 으로 PNG 를 뽑아 **눈으로** 확인한 뒤 고칠 것 (창을 사용자 화면에 띄우지 말 것)
- Mesen `settings.json` 의 `ScriptWindow.AllowNetworkAccess` 가 true 여야 한다
- 범위를 키우지 말 것 — 사용자가 규모 커지는 걸 싫어한다([[mt1-pareido-automap]])
- 관련: [[mt1-hangul-project]], [[bizhawk-second-screen]]
