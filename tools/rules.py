# -*- coding: utf-8 -*-
r"""사이버 돌 번역 규칙 — 빌더가 «반드시» 거친다.
  squeeze(): 문장부호 뒤 공백 1칸 삭제(2칸 이상 = 칸 맞춤이라 둠). 반각·전각 공백 둘 다.
"""
PUNCT_AFTER = set(',.!?:;)]}\'"~') | set('、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥')
SPACES = (' ', '　')


def squeeze(s):
    import re
    out = []; i = 0; n = len(s)
    while i < n:
        out.append(s[i])
        # ★조사 괄호 «이(가) 필요» 의 공백은 낱말 띄어쓰기 — 지우지 않는다(걸리버·린다 큐브에서 겪음)
        josa = s[i] == ')' and re.search(r'\([가-힣]{1,2}\)$', s[:i + 1])
        if s[i] in PUNCT_AFTER and not josa and i + 1 < n and s[i + 1] in SPACES and not (i + 2 < n and s[i + 2] in SPACES):
            i += 2
            continue
        i += 1
    return ''.join(out)


if __name__ == '__main__':
    assert squeeze('어머, 나가는 거야?') == '어머,나가는 거야?'
    assert squeeze('어머、　나가') == '어머、나가'
    assert squeeze('A,  B') == 'A,  B'
    assert squeeze('「X」이(가) 필요합니다.') == '「X」이(가) 필요합니다.'
    assert squeeze('(웃음) 그래') == '(웃음) 그래'
    print('ok')
