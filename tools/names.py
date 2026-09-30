# -*- coding: utf-8 -*-
r"""사이버 돌 이름표 추출 — FIELD/FSPR.BIN 12바이트 이름 칸(반각 JIS X 0201, 공백 채움 + 00)
  기록 간격 대개 0x20(무기·부품)·0x18(아이템) · 0x33D8‥0x859C · 끝의 SPINAL/NERVE 파일 이름 표는 뺌.
  한글은 8×8 셀 1칸 = 1바이트 → 번역은 «12칸 이내».
  python tools/names.py → my files/tsv/cyberdoll_names.tsv (번호·오프셋·원문·번역 빈칸)
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FSPR = os.path.join(ROOT, 'work', 'disc', 'FIELD_FSPR.BIN')
END = 0x8600                        # 이 뒤는 파일 이름 표


def printable(c):
    return 0x20 <= c < 0x7F or 0xA1 <= c <= 0xDF


def names(d=None):
    d = d or open(FSPR, 'rb').read()
    out = []
    for i in range(0, END, 4):          # ★이름은 4바이트 정렬(앞 바이트가 글자처럼 보여도 이름 — 2026-09-28 56개 빠뜨렸던 것)
        s = d[i:i + 12]
        if all(printable(c) for c in s) and d[i + 12] == 0 and s.strip():
            out.append((i, s.decode('cp932')))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rows = names()
    dst = os.path.join(ROOT, 'my files', 'tsv'); os.makedirs(dst, exist_ok=True)
    with open(os.path.join(dst, 'cyberdoll_names.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('번호\t오프셋\t원문\t번역(12칸 이내)\n')
        for k, (o, s) in enumerate(rows):
            f.write('%03d\t%05X\t%s\t\n' % (k, o, s.rstrip()))
    print('%d 개 → my files/tsv/cyberdoll_names.tsv (중복 제외 %d 종)' % (len(rows), len({s.rstrip() for _, s in rows})))
