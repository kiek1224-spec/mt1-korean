---
name: powershell-utf8-trap
description: PowerShell 로 한글 든 파일을 치환하면 깨지고 줄까지 붙는다 - Write 도구를 쓸 것
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 78197005-a275-43e3-a636-a0b18e7cd816
  modified: 2026-09-12T17:19:29.312Z
---

Windows PowerShell 5.1 에서
`(Get-Content f -Raw) -replace 'a','b' | Set-Content f -Encoding utf8`
로 **한글 주석이 든 소스를 고치면 안 된다.** 실제로 두 가지가 동시에 터졌다:
1. 한글이 전부 모지바케가 됐다.
2. **주석 줄과 다음 줄이 하나로 붙었다** (`# ...고른다func foo():`) — 문법 오류.

**How to apply:** 파일 내용 수정은 항상 Edit / Write 도구로 한다. PowerShell 은
명령 실행용으로만 쓴다. 스크립트를 인라인으로 넘길 때도 here-string 이 `%` 서식
문자열을 파서 오류로 만드니(`print("%-14s" ...)`) **파일로 써서 실행**할 것.

**Why:** 이 프로젝트 소스는 주석이 전부 한글이라 정면으로 걸린다.
[[smb1-godot-port]] 작업 중 실제로 두 파일을 날려 다시 썼다.
