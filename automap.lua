-- 여신전생 1 (NES) 던전 자동지도  -- Mesen 2 전용
--
-- 쓰는 법
--   Mesen 에서  Debug > Script Window  를 열고 이 파일을 Open 한 뒤 실행(F5).
--   던전에 들어가면 **지금 있는 구역**의 지도가 화면 귀퉁이에 겹쳐 그려진다.
--
--   M = 켜기/끄기      N = 위치(네 귀퉁이) 옮기기      V = 표식 켜기/끄기
--
--   ★X·Z 는 게임 조작키라 쓰지 않는다(사용자 보고 2026-09-13).
--
--   표식 (모양으로도 구별되게 그린다)
--     노랑 꽉 찬 네모 = 올라가는 계단      파랑 꽉 찬 네모 = 내려가는 계단
--     초록 꽉 찬 네모 = 엘리베이터
--     주황 속 빈 네모 = 보물상자
--     분홍 점         = 대화 NPC (상점·회복의 샘·사교의 관·장로 포함)
--     빨강 ✕          = 고정 전투 (밟으면 반드시 시작 - 보스 자리 포함)
--     보라 꽉 찬 마름모 = 텔레포트 칸 (밟으면 순간이동)
--     보라 속 빈 마름모 = 텔레포트 도착 칸
--     흰 선 = 벽 / 하늘 선 = 문 / 주황빨강 네모와 화살표 = 나와 가는 쪽
--
--   ★화면에 글자는 하나도 안 찍는다. `emu.drawString` 이 실기에서 화면 왼쪽에 글자를
--     세로로 흘리고 지도 밖 게임 화면에까지 찍혔다(사용자 보고 2026-09-12).
--
-- ─────────────────────────────────────────────────────────────────────────────
-- 레이어의 뜻 (2026-09-13)
--   어느 레이어가 무엇인지는 pareido.jp 의 브라우저 NES 에뮬레이터(「ダンジョン自動マップ」)
--   지도 코드에서 단서를 얻었다. 그 코드도 우리와 같은 표(지도 $14004, 포인터표 $12AF5)를
--   읽는다. 코드는 옮기지 않았고, 형식은 **전부 우리 롬으로 다시 검증**했다.
--
--   포인터표: 뱅크$09 $AAF5, 블록 6개 x 포인터 14개. 레이어id = 포인터번호*2.
--   각 표는 $FF 또는 **다음 포인터 주소**에서 끝난다.
--     레이어 $0A  5바이트 [X][Y|플래그][도착X][도착Y][구역]
--                 = 내려가는 계단, 도착지 = 올라가는 계단
--                 (검증: 도착지 72곳 전부 레이어 $08 출발점과 ±1 안에서 맞물린다)
--     레이어 $10  앞에 길이 바이트, 그 뒤 4바이트 [X][Y|플래그][탑][층]
--                 = 엘리베이터가 서는 칸. $FCB7 이 칸 속성을 볼 때 이걸 조회한다.
--                 (검증: 층 값이 층표 상위 4비트와 23/25 일치)
--     레이어 $16  6바이트 [X][Y|플래그][종류][..][..][..]
--                 종류 32 = 보물상자, 그 밖 = 대화 칸 (28 회복의 샘 / 1 사교의 관 / 4 상점 /
--                 15 장로 도 대화 칸으로 묶는다). ★5바이트로 읽으면 쓰레기가 나온다.
--     레이어 $14  3바이트 [X][Y|플래그][값] = 고정 전투
--     레이어 $0E  6바이트 [X][Y|플래그][도착X][도착Y][도착블록][도착층] = 텔레포트 (2026-09-14)
--                 ★이것은 **게임 코드로 확인**했다: 고정뱅크 $FC3A `LDA #$0E / LDY #$04 / JSR $F51B`
--                 가 지금 칸을 표에서 찾고, 있으면 뒤 4바이트를 $0780(X) $0781(Y) $0782(블록)
--                 $055D(층)에 넣는다. 47곳. 마지막 바이트 = 도착 칸 층표의 층 45/47
--                 (안 맞는 2곳은 도착 칸 층표가 0 = 특수 구역).
--   ★$16·$14 의 **형식**(칸 수·지도 범위)은 검증했지만, "상자·대화·고정전투"라는 **뜻**은
--     사이트 해석이고 우리가 게임 속에서 확인한 것은 아니다.
--   겹치는 칸은: 상자·대화 -> 엘리베이터 -> 계단이 덮어쓰고, 그 뒤 텔레포트 출발 -> 도착 ->
--   고정 전투 순서로 빈 칸에만 찍는다(텔레포트 칸과 겹치는 고정 전투 1곳은 텔레포트로 보인다).
--
-- 층표 (고정뱅크 CPU $CB7D, 16x8 = 8x8 블록마다 1바이트)
--   상위 4비트 = 층, 하위 4비트 = 탑. 게임도 $CA69 `LDA $CB7D,X / LSR x4 / CMP $055D`
--   로 현재 층($055D)과 비교한다. 원판과 한글판이 같다.
--   ★고정뱅크는 PRG 끝에서 두 번째 8KB 라 롬 크기에 따라 PRG 주소가 다르다
--     (원판 128KB -> $1CB7D, 한글판 256KB -> $3CB7D).
--
-- 구역
--   1) 걸어서 오갈 수 있는 칸을 묶는다. 두 칸 사이는 **양쪽 기록이 다 뚫림(0)이나 문(3)**일
--      때만 잇는다(한쪽만 보면 99.1% 불일치 자리로 새어 넘는다).
--   2) 층표 바이트가 다른 블록 사이는 잇지 않는다(지도에선 붙어 있어도 게임 속에선 다른 층).
--   3) 그 묶음이 닿는 8x8 블록들 = 화면에 보여 줄 구역.
--
-- 지도 (2026-09-08 역어셈블·실측으로 확정)
--   PRG 뱅크 $0A. 읽는 코드는 고정뱅크 $CAA4~$CAD9:  주소 = $8004 + X + Y*$80  (128 x 64)
--   한 칸 = 1바이트, 2비트씩: 비트0-1 서 / 2-3 남 / 4-5 동 / 6-7 북.  0 뚫림 / 1 벽 / 3 문
--   ★한글패치는 뱅크 $0A 를 한 바이트도 안 건드린다.
--
-- 위치와 방향
--   $F018 LDA $0780 / ADC $04AB / STA $0780   -> $0780 = X,  $04AB = 이번 걸음의 dX
--   $F025 LDA $0781 / ADC $04AC / STA $0781   -> $0781 = Y,  $04AC = 이번 걸음의 dY
--   게임이 실제로 더하는 dX/dY(부호 있는 1바이트)로 화살표를 그린다.

