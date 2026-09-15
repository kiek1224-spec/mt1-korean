#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
헤드리스 NES 부팅 검증기 (MT1 전용 최소 구현)
  - 6502 공식 명령 전체
  - MMC3 / 매퍼191 (PRG R6,R7 + CHR R0~R5, CHR A17로 RAM 선택)
  - PPU 스텁: vblank, NMI, 스프라이트0 히트, $2007 쓰기(VRAM/CHR-RAM 배열)

목적은 그래픽 재현이 아니라 "죽지 않고 메인 루프를 돈다"의 증명.
검사 항목: 불법 오피코드 / PC가 RAM·미매핑 영역으로 이탈 / NMI 미도달 /
          같은 PC에서의 무한정지 / 스택 폭주.
"""
import sys

# ---------------------------------------------------------------- 6502 표
IMP,ACC,IMM,ZP,ZPX,ZPY,IZX,IZY,REL,ABS,ABX,ABY,IND = range(13)
OPS = {}
def _o(c, n, m, cy): OPS[c] = (n, m, cy)
for c,n,m,cy in [
 (0x00,'BRK',IMP,7),(0x01,'ORA',IZX,6),(0x05,'ORA',ZP,3),(0x06,'ASL',ZP,5),
 (0x08,'PHP',IMP,3),(0x09,'ORA',IMM,2),(0x0A,'ASL',ACC,2),(0x0D,'ORA',ABS,4),
 (0x0E,'ASL',ABS,6),(0x10,'BPL',REL,2),(0x11,'ORA',IZY,5),(0x15,'ORA',ZPX,4),
 (0x16,'ASL',ZPX,6),(0x18,'CLC',IMP,2),(0x19,'ORA',ABY,4),(0x1D,'ORA',ABX,4),
 (0x1E,'ASL',ABX,7),(0x20,'JSR',ABS,6),(0x21,'AND',IZX,6),(0x24,'BIT',ZP,3),
 (0x25,'AND',ZP,3),(0x26,'ROL',ZP,5),(0x28,'PLP',IMP,4),(0x29,'AND',IMM,2),
 (0x2A,'ROL',ACC,2),(0x2C,'BIT',ABS,4),(0x2D,'AND',ABS,4),(0x2E,'ROL',ABS,6),
 (0x30,'BMI',REL,2),(0x31,'AND',IZY,5),(0x35,'AND',ZPX,4),(0x36,'ROL',ZPX,6),
 (0x38,'SEC',IMP,2),(0x39,'AND',ABY,4),(0x3D,'AND',ABX,4),(0x3E,'ROL',ABX,7),
 (0x40,'RTI',IMP,6),(0x41,'EOR',IZX,6),(0x45,'EOR',ZP,3),(0x46,'LSR',ZP,5),
 (0x48,'PHA',IMP,3),(0x49,'EOR',IMM,2),(0x4A,'LSR',ACC,2),(0x4C,'JMP',ABS,3),
 (0x4D,'EOR',ABS,4),(0x4E,'LSR',ABS,6),(0x50,'BVC',REL,2),(0x51,'EOR',IZY,5),
 (0x55,'EOR',ZPX,4),(0x56,'LSR',ZPX,6),(0x58,'CLI',IMP,2),(0x59,'EOR',ABY,4),
 (0x5D,'EOR',ABX,4),(0x5E,'LSR',ABX,7),(0x60,'RTS',IMP,6),(0x61,'ADC',IZX,6),
 (0x65,'ADC',ZP,3),(0x66,'ROR',ZP,5),(0x68,'PLA',IMP,4),(0x69,'ADC',IMM,2),
 (0x6A,'ROR',ACC,2),(0x6C,'JMP',IND,5),(0x6D,'ADC',ABS,4),(0x6E,'ROR',ABS,6),
 (0x70,'BVS',REL,2),(0x71,'ADC',IZY,5),(0x75,'ADC',ZPX,4),(0x76,'ROR',ZPX,6),
 (0x78,'SEI',IMP,2),(0x79,'ADC',ABY,4),(0x7D,'ADC',ABX,4),(0x7E,'ROR',ABX,7),
 (0x81,'STA',IZX,6),(0x84,'STY',ZP,3),(0x85,'STA',ZP,3),(0x86,'STX',ZP,3),
 (0x88,'DEY',IMP,2),(0x8A,'TXA',IMP,2),(0x8C,'STY',ABS,4),(0x8D,'STA',ABS,4),
 (0x8E,'STX',ABS,4),(0x90,'BCC',REL,2),(0x91,'STA',IZY,6),(0x94,'STY',ZPX,4),
 (0x95,'STA',ZPX,4),(0x96,'STX',ZPY,4),(0x98,'TYA',IMP,2),(0x99,'STA',ABY,5),
 (0x9A,'TXS',IMP,2),(0x9D,'STA',ABX,5),(0xA0,'LDY',IMM,2),(0xA1,'LDA',IZX,6),
 (0xA2,'LDX',IMM,2),(0xA4,'LDY',ZP,3),(0xA5,'LDA',ZP,3),(0xA6,'LDX',ZP,3),
 (0xA8,'TAY',IMP,2),(0xA9,'LDA',IMM,2),(0xAA,'TAX',IMP,2),(0xAC,'LDY',ABS,4),
 (0xAD,'LDA',ABS,4),(0xAE,'LDX',ABS,4),(0xB0,'BCS',REL,2),(0xB1,'LDA',IZY,5),
 (0xB4,'LDY',ZPX,4),(0xB5,'LDA',ZPX,4),(0xB6,'LDX',ZPY,4),(0xB8,'CLV',IMP,2),
 (0xB9,'LDA',ABY,4),(0xBA,'TSX',IMP,2),(0xBC,'LDY',ABX,4),(0xBD,'LDA',ABX,4),
 (0xBE,'LDX',ABY,4),(0xC0,'CPY',IMM,2),(0xC1,'CMP',IZX,6),(0xC4,'CPY',ZP,3),
 (0xC5,'CMP',ZP,3),(0xC6,'DEC',ZP,5),(0xC8,'INY',IMP,2),(0xC9,'CMP',IMM,2),
 (0xCA,'DEX',IMP,2),(0xCC,'CPY',ABS,4),(0xCD,'CMP',ABS,4),(0xCE,'DEC',ABS,6),
 (0xD0,'BNE',REL,2),(0xD1,'CMP',IZY,5),(0xD5,'CMP',ZPX,4),(0xD6,'DEC',ZPX,6),
 (0xD8,'CLD',IMP,2),(0xD9,'CMP',ABY,4),(0xDD,'CMP',ABX,4),(0xDE,'DEC',ABX,7),
 (0xE0,'CPX',IMM,2),(0xE1,'SBC',IZX,6),(0xE4,'CPX',ZP,3),(0xE5,'SBC',ZP,3),
 (0xE6,'INC',ZP,5),(0xE8,'INX',IMP,2),(0xE9,'SBC',IMM,2),(0xEA,'NOP',IMP,2),
 (0xEC,'CPX',ABS,4),(0xED,'SBC',ABS,4),(0xEE,'INC',ABS,6),(0xF0,'BEQ',REL,2),
 (0xF1,'SBC',IZY,5),(0xF5,'SBC',ZPX,4),(0xF6,'INC',ZPX,6),(0xF8,'SED',IMP,2),
 (0xF9,'SBC',ABY,4),(0xFD,'SBC',ABX,4),(0xFE,'INC',ABX,7)]:
    _o(c,n,m,cy)

SIZE = {IMP:1,ACC:1,IMM:2,ZP:2,ZPX:2,ZPY:2,IZX:2,IZY:2,REL:2,ABS:3,ABX:3,ABY:3,IND:3}

CPF = 29781          # CPU cycles / frame
SPR0_AT = 9000       # 프레임 내 스프라이트0 히트 시점
VBL_AT = 27000       # vblank 시작


class NES:
    def __init__(self, path):
        d = open(path, 'rb').read()
        h = d[:16]
        assert h[:4] == b'NES\x1a', "iNES 헤더 아님"
        self.prg_kb, self.chr_kb = h[4] * 16, h[5] * 8
        need = 16 + h[4] * 16384 + h[5] * 8192
        assert need == len(d), f"헤더 선언 {need}B != 실제 {len(d)}B"
        self.mapper = (h[6] >> 4) | (h[7] & 0xF0)
        p = 16 + h[4] * 16384
        self.prg = d[16:p]
        self.chr = bytearray(d[p:])
        # 매퍼191 = 2KB(비트7 선택) / 매퍼195 = 4KB(뱅크 $00~$03)
        self.chrram = bytearray(0x1000 if self.mapper == 195 else 0x800)
        self.ram = bytearray(0x800)
        self.prgram = bytearray(0x2000)         # MMC3 계열 $6000-$7FFF 8KB
        self.prgram_writes = 0
        self.vram = bytearray(0x1000)
        self.nbanks = len(self.prg) // 0x2000
        self.r = [0] * 8
        self.bsel = 0
        self.prgmode = 0
        self.map_prg()
        # PPU
        # 표준 컨트롤러 1P. pad 비트: 0=A 1=B 2=Select 3=Start 4=Up 5=Down 6=Left 7=Right
        self.pad = 0
        self.pad_strobe = 0
        self.pad_shift = 0
        self.pad_count = 0
        self.ppuctrl = 0
        self.ppustatus = 0
        self.vaddr = 0
        self.latch = 0
        self.chr_writes = 0
        self.chr_rom_writes = 0
        self.vram_writes = 0
        # CPU
        self.a = self.x = self.y = 0
        self.s = 0xFD
        self.p = 0x24
        self.cyc = 0
        self.pc = self.rd16(0xFFFC)
        self.nmi_count = 0

    # ---------------- 뱅크 매핑 (MMC3 PRG 모드 0/1)
    def map_prg(self):
        n = self.nbanks
        if self.prgmode == 0:
            self.pb = [self.r[6] % n, self.r[7] % n, (n - 2) % n, (n - 1) % n]
        else:
            self.pb = [(n - 2) % n, self.r[7] % n, self.r[6] % n, (n - 1) % n]

    def rd(self, a):
        a &= 0xFFFF
        if a < 0x2000:
            return self.ram[a & 0x7FF]
        if a < 0x4000:
            r = a & 7
            if r == 2:
                v = self.ppustatus
                self.ppustatus &= 0x7F
                self.latch = 0
                return v
            return 0
        if a == 0x4016:
            # 표준 컨트롤러: 스트로브 중에는 A 버튼을 계속 돌려주고,
            # 아니면 시프트 레지스터에서 한 비트씩. 8번 넘게 읽으면 1.
            if self.pad_strobe:
                return self.pad & 1
            if self.pad_count >= 8:
                return 1
            v = self.pad_shift & 1
            self.pad_shift >>= 1
            self.pad_count += 1
            return v
        if a < 0x4020:
            return 0
        if a < 0x6000:
            return 0
        if a < 0x8000:
            return self.prgram[a - 0x6000]
        b = (a - 0x8000) >> 13
        return self.prg[self.pb[b] * 0x2000 + (a & 0x1FFF)]

    def wr(self, a, v):
        a &= 0xFFFF; v &= 0xFF
        if a < 0x2000:
            self.ram[a & 0x7FF] = v; return
        if a < 0x4000:
            r = a & 7
            if r == 0:
                self.ppuctrl = v
            elif r == 6:
                if self.latch == 0:
                    self.vaddr = (self.vaddr & 0x00FF) | ((v & 0x3F) << 8); self.latch = 1
                else:
                    self.vaddr = (self.vaddr & 0xFF00) | v; self.latch = 0
            elif r == 7:
                self.ppuwrite(self.vaddr, v)
                self.vaddr = (self.vaddr + (32 if self.ppuctrl & 4 else 1)) & 0x3FFF
            elif r == 5:
                self.latch ^= 1
            return
        if a == 0x4016:
            new = v & 1
            if self.pad_strobe and not new:      # 1 -> 0 에서 버튼 상태를 래치
                self.pad_shift = self.pad
                self.pad_count = 0
            self.pad_strobe = new
            if new:
                self.pad_shift = self.pad
                self.pad_count = 0
            return
        if a < 0x4020:
            return
        if a < 0x6000:
            return
        if a < 0x8000:
            self.prgram[a - 0x6000] = v
            self.prgram_writes += 1
            return
        even = (a & 1) == 0
        if a < 0xA000:
            if even:
                self.bsel = v
                self.prgmode = (v >> 6) & 1
                self.map_prg()
            else:
                self.r[self.bsel & 7] = v
                self.map_prg()
        # $A000~$FFFF: 미러링/IRQ - PRG 매핑에 영향 없음

    def ppuwrite(self, a, v):
        a &= 0x3FFF
        if a < 0x2000:
            # 매퍼191: 해당 1KB 슬롯의 뱅크 번호 비트7이 서 있을 때만 CHR-RAM
            if a < 0x0800:   bank = self.r[0] & 0xFE
            elif a < 0x1000: bank = self.r[1] & 0xFE
            else:            bank = self.r[2 + ((a - 0x1000) >> 10)]
            if self.mapper == 195:
                # 매퍼195: 1KB뱅크 번호 $00~$03 이 곧 CHR-RAM 4KB (문 크리스탈 롬으로 실측)
                eff = (bank | ((a >> 10) & 1)) if a < 0x1000 else bank
                if eff < 4:
                    self.chr_writes += 1
                    self.chrram[((eff & 3) << 10) | (a & 0x3FF)] = v
                else:
                    self.chr_rom_writes += 1
                return
            if bank & 0x80:
                self.chr_writes += 1
                self.chrram[((bank & 1) << 10) | (a & 0x3FF)] = v
            else:
                self.chr_rom_writes += 1      # ROM -> 무시 (원본과 동일)
        elif a < 0x3F00:
            self.vram[(a - 0x2000) & 0xFFF] = v
            self.vram_writes += 1

    def rd16(self, a):
        return self.rd(a) | (self.rd(a + 1) << 8)

    # ---------------- 스택
    def push(self, v):
        self.ram[0x100 | self.s] = v & 0xFF
        self.s = (self.s - 1) & 0xFF

    def pop(self):
        self.s = (self.s + 1) & 0xFF
        return self.ram[0x100 | self.s]

    # ---------------- 플래그
    def setzn(self, v):
        self.p = (self.p & ~0x82) | (0x02 if (v & 0xFF) == 0 else 0) | (v & 0x80)

    def addr(self, m):
        pc = self.pc
        if m == IMM: self.pc += 1; return pc
        if m == ZP:  self.pc += 1; return self.rd(pc)
        if m == ZPX: self.pc += 1; return (self.rd(pc) + self.x) & 0xFF
        if m == ZPY: self.pc += 1; return (self.rd(pc) + self.y) & 0xFF
        if m == ABS: self.pc += 2; return self.rd16(pc)
        if m == ABX: self.pc += 2; return (self.rd16(pc) + self.x) & 0xFFFF
        if m == ABY: self.pc += 2; return (self.rd16(pc) + self.y) & 0xFFFF
        if m == IZX:
            self.pc += 1; z = (self.rd(pc) + self.x) & 0xFF
            return self.rd(z) | (self.rd((z + 1) & 0xFF) << 8)
        if m == IZY:
            self.pc += 1; z = self.rd(pc)
            return ((self.rd(z) | (self.rd((z + 1) & 0xFF) << 8)) + self.y) & 0xFFFF
        if m == REL:
            self.pc += 1; o = self.rd(pc)
            return (self.pc + (o - 256 if o & 0x80 else o)) & 0xFFFF
        if m == IND:
            self.pc += 2; p = self.rd16(pc)
            return self.rd(p) | (self.rd((p & 0xFF00) | ((p + 1) & 0xFF)) << 8)
        return 0

    def nmi(self):
        self.push((self.pc >> 8) & 0xFF); self.push(self.pc & 0xFF)
        self.push(self.p & ~0x10)
        self.p |= 0x04
        self.pc = self.rd16(0xFFFA)
        self.nmi_count += 1
        self.cyc += 7

    def step(self):
        op = self.rd(self.pc)
        if op not in OPS:
            raise RuntimeError(f"불법 오피코드 ${op:02X} @ ${self.pc:04X}")
        n, m, cy = OPS[op]
        self.pc = (self.pc + 1) & 0xFFFF
        self.cyc += cy
        a = self.addr(m) if m not in (IMP, ACC) else 0
        A, P = self.a, self.p

        if   n == 'LDA': self.a = self.rd(a); self.setzn(self.a)
        elif n == 'LDX': self.x = self.rd(a); self.setzn(self.x)
        elif n == 'LDY': self.y = self.rd(a); self.setzn(self.y)
        elif n == 'STA': self.wr(a, self.a)
        elif n == 'STX': self.wr(a, self.x)
        elif n == 'STY': self.wr(a, self.y)
        elif n == 'TAX': self.x = self.a; self.setzn(self.x)
        elif n == 'TAY': self.y = self.a; self.setzn(self.y)
        elif n == 'TXA': self.a = self.x; self.setzn(self.a)
        elif n == 'TYA': self.a = self.y; self.setzn(self.a)
        elif n == 'TSX': self.x = self.s; self.setzn(self.x)
        elif n == 'TXS': self.s = self.x
        elif n == 'PHA': self.push(self.a)
        elif n == 'PHP': self.push(self.p | 0x30)
        elif n == 'PLA': self.a = self.pop(); self.setzn(self.a)
        elif n == 'PLP': self.p = (self.pop() & 0xEF) | 0x20
        elif n in ('AND','ORA','EOR'):
            v = self.rd(a)
            self.a = self.a & v if n == 'AND' else (self.a | v if n == 'ORA' else self.a ^ v)
            self.setzn(self.a)
        elif n == 'ADC':
            v = self.rd(a); r = self.a + v + (P & 1)
            self.p = (self.p & ~0x41) | (1 if r > 0xFF else 0) \
                     | (0x40 if (~(self.a ^ v) & (self.a ^ r) & 0x80) else 0)
            self.a = r & 0xFF; self.setzn(self.a)
        elif n == 'SBC':
            v = self.rd(a) ^ 0xFF; r = self.a + v + (P & 1)
            self.p = (self.p & ~0x41) | (1 if r > 0xFF else 0) \
                     | (0x40 if (~(self.a ^ v) & (self.a ^ r) & 0x80) else 0)
            self.a = r & 0xFF; self.setzn(self.a)
        elif n in ('CMP','CPX','CPY'):
            reg = self.a if n == 'CMP' else (self.x if n == 'CPX' else self.y)
            v = self.rd(a); r = (reg - v) & 0x1FF
            self.p = (self.p & ~1) | (1 if reg >= v else 0); self.setzn(r)
        elif n == 'BIT':
            v = self.rd(a)
            self.p = (self.p & ~0xC2) | (v & 0xC0) | (0x02 if (self.a & v) == 0 else 0)
        elif n in ('INC','DEC'):
            v = (self.rd(a) + (1 if n == 'INC' else -1)) & 0xFF
            self.wr(a, v); self.setzn(v)
        elif n == 'INX': self.x = (self.x + 1) & 0xFF; self.setzn(self.x)
        elif n == 'INY': self.y = (self.y + 1) & 0xFF; self.setzn(self.y)
        elif n == 'DEX': self.x = (self.x - 1) & 0xFF; self.setzn(self.x)
        elif n == 'DEY': self.y = (self.y - 1) & 0xFF; self.setzn(self.y)
        elif n in ('ASL','LSR','ROL','ROR'):
            v = self.a if m == ACC else self.rd(a)
            if n == 'ASL': c = v >> 7; v = (v << 1) & 0xFF
            elif n == 'LSR': c = v & 1; v >>= 1
            elif n == 'ROL': c = v >> 7; v = ((v << 1) | (P & 1)) & 0xFF
            else: c = v & 1; v = (v >> 1) | ((P & 1) << 7)
            self.p = (self.p & ~1) | c
            if m == ACC: self.a = v
            else: self.wr(a, v)
            self.setzn(v)
        elif n == 'JMP': self.pc = a
        elif n == 'JSR':
            r = (self.pc - 1) & 0xFFFF
            self.push(r >> 8); self.push(r & 0xFF); self.pc = a
        elif n == 'RTS': self.pc = (self.pop() | (self.pop() << 8)) + 1 & 0xFFFF
        elif n == 'RTI':
            self.p = (self.pop() & 0xEF) | 0x20
            self.pc = self.pop() | (self.pop() << 8)
        elif n == 'BRK':
            raise RuntimeError(f"BRK 실행 @ ${(self.pc-2)&0xFFFF:04X}")
        elif n[0] == 'B':
            cond = {'BPL': not P & 0x80, 'BMI': P & 0x80, 'BVC': not P & 0x40,
                    'BVS': P & 0x40, 'BCC': not P & 1, 'BCS': P & 1,
                    'BNE': not P & 2, 'BEQ': P & 2}[n]
            if cond: self.pc = a; self.cyc += 1
        elif n == 'CLC': self.p &= ~1
        elif n == 'SEC': self.p |= 1
        elif n == 'CLI': self.p &= ~4
        elif n == 'SEI': self.p |= 4
        elif n == 'CLV': self.p &= ~0x40
        elif n == 'CLD': self.p &= ~8
        elif n == 'SED': self.p |= 8
        elif n == 'NOP': pass
        else: raise RuntimeError('미구현 ' + n)


def verify(path, frames=600, verbose=True):
    n = NES(path)
    if verbose:
        print(f"  매퍼 {n.mapper}  PRG {n.prg_kb}KB({n.nbanks}뱅크)  CHR {n.chr_kb}KB")
        print(f"  리셋 벡터 ${n.pc:04X}   NMI 벡터 ${n.rd16(0xFFFA):04X}")
    fstart = 0
    spr0_done = vbl_done = False
    hist = {}
    ins = 0
    while n.nmi_count < frames:
        pos = n.cyc - fstart
        if pos >= CPF:
            fstart += CPF; spr0_done = vbl_done = False
            n.ppustatus &= 0x3F
        elif not spr0_done and pos >= SPR0_AT:
            n.ppustatus |= 0x40; spr0_done = True
        elif not vbl_done and pos >= VBL_AT:
            n.ppustatus |= 0x80; vbl_done = True
            if n.ppuctrl & 0x80 and not (n.p & 0x04 and False):
                n.nmi()
        pc = n.pc
        if pc < 0x6000:
            raise RuntimeError(f"PC가 롬 밖으로 이탈: ${pc:04X}")
        hist[pc] = hist.get(pc, 0) + 1
        n.step()
        ins += 1
        if ins > 40_000_000:
            raise RuntimeError("명령 한도 초과 (진행 없음)")
    if verbose:
        print(f"  주행: {ins:,}명령 / {n.cyc:,}사이클 / NMI {n.nmi_count}회")
        print(f"  VRAM 쓰기 {n.vram_writes:,}회   CHR-RAM 쓰기 {n.chr_writes:,}회  CHR-ROM 무시 {n.chr_rom_writes:,}회   서로 다른 PC {len(hist):,}개")
        print(f"  PRG-RAM($6000) 쓰기 {n.prgram_writes:,}회   비어있지 않은 바이트 {sum(1 for x in n.prgram if x):,}개")
    return n


if __name__ == '__main__':
    for f in sys.argv[1:]:
        print(f.split('/')[-1])
        try:
            verify(f)
            print("  === 부팅 정상 ===")
        except Exception as e:
            print(f"  !!! 실패: {e}")
        print()
