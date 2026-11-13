"""
Parser: Prevenção de ISC — indicadores de processo (Checklist de ISC, atb-sistema).

Fonte: o Checklist de ISC (HUSF-FOR-CIH-006-01) digitalizado em /controles/isc e
o mapa cirúrgico importado em /isc/admin/importar. Uma chamada por competência:

    GET /controles/isc/api/competencia?inst=HUSF&mes=YYYY-MM&key=<VIG_API_KEY>

A conformidade é calculada NO APP (isc-regras.mjs), a partir dos fatos gravados —
o pipeline só transporta {n, conf}. Mudou um critério? O app recalcula e a
próxima geração do mês traz o número novo; nada de regra duplicada aqui.

Saída (um ponto da série `iscProcesso` do data_iras.json; `n` = denominador,
`c` = conformes):
    ck        nº de checklists digitalizados no mês
    mapa      True se o mapa cirúrgico do mês foi importado (sem mapa, não há
              adesão — e isso é diferente de adesão zero)
    ades      adesão ao checklist {n, c}: cirurgias cardíacas, neuro e cesáreas
              do mapa com checklist do mesmo paciente/data
    adesEq    {cardio, neuro, ces}: idem, por equipe
    itens     {banho, tricotomia, glicemia, degermacao, antissepsia, maos,
               paramentacao, profilaxia}: conformidade {n, c}
    abp       componentes da antibioticoprofilaxia {realizada, droga, tempo,
              dose, redose}: {n, c}
    excl      checklists de cirurgia contaminada/infectada (fora da profilaxia)
    redoseDesn  dose complementar dada em cirurgia ≤ 4 h
    soltos    checklists que não casaram com cirurgia aplicável do mapa

Nenhum dado de paciente trafega: a API só devolve agregados.
"""
import json
import urllib.request

EQUIPES = {'CARDIO': 'cardio', 'NEURO': 'neuro', 'GO-OBST': 'ces'}


def fetch(base_url, inst, mes, key=None, timeout=30):
    """mes no formato 'YYYY-MM'. Devolve o JSON cru da API."""
    url = (f'{base_url.rstrip("/")}/controles/isc/api/competencia'
           f'?inst={inst}&mes={mes}')
    if key:
        url += f'&key={key}'
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def _nc(x):
    x = x or {}
    return {'n': int(x.get('n') or 0), 'c': int(x.get('conf') or 0)}


def build(api):
    """JSON da API -> ponto da série (sem 'p'/'c'), ou None se o mês não tem dado."""
    ck = int(api.get('checklists') or 0)
    ad = api.get('adesao') or {}
    mapa = bool(ad.get('mapa'))
    if ck == 0 and not mapa:
        return None
    pt = {
        'ck': ck,
        'mapa': mapa,
        'ades': _nc(ad.get('total')) if mapa else None,
        'adesEq': {v: _nc(ad.get(k)) for k, v in EQUIPES.items()} if mapa else None,
        'itens': {k: _nc(v) for k, v in (api.get('itens') or {}).items()},
        'abp': {k: _nc(v) for k, v in (api.get('componentes') or {}).items()},
        'excl': int(api.get('excluidas_profilaxia') or 0),
        'redoseDesn': int(api.get('redose_desnecessaria') or 0),
        'soltos': int(api.get('checklists_sem_cirurgia') or 0),
    }
    if mapa:
        pt['cirMapa'] = int(ad.get('cirurgias_no_mapa') or 0)
    return pt