local PRG_MAP      = 0x14004        -- 지도 시작 (파일 $14014 - 헤더 16)
local MAP_W, MAP_H = 128, 64
local BLK          = 8              -- 구역을 맞추는 격자
local BCOLS        = MAP_W // BLK   -- 16
local MAXPX        = 96             -- 지도 상자 한 변 최대 픽셀

local ADDR_X, ADDR_Y   = 0x0780, 0x0781
local ADDR_DX, ADDR_DY = 0x04AB, 0x04AC

local C_BACK, C_WALL, C_DOOR, C_EDGE = 0x000000, 0xE8E8F0, 0x40B4FF, 0x303048
local C_ME                            = 0xFF6040

local KIND_UP, KIND_DOWN, KIND_ELEV, KIND_CHEST, KIND_NPC, KIND_FIGHT = 1, 2, 3, 4, 5, 6
local KIND_WARP, KIND_WARPTO = 7, 8
-- {색, 모양}  모양: fill 꽉 찬 네모 / box 속 빈 네모 / dot 점 / cross ✕ / diamond 마름모 / odiamond 속 빈 마름모
local KIND_STYLE = {
  [KIND_UP]     = {0xFFE040, "fill"},
  [KIND_DOWN]   = {0x4070FF, "fill"},
  [KIND_ELEV]   = {0x40E080, "fill"},
  [KIND_CHEST]  = {0xFF9020, "box"},
  [KIND_NPC]    = {0xFF70D0, "dot"},
  [KIND_FIGHT]  = {0xFF3030, "cross"},
  [KIND_WARP]   = {0xB070FF, "diamond"},
  [KIND_WARPTO] = {0xB070FF, "odiamond"},
}

