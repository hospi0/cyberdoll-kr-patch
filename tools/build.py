# -*- coding: utf-8 -*-
r"""사이버 돌 한글 빌더 (2026-09-30) — my files/tsv/cyberdoll_*.tsv 번역 전량 → 트랙 01
  ① 16×16 대사 = ETC/MSGDT.BIN(u16 글자 번호, 800A 줄바꿈, FFFF 끝)
     · 창 = 18칸 × 3줄(그리기 0x06008AC4: 줄 버퍼 셀 36 = 글자 18, 줄 번호 0·2·4). 18칸 넘는 줄은 «낱말 단위»로 다시 접고
       늘어난 줄 수만큼 그 덩어리 뒤 빈 줄(쪽 맞춤용 «　»)을 줄인다. 낱말 하나가 18칸 넘으면 오류.
     · 부호 뒤 공백 = rules.squeeze(빌더에서 무조건). 받은 번역의 «\ｎ»(전각 n) = 줄바꿈.
     · 글자 칸: 고정 글자판 0x00‥0xDF(반각 영숫자·부호는 전각 칸으로) · 그 밖 = 칸 0xE0 부터 배정
       (한글 = 나눔고딕 16 명암 4단계 / 기호 = 원본 글꼴에 있던 그림 복사, 없으면 나눔고딕). 한도 0x4FF(0x500~ 는 전투가 덮음).
     · 메시지 영역은 원래 끝 0x2D198 을 넘으면 안 됨(뒤 = 위치 고정 표·자료, 실행 파일이 직접 가리킴) → 넘치는 뒤쪽 메시지는
       WIND.BIN 끝 블록(Low RAM, 상주)에 두고 주소 표(0x2D198~ 의 옛 시작 주소)만 새 주소로.
  ② 8×8 글(FSPR 이름·아이템·적 + 실행 파일 문자열) = 동적 셀 캐시 훅(tools/hook8.py) 음절 ID
     · ID 순서 = 이름판 53자(1바이트 0‥52) → 나머지 쓰는 횟수 순. 1바이트 68개, 그 뒤 2바이트.
     · 칸: 이름12 = 12B(공백 채움) · 아이템10 = 10B · 적10 = 10B · 실행N = N B 제자리.
     · 8×8 글꼴(1bpp 8B/음절)은 WIND 끝 블록(hook8 blob 자리는 코드만).
  ③ 대사 속 %s(주인공 이름·보물 아이템 이름) = 8×8 음절 ID 바이트 → 새 함수 hook16 이 «ID → 16×16 칸» 표로 바꿈
     (원래 0x06008F8A: 0x06008E62 정리 + 바이트 − 0x20). 그래서 8×8 음절도 16×16 칸을 받는다.
  ④ 이름 입력판(EV01·FNT) = tools/namegrid.py
  python tools/build.py            → 검사 + work/kr/*
  python tools/build.py --write    → + 트랙 01 → work/out
"""
import collections, glob, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import dump, extract, hook8, namegrid, ocrmap, poc, rules
from PIL import ImageFont

TSV = os.path.join(ROOT, 'my files', 'tsv')
W16, LINES = 18, 3
MSG_END = 0x2D198                   # 메시지 영역 끝(원본) — 넘지 말 것
MSG_BASE = 0x060C8000
SLOT_LO, SLOT_HI = 0xE0, 0x500      # 16×16 새 글자 칸
BLK = 0x800                         # 16×16 칸 32개 묶음(위 반쪽 0x400 + 아래 반쪽 0x400)
TOP = ocrmap.FONT_OFF + (SLOT_HI >> 5) * BLK    # WIND 끝 블록 영역의 끝(0x19A82)
WIND_RAM = 0x00200000
FMT_W = {'s': 8}                    # 폭 어림: %s(이름) 8칸, %Nd 는 N칸


class Err(Exception):
    pass


