# -*- coding: utf-8 -*-
r"""사이버 돌 스프라이트 압축(FNT.BIN 등) — 게임 해제 함수 0x0600A33C 를 그대로 옮긴 것 (2026-09-28)
  부르는 곳: 스프라이트 묶음 등록 0x0600C2A0 — 텍스처마다 해제(블록+4 → 버퍼) 후 0x060BBDF8(가로=블록+0, 세로=블록+2)로 VDP1 에 DMA.
  블록 = u16 가로 · u16 세로 · 압축 스트림. 스트림 = u32(작은 끝 u16 둘: 하위, 상위) 출력 크기 + 비트/바이트 섞인 본문.
  비트 버퍼 16비트(작은 끝으로 2바이트씩 채움), «맨 윗비트를 먼저 보고 → 나중에 한 칸 민다».
  명령: 1 = 리터럴 1바이트
        0 1 b [1]            = 2B: 거리 = 0x100·(비트열) + b 가변, 길이 = len()
        0 1 b(≠0) 0          = 28: 거리 b, 길이 len()
        0 1 0 0 1 n          = 2A: 리터럴 n+0x14 바이트
        0 1 0 0 0 v          = 29: 바이트 v 를 len() 번
        0 0 b 1              = 1E: 거리 b + 0x100~0x800, 2바이트 복사
        0 0 b(≠0) 0          = 14: 거리 b, 2바이트 복사
        0 0 0 0              = 15: 0 을 len() 번
  len(): 1→3, 01→4, 001→5, 0001→6, 00001 1 1 u16, 00001 1 0 →7, 00000 1 u8→u8+16, 00000 0 abc → 8+abc
  python tools/fntlz.py → FNT.BIN 108 블록을 풀어 VDP1 스테이트(work/mem/name) 글자와 대조
"""
import os, struct, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Bits:
    def __init__(self, d, p):
        self.d = d; self.p = p
        self.b = d[p + 1] << 8 | d[p]; self.p += 2; self.n = 16

    def top(self):
        return self.b & 0x8000

    def shift(self):
        self.b = (self.b << 1) & 0xFFFF
        self.n -= 1
        if self.n == 0:
            self.b = self.d[self.p + 1] << 8 | self.d[self.p]; self.p += 2; self.n = 16

    def byte(self):
        v = self.d[self.p]; self.p += 1; return v


def _len(s):
    if s.top(): return 3
    s.shift()
    if s.top(): return 4
    s.shift()
    if s.top(): return 5
    s.shift()
    if s.top(): return 6
    s.shift()
    if s.top():
        s.shift()
        if s.top():
            v = s.d[s.p + 1] << 8 | s.d[s.p]; s.p += 2; return v
        return 7
    s.shift()
    if s.top():
        return s.byte() + 0x10
    s.shift()
    r = 0
    if s.top(): r = 4
    s.shift()
    if s.top(): r += 2
    s.shift()
    if s.top(): r += 1
    return r + 8


def decode(d, p=0):
    """d[p:] = 압축 스트림(블록+4) → 바이트"""
    size = (d[p] | d[p + 1] << 8) | (d[p + 2] | d[p + 3] << 8) << 16
    s = Bits(d, p + 4); out = bytearray()

    def copy(off, n):
        for _ in range(n):
            out.append(out[len(out) - off])
    while len(out) < size:
        if s.top():                               # 0A 리터럴
            out.append(s.byte()); s.shift(); continue
        s.shift()
        if s.top():
            b = s.byte(); s.shift()
            if s.top():                           # 2B
                s.shift()
                r = 0x100 if s.top() else 0
                s.shift()
                if not s.top():
                    r += 0x100
                else:
                    for add in (0x300, 0x700, 0xF00, 0x1F00):
                        r *= 2; s.shift()
                        if s.top(): r += 0x100
                        s.shift()
                        if not s.top():
                            r += add; break
                    else:
                        r *= 2; s.shift()
                        if s.top(): r += 0x100
                        s.shift()
                        r *= 2
                        if s.top(): r += 0x100
                        r += 0x3F00
                s.shift(); n = _len(s); copy(r + b, n); s.shift()
            elif b:                               # 28
                s.shift(); n = _len(s); copy(b, n); s.shift()
            else:
                s.shift()
                if s.top():                       # 2A
                    b = s.byte(); s.shift()
                    for _ in range(b + 0x14):
                        out.append(s.byte())
                else:                             # 29
                    b = s.byte(); s.shift(); n = _len(s); out += bytes([b]) * n; s.shift()
        else:
            b = s.byte(); s.shift()
            if s.top():                           # 1E
                s.shift(); r = b
                if s.top(): r += 0x400
                s.shift()
                if s.top(): r += 0x200
                s.shift()
                if s.top(): r += 0x100
                r += 0x100
                copy(r, 2); s.shift()
            elif b:                               # 14
                copy(b, 2); s.shift()
            else:                                 # 15
                s.shift(); n = _len(s); out += bytes(n); s.shift()
    return bytes(out[:size]), s.p


