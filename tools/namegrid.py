# -*- coding: utf-8 -*-
r"""사이버 돌 이름 입력판 한글화 (2026-09-28)
  입력판 = 6열 × 10행(EV01 +0x3D5C 텍스처 번호 격자, 0xFF 빈칸). 글자 → 코드 = EV01 +0x3DEC[텍스처 번호](RAM 0x2F2DEC).
  글자 그림 = ETC/FNT.BIN 블록(텍스처 번호 = 블록 번호, tools/fntlz.py) 16×16 8bpp, 팔레트 +0x3F10(녹색 명암).
  «가기그게고» 식: 가타카나 아이우에오 열 → ㅏㅣㅡㅔㅗ, 행 = 아·가·사·다·나·하·마·파·라 + ﾜ줄 바비보부 + 작은글자 열 카타차자.
  코드 = 8×8 훅 1바이트 음절 ID(⛔0xDE·0xDF 제외 — 이름 정리 0x06008E62 가 탁점으로 합침).
  대사 속 이름({8025}{8073} = %s)은 바이트 − 0x20 = 16×16 글자 번호 → 같은 번호 칸에 같은 음절을 그려 둔다.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fntlz

EV_TAB = 0x3DEC                     # EV01 코드표
# (텍스처 번호, 음절) — 격자 순서(행마다 6칸, 기능키 52·54·55 = END·英·BS 는 그대로)
GRID = [
    (57, '아'), (65, '이'), (99, '으'), (59, '에'), (82, '오'), (97, '카'),
    (66, '가'), (68, '기'), (70, '그'), (67, '게'), (69, '고'), (103, '타'),
    (88, '사'), (90, '시'), (92, '스'), (89, '세'), (91, '소'), (107, '차'),
    (93, '다'), (95, '디'), (98, '드'), (94, '데'), (96, '도'), (105, '자'),
    (77, '나'), (79, '니'), (81, '느'), (78, '네'), (80, '노'),
    (60, '하'), (62, '히'), (64, '흐'), (61, '헤'), (63, '호'),
    (71, '마'), (73, '미'), (75, '므'), (72, '메'), (74, '모'),
    (102, '파'), (106, '피'), (104, '프'), (53, '페'), (56, '포'),
    (83, '라'), (85, '리'), (87, '르'), (84, '레'), (86, '로'),
    (100, '바'), (101, '비'), (76, '보'), (51, '부'),
]
SYLS = [s for _, s in GRID]
# 판 바꾸기 키(2026-09-30 사용자): 한글판의 «英»(54) → «영», 영문판의 «カナ»(58) → «한글». BS(55)·END(52)는 영어 그대로
FUNC_KEYS = {54: '영', 58: '한글'}
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
LV = [0, 8, 4, 3, 1]                # 명암 0‥4 → 팔레트 번호(밝기 0·10·23·31·40)


def glyph16(ch):
    from PIL import Image, ImageDraw, ImageFont
    F = ImageFont.truetype(FONT, 16)
    im = Image.new('L', (16, 16)); dr = ImageDraw.Draw(im)
    l, t, r, b = dr.textbbox((0, 0), ch, font=F)
    dr.text(((16 - (r - l)) // 2 - l, (16 - (b - t)) // 2 - t), ch, font=F, fill=255)
    return bytes(LV[0 if v < 40 else 1 if v < 90 else 2 if v < 150 else 3 if v < 210 else 4] for v in im.getdata())


GALMURI_C = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11-Condensed.bdf'


def glyph16_fit(text):
    """16×16 한 칸에 두 음절(«한글») — 작은 한글은 벡터 글꼴을 줄이면 뭉개진다 → 갈무리11 콘덴스드 비트맵(음절 폭 ~7)을
       나란히, 가운데 맞춤, 가장 밝은 단계 하나"""
    sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
    import bdf
    F = bdf.Font(GALMURI_C)
    pts = []; x = 0
    for ch in text:
        p, adv = F.draw(ch, x, 0)
        pts += p; x += adv
    xs = [a for a, _ in pts]; ys = [b for _, b in pts]
    dx = (16 - (max(xs) - min(xs) + 1)) // 2 - min(xs); dy = (16 - (max(ys) - min(ys) + 1)) // 2 - min(ys)
    g = bytearray(256)
    for a, b in pts:
        if 0 <= a + dx < 16 and 0 <= b + dy < 16:
            g[(b + dy) * 16 + a + dx] = LV[4]
    return bytes(g)


def build(sid, id_to_bytes):
    """sid = 음절 → ID. 반환 (새 EV01, 새 FNT)"""
    ev = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'EVENT_EV01.BIN'), 'rb').read())
    f = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'ETC_FNT.BIN'), 'rb').read())
    P = fntlz.fnt_blocks(bytes(f)) + [0x20A8]
    blocks = {k: bytes(f[P[k]:P[k + 1]]) for k in range(108)}
    for tex, s in GRID:
        code = id_to_bytes(sid[s])
        assert len(code) == 1 and code[0] not in (0xDE, 0xDF, 0x20), (s, code)
        ev[EV_TAB + tex] = code[0]
        blocks[tex] = b'\x10\x00\x10\x00' + fntlz.encode2(glyph16(s))
    for tex, s in FUNC_KEYS.items():
        blocks[tex] = b'\x10\x00\x10\x00' + fntlz.encode2(glyph16(s) if len(s) == 1 else glyph16_fit(s))
    # 블록 다시 싣기(순서 그대로, 0x20A8 안) + 주소표
    o = 0; body = bytearray()
    for k in range(108):
        struct.pack_into('>I', f, 0x20A8 + 4 * k, 0x295000 + o)
        body += blocks[k]; o += len(blocks[k])
    assert len(body) <= 0x20A8, ('FNT 블록 자리 넘침', len(body))
    f[:0x20A8] = bytes(body) + bytes(0x20A8 - len(body))
    for k in range(108):                        # 되풀기 검사
        p = struct.unpack_from('>I', f, 0x20A8 + 4 * k)[0] - 0x295000
        out, _ = fntlz.decode(bytes(f), p + 4)
        assert len(out) == f[p] * f[p + 2], k
    print('이름판 %d자 · FNT 블록 %d / %d B' % (len(GRID), len(body), 0x20A8))
    return bytes(ev), bytes(f)
