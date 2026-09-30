# -*- coding: utf-8 -*-
r"""사이버 돌 번역 TSV 추출 (2026-09-28) → my files/tsv/
  열 = ID · 위치 · 구분 · 공유 · 원문 · 번역 (블루 시드·린다 큐브와 같은 꼴)
  ① cyberdoll_001‥.tsv  대사 = ETC/MSGDT.BIN(16×16, 2,050 메시지, 0번 = 글자판·빈 메시지 제외)
       위치 = 메시지 번호(같은 문장이 여럿이면 첫 번호, 공유 = 개수 — 빌더가 같은 원문 전부에 넣음)
       줄바꿈 = \n · 문장 끝 줄바꿈은 뺌(빌더가 붙임) · 서식 {8025}{8073} → {%s}, {8025}{8064} → {%d} …(0x8000+ASCII)
  ② cyberdoll_names.tsv  8×8 이름 = FIELD/FSPR.BIN — 구분 «이름12»(무기·부품·칩 12칸) / «아이템10» / «적10»
       위치 = FSPR 오프셋(16진). 칸 = 한글 1음절 1칸(자주 안 쓰는 음절은 2칸일 수 있음 — 빌더가 검사).
       무기 번역(work/tr/names_weapons.tsv)은 채워 둠.
  ③ cyberdoll_exe.tsv  8×8 실행 파일 문자열(가타카나 든 것) — 구분 «실행N»(N = 원래 바이트 수, 제자리 한도)
       ⛔영어만 된 문자열은 뽑지 않음(사용자: 영어 건드리지 말 것).
  python tools/extract.py
"""
import csv, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import dump, names

OUT = os.path.join(ROOT, 'my files', 'tsv')
HEAD = 'ID\t위치\t구분\t공유\t원문\t번역\n'
LIMIT = 29 * 1024                   # ★파일 하나 29KB 이하(줄 수 아님 — 사용자 2026-09-28)


def write_split(stem, lines):
    """머리줄 + 줄들을 29KB 이하 파일들로(UTF-8 바이트 기준) → stem_001.tsv …, 파일 수 반환"""
    for f in os.listdir(OUT):
        if re.match(re.escape(stem) + r'(_\d{3})?\.tsv$', f):
            os.remove(os.path.join(OUT, f))
    files = []; cur = []; size = len(HEAD.encode('utf-8'))
    for ln in lines:
        b = len(ln.encode('utf-8'))
        if cur and size + b > LIMIT:
            files.append(cur); cur = []; size = len(HEAD.encode('utf-8'))
        cur.append(ln); size += b
    if cur:
        files.append(cur)
    for k, fl in enumerate(files):
        with open(os.path.join(OUT, '%s_%03d.tsv' % (stem, k + 1)), 'w', encoding='utf-8', newline='\n') as f:
            f.write(HEAD + ''.join(fl))
    return len(files)


ITEM0, NITEM = 0x485C, 22           # 아이템 표(16B 기록, 이름 10B)
ENEMY0, NENEMY, ENEMY_STEP = 0x12785, 11, 0x384   # 적 기록(이름 10B + 00)
EXE_LO, EXE_HI = 0x60F00, 0x63100   # 실행 파일 안 UI 문자열 구역


def fmt_codes(s):
    """{8025}{802D}{8038}{8073} → {%-8s}"""
    def rep(m):
        cs = re.findall(r'\{80([0-9A-F]{2})\}', m.group())
        return '{' + ''.join(chr(int(c, 16)) for c in cs) + '}'
    return re.sub(r'\{8025\}(?:\{80[0-9A-F]{2}\})*?\{80(?:73|64|69|6F|75|78|58|66|63)\}', rep, s)


def dialogue():
    cm = dump.charmap(); ms = dump.messages()
    first = {}; count = {}
    for i, m in enumerate(ms):
        if i == 0 or not m:
            continue
        t = dump.text(m, cm, mark=False)
        if t.endswith('\\n'):
            t = t[:-2]
        t = fmt_codes(t)
        if not t.strip('　 \\n'):
            continue
        if t not in first:
            first[t] = i; count[t] = 0
        count[t] += 1
    rows = sorted(first.items(), key=lambda kv: kv[1])
    nf = write_split('cyberdoll', ['%05d\t%04d\t대사\t%d\t%s\t\n' % (j + 1, i, count[t], t) for j, (t, i) in enumerate(rows)])
    left = [t for t in first if re.search(r'\{80[0-9A-F]{2}\}', t)]
    return len(rows), sum(count.values()), nf, left


