#!/usr/bin/env python3
# limpar_mes.py — remove todos os pontos de uma competência das séries do data_iras.json
# Uso: python3 limpar_mes.py data_iras.json ago/26
import json, sys

path, alvo = sys.argv[1], sys.argv[2]
d = json.load(open(path, encoding='utf-8'))
n = 0
def limpa(o):
    global n
    if isinstance(o, list):
        antes = len(o)
        o[:] = [x for x in o if not (isinstance(x, dict) and x.get('p') == alvo)]
        n += antes - len(o)
        for x in o: limpa(x)
    elif isinstance(o, dict):
        for v in o.values(): limpa(v)
limpa(d)
json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'removidos {n} pontos de {alvo!r} em {path}')