local PRG = emu.memType.nesPrgRom
local RAM = emu.memType.nesMemory

local show, corner, showMarks = true, 0, true
local prevM, prevN, prevV     = false, false, false

-- ── 지도 읽기 (롬이라 한 번만) ─────────────────────────────────────────────
local MAP = {}
for i = 0, MAP_W * MAP_H - 1 do MAP[i] = emu.read(PRG_MAP + i, PRG) end

-- ── 층표 ($CB7D) ─────────────────────────────────────────────────────────
-- 롬 크기를 후보로 대 보고 **층표로서 말이 되는 쪽**을 고른다(FF 가 하나도 없어야 한다).
-- 원판에서 한글판 주소를 읽으면 범위 밖이고, 한글판에서 원판 주소를 읽으면 전부 FF 다.
local function readFloorTable(prgsz)
  local base = prgsz - 0x4000 + (0xCB7D - 0xC000)
  local t, ff, zero = {}, 0, 0
  for i = 0, 127 do
    local v = emu.read(base + i, PRG)
    t[i] = v
    if v == 0xFF then ff = ff + 1 end
    if v == 0x00 then zero = zero + 1 end
  end
  if ff > 0 or zero > 32 then return nil end
  return t
end

local floorTbl = nil
do
  local cands = {}
  local ok, n = pcall(emu.getMemorySize, PRG)
  if ok and type(n) == "number" and n > 0 then cands[#cands + 1] = n end
  for _, s in ipairs({0x40000, 0x20000, 0x80000}) do cands[#cands + 1] = s end
  for _, s in ipairs(cands) do
    local ok2, t = pcall(readFloorTable, s)
    if ok2 and t then floorTbl = t break end
  end
end

local function blockOf(x, y) return (y // BLK) * BCOLS + x // BLK end
local function sameFloor(x, y, nx, ny)
  if not floorTbl then return true end          -- 층표를 못 찾으면 벽만으로 나눈다
  return floorTbl[blockOf(x, y)] == floorTbl[blockOf(nx, ny)]
end

-- 면 번호 0=서 1=남 2=동 3=북 (비트 자리 = 번호*2)
local DX  = {[0] = -1, 0, 1, 0}
local DY  = {[0] = 0, 1, 0, -1}
local OPP = {[0] = 2, 3, 0, 1}
local function sideOf(c, s) return (c >> (s * 2)) & 3 end
local function passable(v) return v == 0 or v == 3 end

-- ── 구역 계산 ─────────────────────────────────────────────────────────────
local comp       = {}   -- [칸번호] = 묶음 번호
local compN      = {}   -- [묶음] = 칸 수
local compBlocks = {}   -- [묶음] = { [블록번호] = true }
local compBox    = {}   -- [묶음] = {x0, y0, x1, y1}  8격자에 맞춘 상자(x1,y1 은 끝+1)
local ncomp      = 0

for i = 0, MAP_W * MAP_H - 1 do comp[i] = -1 end
for sy = 0, MAP_H - 1 do
  for sx = 0, MAP_W - 1 do
    local si = sy * MAP_W + sx
    if comp[si] < 0 then
      local cid = ncomp
      ncomp = ncomp + 1
      comp[si] = cid
      local stack, top = {si}, 1
      local n, x0, y0, x1, y1 = 0, sx, sy, sx, sy
      local blocks = {}
      while top > 0 do
        local i = stack[top]
        stack[top] = nil
        top = top - 1
        local x, y = i % MAP_W, i // MAP_W
        n = n + 1
        if x < x0 then x0 = x end
        if y < y0 then y0 = y end
        if x > x1 then x1 = x end
        if y > y1 then y1 = y end
        blocks[blockOf(x, y)] = true
        local c = MAP[i]
        for s = 0, 3 do
          local nx, ny = x + DX[s], y + DY[s]
          if nx >= 0 and nx < MAP_W and ny >= 0 and ny < MAP_H then
            local j = ny * MAP_W + nx
            if comp[j] < 0 and passable(sideOf(c, s)) and passable(sideOf(MAP[j], OPP[s]))
               and sameFloor(x, y, nx, ny) then
              comp[j] = cid
              top = top + 1
              stack[top] = j
            end
          end
        end
      end
      compN[cid] = n
      compBlocks[cid] = blocks
      compBox[cid] = {x0 - x0 % BLK, y0 - y0 % BLK, (x1 // BLK + 1) * BLK, (y1 // BLK + 1) * BLK}
    end
  end
end

-- ── 레이어 표 ─────────────────────────────────────────────────────────────
local PTRTBL = 0x12AF5          -- 뱅크$09 의 $AAF5
local ptrs, uniq = {}, {}
do
  local seen = {}
  for i = 0, 6 * 14 - 1 do
    local p = emu.read(PTRTBL + i * 2, PRG) | (emu.read(PTRTBL + i * 2 + 1, PRG) << 8)
    ptrs[i] = p
    if not seen[p] then seen[p] = true; uniq[#uniq + 1] = p end
  end
  table.sort(uniq)
end
local function nextPtr(p)
  for _, u in ipairs(uniq) do if u > p then return u end end
  return p + 64
end
-- 포인터는 CPU $8000~$BFFF(뱅크$08/$09). 두 뱅크 모두 PRG 주소 = CPU + $8000 이다.
local function rdc(cpu) return emu.read(cpu + 0x8000, PRG) end

-- 6블록의 레이어 lid 표를 훑는다. 끝은 $FF 또는 다음 포인터.
local function eachEntry(lid, stride, skipLen, fn)
  for b = 0, 5 do
    local w = ptrs[b * 14 + (lid >> 1)]
    if w >= 0x8000 and w < 0xC000 then
      local stop = nextPtr(w)
      local k = w
      if skipLen then k = k + 1 + rdc(w) end
      while k <= stop - stride do
        local x = rdc(k)
        if x == 0xFF then break end
        fn(x, rdc(k + 1) & 0x3F, k)
        k = k + stride
      end
    end
  end
end

local marks = {}                -- ["x,y"] = {x, y, 종류}
local function key(x, y) return x .. "," .. y end
local function inMap(x, y) return x < MAP_W and y < MAP_H end

-- 겹치는 칸의 우선순위는 불러오는 순서로 정한다 (위 설명 참조).
eachEntry(0x16, 6, false, function(x, y, k)             -- 보물상자 / 대화 (같은 칸은 먼저 나온 것)
  if inMap(x, y) and not marks[key(x, y)] then
    marks[key(x, y)] = {x, y, rdc(k + 2) == 32 and KIND_CHEST or KIND_NPC}
  end
end)
eachEntry(0x10, 4, true, function(x, y)                 -- 엘리베이터
  if inMap(x, y) then marks[key(x, y)] = {x, y, KIND_ELEV} end
end)
eachEntry(0x0A, 5, false, function(x, y, k)             -- 내려가는 계단 -> 도착지는 올라가는 계단
  local tx, ty = rdc(k + 2), rdc(k + 3)
  if inMap(x, y) then marks[key(x, y)] = {x, y, KIND_DOWN} end
  if inMap(tx, ty) then
    local m = marks[key(tx, ty)]
    if not (m and m[3] == KIND_DOWN) then marks[key(tx, ty)] = {tx, ty, KIND_UP} end
  end
end)
eachEntry(0x0E, 6, false, function(x, y)                -- 텔레포트 칸 (빈 칸에만)
  if inMap(x, y) and not marks[key(x, y)] then marks[key(x, y)] = {x, y, KIND_WARP} end
end)
eachEntry(0x0E, 6, false, function(x, y, k)             -- 텔레포트 도착 칸 (출발 칸을 다 찍은 뒤, 빈 칸에만)
  local tx, ty = rdc(k + 2), rdc(k + 3) & 0x3F
  if inMap(tx, ty) and not marks[key(tx, ty)] then marks[key(tx, ty)] = {tx, ty, KIND_WARPTO} end
end)
eachEntry(0x14, 3, false, function(x, y)                -- 고정 전투는 빈 칸에만
  if inMap(x, y) and not marks[key(x, y)] then marks[key(x, y)] = {x, y, KIND_FIGHT} end
end)

-- ★세는 것은 완성된 표를 훑어서 한다(같은 칸이 두 번 나오는 자리에서 어긋나지 않게).
local count = {}
for k = KIND_UP, KIND_WARPTO do count[k] = 0 end
for _, m in pairs(marks) do count[m[3]] = count[m[3]] + 1 end
local nbig = 0
for cid = 0, ncomp - 1 do
  if compN[cid] >= 4 then nbig = nbig + 1 end
end

-- 헤드리스 검증이 계산 결과를 읽어 파이썬 분석과 맞춰 보는 자리
AUTOMAP_INFO = { comps = ncomp, bigComps = nbig, up = count[KIND_UP], down = count[KIND_DOWN],
                 elev = count[KIND_ELEV], chest = count[KIND_CHEST], npc = count[KIND_NPC],
                 fight = count[KIND_FIGHT], warp = count[KIND_WARP], warpTo = count[KIND_WARPTO],
                 floorTable = floorTbl and 1 or 0 }

-- ── 그리기 ────────────────────────────────────────────────────────────────
local function s8(v) if v >= 128 then return v - 256 end return v end

-- 표식 한 칸. 글자 대신 모양으로 그린다.
local function mark(X, Y, cell, kind)
  local col, shape = KIND_STYLE[kind][1], KIND_STYLE[kind][2]
  local s = cell - 2
  if s < 2 then s = 2 end
  if shape == "fill" then
    emu.drawRectangle(X + 1, Y + 1, s, s, col, true, 1)
  elseif shape == "box" then
    emu.drawRectangle(X + 1, Y + 1, s, s, col, false, 1)
  elseif shape == "dot" then
    local c = cell // 2
    emu.drawRectangle(X + c - 1, Y + c - 1, 3, 3, col, true, 1)
  elseif shape == "diamond" or shape == "odiamond" then
    local c = cell // 2
    local r = math.max(1, c - 1)
    local cx, cy = X + c, Y + c
    if shape == "diamond" then
      for d = -r, r do
        local half = r - math.abs(d)
        emu.drawLine(cx - half, cy + d, cx + half, cy + d, col, 1)
      end
    else
      emu.drawLine(cx, cy - r, cx + r, cy, col, 1)
      emu.drawLine(cx + r, cy, cx, cy + r, col, 1)
      emu.drawLine(cx, cy + r, cx - r, cy, col, 1)
      emu.drawLine(cx - r, cy, cx, cy - r, col, 1)
    end
  else                                                 -- cross
    emu.drawLine(X + 1, Y + 1, X + cell - 1, Y + cell - 1, col, 1)
    emu.drawLine(X + cell - 1, Y + 1, X + 1, Y + cell - 1, col, 1)
  end
end

-- 칸 가운데에 삼각형 화살표. dx,dy 는 -1/0/1.
local function arrow(cx, cy, dx, dy, r, col)
  if dx == 0 and dy == 0 then
    emu.drawRectangle(cx - 1, cy - 1, 3, 3, col, true, 1)
    return
  end
  local tipx, tipy = cx + dx * r, cy + dy * r
  local bx, by = cx - dx * r, cy - dy * r
  local px, py = -dy, dx
  emu.drawLine(tipx, tipy, bx + px * r, by + py * r, col, 1)
  emu.drawLine(tipx, tipy, bx - px * r, by - py * r, col, 1)
  emu.drawLine(bx + px * r, by + py * r, bx - px * r, by - py * r, col, 1)
end

local function draw()
  if not show then return end
  local px = emu.read(ADDR_X, RAM)
  local py = emu.read(ADDR_Y, RAM)
  if px >= MAP_W or py >= MAP_H then return end      -- 마을·전투·메뉴
  local dx = s8(emu.read(ADDR_DX, RAM))
  local dy = s8(emu.read(ADDR_DY, RAM))

  local cid = comp[py * MAP_W + px]
  local box, blocks = compBox[cid], compBlocks[cid]
  local bx0, by0 = box[1], box[2]
  local w, h = box[3] - bx0, box[4] - by0

  local cell = MAXPX // math.max(w, h)
  if cell > 8 then cell = 8 end
  if cell < 3 then cell = 3 end
  local bw, bh = w * cell, h * cell
  local CO = { {6, 6}, {256 - bw - 7, 6}, {6, 240 - bh - 7}, {256 - bw - 7, 240 - bh - 7} }
  local ox, oy = CO[corner + 1][1], CO[corner + 1][2]

  emu.drawRectangle(ox - 2, oy - 2, bw + 4, bh + 4, C_BACK, true, 1)
  emu.drawRectangle(ox - 2, oy - 2, bw + 4, bh + 4, C_EDGE, false, 1)

  for y = by0, box[4] - 1 do
    for x = bx0, box[3] - 1 do
      -- 불규칙한 구역이면 상자 안이라도 구역에 안 속한 블록은 비워 둔다
      if blocks[blockOf(x, y)] then
        local c = MAP[y * MAP_W + x]
        local X, Y = ox + (x - bx0) * cell, oy + (y - by0) * cell
        local n, e, s, wv = sideOf(c, 3), sideOf(c, 2), sideOf(c, 1), sideOf(c, 0)
        if n ~= 0 then emu.drawLine(X, Y, X + cell, Y, n == 1 and C_WALL or C_DOOR, 1) end
        if wv ~= 0 then emu.drawLine(X, Y, X, Y + cell, wv == 1 and C_WALL or C_DOOR, 1) end
        if s ~= 0 then emu.drawLine(X, Y + cell, X + cell, Y + cell, s == 1 and C_WALL or C_DOOR, 1) end
        if e ~= 0 then emu.drawLine(X + cell, Y, X + cell, Y + cell, e == 1 and C_WALL or C_DOOR, 1) end
      end
    end
  end

  if showMarks then
    for _, m in pairs(marks) do
      local mx, my = m[1], m[2]
      if mx >= bx0 and mx < box[3] and my >= by0 and my < box[4] and blocks[blockOf(mx, my)] then
        mark(ox + (mx - bx0) * cell, oy + (my - by0) * cell, cell, m[3])
      end
    end
  end

  local mx, my = ox + (px - bx0) * cell, oy + (py - by0) * cell
  emu.drawRectangle(mx + 1, my + 1, cell - 1, cell - 1, C_ME, true, 1)
  arrow(mx + cell // 2, my + cell // 2, dx, dy, math.max(2, cell // 2), C_ME)
end

-- ── 키 (누르는 순간만 먹게) ──────────────────────────────────────────────
local function edge(name, prev)
  local ok, v = pcall(emu.isKeyPressed, name)    -- 키 이름이 틀려도 지도는 계속 나오게
  if not ok then return false, false end
  return (v and not prev), (v or false)
end

local function keys()
  local hit
  hit, prevM = edge("M", prevM); if hit then show = not show end
  hit, prevN = edge("N", prevN); if hit then corner = (corner + 1) % 4 end
  hit, prevV = edge("V", prevV); if hit then showMarks = not showMarks end
end

emu.addEventCallback(function()
  keys()
  draw()
end, emu.eventType.endFrame)

emu.displayMessage("automap", string.format(
  "자동지도 ON  계단↑%d ↓%d  엘베%d  상자%d  NPC%d  전투%d  텔포%d  (M끄기 N위치 V표식)",
  count[KIND_UP], count[KIND_DOWN], count[KIND_ELEV],
  count[KIND_CHEST], count[KIND_NPC], count[KIND_FIGHT], count[KIND_WARP]))
