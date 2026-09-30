# -*- coding: utf-8 -*-
r"""사이버 돌 배포 묶음 — dist/CyberDoll_KR_<VER>/ : 트랙 01 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat
  검증: 원본 트랙 01 → xdelta 적용 → md5 = 빌드 결과(work/out) md5.
  python tools/make_dist.py   (먼저 python tools/build.py --write)
"""
import hashlib, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc

VER = 'v0.9'
XDELTA = r'C:\claude\utils\xdelta.exe'
OUT = os.path.join(ROOT, 'work', 'out')
NAME = 'CyberDoll_KR_' + VER
TITLE = '사이버 돌 (세가 새턴 일본판) 한글 패치 ' + VER
ROMNAME = 'Cyber Doll (Japan)'
TRACKS = 11


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 1번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 01 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 01 이름으로 바꿔 넣고, 나머지 트랙과 cue 는 그대로 쓰세요
     (트랙 01 크기는 그대로라 cue 는 고칠 필요 없습니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 01" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - 대사 전부(16×16 대화창)
  - 무기·부품·칩·아이템·적 이름, 메뉴·상태·저장 화면의 일본어 문구(8×8 글자)
  - 이름 입력판(한글 음절판), 대사 속 주인공·아이템 이름
  - 게임 소개 영상(GM_DEMO) 화면 자막
  - 영어 메뉴 라벨(ATTACK·ITEM 등)은 원래 영어 그대로 둡니다.


[ 알려진 점 ]

  - 아직 끝까지 실기로 통독하지 못했습니다. 이상한 곳이 있으면 알려 주세요.
  - 창 폭(한 줄 18칸) 때문에 긴 줄은 낱말 단위로 다시 접었습니다.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 01 파일을 이 폴더에 넣어 주세요(readme 참고).
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다(readme 의 원본md5 확인).
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    os.makedirs(d, exist_ok=True)
    b = ROMNAME + ' (Track 01).bin'
    src = disc.ROM; out = os.path.join(OUT, b)
    assert os.path.basename(src) == b
    patch = NAME + '.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-s', src, out, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-s', src, pp, chk], check=True)
    o, want, got = md5(src), md5(out), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    kbin = ROMNAME + ' (Track 01) [KR].bin'
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = (TITLE + '\n' + '=' * 60 + '\n\n' + HEAD.format(tracks=TRACKS, rom=ROMNAME, o=o, d=want)
              + BODY.format(bin=b, patch=patch))
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(
        BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    print('원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-40s %12d' % (f, os.path.getsize(os.path.join(d, f))))


if __name__ == '__main__':
    main()
