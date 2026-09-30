# -*- coding: utf-8 -*-
"""8×8 이름 칸(FSPR 12B 고정) 넘치는 번역 다듬기 (2026-09-30 빌더 첫 검사).
   백업 work/build/tsv_before_trim8/ · python trim8.py [--write]"""
import glob, os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
R = [
    ('00608', '080FC', 'LG 라이트 메탈 와이어', 'LG 메탈와이어'),        # LGﾗｲﾄﾒﾀﾙﾜｲﾔｰ
    ('00635', '0845C', 'LG 일렉트로 튜브', 'LG 일렉트로튜브'),          # LGｴﾚｸﾄﾛﾁｭｰﾌﾞ
]
w = '--write' in sys.argv
tdir = os.path.join(ROOT, 'my files', 'tsv')
bak = os.path.join(ROOT, 'work', 'build', 'tsv_before_trim8')
if w and not os.path.exists(bak):
    shutil.copytree(tdir, bak)
hit = 0
for f in sorted(glob.glob(os.path.join(tdir, 'cyberdoll_*.tsv'))):
    lines = open(f, encoding='utf-8').read().split('\n'); ch = False
    for i, ln in enumerate(lines):
        c = ln.split('\t')
        for rid, pos, a, b in R:
            if len(c) >= 6 and c[0] == rid and c[1] == pos and c[5] == a:
                c[5] = b; lines[i] = '\t'.join(c); ch = True; hit += 1
                print(rid, a, '→', b)
    if ch and w:
        open(f, 'w', encoding='utf-8').write('\n'.join(lines))
print('적용 %d / %d' % (hit, len(R)))