def fnt_blocks(f):
    ptr = [struct.unpack_from('>I', f, 0x20A8 + 4 * k)[0] - 0x295000 for k in range(108)]
    return ptr


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    f = open(os.path.join(ROOT, 'work', 'disc', 'ETC_FNT.BIN'), 'rb').read()
    v1 = open(os.path.join(ROOT, 'work', 'mem', 'name', 'VDP1_VRAM.bin'), 'rb').read()
    vram = {v1[0x79400 + k * 0x100:0x79500 + k * 0x100]: k for k in range(56)}
    ok = 0; found = 0
    for k, p in enumerate(fnt_blocks(f)):
        w, h = f[p], f[p + 2]                     # 가로·세로 = 1바이트(0x0600C2BE·C2B8)
        out, end = decode(f, p + 4)
        ok += len(out) == w * h and end <= (fnt_blocks(f) + [0x20A8])[k + 1]
        found += out in vram
    print('블록 108 · 크기 맞음 %d · VDP1 글자와 완전 일치 %d/56' % (ok, found))


if __name__ == '__main__':
    main()


class _W:
    """해제기와 같은 순서(윗비트 보고 → 밀기)로 비트·바이트를 섞어 쓰는 기록기"""
    def __init__(self, size):
        self.o = bytearray(struct.pack('<HH', size & 0xFFFF, size >> 16))
        self.slot = len(self.o); self.o += b'\x00\x00'; self.w = 0; self.n = 0

    def bit(self, v):
        if v:
            self.w |= 0x8000 >> self.n
        struct.pack_into('<H', self.o, self.slot, self.w)

    def shift(self):
        self.n += 1
        if self.n == 16:
            self.slot = len(self.o); self.o += b'\x00\x00'; self.w = 0; self.n = 0

    def byte(self, b):
        self.o.append(b)


def _enc_len(w, n):
    for k, v in enumerate((3, 4, 5, 6)):
        if n == v:
            for _ in range(k):
                w.bit(0); w.shift()
            w.bit(1); return
    for _ in range(4):
        w.bit(0); w.shift()
    if 8 <= n <= 15:
        w.bit(0); w.shift(); w.bit(0); w.shift()
        r = n - 8
        w.bit(r & 4); w.shift(); w.bit(r & 2); w.shift(); w.bit(r & 1); return
    if 16 <= n <= 271:
        w.bit(0); w.shift(); w.bit(1); w.byte(n - 16); return
    w.bit(1); w.shift()
    if n == 7:
        w.bit(0); return
    w.bit(1); w.byte(n & 0xFF); w.byte(n >> 8)


def encode(data):
    """리터럴 · 0 반복(15) · 같은 바이트 반복(29) 만 쓰는 단순 압축 → 게임 해제기가 그대로 푼다"""
    w = _W(len(data)); i = 0
    while i < len(data):
        v = data[i]; n = 1
        while i + n < len(data) and data[i + n] == v and n < 0xFFFF:
            n += 1
        if n >= 3:
            w.bit(0); w.shift()
            w.bit(0) if v == 0 else w.bit(1)
            w.byte(0); w.shift()
            if v == 0:                             # 15
                w.bit(0); w.shift()
            else:                                  # 29
                w.bit(0); w.shift(); w.bit(0); w.byte(v); w.shift()
            _enc_len(w, n); w.shift()
            i += n
        else:
            w.bit(1); w.byte(v); w.shift(); i += 1
    return bytes(w.o)


def _len_bits(n):
    if 3 <= n <= 6: return n - 2
    if n == 7: return 7
    if 8 <= n <= 15: return 8
    if 16 <= n <= 271: return 6 + 8
    return 6 + 16


def encode2(data):
    """최적 파싱(DP): 리터럴 · 2바이트 복사(14, 거리 1‥255) · 복사(28, 거리 1‥255, 길이 3+) · 0 반복(15) · 바이트 반복(29)"""
    N = len(data); INF = 1 << 30
    cost = [INF] * (N + 1); cost[N] = 0; how = [None] * (N + 1)
    for i in range(N - 1, -1, -1):
        best = 9 + cost[i + 1]; h = ('L',)
        v = data[i]; r = 1
        while i + r < N and data[i + r] == v and r < 0xFFFF:
            r += 1
        for n in range(3, r + 1):
            c = (11 if v == 0 else 20) + _len_bits(n) + cost[i + n]
            if c < best: best, h = c, ('Z' if v == 0 else 'R', n)
        for d in range(1, min(i, 255) + 1):
            m = 0
            while i + m < N and data[i + m - d] == data[i + m]:
                m += 1
            if m >= 2:
                c = 11 + cost[i + 2]
                if c < best: best, h = c, ('C2', d)
            for n in range(3, m + 1):
                c = 11 + _len_bits(n) + cost[i + n]
                if c < best: best, h = c, ('C', d, n)
        cost[i] = best; how[i] = h
    w = _W(N); i = 0
    while i < N:
        h = how[i]
        if h[0] == 'L':
            w.bit(1); w.byte(data[i]); w.shift(); i += 1
        elif h[0] == 'C2':                         # 14: 0 0 d 0
            w.bit(0); w.shift(); w.bit(0); w.byte(h[1]); w.shift(); w.bit(0); w.shift(); i += 2
        elif h[0] == 'C':                          # 28: 0 1 d 0 len
            w.bit(0); w.shift(); w.bit(1); w.byte(h[1]); w.shift(); w.bit(0); w.shift()
            _enc_len(w, h[2]); w.shift(); i += h[2]
        else:
            n = h[1]; v = data[i]
            w.bit(0); w.shift(); w.bit(0 if v == 0 else 1); w.byte(0); w.shift()
            if v == 0:
                w.bit(0); w.shift()
            else:
                w.bit(0); w.shift(); w.bit(0); w.byte(v); w.shift()
            _enc_len(w, n); w.shift(); i += n
    return bytes(w.o)
