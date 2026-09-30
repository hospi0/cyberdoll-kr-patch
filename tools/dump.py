# -*- coding: utf-8 -*-
r"""ETC/MSGDT.BIN → 글 (2026-09-28, 판독용 초벌) — work/msg_jp.tsv
  메시지 = u16 BE 글자 번호 … FFFF. 800A = \n, 그 밖 0x8000 이상 = {XXXX}. 글자 번호 → work/charmap.tsv(tools/ocrmap.py)
  점수 0.6 미만 칸은 «〔번호〕» 대신 글자 뒤에 ˀ 표시(판독 확인용).
  python tools/dump.py
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def charmap():
    cm = {}
    for ln in open(os.path.join(ROOT, 'work', 'charmap.tsv'), encoding='utf-8'):
        c = ln.rstrip('\n').split('\t')
        if c[0] == '번호':
            continue
        cm[int(c[0], 16)] = (c[1] or '　', float(c[2]))
    fx = os.path.join(ROOT, 'work', 'charfix.tsv')      # 눈으로 확인한 교정(tools/ocrsheet.py 대조표) — 우선
    if os.path.exists(fx):
        for ln in open(fx, encoding='utf-8'):
            c = ln.rstrip('\n').split('\t')
            if len(c) >= 2 and c[0] != '번호':
                cm[int(c[0], 16)] = (c[1], 1.0)
    cm[0] = ('　', 1.0)                                  # 0번 = 빈칸
    for i in range(0xE0, 0x520):                        # 대조표로 전부 본 칸 = 확정
        if i in cm and cm[i][1] < 1.0:
            cm[i] = (cm[i][0], 0.99)
    return cm


def messages():
    d = open(os.path.join(ROOT, 'work', 'disc', 'ETC_MSGDT.BIN'), 'rb').read()
    w = struct.unpack('>%dH' % (len(d) // 2), d)
    out = []; cur = []
    for v in w:
        if v == 0xFFFF:
            out.append(cur); cur = []
            if len(out) == 2050:
                break
        else:
            cur.append(v)
    return out


def text(msg, cm, mark=True):
    s = []
    for v in msg:
        if v == 0x800A:
            s.append('\\n')
        elif v >= 0x8000:
            s.append('{%04X}' % v)
        else:
            ch, sc = cm.get(v, ('〓', 0))
            s.append(ch + ('ˀ' if mark and sc < 0.6 else ''))
    return ''.join(s)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cm = charmap(); ms = messages()
    with open(os.path.join(ROOT, 'work', 'msg_jp.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('번호\t글자수\t글\n')
        for i, m in enumerate(ms):
            f.write('%04d\t%d\t%s\n' % (i, sum(1 for v in m if v < 0x8000), text(m, cm)))
    print('메시지 %d' % len(ms))


if __name__ == '__main__':
    main()
