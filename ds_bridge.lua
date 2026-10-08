-- 여신전생 1 DS 브리지  -- Mesen 2 전용
--
-- 두 번째 화면 창(mt1_ds_window.py)에 **파티 위치·가는 방향·층과 MAG·마카·구슬**을 보내고,
-- 창이 시키면 **패스워드 입력 화면에서 대신 친다**. 지도·패스워드 계산과 그리기는 전부 창 쪽(파이썬)이 한다.
-- 게임 화면에는 아무것도 안 그린다.
--
-- 쓰는 법
--   1) Mesen 에서 Debug > Script Window 로 이 파일을 열고 실행(F5)
--   2) python mt1_ds_window.py   (순서는 상관없다. 창이 알아서 다시 붙는다)
--
-- 통신 (127.0.0.1:9876, DebugServer_gui.lua 의 9999 와 안 겹치게)
--   브리지 -> 창, 한 줄에 JSON 하나
--     {"x":15,"y":24,"dx":1,"dy":0,"f":1,"m":4321,"g":1234,"o":7,"p":0}
--       f = 층 $055D (9 = 지하 1층, 10 = 지하 2층), m = 마카 $0550/1, g = MAG $0554/5, o = 구슬 $0553,
--       p = 1 이면 패스워드 입력 화면, w = $07FF bit7 (裏 시나리오: 다이달로스 탑의 가게·샘·사교의 관 등이 자리를 옮긴다 —
--       지도 레이어 $16 의 조건 비트, mt1_ds_window.py 「FLAG_W」 설명). 값이 바뀔 때 보내고, 안 바뀌어도 60프레임마다 한 번.
--       bs = 보스 처치 깃발 $065E (블록 세트 $0782 마다 비트 하나. 2026-10-05 — 로키를 이기면 그 칸이 텔레포트가 된다,
--       mt1_ds_window.py 「_build_bosses」 설명).
--       b = 1 이면 전투 중($0690). 그때만 eg = 지금 그룹 $0652, ek = 그룹 4개의 종류 $0610~, ec = 마릿수 $060C~,
--       hp = 적 HP 8칸 $061C+2i (2026-10-04, 뜻은 mt1_ds_window.py 「1-3. 적 악마 정보」). 전투 밖에서는 "b":0 만.
--       ★$060C~ 는 패스워드 입력 화면에서는 입력 칸으로 쓰인다 — 반드시 b 로 걸러서 읽을 것.
--     {"ram":"<2KB 16진>"}                        RAM 요청에 대한 답
--     {"pw":"typing","done":12,"total":31}        자동 입력 진행 / 끝: accepted rejected lost stuck stopped
--   창 -> 브리지, 한 줄에 명령 하나
--     RAM                                         지금 RAM 2KB 를 보내 달라
--     TYPE 3:2,12:155,...                         입력판 칸:글자번호 목록대로 입력하고 START (끝에 빈칸 0:189 포함)
--     STOP                                        자동 입력 그만
--   ★endFrame 콜백 안에서 보내고 받으므로 **Mesen 이 일시정지면 아무것도 안 간다.**
--
-- 근거
--   LuaSocket 은 MesenCore.dll 안에 package.preload["socket.core"] 로 들어 있다
--   (DebugServer_gui.lua, 2026-09-03 실측). 소켓을 못 불러오면 Script Window 설정에서
--   네트워크/입출력 접근을 허용해야 한다.
--   $0780 = X, $0781 = Y, $04AB/$04AC = 이번 걸음의 dX/dY (부호 있는 1바이트, automap.lua 참고)
--   $055D = 층. 계단($FB11 올라감: 9 -> 1 그 밖 +1 / $FBBB 내려감: 1 -> 9, 9 -> 10 그 밖 -1)·이음매($F856)·
--           텔레포트($FC24 근처)가 쓴다. 던전 안에서 플레이한 세이브는 층표 층과 전부 같았다(특수 구역 세이브는 없음).
--   마카·구슬·MAG = 상태 화면($B9F3~, 뱅크 1)이 그리는 값. 2026-10-03 값을 넣어 화면의 「MAG」「구슬」「마카」와 대조했다.
--   패스워드 입력 화면 = 입력 루프 $A731 (뱅크 7). 커서 $C2(0~16)·$C3(0/3 = 줄), 위치 $C8, 칸 $060C~(40),
--   스택에 복귀주소 $A733 이 [33 A7] 로 남는다. 칸 -> 글자 번호 표는 PRG $E9D8(원판·한글판 같음).
--   ★A 처리 루틴은 안에서 화면을 한 번 기다려 그 프레임엔 복귀주소가 덮인다 -> 감지가 잠깐 거짓이 될 수 있다.
--   ★setInput 은 inputPolled 에서 불러야 먹는다(endFrame 에서 부르면 오류 없이 무시 — mrun.py 머리말).