# ── TSV ──────────────────────────────────────────────────
def load_rows():
    rows = []
    for p in sorted(glob.glob(os.path.join(TSV, 'cyberdoll_*.tsv'))):
        for ln in open(p, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 6 and c[0]:
                t = c[5].strip(' \r').replace('\\ｎ', '\\n')      # ★받은 번역 일부(01635‥)가 줄바꿈을 «\ｎ»(전각 n)으로 씀
                rows.append({'id': c[0], 'pos': c[1], 'kind': c[2], 'src': c[4], 'tr': t})
    return rows


# ── 16×16 글자 ───────────────────────────────────────────
def is_h(ch):
    return '가' <= ch <= '힣'


def full(ch):
    """반각 → 전각(고정 글자판 찾기용)"""
    o = ord(ch)
    if ch == ' ':
        return '　'
    if 0x21 <= o <= 0x7E:
        return chr(o + 0xFEE0)
    return {'·': '・', '“': '¨', '‘': '’'}.get(ch, ch)


def fmt_codes(tok):
    """'%-8d' → [0x8025, 0x802D, 0x8038, 0x8064] · 'XXXX'(16진 4자리) → [값]"""
    if re.fullmatch(r'[0-9A-Fa-f]{4}', tok):
        return [int(tok, 16)]
    assert tok.startswith('%'), tok
    return [0x8000 | ord(c) for c in tok]


def fmt_width(tok):
    m = re.fullmatch(r'%-?(\d*)([a-zA-Z])', tok)
    if not m:
        return 0
    return int(m.group(1)) if m.group(1) else FMT_W.get(m.group(2), 4)


def split_units(s):
    """글 → [('ch', 글자) | ('fmt', 토큰) | ('nl',)]"""
    out = []; i = 0
    while i < len(s):
        if s.startswith('\\n', i):
            out.append(('nl',)); i += 2
        elif s[i] == '{':
            j = s.index('}', i); out.append(('fmt', s[i + 1:j])); i = j + 1
        else:
            out.append(('ch', s[i])); i += 1
    return out


def width(line):
    return sum(1 if u[0] == 'ch' else fmt_width(u[1]) for u in split_units(line))


def punct_split(w):
    """18칸 넘는 낱말 → 부호 뒤에서 끊은 조각들(부호 없으면 그대로 — 글자 단위로 자르지 않는다)"""
    if width(w) <= W16:
        return [w]
    out = []
    while width(w) > W16:
        cut = None
        for k in range(1, len(w)):
            if w[k - 1] in rules.PUNCT_AFTER and w[k] not in rules.PUNCT_AFTER and width(w[:k]) <= W16:
                cut = k
        if cut is None:
            break
        out.append(w[:cut]); w = w[cut:]
    return out + [w]


JOSA = r'(?:을|를|은|는|에|의|로|으로|와|과|에게|에서|께|까지|부터|처럼|보다)'


def wrap_line(line, rid, errs):
    """18칸 넘는 한 줄 → 최소 줄 수로, 줄 길이를 고르게(가장 긴 줄이 가장 짧도록) 낱말 단위로 나눈다"""
    pcs = []                                    # (조각, 앞 이음) — 띄어쓰기 자리 ' ', 부호 뒤 끊은 자리 ''
    for k, w in enumerate(line.split(' ')):
        if not w:
            continue
        for q, p in enumerate(punct_split(w)):
            pcs.append((p, ' ' if pcs and q == 0 else ''))
    for p, _ in pcs:
        if width(p) > W16:
            errs.append('%s 낱말 하나가 %d칸 > %d «%s»' % (rid, width(p), W16, p))
            return [line]
    n = len(pcs)
    seg = lambda a, b: ''.join((g if k > a else '') + p for k, (p, g) in enumerate(pcs) if a <= k < b)
    best = {n: (0, [])}                          # 뒤에서부터: best[i] = (가장 긴 줄, 나눈 줄들)
    for i in range(n - 1, -1, -1):
        cands = []
        for j in range(i + 1, n + 1):
            s = seg(i, j)
            if width(s) > W16:
                break
            if best.get(j) is not None:
                cands.append((1 + len(best[j][1]), max(width(s), best[j][0]), [s] + best[j][1]))
        best[i] = (min(cands)[1], min(cands)[2]) if cands else None
    return best[0][1]


def fix_josa(lines):
    """줄 첫머리에 홀로 온 조사(＜…＞\\n를 알 텐데) → 앞줄 끝에 붙이거나, 앞줄 마지막 낱말을 내린다"""
    n = 0
    for k in range(1, len(lines)):
        m = re.match(JOSA + r'(?=[ 　.,!?…．，！？]|$)', lines[k])
        prev = lines[k - 1]
        if not m or not prev.strip('　 ') or prev.endswith((' ', '　')):
            continue
        j = m.group(); rest = lines[k][len(j):].lstrip(' ')
        if width(prev + j) <= W16:
            lines[k - 1] = prev + j; lines[k] = rest; n += 1
        elif ' ' in prev:
            head, last = prev.rsplit(' ', 1)
            if width(last + j + (' ' + rest if rest else '')) <= W16:
                lines[k - 1] = head; lines[k] = last + j + (' ' + rest if rest else ''); n += 1
    return n


def reflow(text, rid, errs, warns):
    """넘치는 줄만 고르게 다시 접고(나머지 줄은 번역자 줄바꿈 그대로) → 줄 첫머리 조사 붙이기 →
       덩어리(빈 줄 사이)에서 늘어난 줄 수만큼 그 뒤 빈 줄(쪽 맞춤용)을 줄인다"""
    lines = text.split('\\n')
    blank = lambda l: not l.strip('　 ')
    out = []; i = 0; changed = False
    while i < len(lines):
        if blank(lines[i]):
            out.append(lines[i]); i += 1; continue
        j = i
        while j < len(lines) and not blank(lines[j]):
            j += 1
        blk = lines[i:j]
        new = []
        for l in blk:
            if width(l) <= W16:
                new.append(l); continue
            if '{' in l:
                warns.append('%s 서식 든 줄 다시 접음(서식 폭 어림) «%s»' % (rid, l[:50]))
            new += wrap_line(l, rid, errs)
        if fix_josa(new):
            changed = True
            new = [l for l in new if l != '']
        extra = len(new) - len(blk)
        changed |= new != blk
        out += new; i = j
        while extra > 0 and i < len(lines) and blank(lines[i]):          # 쪽 맞춤 빈 줄로 흡수
            i += 1; extra -= 1
    return '\\n'.join(out), changed


# ── 8×8 ──────────────────────────────────────────────────
def half8(ch):
    o = ord(ch)
    if 0xFF01 <= o <= 0xFF5E:
        return chr(o - 0xFEE0)
    return {'　': ' ', '・': '･', '·': '･', '「': '｢', '」': '｣', '。': '｡', '、': '､', 'ー': '-', '－': '-', '…': '...', '～': '~'}.get(ch, ch)


def enc8(t, sid):
    out = b''
    for ch in t:
        if is_h(ch):
            out += hook8.id_to_bytes(sid[ch]); continue
        for c in half8(ch):
            b = c.encode('cp932')
            if len(b) != 1 or (0xA6 <= b[0] <= 0xDF) or (0x96 <= b[0] <= 0x9F) or b[0] >= 0xE0:
                raise Err('8×8 에 못 쓰는 글자 %r' % ch)
            out += b
    return out


# ── hook16: 대사 속 %s 문자열(8×8 음절 ID 바이트) → 16×16 칸 번호 ──────────
def hook16(base, tab_addr):
    a = hook8.A(base)
    a.movi(0, 'r7'); a.movl_pc('TAB', 'r3')
    a.label('loop')
    a.movb_load('r4', 'r1'); a.extub('r1', 'r1')
    a.tst('r1', 'r1'); a.bt('done')
    a.movi(0x20, 'r2'); a.cmpeq('r2', 'r1'); a.bf('notsp')
    a.movb_disp_r0(1, 'r4'); a.extub('r0', 'r0')                   # 공백: 뒤가 공백·끝이면 버림(칸 채움), 아니면 빈칸 하나
    a.tst('r0', 'r0'); a.bt('skip')
    a.cmpeq('r2', 'r0'); a.bt('skip')
    a.bra('store'); a.movi(0, 'r0')
    a.label('skip')
    a.addi(1, 'r4'); a.bra('loop'); a.nop()
    a.label('notsp')
    a.mov('r1', 'r5'); a.addi(-128, 'r5'); a.addi(-22, 'r5')        # b − 0x96
    a.movi(10, 'r0'); a.cmphs('r0', 'r5'); a.bf('kor')
    a.mov('r1', 'r5'); a.addi(-128, 'r5'); a.addi(-38, 'r5')        # b − 0xA6
    a.movi(58, 'r0'); a.cmphs('r0', 'r5'); a.bt('c2')
    a.bra('kor'); a.addi(10, 'r5')
    a.label('c2')
    a.mov('r1', 'r5'); a.addi(-128, 'r5'); a.addi(-96, 'r5')        # b − 0xE0
    a.movi(16, 'r0'); a.cmphs('r0', 'r5'); a.bt('ascii')
    a.movb_disp_r0(1, 'r4'); a.extub('r0', 'r0')
    a.mov('r5', 'r2'); a.shll8('r2'); a.sub('r5', 'r2'); a.add('r0', 'r2'); a.addi(67, 'r2')
    a.mov('r2', 'r5'); a.addi(1, 'r4')
    a.label('kor')
    a.mov('r5', 'r0'); a.shll('r0'); a.movw_r0m('r3', 'r0'); a.extuw('r0', 'r0')
    a.bra('store'); a.nop()
    a.label('ascii')
    a.mov('r1', 'r0'); a.addi(-32, 'r0')
    a.label('store')
    a.movw_store('r0', 'r6'); a.addi(2, 'r6'); a.addi(1, 'r7'); a.addi(1, 'r4')
    a.bra('loop'); a.nop()
    a.label('done')
    a.rts(); a.mov('r7', 'r0')
    a.defl('TAB', tab_addr)
    code, _ = a.assemble()
    return code


def patch_fmt_s(exe, h16):
    """0x06008F8A‥: %s 결과 → hook16(R4 글, R6 출력) 부르고 R7 = 글자 수로 0x060090C6 (함수 끝)"""
    g = bytearray(exe)
    L = hook8.EXE_LOAD
    assert struct.unpack_from('>H', g, 0x06008F8A - L)[0] == 0xBF6A           # BSR 0x06008E62
    ws = [0x66F2,          # 8F8A mov.l @r15,r6
          0xD002,          # 8F8C mov.l @(8F98),r0
          0x400B,          # 8F8E jsr @r0
          0x6453,          # 8F90 mov r5,r4
          0xA098,          # 8F92 bra 0x060090C6
          0x6703,          # 8F94 mov r0,r7
          0x0009]          # 8F96 nop
    for k, w in enumerate(ws):
        struct.pack_into('>H', g, 0x06008F8A - L + 2 * k, w)
    struct.pack_into('>I', g, 0x06008F98 - L, h16)
    for a in range(0x06008F9C, 0x06008FB4, 2):                               # 옛 반복 자리(안 씀) → nop
        struct.pack_into('>H', g, a - L, 0x0009)
    return bytes(g)


# ── 본체 ─────────────────────────────────────────────────
def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print('규칙: 16×16 창 %d칸×%d줄 · 부호 뒤 공백 삭제 · 낱말 쪼갬 금지 · 8×8 칸 바이트 한도' % (W16, LINES))
    rows = load_rows()
    errs, warns = [], []
    # ---- 대사 묶음(같은 원문 → 메시지들)
    cm = dump.charmap(); ms = dump.messages()
    groups = collections.defaultdict(list)
    for i, m in enumerate(ms):
        if i == 0 or not m:
            continue
        t = dump.text(m, cm, mark=False)
        if t.endswith('\\n'):
            t = t[:-2]
        t = extract.fmt_codes(t)
        if not t.strip('　 \\n'):
            continue
        groups[t].append(i)
    dlg = {r['src']: r for r in rows if r['kind'] == '대사'}
    assert set(dlg) == set(groups), ('대사 원문 불일치', len(set(dlg) ^ set(groups)))
    tr16 = {}; nref = 0
    for src, r in dlg.items():
        t = rules.squeeze(r['tr'])
        if re.findall(r'\{[^}]*\}', t) != re.findall(r'\{[^}]*\}', src):
            errs.append('%s 서식 토큰 다름 원문 %s / 번역 %s' % (r['id'], re.findall(r'\{[^}]*\}', src), re.findall(r'\{[^}]*\}', t)))
        t, ch = reflow(t, r['id'], errs, warns)
        nref += ch
        for l in t.split('\\n'):
            if '{' not in l and width(l) > W16:
                errs.append('%s 줄 %d칸 > %d «%s»' % (r['id'], width(l), W16, l))
        tr16[src] = t
    # ---- 8×8 글
    rows8 = [r for r in rows if r['kind'] != '대사']
    cnt8 = collections.Counter(ch for r in rows8 for ch in rules.squeeze(r['tr']) if is_h(ch))
    order8 = list(namegrid.SYLS) + [s for s, _ in sorted(cnt8.items(), key=lambda kv: (-kv[1], kv[0])) if s not in namegrid.SYLS]
    sid = {ch: i for i, ch in enumerate(order8)}
    # ---- 16×16 칸 배정
    fixed = {}
    for c in range(SLOT_LO):
        ch = cm.get(c, ('', 0))[0]
        if ch and ch not in fixed:
            fixed[ch] = c
    orig_slot = {}
    for c in range(SLOT_LO, 0x520):
        ch = cm.get(c, ('', 0))[0]
        if ch and ch not in orig_slot:
            orig_slot[ch] = c
    need = []
    for t in tr16.values():
        for u in split_units(t):
            if u[0] == 'ch' and full(u[1]) not in fixed and full(u[1]) not in need:
                need.append(full(u[1]))
    for ch in order8:
        if ch not in need:
            need.append(ch)
    if SLOT_LO + len(need) > SLOT_HI:
        raise Err('16×16 칸 %d > %d' % (len(need), SLOT_HI - SLOT_LO))
    slot = dict(fixed); newslot = {}
    for k, ch in enumerate(need):
        slot[ch] = newslot[ch] = SLOT_LO + k
    wind0 = open(ocrmap.WIND, 'rb').read()
    wind = bytearray(wind0)
    raw0 = ocrmap.glyphs(wind0, 0x520)
    F16 = ImageFont.truetype(poc.FONT, 16)
    ncopy = nrend = 0
    for ch, c in newslot.items():
        if not is_h(ch) and ch in orig_slot:
            poc.put_glyph(wind, c, raw0[orig_slot[ch]]); ncopy += 1
        else:
            poc.put_glyph(wind, c, poc.render(ch, F16)); nrend += 1
    last_slot = SLOT_LO + len(need) - 1
    print('16×16 칸: 새 %d (한글·기호, 0x%X‥0x%X) · 원본 기호 그림 복사 %d · 그림 %d' % (len(need), SLOT_LO, last_slot, ncopy, nrend))
    # ---- 메시지 부호
    def enc16(t):
        out = []
        for u in split_units(t):
            if u[0] == 'nl':
                out.append(0x800A)
            elif u[0] == 'fmt':
                out += fmt_codes(u[1])
            else:
                out.append(slot[full(u[1])])
        return out
    new_ms = list(ms)
    for src, ids in groups.items():
        codes = enc16(tr16[src])
        for i in ids:
            new_ms[i] = codes + ([0x800A] if ms[i] and ms[i][-1] == 0x800A else [])
    # ---- 되읽기 검사: 새 메시지 부호 → 글자 = 조판한 번역(전각화) · 미리보기 work/build/preview.tsv
    inv = {c: ch for ch, c in slot.items()}
    inv.update({c: ch for ch, c in fixed.items()})
    pv = ['번호\t번역(조판 후, / = 줄)']
    for src, ids in groups.items():
        back = ''
        for v in new_ms[ids[0]]:
            back += '\\n' if v == 0x800A else ('{%04X}' % v if v >= 0x8000 else inv[v])
        want = ''.join('\\n' if u[0] == 'nl' else ('{' + u[1] + '}') if u[0] == 'fmt' else full(u[1]) for u in split_units(tr16[src]))
        got = re.sub(r'(\{8025\}(\{80[0-9A-F]{2}\})+)', lambda m: '{' + ''.join(chr(int(x, 16) & 0xFF) for x in re.findall(r'80([0-9A-F]{2})', m.group())) + '}', back)
        if got.rstrip('\\n') != want and got != want:
            errs.append('%s 되읽기 불일치 «%s» ≠ «%s»' % (dlg[src]['id'], got[:40], want[:40]))
        pv.append('%04d\t%s' % (ids[0], tr16[src].replace('\\n', ' / ')))
    os.makedirs(os.path.join(ROOT, 'work', 'build'), exist_ok=True)
    open(os.path.join(ROOT, 'work', 'build', 'preview.tsv'), 'w', encoding='utf-8').write('\n'.join(pv) + '\n')
    # ---- 8×8 부호·칸
    fspr = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'FIELD_FSPR.BIN'), 'rb').read())
    exe = open(os.path.join(ROOT, 'work', 'disc', '0'), 'rb').read()
    exe_b = bytearray(exe)
    lim = {'이름12': 12, '아이템10': 10, '적10': 10}
    n8 = 0; reloc = []
    for r in rows8:
        t = rules.squeeze(r['tr'])
        try:
            b = enc8(t, sid)
        except Err as e:
            errs.append('%s %s' % (r['id'], e)); continue
        o = int(r['pos'], 16)
        if r['kind'].startswith('실행'):
            n = int(r['kind'][2:])
            src = r['src'].encode('cp932')
            assert exe[o:o + n] == src and exe[o + n] == 0, ('실행 파일 원문 불일치', r['id'])
            if len(b) > n:                  # 제자리에 안 들어가면 WIND 끝 블록으로 옮기고 그 문자열을 가리키는 포인터를 바꾼다
                a = hook8.EXE_LOAD + o
                ptrs = [i for i in range(0, len(exe) - 3, 2) if struct.unpack_from('>I', exe, i)[0] == a]
                if not ptrs:
                    errs.append('%s 실행 파일 %X: %d B > %d, 가리키는 포인터 없음 «%s»' % (r['id'], o, len(b), n, t)); continue
                reloc.append((r['id'], b, ptrs))
            else:
                exe_b[o:o + n] = b + bytes(n - len(b))
        else:
            n = lim[r['kind']]
            assert fspr[o:o + len(r['src'].encode('cp932'))] == r['src'].encode('cp932'), ('FSPR 원문 불일치', r['id'])
            if r['kind'] == '적10' and b' ' in b:
                # ★같은 적이 여럿이면 0x06034334 가 이름의 «첫 공백 또는 NUL» 자리에 « A»/« B» 를 덮어쓴다
                #   (2026-09-30 실기 «플라이 레이디» → «플라이 A이디») → 적 이름엔 공백 금지
                errs.append('%s 적 이름에 공백 «%s» — A/B 표시가 공백 자리에 덮어써짐' % (r['id'], t)); continue
            if len(b) > n:
                errs.append('%s %s %X: %d B > %d «%s»' % (r['id'], r['kind'], o, len(b), n, t)); continue
            # ★아이템 이름은 NUL 로 끝나면 게임이 «바이트 수»로 오른쪽 맞춤한다(2026-10-01 실기 — 본 크래셔·마그네가더가
            #   오른쪽으로 밀림, 2바이트 음절 탓에 끝도 안 맞음). 원문은 전부 10B 꽉 참(공백 채움) → 공백으로 채워 왼쪽 맞춤 유지
            pad = b' ' if fspr[o + n - 1] == 0x20 or r['kind'] in ('이름12', '아이템10') else b'\x00'
            fspr[o:o + n] = b + pad * (n - len(b))
        n8 += 1
    # ---- 오류면 멈춤
    if errs:
        os.makedirs(os.path.join(ROOT, 'work', 'build'), exist_ok=True)
        open(os.path.join(ROOT, 'work', 'build', 'errors.txt'), 'w', encoding='utf-8').write('\n'.join(errs) + '\n')
        print('⛔ 오류 %d건 (전체 work/build/errors.txt)' % len(errs))
        for e in errs[:40]:
            print('  ' + e)
        sys.exit(1)
    # ---- MSGDT 배치: 앞에서부터 원래 끝(0x2D198)까지, 넘치는 뒤쪽은 WIND 끝 블록
    msgdt = open(os.path.join(ROOT, 'work', 'disc', 'ETC_MSGDT.BIN'), 'rb').read()
    enc = [struct.pack('>%dH' % len(m), *m) + b'\xff\xff' for m in new_ms]
    main_area = bytearray(); k = 0
    while k < len(enc) and len(main_area) + len(enc[k]) <= MSG_END:
        main_area += enc[k]; k += 1
    over = b''.join(enc[k:])
    font8 = [poc.glyph8(ch) for ch in order8]
    tab = struct.pack('>%dH' % len(order8), *[slot[ch] for ch in order8])
    data = tab + bytes(-len(tab) % 4) + b''.join(font8)
    reloc_at = []
    for rid, b, ptrs in reloc:                   # 옮긴 실행 파일 문자열(NUL 끝, 2바이트 정렬)
        reloc_at.append((len(data), ptrs)); data += b + b'\x00'; data += bytes(len(data) % 2)
    res_size = len(data) + len(over)
    res_start = TOP - res_size; res_start -= (res_start - ocrmap.FONT_OFF) % BLK      # 묶음 경계
    if (res_start - ocrmap.FONT_OFF) // BLK <= (last_slot >> 5):
        raise Err('WIND 끝 블록 자리 부족: 자료 %d B, 마지막 글자 칸 0x%X' % (res_size, last_slot))
    tab_addr = WIND_RAM + res_start
    font_addr = tab_addr + len(tab) + (-len(tab) % 4)
    over_off = res_start + len(data)
    wind[res_start:res_start + len(data)] = data
    wind[over_off:over_off + len(over)] = over
    starts_old = []; o = 0
    for m in ms:
        starts_old.append(MSG_BASE + o); o += len(m) * 2 + 2
    starts_new = []; o = 0
    for i, e in enumerate(enc):
        starts_new.append(MSG_BASE + o if i < k else WIND_RAM + over_off + (o - len(main_area)))
        o += len(e)
    remap = {a: b for a, b in zip(starts_old, starts_new) if a != b}
    new = bytearray(msgdt)
    new[:MSG_END] = bytes(main_area) + bytes(MSG_END - len(main_area))
    nfix = 0
    for p in range(MSG_END, len(new) - 3, 4):
        v = struct.unpack_from('>I', new, p)[0]
        if v in remap:
            struct.pack_into('>I', new, p, remap[v]); nfix += 1
    print('MSGDT: 메시지 %d 중 %d 는 제자리 영역(%d / %d B), %d 개(%d B)는 WIND 끝 블록 0x%X · 주소 표 %d 곳 다시 씀 · 다시 접은 문장 %d'
          % (len(enc), k, len(main_area), MSG_END, len(enc) - k, len(over), WIND_RAM + over_off, nfix, nref))
    # ---- 훅(8×8 C·H2 + hook16) → WIND 옛 가타카나 셀 자리
    blob, c_addr, h2_addr = hook8.build(font8, font_addr=font_addr)
    h16_addr = hook8.BASE + len(blob); h16_addr += -h16_addr % 4
    blob = blob + bytes(h16_addr - hook8.BASE - len(blob)) + hook16(h16_addr, tab_addr)
    if hook8.BLOB_OFF + len(blob) > hook8.BLOB_END:
        raise Err('훅 자리 넘침 %d B' % len(blob))
    wind[hook8.BLOB_OFF:hook8.BLOB_END] = blob + bytes(hook8.BLOB_END - hook8.BLOB_OFF - len(blob))
    assert len(wind) == len(wind0)
    for off, ptrs in reloc_at:
        for i in ptrs:
            struct.pack_into('>I', exe_b, i, WIND_RAM + res_start + off)
    exe_out = hook8.patch_exe(bytes(exe_b), c_addr, h2_addr)
    exe_out = patch_fmt_s(exe_out, h16_addr)
    ev01, fnt = namegrid.build(sid, hook8.id_to_bytes)
    print('8×8: 글 %d줄 · 음절 %d(1바이트 %d) · 글꼴 0x%X · ID→칸 표 0x%X · 훅 %d B (hook16 0x%X)'
          % (n8, len(order8), min(68, len(order8)), font_addr, tab_addr, len(blob), h16_addr))
    print('WIND 끝 블록: 0x%X‥0x%X (%d B)' % (WIND_RAM + res_start, WIND_RAM + TOP, TOP - res_start))
    for w in warns[:20]:
        print('⚠️ ' + w)
    if len(warns) > 20:
        print('⚠️ … 경고 %d건' % len(warns))
    out = os.path.join(ROOT, 'work', 'kr'); os.makedirs(out, exist_ok=True)
    files = {'/ETC/WIND.BIN': bytes(wind), '/0': exe_out, '/ETC/MSGDT.BIN': bytes(new), '/FIELD/FSPR.BIN': bytes(fspr),
             '/EVENT/EV01.BIN': ev01, '/ETC/FNT.BIN': fnt}
    for p, d in files.items():
        open(os.path.join(out, p.strip('/').replace('/', '_')), 'wb').write(d)
    # ⑤ 동영상 화면 자막(tools/moviesub.py 가 구운 work/kr/GM_DEMO.CPK, 원본 크기 그대로 — 느려서 빌드 때 다시 굽지 않음)
    gm = os.path.join(ROOT, 'work', 'kr', 'GM_DEMO.CPK')
    if os.path.exists(gm):
        files['/CINEPACK/GM_DEMO.CPK'] = open(gm, 'rb').read()
        print('동영상: CINEPACK/GM_DEMO.CPK (한글 자막)')
    if '--write' in sys.argv:
        import inplace, disc
        o2 = os.path.join(ROOT, 'work', 'out'); os.makedirs(o2, exist_ok=True)
        dst = os.path.join(o2, os.path.basename(disc.ROM))
        inplace.patch(disc.ROM, dst, files)
        print('→', dst)


if __name__ == '__main__':
    try:
        main()
    except Err as e:
        print('⛔', e); sys.exit(1)
