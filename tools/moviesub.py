# -*- coding: utf-8 -*-
r"""사이버 돌 GM_DEMO(게임 소개 영상) 화면 자막 한글화 (2026-10-01)
  영상 = CINEPACK/GM_DEMO.CPK: Sega FILM Cinepak 352×112(화면에 1:1 — 원문 일본어 글자 10×10), 15fps, 모든 프레임 키, 띠 1개.
  ⚠처음(10-01)엔 «세로 반 해상도»로 잘못 알고 2배 높이로 그려 반으로 줄임 → 실기에서 글자가 위아래로 눌림(사용자) → 제 크기로 그림.
  자막 = 그림 아래 97‥106줄에 일본어 흰 글자(음성 없음, 내레이션 글).
  ① 프레임 전부 → work/movie/gm/fr/(ffmpeg) · 자막 띠(95‥108줄) 흰 글자 모양이 바뀌는 곳으로 구간 → work/movie/gm/segs.json
  ② 자막 표 my files/tsv/movie_subs.tsv (영상 · 구간 번호들 · 원문 · 번역) — 연도(A.D.xxxx)·영어만 있는 줄은 원본 그대로(표에 없음)
  ③ 자막마다 [첫 구간 − PAD, 끝 구간 + PAD] 프레임(이웃 자막과 겹치지 않게)의 띠 94‥110줄을 검게 칠하고,
     나눔고딕 Bold PX + 검은 1px 테두리로 한글을 제 크기로 그려 얹음 → work/movie/gm/kr/
  ④ 그 프레임만 cinepak 재굽기(tools/movenc.py, 프레임별 원래 바이트 이하 — 모자라면 앞에서 남긴 바이트) → work/kr/GM_DEMO.CPK(원본 크기)
  미리보기 work/movie/gm/GM_DEMO_kr.mp4
  python tools/moviesub.py
"""
import glob, json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import movenc, rules

FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX = 13
W, H = 352, 112
BAND = (94, 111)                    # 검게 칠할 줄(반 해상도)
X0 = 12                             # 원문처럼 왼쪽 맞춤
PAD = 5                             # 원문 글자가 흐려지며 나타나고 사라지는 프레임까지 덮기
DONOR = 150                         # 바이트를 갚을 끝쪽 자막 없는 프레임 수
EXT = 40                            # 구간 앞뒤로 흰 글자 따라 넓힐 최대 프레임
GM = os.path.join(ROOT, 'work', 'movie', 'gm')
SRC = os.path.join(ROOT, 'work', 'movie', 'GM_DEMO.CPK')
TSV = os.path.join(ROOT, 'my files', 'tsv', 'movie_subs.tsv')
OUT = os.path.join(ROOT, 'work', 'kr', 'GM_DEMO.CPK')


def rows():
    out = []
    for ln in open(TSV, encoding='utf-8').read().split('\n')[1:]:
        c = ln.split('\t')
        if len(c) >= 4 and c[0] == 'GM_DEMO' and c[3].strip():
            out.append(([int(x) for x in c[1].split(',')], c[2], rules.squeeze(c[3].strip())))
    return out


