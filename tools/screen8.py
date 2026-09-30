# -*- coding: utf-8 -*-
r"""스테이트 → NBG2(8×8) 화면 글을 «원래 바이트»로 되살려 출처 파일을 찾는다 (2026-09-28)
  풀 셀(0x76‥0x7F·0x86‥0xBF) → 캐시 표(0x060C7000, hook8.TBL)로 음절 ID → 바이트(hook8.id_to_bytes).
  한 줄에서 연속 글자(공백 2칸 이상에서 끊음) → 디스크 파일·RAM 에서 검색.
  python tools/screen8.py <스테이트 이름(work/mem/…)>
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import hook8


def rows(name):
    m = os.path.join(ROOT, 'work', 'mem', name)
    v = open(os.path.join(m, 'VDP2_VRAM.bin'), 'rb').read()
    H = open(os.path.join(m, 'WorkRAMH.bin'), 'rb').read()
    L = open(os.path.join(m, 'WorkRAML.bin'), 'rb').read()
    if L[0x3742:0x3746] == bytes.fromhex('4f222f86'):          # 크래시 수정 뒤 빌드(훅 0x203742, 표 0x060C7000)
        tbl = struct.unpack_from('>68H', H, hook8.TBL - 0x06000000)
    else:                                                      # 옛 빌드 37f5cb81(훅 0x21A300, 표 0x21A800)
        print('(옛 빌드 스테이트: 표 0x21A800)')
        tbl = struct.unpack_from('>68H', L, 0x1A800)
    out = []
    for y in range(64):
        b = bytearray()
        for x in range(64):
            c = struct.unpack_from('>H', v, 0x4000 + (y * 64 + x) * 2)[0] & 0x3FF
            if 0x76 <= c <= 0x7F or 0x86 <= c <= 0xBF:
                s = c - 0x76 if c < 0x80 else c - 0x86 + 10
                b += hook8.id_to_bytes(tbl[s]) if tbl[s] < 4000 else b'?'
            elif 0 < c < 0x60:
                b.append(c + 0x20)
            elif c == 0:
                b.append(0x20)
            else:
                b += b'#'
        out.append(bytes(b))
    return out


def syllables():
    """빌드와 같은 음절 ID 순서(work/tr/names_weapons.tsv 쓰는 횟수 순)"""
    import csv, collections
    tr = list(csv.reader(open(os.path.join(ROOT, 'work', 'tr', 'names_weapons.tsv'), encoding='utf-8'), delimiter='	'))[1:]
    cnt = collections.Counter(ch for _, _, kr in tr for ch in kr if '가' <= ch <= '힣')
    return [s for s, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))]


def korean(b, order):
    """훅 부호로 읽은 글(한글 번역 뜻)"""
    out = ''; i = 0
    while i < len(b):
        x = b[i]
        if 0x96 <= x <= 0x9F:
            out += order[x - 0x96]; i += 1
        elif 0xA6 <= x <= 0xDF:
            out += order[x - 0xA6 + 10]; i += 1
        elif 0xE0 <= x <= 0xEF and i + 1 < len(b):
            k = 68 + (x - 0xE0) * 255 + b[i + 1] - 1
            out += order[k] if k < len(order) else '?'; i += 2
        else:
            out += chr(x) if x < 0x80 else '?'; i += 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    name = sys.argv[1]
    order = syllables()
    files = {f: open(os.path.join(ROOT, 'work', 'disc', f), 'rb').read() for f in os.listdir(os.path.join(ROOT, 'work', 'disc'))}
    for y, r in enumerate(rows(name)):
        t = r.decode('cp932', 'replace').rstrip()
        if not t.strip(' #'):
            continue
        print('%2d |%s|   훅: %s' % (y, t, korean(r, order).rstrip()))
        for piece in [p.strip(b' #') for p in r.split(b'  ')]:
            if len(piece) < 3 or not any(b >= 0x80 for b in piece):
                continue
            hits = ['%s+%X' % (f, d.find(piece)) for f, d in files.items() if piece in d]
            print('     %-16s → %s' % (piece.decode('cp932', 'replace'), ', '.join(hits[:4]) or '(디스크에 없음)'))


if __name__ == '__main__':
    main()
