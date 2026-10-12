#!/usr/bin/env python3
"""
backfill_neo_ipcs.py — recompõe a série utiNeo.ipcs de um ano no data_iras.json a
partir do CVE Mestre (Plan3 Neo), acrescentando casos (n) e cat-dia (cd) a cada ponto
mensal — necessário p/ a barra de erro (IC95%) e o g-chart. Preserva pontos anuais.

Uso: python backfill_neo_ipcs.py data_iras.json /caminho/PLANILHA_CVE_HUSF_mestre.xlsx 26
"""
import json, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0] if '/' in __file__ else '.')
from husf_pipeline.parsers._util import XlsxProvider
from husf_pipeline.parsers import cve_mestre

ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
_IDX = {a: i for i, a in enumerate(ABBR)}

def main():
    data_path, mestre_path = sys.argv[1], sys.argv[2]
    yy = sys.argv[3] if len(sys.argv) > 3 else '26'
    d = json.load(open(data_path, encoding='utf-8'))
    prov = XlsxProvider(mestre_path)
    novos = []
    for mi in range(12):
        neo = cve_mestre.parse(prov, mi, 2000 + int(yy))['neo']
        if neo.get('ipcs') is None:
            continue
        cd = neo.get('ipcs_cd')
        if not cd:                       # mês sem cat-dia (unidade sem dado) → pula
            continue
        novos.append({'p': f'{ABBR[mi]}/{yy}', 'v': neo['ipcs'],
                      'n': neo.get('ipcs_n', 0), 'cd': cd})
    antigos = [p for p in d['utiNeo'].get('ipcs', []) if not str(p.get('p', '')).endswith(f'/{yy}')]
    serie = [{k: v for k, v in p.items() if k != 'c'} for p in (antigos + novos)]
    def key(p):
        lbl = str(p.get('p', ''))
        if '/' in lbl:
            mm, yy2 = lbl.split('/'); return (int(yy2), _IDX.get(mm[:3], 0))
        if lbl.isdigit():                 # ano anual (ex.: '2025') → antes dos meses daquele ano
            return (int(lbl) % 100, -1)
        return (9999, 0)
    serie.sort(key=key)
    if serie:
        serie[-1]['c'] = 1
    d['utiNeo']['ipcs'] = serie
    json.dump(d, open(data_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'utiNeo.ipcs: {len(antigos)} antigos + {len(novos)} de /{yy}  ({len(serie)} pts)')
    print('último:', serie[-1] if serie else None)

if __name__ == '__main__':
    main()