def plate(text, F):
    """352×112 RGBA 판: 띠는 검정, 한글은 제 크기(화면 1:1)"""
    big = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
    w = d.textlength(text, font=F)
    assert X0 + w <= W - 4, ('줄 넘침 %dpx' % w, text)
    l, t, r, b = d.textbbox((0, 0), text, font=F)
    y = (BAND[0] + BAND[1]) // 2 - (b + t) // 2      # 띠 가운데
    assert y + t - 1 >= BAND[0] and y + b + 1 <= BAND[1], ('띠 밖', text)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                d.text((X0 + dx, y + dy), text, font=F, fill=(0, 0, 0, 255))
    d.text((X0, y), text, font=F, fill=(255, 255, 255, 255))
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(base).rectangle((0, BAND[0], W - 1, BAND[1] - 1), fill=(0, 0, 0, 255))
    return Image.alpha_composite(base, big)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    segs = json.load(open(os.path.join(GM, 'segs.json')))
    rs = rows()
    F = ImageFont.truetype(FONT, PX)
    # ★구간 감지는 자막이 밝은 그림 위로 먼저 나타나는 프레임을 놓친다(2026-10-01 «一人の男が…» 앞 11프레임 일본어 남음)
    #   → 띠의 흰 글자 수(cnt)가 이어지는 동안 앞뒤로 넓히고(이웃 자막 경계·최대 EXT 프레임), 그 뒤 PAD
    cnt = json.load(open(os.path.join(GM, 'cnt.json')))
    raw = [[segs[s[0]][0], segs[s[-1]][1]] for s, _, _ in rs]
    spans = []
    for k, (a, b) in enumerate(raw):
        lo = raw[k - 1][1] + 1 if k else 0
        hi = raw[k + 1][0] - 1 if k + 1 < len(raw) else len(cnt) - 1
        while a - 1 >= lo and cnt[a - 1] >= 30 and raw[k][0] - (a - 1) <= EXT:
            a -= 1
        while b + 1 <= hi and cnt[b + 1] >= 30 and (b + 1) - raw[k][1] <= EXT:
            b += 1
        spans.append([max(lo, a - PAD), min(hi, b + PAD)])
    for k in range(1, len(spans)):                  # 이웃과 겹치면 가운데서 가름
        if spans[k][0] <= spans[k - 1][1]:
            mid = (spans[k - 1][1] + spans[k][0]) // 2
            spans[k - 1][1] = mid; spans[k][0] = mid + 1
    nfr = len(glob.glob(os.path.join(GM, 'fr', 'f*.png')))
    kr = os.path.join(GM, 'kr'); os.makedirs(kr, exist_ok=True)
    for f in glob.glob(os.path.join(kr, 'f*.png')):
        os.remove(f)
    n = 0
    for (seg, jp, ko), (a, b) in zip(rs, spans):
        p = plate(ko, F)
        for i in range(max(0, a), min(nfr - 1, b) + 1):
            im = Image.open(os.path.join(GM, 'fr', 'f%04d.png' % (i + 1))).convert('RGBA')
            Image.alpha_composite(im, p).convert('RGB').save(os.path.join(kr, 'f%04d.png' % (i + 1)))
            n += 1
    print('자막 %d줄 · 덮은 프레임 %d / %d' % (len(rs), n, nfr))
    # 자막 프레임은 글씨 때문에 원래보다 조금 커져 합계가 자리를 넘는다(2026-10-01 첫 굽기 +1,240 B) →
    # 끝의 자막 없는 프레임(로고 등) DONOR 장을 원본 그림 그대로 다시 구워(빚이 있으면 q 를 올림) 모자란 바이트를 갚는다
    done = {int(os.path.basename(p)[1:5]) - 1 for p in glob.glob(os.path.join(kr, 'f*.png'))}
    donors = [i for i in range(nfr - 1, -1, -1) if i not in done][:DONOR]
    for i in donors:
        Image.open(os.path.join(GM, 'fr', 'f%04d.png' % (i + 1))).save(os.path.join(kr, 'f%04d.png' % (i + 1)))
    print('기증 프레임 %d장(%d‥%d)' % (len(donors), min(donors) + 1, max(donors) + 1))
    room = os.path.getsize(SRC)
    L = movenc.reencode(SRC, os.path.join(GM, 'fr'), kr, OUT, room, log=lambda *a: None)
    data = open(OUT, 'rb').read()
    open(OUT, 'wb').write(data + bytes(room - len(data)))           # 원본 크기(디스크 제자리)
    print('→ %s %d B (다시 구운 내용 %d B)' % (OUT, room, L))
    # 미리보기: 원본 프레임 + 덮은 프레임 → mp4(세로 두 배)
    prev = os.path.join(GM, 'prev'); os.makedirs(prev, exist_ok=True)
    subprocess.run([FF, '-v', 'error', '-y', '-i', OUT, '-vf', 'scale=352:224', '-c:v', 'libx264', '-crf', '18',
                    '-c:a', 'aac', os.path.join(GM, 'GM_DEMO_kr.mp4')], check=True)
    print('미리보기', os.path.join(GM, 'GM_DEMO_kr.mp4'))


if __name__ == '__main__':
    main()