def name_rows():
    d = open(names.FSPR, 'rb').read()
    tr = {}
    p = os.path.join(ROOT, 'work', 'tr', 'names_weapons.tsv')
    if os.path.exists(p):
        offs = {'%03d' % k: o for k, (o, _) in enumerate(names.names(d))}
        for n, jp, kr in list(csv.reader(open(p, encoding='utf-8'), delimiter='\t'))[1:]:
            tr[offs[n]] = kr
    rows = [(o, '이름12', s.rstrip()) for o, s in names.names(d)]
    for k in range(NITEM):
        o = ITEM0 + 16 * k
        rows.append((o, '아이템10', d[o:o + 10].split(b'\x00')[0].decode('cp932').rstrip()))
    for k in range(NENEMY):
        o = ENEMY0 + ENEMY_STEP * k
        rows.append((o, '적10', d[o:o + 11].split(b'\x00')[0].decode('cp932').rstrip()))
    cnt = {}
    for _, _, s in rows:
        cnt[s] = cnt.get(s, 0) + 1
    nf = write_split('cyberdoll_names', ['%05d\t%05X\t%s\t%d\t%s\t%s\n' % (j + 1, o, kind, cnt[s], s, tr.get(o, '')) for j, (o, kind, s) in enumerate(rows)])
    return len(rows), len(tr), nf


def exe_rows():
    g = open(os.path.join(ROOT, 'work', 'disc', '0'), 'rb').read()
    rows = []
    for m in re.finditer(rb'(?<=[\x00\xff])[\x20-\x7e\xa1-\xdf]{3,}\x00', g[EXE_LO:EXE_HI]):
        s = m.group()[:-1]
        if sum(1 for c in s if 0xA6 <= c <= 0xDF) >= 2 and not (len(s) <= 3 and 0x30 <= s[0] <= 0x39):   # «8ﾚﾕ» 같은 데이터 잡음 제외
            rows.append((EXE_LO + m.start(), s))
    with open(os.path.join(OUT, 'cyberdoll_exe.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(HEAD)
        for j, (o, s) in enumerate(rows):
            f.write('%05d\t%05X\t실행%d\t1\t%s\t\n' % (j + 1, o, len(s), s.decode('cp932')))
    return len(rows)


def merge_tail(nd, nn):
    """★자투리 합치기(사용자 2026-09-28): 마지막 대사 파일 + 마지막 이름 파일 + 실행 파일 → 마지막 대사 파일 하나(구분 열로 구별)"""
    parts = [os.path.join(OUT, 'cyberdoll_%03d.tsv' % nd), os.path.join(OUT, 'cyberdoll_names_%03d.tsv' % nn),
             os.path.join(OUT, 'cyberdoll_exe.tsv')]
    body = ''.join(open(p, encoding='utf-8').read().split('\n', 1)[1] for p in parts)
    assert len((HEAD + body).encode('utf-8')) <= LIMIT, '합친 파일이 29KB 넘음'
    for p in parts[1:]:
        os.remove(p)
    open(parts[0], 'w', encoding='utf-8', newline='\n').write(HEAD + body)
    return os.path.basename(parts[0]), len((HEAD + body).encode('utf-8'))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(OUT, exist_ok=True)
    n, tot, nd, left = dialogue()
    print('대사: 서로 다른 문장 %d (메시지 %d) → cyberdoll_001‥%03d.tsv (파일당 29KB 이하)' % (n, tot, nd))
    if left:
        print('  ⚠서식으로 못 바꾼 제어 코드 남음:', left[:3])
    a, b, nn = name_rows()
    print('이름: %d 줄(무기 번역 %d 채움)' % (a, b))
    print('실행 파일: %d 줄' % exe_rows())
    f, sz = merge_tail(nd, nn)
    print('→ 마지막 대사·이름 자투리·실행 파일 합침: %s (%d B) · 이름 = cyberdoll_names_001‥%03d' % (f, sz, nn - 1))


if __name__ == '__main__':
    main()
