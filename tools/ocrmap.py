# -*- coding: utf-8 -*-
r"""글꼴 칸 → 문자 표 만들기 (2026-09-28) — 게임 글꼴 칸을 MS 고딕 16px 로 그린 JIS 문자와 모양 대조
  글꼴 = ETC/WIND.BIN +0x5A82 (Low RAM 0x205A82), 16×16 2bpp: 글자 c 의 위 반쪽 = (c>>5)*0x800 + (c&31)*32,
         아래 반쪽 = +0x400, 반쪽 32B = 왼 8×8(16B, 줄마다 2B) + 오른 8×8(16B), 바이트마다 2비트 픽셀 4개(MSB 먼저)
         (실행 파일 0x06008C80 글자 그리기, 0x06008AC4 글줄)
  대조: 0 아닌 픽셀 = 1 로 이진화, 후보 = JIS 전각 전부 + ASCII, ±1px 이동, Dice 계수 최고
  → work/charmap.tsv (번호 · 문자 · 점수 · 2등 문자 · 2등 점수) · 그림 work/charmap_check.png(낮은 점수 칸 표시)
  python tools/ocrmap.py
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
WIND = os.path.join(ROOT, 'work', 'disc', 'ETC_WIND.BIN')
FONT_OFF = 0x5A82


def glyphs(d, n):
    out = np.zeros((n, 16, 16), np.uint8)
    for c in range(n):
        for half, off in ((0, 0), (1, 0x400)):
            a = FONT_OFF + (c >> 5) * 0x800 + (c & 31) * 32 + off
            if a + 32 > len(d):
                continue
            for cell in (0, 1):
                for y in range(8):
                    for bx in range(2):
                        b = d[a + cell * 16 + y * 2 + bx]
                        for k, s in enumerate((6, 4, 2, 0)):
                            out[c, half * 8 + y, cell * 8 + bx * 4 + k] = (b >> s) & 3
    return out


def candidates():
    chars = []
    for hi in list(range(0x81, 0x85)) + list(range(0x88, 0xA0)) + list(range(0xE0, 0xEB)):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F:
                continue
            try:
                ch = bytes([hi, lo]).decode('cp932')
            except UnicodeDecodeError:
                continue
            chars.append(ch)
    return chars


def render(chars):
    F = ImageFont.truetype(r'C:\Windows\Fonts\msgothic.ttc', 16)
    arr = np.zeros((len(chars), 16, 16), np.uint8)
    for i, ch in enumerate(chars):
        im = Image.new('L', (16, 16)); ImageDraw.Draw(im).text((0, 0), ch, font=F, fill=255)
        arr[i] = (np.array(im) > 96)
    return arr


def norm(img, size=14):
    """글자 상자로 잘라 size×size 로 늘린 흐린 그림(모양 비교용) + 가로세로 비"""
    ys, xs = np.nonzero(img)
    if len(ys) == 0:
        return np.zeros(size * size, np.float32), 1.0
    crop = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32) * 255
    h, w = crop.shape
    im = Image.fromarray(crop.astype(np.uint8)).resize((size, size), Image.BILINEAR)
    v = np.asarray(im, np.float32).reshape(-1)
    v -= v.mean(); v /= (np.linalg.norm(v) + 1e-6)
    return v, (w + 1) / (h + 1)


# 0x00‥0xDF = 고정 글자판(그림을 보고 적음, 한 줄 32칸). 0xE0 부터는 대본에 처음 나오는 순서라 자동 대조.
FIXED = ('　！”＃＄％＆’（）＊＋，－．／０１２３４５６７８９：；＜＝＞？'
         '＠ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ［￥］＾≪'
         '｀ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ｛｜｝～≫'
         'ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただ'
         'ち。「」、・ヲァィゥェォャュョッーアイウエオカキクケコサシスセソ'
         'タチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜'
         'ひびぴふぶぷガギグゲゴザジズゼゾダヂヅデドパピプペポバビブベボぽ')
assert len(FIXED) == 0xE0


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = open(WIND, 'rb').read()
    n = min(((len(d) - FONT_OFF) // 0x800) * 32, 0x600)
    raw = glyphs(d, n)
    G, GA = zip(*[norm(raw[i] / 3.0) for i in range(n)])        # 명암 그대로(흐린 가장자리 포함)
    G = np.stack(G); GA = np.array(GA)
    chars = candidates() + [chr(c) for c in range(0x21, 0x7F)]
    S = None
    for path in (r'C:\Windows\Fonts\msgothic.ttc', r'C:\Windows\Fonts\meiryo.ttc', r'C:\Windows\Fonts\YuGothM.ttc'):
        F = ImageFont.truetype(path, 32)
        R = []; RA = []
        for ch in chars:
            im = Image.new('L', (44, 44)); ImageDraw.Draw(im).text((4, 2), ch, font=F, fill=255)
            v, ar = norm(np.array(im) / 255.0); R.append(v); RA.append(ar)
        R = np.stack(R); RA = np.array(RA)
        s1 = G @ R.T - 0.3 * np.abs(np.log(GA[:, None] / RA[None, :]))   # 가로세로 비가 다르면 감점
        S = s1 if S is None else np.maximum(S, s1)                          # 글꼴 여럿 중 가장 잘 맞는 것
    order = np.argsort(-S, axis=1)[:, :2]
    with open(os.path.join(ROOT, 'work', 'charmap.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('번호\t문자\t점수\t2등\t2등점수\n')
        for i in range(n):
            if not raw[i].any():
                f.write('%X\t\t0\t\t0\n' % i); continue
            a, b = order[i]
            if i < len(FIXED):
                f.write('%X\t%s\t1.000\t\t0\n' % (i, FIXED[i])); continue
            f.write('%X\t%s\t%.3f\t%s\t%.3f\n' % (i, chars[a], S[i, a], chars[b], S[i, b]))
    sc = [S[i, order[i][0]] for i in range(n) if raw[i].any()]
    print('칸 %d · 점수 중간값 %.3f · 0.6 미만 %d' % (n, float(np.median(sc)), sum(1 for x in sc if x < 0.6)))


if __name__ == '__main__':
    main()