-- 헤드리스 시험은 DS_BRIDGE_PORT 를 먼저 정해 다른 포트를 쓴다(사용자가 켜 둔 Mesen 의 9876 에 붙지 않게 — 2026-10-03 실제로 붙었다)
local PORT = DS_BRIDGE_PORT or 9876
local RAM  = emu.memType.nesMemory

local okS, socket = pcall(require, "socket.core")
if not okS then
  emu.displayMessage("DS", "소켓을 못 불러왔다 - Script Window 설정에서 네트워크 접근을 허용할 것")
  return
end

local server = assert(socket.tcp())
pcall(function() server:setoption("reuseaddr", true) end)
local okB, errB = server:bind("127.0.0.1", PORT)
if not okB then
  emu.displayMessage("DS", "포트 " .. PORT .. " 을 못 열었다: " .. tostring(errB))
  return
end
server:listen(4)
server:settimeout(0)

local clients, partial = {}, {}
local last, frame = "", 0

local function rd(a) return emu.read(a, RAM) end
local function s8(v) if v >= 128 then return v - 256 end return v end

local function closeAll()
  for _, c in ipairs(clients) do pcall(function() c:close() end) end
  clients = {}
  pcall(function() server:close() end)
end

local function sendAll(msg)
  for i = #clients, 1, -1 do
    local _, err = clients[i]:send(msg)
    if err and err ~= "timeout" then                 -- 창이 닫혔다
      pcall(function() clients[i]:close() end)
      partial[clients[i]] = nil
      table.remove(clients, i)
    end
  end
end

-- ── 패스워드 입력 화면 감지 (mt1_ds_window.py 의 is_input_screen 과 같은 규칙) ──
local VALID = {}
for i = 0, 33 do VALID[emu.read(0xE9D8 + i, emu.memType.nesPrgRom)] = true end

local function onInputScreen()
  local row = rd(0xC3)
  if (row ~= 0 and row ~= 3) or rd(0xC2) > 16 or rd(0xC8) >= 40 or rd(0xC9) > 1 then return false end
  for i = 0, 39 do if not VALID[rd(0x60C + i)] then return false end end
  for a = 0x100, 0x1FD do if rd(a) == 0x33 and rd(a + 1) == 0xA7 then return true end end
  return false
end

-- ── 자동 입력 (웹판 password.js 의 Typer 와 같은 판단) ──────────────────────
-- 프레임이 끝날 때마다 RAM 을 보고 다음 프레임에 누를 버튼을 정한다. 누른 다음 프레임은 반드시 뗀다
-- (게임이 'A 를 뗐다'·'방향키를 뗐다'를 봐야 다음 입력을 받는다).
local ty = nil            -- { cells, tiles, state, rest, sig, idle, miss, after, left, done, total }
local pressNext = nil

local function typerStep()
  local here = onInputScreen()
  if ty.state == "submitted" then                    -- START 뒤: 계속 벗어나 있으면 받아 줌, 되돌아오면 거부
    ty.after = ty.after + 1
    if not here then
      ty.left = ty.left + 1
      if ty.left > 120 then ty.state = "accepted" end
    elseif ty.left > 10 then ty.state = "rejected" end
    if ty.after > 400 then ty.state = (ty.left > 0) and "accepted" or "rejected" end
    return nil
  end
  if ty.state ~= "typing" then return nil end
  if not here then
    ty.miss = ty.miss + 1
    if ty.miss > 30 then ty.state = "lost" end
    return nil
  end
  ty.miss = 0
  if ty.rest > 0 then ty.rest = ty.rest - 1; return nil end
  local pos = rd(0xC8)
  local cell = rd(0xC2) + ((rd(0xC3) ~= 0) and 17 or 0)
  local buf = {}
  for i = 0, 39 do buf[i + 1] = rd(0x60C + i) end
  local sig = pos .. ":" .. cell .. ":" .. table.concat(buf, ",")
  if sig == ty.sig then
    ty.idle = ty.idle + 1
    if ty.idle > 60 then ty.state = "stuck"; return nil end
  else ty.sig = sig; ty.idle = 0 end
  local i = 0
  while i < #ty.tiles and buf[i + 1] == ty.tiles[i + 1] do i = i + 1 end
  ty.done = math.min(i, ty.total)
  ty.rest = 1
  if i >= #ty.tiles then ty.state = "submitted"; return "start" end
  if pos ~= i then return (pos < i) and "up" or "b" end
  local want = ty.cells[i + 1]
  if cell == want then ty.rest = 2; return "a" end   -- 쓰기와 다음 칸 이동이 끝나게 한 프레임 더 쉰다
  return (((want - cell + 34) % 34) <= 17) and "right" or "left"
