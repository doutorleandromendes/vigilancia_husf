#!/usr/bin/env python3
"""
comparar_vig.py — roda o parser novo (vig_competencia) contra um mês que JÁ foi
gerado pelas planilhas e mostra, lado a lado, onde os dois discordam.

Agosto/26 existe nas duas fontes (Sheets e vig_censo), então é o juiz da
migração: divergência esperada é só a do denominador (pac-dia dos dias
coletados vs mês inteiro). Qualquer outra é bug de mapeamento.

Uso:
  export VIG_API_KEY=...        # mesma chave do Render
  python3 comparar_vig.py data_iras.json 2026-08 ago/26
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from husf_pipeline.parsers import vig_competencia as VC
except ImportError:
    import vig_competencia as VC

BASE = os.environ.get('VIG_URL', 'https://app.lcmendes.med.br')
KEY = os.environ.get('VIG_API_KEY')
INST = os.environ.get('VIG_INST', 'HUSF')


def ponto(serie, label):
    """Valor do ponto `label` numa série [{p, v}]."""
    for pt in serie or []:
        if pt.get('p') == label:
            return pt.get('v')
    return None


def linha(nome, antigo, novo):
    if antigo is None and novo is None:
        return
    if antigo in (None, 0) or novo is None:
        delta = '—'
    else:
        delta = f'{(novo - antigo) / antigo * 100:+.0f}%'
    flag = ''
    if antigo is not None and novo is not None:
        try:
            if abs(novo - antigo) > max(0.01, abs(antigo) * 0.02):
                flag = '  ←'
        except TypeError:
            pass
    a = '—' if antigo is None else f'{antigo:>8.2f}'
    n = '—' if novo is None else f'{novo:>8.2f}'
    print(f'  {nome:<34} planilha={a}   vig={n}   {delta:>6}{flag}')


def main():
    data_path, mes_api, label = sys.argv[1], sys.argv[2], sys.argv[3]
    d = json.load(open(data_path, encoding='utf-8'))

    api = VC.fetch(BASE, INST, mes_api, KEY)
    novo = VC.build_all(api)

    print(f'\n=== cobertura ({mes_api}) ===')
    print('  resumo:', api.get('resumo'))
    for b, c in VC.cobertura_resumo(api).items():
        print(f'  {b:<12} setores={c["setores"]:<3} dias {c["dias_min"]}–{c["dias_max"]}')

    print(f'\n=== MDR — densidade /1000 pac-dia ({label}) ===')
    mdr = novo['censo_mdr']
    for unit, node in (('ab', 'utiAB'), ('uc', 'utic'), ('neo', 'utiNeo')):
        mm = (d.get('mdrMensal') or {}).get(node) or {}
        for org in ('esbl', 'acin', 'kpc', 'pseu'):
            linha(f'{node}.{org}', ponto(mm.get(org), label), mdr[unit].get(f'{org}_r'))
        linha(f'{node}.pac-dia', ponto(mm.get('pd'), label), mdr[unit].get('pd'))

    print(f'\n=== ISC global ({label}) ===')
    ig = [p for p in (d.get('isc') or {}).get('global', []) if p.get('p') == label]
    ant = ig[0] if ig else {}
    linha('isc.n',    ant.get('isc'),  novo['censo_isc']['isc']['n'])
    linha('isc.pd',   ant.get('pd'),   novo['censo_isc']['isc']['pd'])
    linha('isc.taxa', ant.get('taxa'), novo['censo_isc']['isc']['taxa'])

    print(f'\n=== Diarreia — /1000 pac-dia ({label}) ===')
    for k in ('cm', 'cc', 'epm', 'utiab', 'utic'):
        linha(f'diarreia.{k}', ponto((d.get('diarreia') or {}).get(k), label),
              novo['diarreia']['diarreia'].get(k))

    print(f'\n=== Isolamentos ({label}) ===')
    iso_novo = novo['isolamentos']
    for metric in ('novos_total', 'novos_pc', 'confirmados_total', 'confirmados_pc'):
        antm = (d.get('isolamentos') or {}).get(metric) or {}
        for ward, vals in sorted(iso_novo.get(metric, {}).items()):
            a = [p for p in antm.get(ward, []) if p.get('p') == label]
            a_n = a[0].get('n') if a else None
            linha(f'{metric}.{ward}.n', a_n, vals.get('n'))

    print(f'\n=== DOTs ({label}) ===')
    for atb in ('cef', 'pip', 'cbp', 'gpp', 'pb'):
        nd = (novo['dots']['dots'].get(atb) or {})
        for u in ('utiab', 'utic', 'clin', 'cir', 'apto', 'epm', 'utineo'):
            linha(f'dots.{atb}.{u}',
                  ponto(((d.get('dots') or {}).get(atb) or {}).get(u), label),
                  nd.get(u))

    print('\n←  = divergência acima de 2%. Esperado em taxas (muda o denominador);'
          '\n    NÃO esperado em contagens absolutas (n, pac-dia) — isso é mapeamento.\n')


if __name__ == '__main__':
    main()
