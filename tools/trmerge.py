# -*- coding: utf-8 -*-
r"""받은 번역 병합 (2026-09-30) — my files/사이버돌번역/*.tsv 의 번역 열 → my files/tsv/cyberdoll_*.tsv
  대사(cyberdoll_001‥011)·이름표(cyberdoll_names_001)는 ID 가 겹치므로 따로, 011 은 대사+이름·실행 파일 합본이라 키 = (ID, 위치, 구분).
  검사: ID·원문 일치 · 원문의 {…} 토큰이 번역에 같은 개수로 · 번역 빈 줄 · 받은 쪽에만 있는 ID
  백업: work/trmerge/tsv_before_merge/ · 보고: work/trmerge/report.tsv
  python tools/trmerge.py [--write]"""
import collections, glob, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'my files', '사이버돌번역')
DST = os.path.join(ROOT, 'my files', 'tsv')
OUT = os.path.join(ROOT, 'work', 'trmerge')


def group(name):
    return 'names' if 'names' in name else 'dlg'


def read(path):
    rows = []
    for ln in open(path, encoding='utf-8-sig').read().split('\n')[1:]:
        if not ln.strip():
            continue
        c = ln.rstrip('\r').split('\t')
        c += [''] * (6 - len(c))
        rows.append(c)
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    w = '--write' in sys.argv
    got = {'dlg': {}, 'names': {}}
    for p in sorted(glob.glob(os.path.join(SRC, '*.tsv'))):
        for c in read(p):
            got[group(os.path.basename(p))][(c[0], c[1], c[2])] = (c, os.path.basename(p))
    rep = ['종류\tID\t파일\t내용']
    cnt = collections.Counter()
    files = {}
    seen = {'dlg': set(), 'names': set()}
    for p in sorted(glob.glob(os.path.join(DST, 'cyberdoll_*.tsv'))):
        g = group(os.path.basename(p))
        lines = open(p, encoding='utf-8').read().split('\n')
        for i, ln in enumerate(lines[1:], 1):
            if not ln.strip():
                continue
            c = ln.split('\t'); c += [''] * (6 - len(c))
            cnt['원본 줄'] += 1
            r = got[g].get((c[0], c[1], c[2]))
            if r is None:
                cnt['받은 번역 없음'] += 1; rep.append('없음\t%s\t%s\t' % (c[0], os.path.basename(p))); continue
            seen[g].add((c[0], c[1], c[2]))
            rc, rf = r
            if rc[4] != c[4]:
                cnt['원문 다름'] += 1; rep.append('원문다름\t%s\t%s\t%s ≠ %s' % (c[0], rf, rc[4][:40], c[4][:40])); continue
            t = rc[5].strip(' \r')
            if not t:
                cnt['번역 빈칸'] += 1; rep.append('빈칸\t%s\t%s\t%s' % (c[0], rf, c[4][:40])); continue
            a = collections.Counter(re.findall(r'\{[0-9A-Fa-f]+\}', c[4])); b = collections.Counter(re.findall(r'\{[0-9A-Fa-f]+\}', t))
            if a != b:
                cnt['토큰 다름'] += 1; rep.append('토큰\t%s\t%s\t원문 %s / 번역 %s' % (c[0], rf, dict(a), dict(b)))
            if c[5].strip() and c[5].strip() != t:
                cnt['기존 번역 덮음'] += 1; rep.append('덮음\t%s\t%s\t%s → %s' % (c[0], rf, c[5][:40], t[:40]))
            c[5] = t
            lines[i] = '\t'.join(c[:6])
            cnt['병합'] += 1
        files[p] = '\n'.join(lines)
    for g in got:
        for k in got[g]:
            if k not in seen[g]:
                cnt['받은 쪽에만'] += 1; rep.append('받은쪽만\t%s\t%s\t' % ('/'.join(k), got[g][k][1]))
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, 'report.tsv'), 'w', encoding='utf-8').write('\n'.join(rep) + '\n')
    print(dict(cnt))
    for r in rep[1:31]:
        print(' ', r)
    if w:
        bak = os.path.join(OUT, 'tsv_before_merge')
        if not os.path.exists(bak):
            shutil.copytree(DST, bak)
        for p, t in files.items():
            open(p, 'w', encoding='utf-8').write(t)
        print('✅ 병합 씀 → my files/tsv (백업 work/trmerge/tsv_before_merge)')


if __name__ == '__main__':
    main()
