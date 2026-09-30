# -*- coding: utf-8 -*-
r"""판독 교정용 대조표 (2026-09-28) — 글꼴 칸(3배) + 자동 판독 글자를 나란히 → work/ocrsheet/sheet_NN.png
  대본(MSGDT)에서 실제로 쓰는 0xE0 이상 칸만, 128칸(16×8)씩. 칸 위 = 번호(16진), 아래 = 판독 글자(점수 0.6 미만은 빨강).
  교정은 work/charfix.tsv(번호\t글자) — tools/ocrmap.py 결과보다 우선.
  python tools/ocrsheet.py
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ocrmap, dump
from PIL import Image, ImageDraw, ImageFont


def used():
    s = set()
    for m in dump.messages():
        s |= {v for v in m if v < 0x8000}
    return s


def main():
    d = open(ocrmap.WIND, 'rb').read()
    raw = ocrmap.glyphs(d, 0x520)
    cm = dump.charmap()
    fix = {}
    p = os.path.join(ROOT, 'work', 'charfix.tsv')
    if os.path.exists(p):
        for ln in open(p, encoding='utf-8'):
            c = ln.rstrip('\n').split('\t')
            if len(c) >= 2 and c[0] != '번호':
                fix[int(c[0], 16)] = c[1]
    ids = sorted(i for i in used() if i >= 0xE0)
    out = os.path.join(ROOT, 'work', 'ocrsheet'); os.makedirs(out, exist_ok=True)
    F = ImageFont.truetype(r'C:\Windows\Fonts\msgothic.ttc', 22)
    S = ImageFont.truetype(r'C:\Windows\Fonts\msgothic.ttc', 11)
    CW, CH = 64, 86
    for k in range(0, len(ids), 128):
        chunk = ids[k:k + 128]
        im = Image.new('RGB', (16 * CW, 8 * CH), (255, 255, 255)); dr = ImageDraw.Draw(im)
        for j, i in enumerate(chunk):
            x0, y0 = (j % 16) * CW, (j // 16) * CH
            g = raw[i]
            for y in range(16):
                for xx in range(16):
                    v = g[y][xx]
                    if v:
                        c = 255 - v * 80
                        dr.rectangle((x0 + 8 + xx * 3, y0 + 12 + y * 3, x0 + 8 + xx * 3 + 2, y0 + 12 + y * 3 + 2), fill=(c, c, c))
            dr.text((x0 + 2, y0), '%X' % i, font=S, fill=(0, 0, 200))
            ch, sc = cm.get(i, ('?', 0))
            if i in fix:
                ch, col = fix[i], (0, 140, 0)
            else:
                col = (200, 0, 0) if sc < 0.6 else (0, 0, 0)
            dr.text((x0 + 20, y0 + 60), ch, font=F, fill=col)
            dr.rectangle((x0, y0, x0 + CW - 1, y0 + CH - 1), outline=(210, 210, 210))
        im.save(os.path.join(out, 'sheet_%02d.png' % (k // 128)))
    print('쓰는 칸 %d → %d장' % (len(ids), (len(ids) + 127) // 128))


if __name__ == '__main__':
    main()
