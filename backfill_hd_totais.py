#!/usr/bin/env python3
"""
backfill_hd_totais.py — recompõe as séries hd.ilav e hd.bact (totais combinando
todos os acessos, /100 pac-mês) de um ANO no data_iras.json, a partir do mestre do
CVE de diálise. Preserva pontos de outros anos (barras anuais históricas).

Uso: python backfill_hd_totais.py data_iras.json /caminho/CVE_dialise_mestre.xlsx 26
"""
import json, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0] if '/' in __file__ else '.')
from husf_pipeline.parsers._util import XlsxProvider
from husf_pipeline.parsers import dialise

ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']

def main():
    data_path, mestre_path = sys.argv[1], sys.argv[2]
    yy = sys.argv[3] if len(sys.argv) > 3 else '26'
    so_mes = '--so-mes' in sys.argv   # dropa pontos que não são mensais do ano (barras anuais legadas)
    d = json.load(open(data_path, encoding='utf-8'))
    prov = XlsxProvider(mestre_path)
    novos = {'ilav': [], 'bact': []}
    for mi in range(12):
        hd = dialise.parse(prov, mi, 2000 + int(yy))['hd']
        lab = f'{ABBR[mi]}/{yy}'
        for k in ('ilav', 'bact'):
            if hd.get(k) is not None:
                novos[k].append({'p': lab, 'v': hd[k]})
    for k in ('ilav', 'bact'):
        if so_mes:
            antigos = []   # descarta tudo que não é mensal do ano (barras anuais legadas)
        else:
            antigos = [p for p in d['hd'].get(k, []) if not str(p.get('p', '')).endswith(f'/{yy}')]
        serie = [{kk: vv for kk, vv in p.items() if kk != 'c'} for p in (antigos + novos[k])]
        # ordena cronologicamente (mmm/yy); rótulos sem '/' vão pro fim preservando ordem
        _ABBR_IDX = {a: i for i, a in enumerate(ABBR)}
        def _key(p):
            lbl = str(p.get('p', ''))
            if '/' in lbl:
                mm, yy2 = lbl.split('/')
                return (int(yy2), _ABBR_IDX.get(mm[:3], 0))
            return (9999, 0)
        serie.sort(key=_key)
        if serie:
            for p in serie:
                p.pop('c', None)
            serie[-1]['c'] = 1
        d['hd'][k] = serie
        print(f'hd.{k}: {len(antigos)} antigos + {len(novos[k])} de /{yy}  -> {len(serie)} pts, último {serie[-1] if serie else None}')
    json.dump(d, open(data_path, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('OK')

if __name__ == '__main__':
    main()