end

local function handle(line)
  local cmd, arg = line:match("^(%u+)%s*(.*)$")
  if cmd == "RAM" then
    local hex = {}
    for a = 0, 0x7FF do hex[#hex + 1] = string.format("%02x", rd(a)) end
    sendAll('{"ram":"' .. table.concat(hex) .. '"}\n')
  elseif cmd == "TYPE" then
    local cells, tiles = {}, {}
    for c, t in arg:gmatch("(%d+):(%d+)") do cells[#cells + 1] = tonumber(c); tiles[#tiles + 1] = tonumber(t) end
    local total = #cells
    if total > 0 and cells[total] == 0 then total = total - 1 end
    ty = { cells = cells, tiles = tiles, state = "typing", rest = 0, sig = "", idle = 0, miss = 0,
           after = 0, left = 0, done = 0, total = total }
  elseif cmd == "STOP" and ty then
    ty.state = "stopped"
  end
end

emu.addEventCallback(function()
  if pressNext then emu.setInput({ [pressNext] = true }, 0) end
end, emu.eventType.inputPolled)

-- ── 전투 정보 (2026-10-04) ── 창이 지도 대신 적 카드를 그린다. 뜻은 mt1_ds_window.py 「1-3. 적 악마 정보」.
--   $0690 전투 중 1 / $0652 지금 그룹 / $0610+g 종류 / $060C+g 마릿수 / $061C+2i HP 8칸(16비트)
local function battleJson()
  if rd(0x0690) ~= 1 then return '"b":0' end
  local ks, cs, hs = {}, {}, {}
  for i = 0, 3 do ks[#ks + 1] = rd(0x0610 + i); cs[#cs + 1] = rd(0x060C + i) end
  for i = 0, 7 do hs[#hs + 1] = rd(0x061C + 2 * i) + rd(0x061D + 2 * i) * 256 end
  return string.format('"b":1,"eg":%d,"ek":[%s],"ec":[%s],"hp":[%s]', rd(0x0652),
    table.concat(ks, ","), table.concat(cs, ","), table.concat(hs, ","))
end

emu.addEventCallback(function()
  frame = frame + 1

  local c = server:accept()
  if c then
    c:settimeout(0)
    clients[#clients + 1] = c
    last = ""                                      -- 새로 붙은 창에는 바로 한 번 보낸다
  end

  -- 창이 보낸 명령 (한 줄씩, 덜 온 줄은 다음 프레임에 이어 받는다)
  for _, cl in ipairs(clients) do
    while true do
      local line, err, part = cl:receive("*l", partial[cl])
      if line then partial[cl] = nil; handle(line)
      else partial[cl] = (part ~= "" and part) or partial[cl]; break end
    end
  end

  -- 자동 입력: 다음 프레임에 누를 버튼을 정하고 진행을 알린다
  pressNext = nil
  if ty then
    local before = ty.state
    pressNext = typerStep()
    if ty.state ~= "typing" and ty.state ~= "submitted" then
      sendAll(string.format('{"pw":"%s","done":%d,"total":%d}\n', ty.state, ty.done, ty.total))
      ty = nil
    elseif frame % 15 == 0 or ty.state ~= before then
      sendAll(string.format('{"pw":"%s","done":%d,"total":%d}\n', ty.state, ty.done, ty.total))
    end
  end

  if #clients == 0 then return end

  local msg = string.format('{"x":%d,"y":%d,"dx":%d,"dy":%d,"f":%d,"m":%d,"g":%d,"o":%d,"p":%d,"w":%d,"bs":%d,%s}\n',
    rd(0x0780), rd(0x0781), s8(rd(0x04AB)), s8(rd(0x04AC)), rd(0x055D),
    rd(0x0550) + rd(0x0551) * 256, rd(0x0554) + rd(0x0555) * 256, rd(0x0553), onInputScreen() and 1 or 0,
    (rd(0x07FF) >= 0x80) and 1 or 0, rd(0x065E), battleJson())

  if msg ~= last or frame % 60 == 0 then
    sendAll(msg)
    last = msg
  end
end, emu.eventType.endFrame)

-- 스크립트를 다시 실행할 때 포트가 붙잡혀 있지 않게 닫는다
if emu.eventType.scriptEnded then
  emu.addEventCallback(closeAll, emu.eventType.scriptEnded)
end

-- 헤드리스 검증이 읽는 자리
DS_BRIDGE_INFO = { port = PORT, listening = 1 }

emu.displayMessage("DS", "DS 브리지 대기 중 (포트 " .. PORT .. ") - mt1_ds_window.py 를 실행하세요")
