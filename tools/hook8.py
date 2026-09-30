# -*- coding: utf-8 -*-
r"""사이버 돌 8×8 한글 — 동적 셀 캐시 훅 (2026-09-28)

  왜: 8×8 글(메뉴·무기/부품 이름)은 1바이트 → 셀(바이트 − 0x20) 고정 글꼴 256칸. VDP2 VRAM 은 메뉴 화면에서 거의 꽉 차
      한글 수백 음절을 상주시킬 수 없다 → 찍는 순간 음절 글리프를 «풀 셀»에 올리고 그 셀 번호를 쓴다(LRU).
  글 → 셀 변환 = 0x060097B2(글줄 객체 그리기, #B/#G/#R/#Y 색 코드 · %서식):
      일반 글자 0x06009A38  «MOV.B @R14+,R4 / EXTU / ADD R8(팔레트) / ADD R10(=−0x20) / MOV.W R4,@R13 / R13+=2»
      %s 결과 0x06009A0A   같은 식(팔레트 R7, 버퍼 R4, 바이트 수 @R15)
      %% 0x06009834        ADD R10 → ADD #−32 로 바꿔 R10 을 비움
  R10(원래 상수 0xFFE0, 리터럴 0x06009810) = 훅 C 주소로 바꿈.
  부호(바이트):
      0x96‥0x9F · 0xA6‥0xDF = 한글 음절 ID 0‥67 (1바이트, 자주 쓰는 순) — 옛 가타카나 자리
      0xE0‥0xEF + b2(0x01‥0xFF) = ID 68 + (lead−0xE0)×255 + (b2−1) (2바이트)
      그 밖 = 원래대로(바이트 − 0x20)
  풀 셀 68칸 = 셀 0x76‥0x7F · 0x86‥0xBF(옛 빈칸·가타카나 자리). 찍을 때마다 글리프를 다시 올린다
      → 표(ID·시각)가 쓰레기여도 글자는 틀리지 않는다(표는 «어느 셀» 고르는 데만 씀).
  %s 는 2바이트 글자 수만큼 뒤에 공백 셀을 채워 열 폭을 원래 바이트 수와 같게 한다.
  배치(2026-09-28 고침): ⛔WIND.BIN 파일 끝 뒤(RAM 0x21A000‥0x21AA00)는 «전투»가 덮어씀 → 전투 메뉴에서 훅으로 뛰다 크래시.
      → 코드·LUT·글꼴 = WIND.BIN 안 «옛 가타카나 8×8 셀» 자리 +0x3742‥0x3E82(1,856 B, 셀 0x86‥0xBF — 이제 풀 셀이라 원래 그림 안 씀,
        네 스테이트(메뉴·이름·대사·전투) 모두 원본 그대로). 파일 크기 그대로.
      캐시 표 = 실행 파일 끝 뒤 틈 0x060C7000‥(0x060C6FEA‥0x060C8000 = 어떤 코드도 안 가리킴, 네 스테이트 모두 0).
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r'C:\claude\project\aww-kr-patch\tools')
import sh2asm

BLOB_OFF = 0x3742                   # WIND.BIN 안 위치(옛 8×8 셀 0x86‥0xBF)
BLOB_END = 0x3E82
BASE = 0x00200000 + BLOB_OFF        # RAM 주소
TBL = 0x060C7000                    # u16 ID ×68
STM = 0x060C7090                    # u32 시각 ×68
CLK = 0x060C71A0                    # u32
NPOOL = 68
EXE_LOAD = 0x06004000


def id_to_bytes(i):
    if i < 10:
        return bytes([0x96 + i])
    if i < 68:
        return bytes([0xA6 + i - 10])
    i -= 68
    assert i < 16 * 255, '음절 너무 많음'
    return bytes([0xE0 + i // 255, 1 + i % 255])


class A(sh2asm.Asm):
    def bsr(self, lab):             self.items.append(('bsr', lab))
    def shll8(self, n):             self.w(0x4018 | sh2asm.R[n] << 8)
    def movw_postinc(self, m, n):   self.w(0x6005 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)
    def movl_store(self, m, n):     self.w(0x2002 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)
    def movb_disp_r0(self, d, m):   self.w(0x8400 | sh2asm.R[m] << 4 | d)          # mov.b @(d,Rm),R0

    def assemble(self):
        # bsr 은 bra 와 같은 변위 → bra 로 조립한 뒤 윗 니블 A → B
        marks = {k for k, it in enumerate(self.items) if it[0] in ('bsr', 'bra*')}
        for k in marks:
            self.items[k] = ('bra', self.items[k][1])
        out, code_len = super().assemble()
        out = bytearray(out); o = 0
        for k, it in enumerate(self.items):
            if it[0] == 'label':
                continue
            if k in marks:
                assert out[o] >> 4 == 0xA
                out[o] = (out[o] & 0x0F) | 0xB0
                self.items[k] = ('bra*', it[1])      # 다음 조립 때도 bsr 로
            o += 2
        return bytes(out), code_len


def build(font_1bpp, font_addr=None):
    """font_1bpp = ID 순 8바이트 글리프 목록 → (blob, C 주소, H2 주소)
       font_addr 를 주면 글꼴은 blob 에 안 넣고 그 주소를 읽는다(tools/build.py — 전량 번역 때 WIND 끝 블록)"""
    a = A(BASE)
    # ---- H2: %s 결과 버퍼(r4, 바이트 수 r5, 팔레트 r6) → 셀, 2바이트 글자 수만큼 공백 채움
    a.label('H2')
    a.stspr_predec('r15')
    a.movl_predec('r8', 'r15'); a.movl_predec('r9', 'r15'); a.movl_predec('r10', 'r15'); a.movl_predec('r11', 'r15')
    a.mov('r4', 'r8'); a.mov('r5', 'r9'); a.mov('r6', 'r11'); a.movi(0, 'r10')
    a.label('h2loop')
    a.mov('r8', 'r4')
    a.bsr('C')
    a.mov('r11', 'r6')              # 지연 슬롯
    a.add('r0', 'r8'); a.sub('r0', 'r9'); a.add('r0', 'r10'); a.addi(-1, 'r10')
    a.cmppl('r9')
    a.bt('h2loop')
    a.tst('r10', 'r10')
    a.bt('h2done')
    a.label('h2pad')
    a.movw_store('r11', 'r13'); a.addi(2, 'r13')
    a.dt('r10')
    a.bf('h2pad')
    a.label('h2done')
    a.movl_postinc('r15', 'r11'); a.movl_postinc('r15', 'r10'); a.movl_postinc('r15', 'r9'); a.movl_postinc('r15', 'r8')
    a.ldspr_postinc('r15')
    a.rts(); a.nop()
    # ---- C: 글자 하나(r4 = 포인터, r6 = 팔레트) → @r13 에 셀 1칸, r13 += 2, r0 = 먹은 바이트 수. r0‥r7 만 씀
    a.label('C')
    a.movb_load('r4', 'r1'); a.extub('r1', 'r1')
    a.movi(1, 'r5')
    a.mov('r1', 'r3'); a.addi(-128, 'r3'); a.addi(-22, 'r3')        # b − 0x96
    a.movi(10, 'r0'); a.cmphs('r0', 'r3')
    a.bf('kor')
    a.mov('r1', 'r3'); a.addi(-128, 'r3'); a.addi(-38, 'r3')        # b − 0xA6
    a.movi(58, 'r0'); a.cmphs('r0', 'r3')
    a.bt('c2')
    a.bra('kor')
    a.addi(10, 'r3')                # 지연 슬롯: ID = +10
    a.label('c2')
    a.mov('r1', 'r3'); a.addi(-128, 'r3'); a.addi(-96, 'r3')        # b − 0xE0
    a.movi(16, 'r0'); a.cmphs('r0', 'r3')
    a.bt('ascii')
    a.movb_disp_r0(1, 'r4'); a.extub('r0', 'r0')
    a.mov('r3', 'r2'); a.shll8('r2'); a.sub('r3', 'r2'); a.add('r0', 'r2'); a.addi(67, 'r2')
    a.mov('r2', 'r3'); a.movi(2, 'r5')
    a.bra('kor'); a.nop()
    a.label('ascii')
    a.mov('r1', 'r0'); a.addi(-32, 'r0'); a.add('r6', 'r0')
    a.movw_store('r0', 'r13'); a.addi(2, 'r13')
    a.rts(); a.mov('r5', 'r0')
    a.label('kor')                  # r3 = ID
    a.movl_pc('TBL', 'r7'); a.movi(0, 'r2'); a.movi(NPOOL, 'r4')
    a.label('sl')
    a.movw_postinc('r7', 'r1'); a.extuw('r1', 'r1')
    a.cmpeq('r3', 'r1')
    a.bt('stamp')
    a.addi(1, 'r2')
    a.dt('r4')
    a.bf('sl')
    # LRU: 시각 최소 칸
    a.movl_pc('STM', 'r7'); a.movi(0, 'r2'); a.movl_load('r7', 'r0'); a.movi(1, 'r4')
    a.label('lru')
    a.mov('r4', 'r1'); a.shll2('r1'); a.add('r7', 'r1'); a.movl_load('r1', 'r1')
    a.cmphs('r0', 'r1')
    a.bt('lnext')
    a.mov('r1', 'r0'); a.mov('r4', 'r2')
    a.label('lnext')
    a.addi(1, 'r4'); a.movi(NPOOL, 'r1'); a.cmphs('r1', 'r4')
    a.bf('lru')
    a.movl_pc('TBL', 'r7'); a.mov('r2', 'r1'); a.shll('r1'); a.add('r7', 'r1'); a.movw_store('r3', 'r1')
    a.label('stamp')                # r2 = 칸
    a.movl_pc('CLK', 'r7'); a.movl_load('r7', 'r0'); a.addi(1, 'r0'); a.movl_store('r0', 'r7')
    a.movl_pc('STM', 'r7'); a.mov('r2', 'r1'); a.shll2('r1'); a.add('r7', 'r1'); a.movl_store('r0', 'r1')
    a.mov('r2', 'r4'); a.addi(0x76, 'r4')
    a.movi(10, 'r0'); a.cmphs('r0', 'r2')
    a.bf('nc')
    a.addi(6, 'r4')
    a.label('nc')                   # r4 = 셀
    a.movl_pc('FONT', 'r7'); a.mov('r3', 'r1'); a.shll2('r1'); a.shll('r1'); a.add('r1', 'r7')
    a.mov('r4', 'r1'); a.shll2('r1'); a.shll2('r1'); a.shll('r1')
    a.movl_pc('VRAM', 'r2'); a.add('r1', 'r2')
    a.add('r6', 'r4')               # r4 = 이름표 낱말(셀 + 팔레트), r6 는 이제 임시
    a.movl_pc('LUT', 'r3'); a.movi(8, 'r1')
    a.label('row')
    a.movb_postinc('r7', 'r0'); a.extub('r0', 'r0'); a.mov('r0', 'r6')
    a.shlr2('r0'); a.shlr2('r0'); a.shll('r0'); a.movw_r0m('r3', 'r0')
    a.movw_store('r0', 'r2'); a.addi(2, 'r2')
    a.mov('r6', 'r0'); a.andi(15); a.shll('r0'); a.movw_r0m('r3', 'r0')
    a.movw_store('r0', 'r2'); a.addi(2, 'r2')
    a.dt('r1')
    a.bf('row')
    a.movw_store('r4', 'r13'); a.addi(2, 'r13')
    a.rts(); a.mov('r5', 'r0')
    code, _ = None, None
    # 리터럴 주소는 코드 조립 후 정해지므로 2번 조립
    for _pass in range(2):
        a.defl('TBL', TBL); a.defl('STM', STM); a.defl('CLK', CLK); a.defl('VRAM', 0x25E00000)
        a.defl('LUT', LUT_ADDR if _pass else 0); a.defl('FONT', FONT_ADDR if _pass else 0)
        code, _ = a.assemble()
        LUT_ADDR = BASE + len(code); LUT_ADDR += -LUT_ADDR % 4
        FONT_ADDR = font_addr if font_addr is not None else LUT_ADDR + 32
    lut = b''.join(struct.pack('>H', sum(4 << (12 - 4 * i) for i in range(4) if n & (8 >> i))) for n in range(16))
    blob = code + bytes(LUT_ADDR - BASE - len(code)) + lut + (b'' if font_addr is not None else b''.join(font_1bpp))
    return blob, a.labels['C'], a.labels['H2']


def patch_exe(exe, c_addr, h2_addr):
    """0 (실행 파일) 바이트 → 고친 바이트"""
    g = bytearray(exe)

    def put(addr, *ws):
        for k, w in enumerate(ws):
            struct.pack_into('>H', g, addr - EXE_LOAD + 2 * k, w)

    def get(addr):
        return struct.unpack_from('>H', g, addr - EXE_LOAD)[0]
    assert struct.unpack_from('>I', g, 0x06009810 - EXE_LOAD)[0] == 0xFFE0
    assert get(0x06009834) == 0x34AC and get(0x06009A3E) == 0x34AC and get(0x06009A14) == 0x36AC
    struct.pack_into('>I', g, 0x06009810 - EXE_LOAD, c_addr)          # R10 = C
    put(0x06009834, 0x74E0)                                           # %%: ADD #-32,R4
    # 일반 글자: MOV R14,R4 / MOV R8,R6 / JSR @R10 / NOP / ADD R0,R14 / NOP
    put(0x06009A38, 0x64E3, 0x6683, 0x4A0B, 0x0009, 0x3E0C, 0x0009)
    # %s: MOV.L @R15,R5 / MOV R7,R6 / MOV R10,R0 / ADD #(H2−C),R0 / JSR @R0 / NOP / BRA 0x06009A44 / NOP / NOP…
    off = h2_addr - c_addr
    assert -128 <= off < 0
    bra = 0xA000 | (((0x06009A44 - (0x06009A16 + 4)) // 2) & 0xFFF)
    put(0x06009A0A, 0x65F2, 0x6673, 0x60A3, 0x7000 | (off & 0xFF), 0x400B, 0x0009, bra, 0x0009, 0x0009, 0x0009, 0x0009, 0x0009)
    return bytes(g)
