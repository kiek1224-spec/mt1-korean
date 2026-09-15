#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MT1 재귀하강 역어셈블러.

선형 스캔은 코드/데이터 경계를 몰라 계속 틀렸다(이번 세션 7회).
엔트리포인트에서 실제 제어흐름을 따라가 "이 바이트는 코드다"를 확정한다.

MMC3 뱅킹 모델
  $8000-$9FFF = R6,  $A000-$BFFF = R7,  $C000-$DFFF = 뱅크30,  $E000-$FFFF = 뱅크31
뱅크 트램폴린
  LDX #n / JSR $C864  -> R6=$C94C[n], R7=$C95A[n] 로 바꾸고 JSR 다음 명령부터 계속
  JSR $C8D5           -> 직전 컨텍스트로 복귀
"""
import sys
from collections import defaultdict

IMP, ACC, IMM, ZP, ZPX, ZPY, IZX, IZY, REL, ABS, ABX, ABY, IND = range(13)
SZ = {IMP:1, ACC:1, IMM:2, ZP:2, ZPX:2, ZPY:2, IZX:2, IZY:2, REL:2, ABS:3, ABX:3, ABY:3, IND:3}
OPS = {}


def _o(c, n, m):
    OPS[c] = (n, m)


for c, n, m in [
    (0x00,'BRK',IMP),(0x01,'ORA',IZX),(0x05,'ORA',ZP),(0x06,'ASL',ZP),(0x08,'PHP',IMP),(0x09,'ORA',IMM),
    (0x0A,'ASL',ACC),(0x0D,'ORA',ABS),(0x0E,'ASL',ABS),(0x10,'BPL',REL),(0x11,'ORA',IZY),(0x15,'ORA',ZPX),
    (0x16,'ASL',ZPX),(0x18,'CLC',IMP),(0x19,'ORA',ABY),(0x1D,'ORA',ABX),(0x1E,'ASL',ABX),(0x20,'JSR',ABS),
    (0x21,'AND',IZX),(0x24,'BIT',ZP),(0x25,'AND',ZP),(0x26,'ROL',ZP),(0x28,'PLP',IMP),(0x29,'AND',IMM),
    (0x2A,'ROL',ACC),(0x2C,'BIT',ABS),(0x2D,'AND',ABS),(0x2E,'ROL',ABS),(0x30,'BMI',REL),(0x31,'AND',IZY),
    (0x35,'AND',ZPX),(0x36,'ROL',ZPX),(0x38,'SEC',IMP),(0x39,'AND',ABY),(0x3D,'AND',ABX),(0x3E,'ROL',ABX),
    (0x40,'RTI',IMP),(0x41,'EOR',IZX),(0x45,'EOR',ZP),(0x46,'LSR',ZP),(0x48,'PHA',IMP),(0x49,'EOR',IMM),
    (0x4A,'LSR',ACC),(0x4C,'JMP',ABS),(0x4D,'EOR',ABS),(0x4E,'LSR',ABS),(0x50,'BVC',REL),(0x51,'EOR',IZY),
    (0x55,'EOR',ZPX),(0x56,'LSR',ZPX),(0x58,'CLI',IMP),(0x59,'EOR',ABY),(0x5D,'EOR',ABX),(0x5E,'LSR',ABX),
    (0x60,'RTS',IMP),(0x61,'ADC',IZX),(0x65,'ADC',ZP),(0x66,'ROR',ZP),(0x68,'PLA',IMP),(0x69,'ADC',IMM),
    (0x6A,'ROR',ACC),(0x6C,'JMP',IND),(0x6D,'ADC',ABS),(0x6E,'ROR',ABS),(0x70,'BVS',REL),(0x71,'ADC',IZY),
    (0x75,'ADC',ZPX),(0x76,'ROR',ZPX),(0x78,'SEI',IMP),(0x79,'ADC',ABY),(0x7D,'ADC',ABX),(0x7E,'ROR',ABX),
    (0x81,'STA',IZX),(0x84,'STY',ZP),(0x85,'STA',ZP),(0x86,'STX',ZP),(0x88,'DEY',IMP),(0x8A,'TXA',IMP),
    (0x8C,'STY',ABS),(0x8D,'STA',ABS),(0x8E,'STX',ABS),(0x90,'BCC',REL),(0x91,'STA',IZY),(0x94,'STY',ZPX),
    (0x95,'STA',ZPX),(0x96,'STX',ZPY),(0x98,'TYA',IMP),(0x99,'STA',ABY),(0x9A,'TXS',IMP),(0x9D,'STA',ABX),
    (0xA0,'LDY',IMM),(0xA1,'LDA',IZX),(0xA2,'LDX',IMM),(0xA4,'LDY',ZP),(0xA5,'LDA',ZP),(0xA6,'LDX',ZP),
    (0xA8,'TAY',IMP),(0xA9,'LDA',IMM),(0xAA,'TAX',IMP),(0xAC,'LDY',ABS),(0xAD,'LDA',ABS),(0xAE,'LDX',ABS),
    (0xB0,'BCS',REL),(0xB1,'LDA',IZY),(0xB4,'LDY',ZPX),(0xB5,'LDA',ZPX),(0xB6,'LDX',ZPY),(0xB8,'CLV',IMP),
    (0xB9,'LDA',ABY),(0xBA,'TSX',IMP),(0xBC,'LDY',ABX),(0xBD,'LDA',ABX),(0xBE,'LDX',ABY),(0xC0,'CPY',IMM),
    (0xC1,'CMP',IZX),(0xC4,'CPY',ZP),(0xC5,'CMP',ZP),(0xC6,'DEC',ZP),(0xC8,'INY',IMP),(0xC9,'CMP',IMM),
    (0xCA,'DEX',IMP),(0xCC,'CPY',ABS),(0xCD,'CMP',ABS),(0xCE,'DEC',ABS),(0xD0,'BNE',REL),(0xD1,'CMP',IZY),
    (0xD5,'CMP',ZPX),(0xD6,'DEC',ZPX),(0xD8,'CLD',IMP),(0xD9,'CMP',ABY),(0xDD,'CMP',ABX),(0xDE,'DEC',ABX),
    (0xE0,'CPX',IMM),(0xE1,'SBC',IZX),(0xE4,'CPX',ZP),(0xE5,'SBC',ZP),(0xE6,'INC',ZP),(0xE8,'INX',IMP),
    (0xE9,'SBC',IMM),(0xEA,'NOP',IMP),(0xEC,'CPX',ABS),(0xED,'SBC',ABS),(0xEE,'INC',ABS),(0xF0,'BEQ',REL),
    (0xF1,'SBC',IZY),(0xF5,'SBC',ZPX),(0xF6,'INC',ZPX),(0xF8,'SED',IMP),(0xF9,'SBC',ABY),(0xFD,'SBC',ABX),
    (0xFE,'INC',ABX)]:
    _o(c, n, m)

BRANCH = {0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0}
TRAMPO_IN = 0xC864
TRAMPO_OUT = 0xC8D5


class Dis:
    def __init__(self, path):
        d = open(path, 'rb').read()
        self.hdr = d[:16]
        self.prg = d[16:16 + self.hdr[4] * 16384]
        self.nb = len(self.prg) // 0x2000
        self.fixed_lo = self.nb - 2
        self.fixed_hi = self.nb - 1
        self.code = bytearray(len(self.prg))
        self.visited = set()
        self.calls = defaultdict(set)
        self.indirect = []
        self.ram = defaultdict(set)
        self.ram_idx = defaultdict(set)
        self.absref = defaultdict(set)
        self.absref_idx = defaultdict(set)   # 인덱스 주소지정 = base..base+255 도달
        self.tblR6 = None
        self.tblR7 = None

    def phys(self, a, r6, r7):
        if a < 0x8000:
            return None
        b = {0: r6, 1: r7, 2: self.fixed_lo, 3: self.fixed_hi}[(a - 0x8000) >> 13]
        return (b % self.nb) * 0x2000 + (a & 0x1FFF)

    def load_bank_tables(self):
        base = self.fixed_lo * 0x2000
        self.tblR6 = self.prg[base + (0xC94C - 0xC000): base + (0xC94C - 0xC000) + 14]
        self.tblR7 = self.prg[base + (0xC95A - 0xC000): base + (0xC95A - 0xC000) + 14]

    def _prev_ldx(self, jsr_pc, r6, r7):
        for back in (2, 3, 4, 5, 6):
            a = (jsr_pc - back) & 0xFFFF
            p = self.phys(a, r6, r7)
            if p is not None and self.prg[p] == 0xA2 and self.code[p] == 1:
                return self.prg[p + 1]
        a = (jsr_pc - 2) & 0xFFFF
        p = self.phys(a, r6, r7)
        if p is not None and self.prg[p] == 0xA2:
            return self.prg[p + 1]
        return None

    def run(self, entries):
        work = list(entries)
        while work:
            pc, r6, r7, stack = work.pop()
            while True:
                key = (pc, r6, r7)
                if key in self.visited:
                    break
                self.visited.add(key)
                p = self.phys(pc, r6, r7)
                if p is None:
                    break
                op = self.prg[p]
                if op not in OPS:
                    break
                name, mode = OPS[op]
                n = SZ[mode]
                self.code[p] = 1
                for k in range(1, n):
                    if p + k < len(self.code):
                        self.code[p + k] = 2
                if mode in (ABS, ABX, ABY, IND):
                    tgt = self.prg[p + 1] | (self.prg[p + 2] << 8)
                elif mode in (ZP, ZPX, ZPY, IZX, IZY):
                    tgt = self.prg[p + 1]
                elif mode == REL:
                    tgt = (pc + 2 + ((self.prg[p + 1] ^ 0x80) - 0x80)) & 0xFFFF
                else:
                    tgt = None

                if mode in (ZP, ZPX, ZPY, IZX, IZY):
                    self.ram[tgt].add((pc, p))
                    if mode in (ZPX, ZPY):
                        self.ram_idx[tgt].add((pc, p))
                elif mode in (ABS, ABX, ABY) and tgt is not None and tgt < 0x0800:
                    self.ram[tgt].add((pc, p))
                    if mode in (ABX, ABY):
                        self.ram_idx[tgt].add((pc, p))
                elif (mode in (ABS, ABX, ABY) and tgt is not None and tgt >= 0x8000
                      and name not in ('JMP', 'JSR')):
                    self.absref[tgt].add((r6, r7, pc))
                    if mode in (ABX, ABY):
                        self.absref_idx[tgt].add((r6, r7, pc))

                nxt = (pc + n) & 0xFFFF

                if op == 0x20:
                    self.calls[tgt].add((r6, r7, pc))
                    if tgt == TRAMPO_IN:
                        idx = self._prev_ldx(pc, r6, r7)
                        if idx is not None and idx < len(self.tblR6):
                            stack = stack + ((r6, r7),)
                            r6, r7 = self.tblR6[idx], self.tblR7[idx]
                        pc = nxt
                        continue
                    if tgt == TRAMPO_OUT:
                        if stack:
                            (r6, r7), stack = stack[-1], stack[:-1]
                        pc = nxt
                        continue
                    work.append((tgt, r6, r7, stack))
                    pc = nxt
                    continue
                if op == 0x4C:
                    pc = tgt
                    continue
                if op == 0x6C:
                    self.indirect.append((pc, tgt, r6, r7))
                    break
                if op in BRANCH:
                    work.append((tgt, r6, r7, stack))
                    pc = nxt
                    continue
                if op in (0x60, 0x40, 0x00):
                    break
                pc = nxt


def main():
    rom = sys.argv[1] if len(sys.argv) > 1 else "mt1_m191_v3.nes"
    d = Dis(rom)
    d.load_bank_tables()
    print("PRG %dKB = 8KB뱅크 %d개, 고정뱅크 %d/%d" % (len(d.prg) // 1024, d.nb, d.fixed_lo, d.fixed_hi))
    print("R6표 $C94C:", " ".join("%02X" % x for x in d.tblR6))
    print("R7표 $C95A:", " ".join("%02X" % x for x in d.tblR7))
    base = d.fixed_hi * 0x2000
    nmi = d.prg[base + 0x1FFA] | (d.prg[base + 0x1FFB] << 8)
    rst = d.prg[base + 0x1FFC] | (d.prg[base + 0x1FFD] << 8)
    irq = d.prg[base + 0x1FFE] | (d.prg[base + 0x1FFF] << 8)
    print("벡터: NMI $%04X  RESET $%04X  IRQ $%04X" % (nmi, rst, irq))
    ent = [(rst, 0, 1, ()), (nmi, 0, 1, ())]
    if irq != 0xFFFF:
        ent.append((irq, 0, 1, ()))
    ent.append((0x8000, 0x0E, 1, ()))
    d.run(ent)

    cov = sum(1 for x in d.code if x)
    print()
    print("도달한 코드 바이트 %d / %d (%.1f%%)" % (cov, len(d.prg), 100 * cov / len(d.prg)))
    per = defaultdict(int)
    for i, v in enumerate(d.code):
        if v:
            per[i // 0x2000] += 1
    print("뱅크별 코드 비율:")
    for b in sorted(per):
        print("   뱅크 $%02X  %5d/8192  %.1f%%" % (b, per[b], 100 * per[b] / 8192))
    print()
    print("풀 수 없는 간접점프 %d곳:" % len(d.indirect))
    for pc, t, r6, r7 in d.indirect[:10]:
        print("   $%04X: JMP ($%04X)  (R6=$%02X)" % (pc, t, r6))
    return d


if __name__ == '__main__':
    main()
