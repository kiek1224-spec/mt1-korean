-- 여신전생 1 DS 브리지  -- Mesen 2 전용
--
-- 두 번째 화면 창(mt1_ds_window.py)에 **파티 위치와 가는 방향만** 보낸다.
-- 지도·표식 계산과 그리기는 전부 창 쪽(파이썬)이 한다. 게임 화면에는 아무것도 안 그린다.
--
-- 쓰는 법
--   1) Mesen 에서 Debug > Script Window 로 이 파일을 열고 실행(F5)
--   2) python mt1_ds_window.py   (순서는 상관없다. 창이 알아서 다시 붙는다)
--
-- 통신
--   127.0.0.1:9876 에서 기다린다 (DebugServer_gui.lua 의 9999 와 안 겹치게).
--   한 줄에 JSON 하나:  {"x":15,"y":24,"dx":1,"dy":0}
--   값이 바뀔 때 보내고, 안 바뀌어도 60프레임마다 한 번 보낸다(창이 "멈춤"을 알아채게).
--   ★endFrame 콜백 안에서 보내므로 **Mesen 이 일시정지면 아무것도 안 간다.**
--
-- 근거
--   LuaSocket 은 MesenCore.dll 안에 package.preload["socket.core"] 로 들어 있다
--   (DebugServer_gui.lua, 2026-09-03 실측). 소켓을 못 불러오면 Script Window 설정에서
--   네트워크/입출력 접근을 허용해야 한다.
--   $0780 = X, $0781 = Y, $04AB/$04AC = 이번 걸음의 dX/dY (부호 있는 1바이트, automap.lua 참고)

local PORT = 9876
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

local clients = {}
local last, frame = "", 0

local function s8(v) if v >= 128 then return v - 256 end return v end

local function closeAll()
  for _, c in ipairs(clients) do pcall(function() c:close() end) end
  clients = {}
  pcall(function() server:close() end)
end

emu.addEventCallback(function()
  frame = frame + 1

  local c = server:accept()
  if c then
    c:settimeout(0)
    clients[#clients + 1] = c
    last = ""                                      -- 새로 붙은 창에는 바로 한 번 보낸다
  end
  if #clients == 0 then return end

  local msg = string.format('{"x":%d,"y":%d,"dx":%d,"dy":%d}\n',
    emu.read(0x0780, RAM), emu.read(0x0781, RAM),
    s8(emu.read(0x04AB, RAM)), s8(emu.read(0x04AC, RAM)))

  if msg ~= last or frame % 60 == 0 then
    for i = #clients, 1, -1 do
      local _, err = clients[i]:send(msg)
      if err and err ~= "timeout" then               -- 창이 닫혔다
        pcall(function() clients[i]:close() end)
        table.remove(clients, i)
      end
    end
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
