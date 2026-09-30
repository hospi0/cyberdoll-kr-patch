# -*- coding: utf-8 -*-
r"""사이버 돌 PoC (2026-09-28) — 대사 667·39번 → 한글 + 무기 이름 8×8 한글. ⛔영어 문자열은 안 건드림(사용자)
  글꼴 = ETC/WIND.BIN +0x5A82, 16×16 2bpp (tools/ocrmap.py 형식). 대본이 안 쓰는 칸 0x4E8‥0x51F(56칸)에 한글을 그림 → 원래 글자 불변.
  글자 = 나눔고딕 16px 을 16×16 에 그려 명암 4단계(0‥3)로 — 게임 글꼴처럼 가는 획 + 흐린 가장자리.
  대사 = MSGDT.BIN 메시지 667 을 새 글자 번호로(길이를 원문과 «다르게» — 번호로 세어 부르는지 시험), 파일 크기는 그대로(끝 0 영역에서 맞춤).
  + 8×8 한글(2026-09-28): 동적 셀 캐시 훅 tools/hook8.py(WIND.BIN 끝 + 실행 파일 패치) · 무기 이름 work/tr/names_weapons.tsv → FIELD/FSPR.BIN.
  python tools/poc.py [--write]  → work/kr/ETC_WIND.BIN · ETC_MSGDT.BIN · FIELD_FSPR.BIN · 0 (· --write: 트랙 01 → work/out)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ocrmap, dump, rules
from PIL import Image, ImageDraw, ImageFont
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothic.ttf'
FREE0 = 0x4E8                       # 대본이 안 쓰는 칸 시작(쓰는 번호 최대 0x4E7)
MSGS = {667: '어머,나가는 거야?',                              # 번호 → 한글(줄바꿈 \n = 800A, 끝 800A 자동)
        39: '잔탄이 줄어든 무기의\n탄창을 교환했습니다.'}      # 무기 목록 화면 대사(원문 «残弾の減少している武器の／マガジンを交換しました。»)
FONT8 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'
PUNCT = {'。': 0x81, '.': 0x81, '、': 0x84, ',': 0x84, '？': 0x1F, '?': 0x1F, '！': 0x01, '!': 0x01, ' ': 0x00, '　': 0x00, '…': None}


def put_glyph(d, c, g):
    """g = 16×16 명암(0‥3) → 글꼴 칸 c"""
    for half, off in ((0, 0), (1, 0x400)):
        a = ocrmap.FONT_OFF + (c >> 5) * 0x800 + (c & 31) * 32 + off
        for cell in (0, 1):
            for y in range(8):
                for bx in range(2):
                    b = 0
                    for k, s in enumerate((6, 4, 2, 0)):
                        b |= (g[half * 8 + y][cell * 8 + bx * 4 + k] & 3) << s
                    d[a + cell * 16 + y * 2 + bx] = b


def render(ch, F):
    im = Image.new('L', (16, 16)); dr = ImageDraw.Draw(im)
    l, t, r, b = dr.textbbox((0, 0), ch, font=F)
    dr.text(((16 - (r - l)) // 2 - l, (16 - (b - t)) // 2 - t), ch, font=F, fill=255)
    px = im.load()
    return [[(3 if px[x, y] >= 170 else 2 if px[x, y] >= 100 else 1 if px[x, y] >= 40 else 0) for x in range(16)] for y in range(16)]


def bdf_glyph(ch):
    """갈무리7 BDF → (행 목록, x0, 맨 윗줄) — 기준선 아래 끝 = 7줄째"""
    for b in open(FONT8, encoding='utf-8').read().split('STARTCHAR'):
        if '\nENCODING %d\n' % ord(ch) in b:
            ln = b.split('\n'); i = ln.index('BITMAP'); rows = ln[i + 1:ln.index('ENDCHAR')]
            w, h, x0, y0 = map(int, [l for l in ln if l.startswith('BBX')][0].split()[1:])
            return [[(int(r, 16) >> (len(r) * 4 - 1 - x)) & 1 for x in range(w)] for r in rows], x0, 7 - h - y0
    raise KeyError(ch)


def glyph8(ch):
    """갈무리7 → 1bpp 8바이트(줄마다 MSB = 왼쪽)"""
    rows, x0, top = bdf_glyph(ch)
    g = bytearray(8)
    for y, r in enumerate(rows):
        for x, v in enumerate(r):
            px = x0 + x
            if v and 0 <= top + y < 8 and px < 8:
                g[top + y] |= 0x80 >> px
    return bytes(g)


def menu_poc(wind):
    """8×8 한글 = 동적 셀 캐시 훅(tools/hook8.py). 무기 이름 번역(work/tr/names_weapons.tsv) → FSPR, 훅·글꼴 → WIND 끝, 실행 파일 패치.
       음절 ID = 쓰는 횟수 순(앞 68개 1바이트). 반환 (FSPR, 새 WIND 바이트, 새 실행 파일)"""
    import csv, collections, hook8, names
    fspr = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'FIELD_FSPR.BIN'), 'rb').read())
    offs = {'%03d' % k: (o, s.rstrip()) for k, (o, s) in enumerate(names.names(bytes(fspr)))}
    tr = []
    for n, jp, kr in list(csv.reader(open(os.path.join(ROOT, 'work', 'tr', 'names_weapons.tsv'), encoding='utf-8'), delimiter='	'))[1:]:
        assert offs[n][1] == jp, ('번호·원문 불일치', n, jp, offs[n][1])
        tr.append((offs[n][0], rules.squeeze(kr)))
    import namegrid
    cnt = collections.Counter(ch for _, kr in tr for ch in kr if '가' <= ch <= '힣')
    # ★음절 ID: 이름 입력판 53자가 먼저(1바이트 0‥52, 0xDE·0xDF 피함) → 나머지는 쓰는 횟수 순
    order = list(namegrid.SYLS) + [s for s, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0])) if s not in namegrid.SYLS]
    sid = {ch: i for i, ch in enumerate(order)}
    for off, kr in tr:
        out = b''.join(hook8.id_to_bytes(sid[ch]) if '가' <= ch <= '힣' else ch.encode('cp932') for ch in kr)
        assert len(out) <= 12, (kr, len(out))
        fspr[off:off + 12] = out.ljust(12, b' ')
    print('8×8 이름 %d개 · 음절 %d(1바이트 %d)' % (len(tr), len(order), min(len(order), 68)))
    # 대사 속 이름: 바이트 − 0x20 = 16×16 칸 → 1바이트 음절 전부 그 칸에 16×16 글리프
    F16 = ImageFont.truetype(FONT, 16)
    for i, ch in enumerate(order[:68]):
        put_glyph(wind, hook8.id_to_bytes(i)[0] - 0x20, render(ch, F16))
    ev01, fnt = namegrid.build(sid, hook8.id_to_bytes)
    blob, c_addr, h2_addr = hook8.build([glyph8(ch) for ch in order])
    assert hook8.BLOB_OFF + len(blob) <= hook8.BLOB_END, ('8×8 훅 자리 넘침', len(blob))
    w = bytes(wind[:hook8.BLOB_OFF]) + blob + bytes(hook8.BLOB_END - hook8.BLOB_OFF - len(blob)) + bytes(wind[hook8.BLOB_END:])
    assert len(w) == len(wind)
    exe = hook8.patch_exe(open(os.path.join(ROOT, 'work', 'disc', '0'), 'rb').read(), c_addr, h2_addr)
    print('훅 %d B @ %X (C %X · H2 %X) · WIND %d → %d B' % (len(blob), hook8.BASE, c_addr, h2_addr, len(wind), len(w)))
    return bytes(fspr), w, exe, ev01, fnt


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    wind = bytearray(open(ocrmap.WIND, 'rb').read())
    msgdt = open(os.path.join(ROOT, 'work', 'disc', 'ETC_MSGDT.BIN'), 'rb').read()
    F = ImageFont.truetype(FONT, 16)
    ms = dump.messages(); orig = dump.messages()
    kmap = {}
    for no, t in MSGS.items():
        text = rules.squeeze(t)             # 부호 뒤 공백은 빌더가 무조건 지운다
        codes = []
        for ch in text:
            if '가' <= ch <= '힣':
                if ch not in kmap:
                    c = FREE0 + len(kmap); assert c < 0x520, '16×16 빈칸 부족'
                    put_glyph(wind, c, render(ch, F)); kmap[ch] = c
                codes.append(kmap[ch])
            elif ch == '\n':
                codes.append(0x800A)
            else:
                codes.append(PUNCT[ch])
        codes.append(0x800A)
        ms[no] = codes
        print('메시지 %d: %d → %d 글자 · %s' % (no, len(orig[no]), len(codes), ' '.join('%X' % v for v in codes)))
    print('한글 %d음절 → 칸 %X‥%X' % (len(kmap), FREE0, FREE0 + len(kmap) - 1))
    # MSGDT 다시 잇기(파일 크기 그대로)
    body = b''.join(struct.pack('>%dH' % len(m), *m) + b'\xff\xff' for m in orig)
    tail = msgdt[len(body):]
    nb = b''.join(struct.pack('>%dH' % len(m), *m) + b'\xff\xff' for m in ms)
    delta = len(nb) - len(body)
    assert tail[:max(delta, 0)] == bytes(max(delta, 0)), '끝 0 영역 부족'
    new = nb + (tail[delta:] if delta >= 0 else bytes(-delta) + tail)
    assert len(new) == len(msgdt)
    # ★파일 뒤 표(0x2D298‥ 4바이트 정렬, [메시지 절대주소 0x060C8000+오프셋, 다른 포인터] 짝)가 메시지를 «주소»로 부른다
    #  → 길이가 바뀌면 옛 시작 주소를 새 시작 주소로 전부 바꿔야 한다(안 하면 뒤 메시지 앞에 찌꺼기 글자, 2026-09-28 실기)
    def starts(msgs):
        o = 0; r = []
        for m in msgs:
            r.append(0x060C8000 + o); o += len(m) * 2 + 2
        return r
    remap = dict(zip(starts(orig), starts(ms)))
    new = bytearray(new); nfix = 0
    for p in range(len(nb) + 3 & ~3, len(new) - 3, 4):
        v = struct.unpack_from('>I', new, p)[0]
        if v in remap:
            struct.pack_into('>I', new, p, remap[v]); nfix += 1
    new = bytes(new)
    print('MSGDT 주소 표: %d 개 다시 씀' % nfix)
    print('MSGDT: %+d B, 크기 그대로 %d B' % (delta, len(new)))
    fspr, wind_out, exe, ev01, fnt = menu_poc(wind)
    os.makedirs(os.path.join(ROOT, 'work', 'kr'), exist_ok=True)
    open(os.path.join(ROOT, 'work', 'kr', 'FIELD_FSPR.BIN'), 'wb').write(fspr)
    open(os.path.join(ROOT, 'work', 'kr', 'ETC_WIND.BIN'), 'wb').write(wind_out)
    open(os.path.join(ROOT, 'work', 'kr', '0'), 'wb').write(exe)
    open(os.path.join(ROOT, 'work', 'kr', 'ETC_MSGDT.BIN'), 'wb').write(new)
    # 미리보기
    raw = ocrmap.glyphs(bytes(wind), 0x520)
    codes = [v for v in ms[39] if v != 0x800A]
    pv = Image.new('L', (len(codes) * 17, 16), 30); p = pv.load()
    for k, v in enumerate(codes):
        for y in range(16):
            for x in range(16):
                if raw[v][y][x]:
                    p[k * 17 + x, y] = int(60 + raw[v][y][x] * 65)
    pv.resize((pv.width * 4, 64), Image.NEAREST).save(os.path.join(ROOT, 'work', 'poc_preview.png'))
    if '--write' in sys.argv:
        import inplace, disc
        out = os.path.join(ROOT, 'work', 'out'); os.makedirs(out, exist_ok=True)
        dst = os.path.join(out, os.path.basename(disc.ROM))
        inplace.patch(disc.ROM, dst, {'/ETC/WIND.BIN': wind_out, '/0': exe, '/ETC/MSGDT.BIN': new, '/FIELD/FSPR.BIN': fspr, '/EVENT/EV01.BIN': ev01, '/ETC/FNT.BIN': fnt})
        print('→', dst)


if __name__ == '__main__':
    main()
