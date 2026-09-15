#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""어떤 **RAM 주소**를 절대주소로 읽고 쓰는 명령을 전 PRG 에서 찾는다.
사용: python refaddr.py <롬> 0780 [0781 ...]
"""
import sys

# 절대/절대인덱스 주소지정 명령들 (오퍼랜드가 16비트)
ABS_OPS = {
    0x0D: "ORA", 0x0E: "ASL", 0x1D: "ORA,X", 0x1E: "ASL,X", 0x19: "ORA,Y",
    0x2C: "BIT", 0x2D: "AND", 0x2E: "ROL", 0x3D: "AND,X", 0x3E: "ROL,X", 0x39: "AND,Y",
    0x4D: "EOR", 0x4E: "LSR", 0x5D: "EOR,X", 0x5E: "LSR,X", 0x59: "EOR,Y",
    0x6D: "ADC", 0x6E: "ROR", 0x7D: "ADC,X", 0x7E: "ROR,X", 0x79: "ADC,Y",
    0x8D: "STA", 0x8E: "STX", 0x8C: "STY", 0x9D: "STA,X", 0x99: "STA,Y",
    0xAD: "LDA", 0xAE: "LDX", 0xAC: "LDY", 0xBD: "LDA,X", 0xBC: "LDY,X",
    0xB9: "LDA,Y", 0xBE: "LDX,Y",
    0xCD: "CMP", 0xCE: "DEC", 0xDD: "CMP,X", 0xDE: "DEC,X", 0xD9: "CMP,Y",
    0xED: "SBC", 0xEE: "INC", 0xFD: "SBC,X", 0xFE: "INC,X", 0xF9: "SBC,Y",
    0xEC: "CPX", 0xCC: "CPY", 0x20: "JSR", 0x4C: "JMP", 0x6C: "JMP()",
}

rom = sys.argv[1]
targets = [int(a, 16) for a in sys.argv[2:]]
d = open(rom, "rb").read()
PRG0 = 0x10
PRGN = d[4] * 16384

for t in targets:
    lo, hi = t & 0xFF, t >> 8
    print("=" * 70)
    print("$%04X 를 오퍼랜드로 갖는 명령" % t)
    hits = 0
    for i in range(PRG0, PRG0 + PRGN - 2):
        if d[i + 1] == lo and d[i + 2] == hi and d[i] in ABS_OPS:
            b = (i - PRG0) // 0x2000
            off = (i - PRG0) % 0x2000
            # ★뱅크$1E 는 CPU $C000, 뱅크$1F 는 **$E000** 이다.
            #   둘 다 $C000 으로 찍으면 $1F 의 주소가 $2000 어긋난다(2026-09-12 에 겪었다).
            if b == 0x1E:   cpu = 0xC000 + off
            elif b == 0x1F: cpu = 0xE000 + off
            else:           cpu = 0xA000 + off      # R7 가정 (R6 면 $8000)
            print("   뱅크$%02X ~$%04X  파일$%05X   %s $%04X"
                  % (b, cpu, i, ABS_OPS[d[i]], t))
            hits += 1
    print("   총 %d건 (※명령 경계를 모르므로 오탐 섞임 - 역어셈블로 확인할 것)" % hits)
