"""
Parser: CVE UTI C (arquivo .xlsx local).

Porta `parseUTIC` do HTML. Extrai os valores DEFINITIVOS da UTIC e as
unidades BRUTAS do UCO usadas para derivar a UTI A/B (combinado - UCO):
  - Plan4: HM alcool UCO (col G=6 ml, col I=8 pac-dia) -> uc_hm + crus.
  - Plan6: DDDs UTIC. Bloco mensal em P6_STARTS[mes]; nome col 13,
    consumo /1000pd col 17, unidades brutas col 16. Somado por grupo de ATB.

Saida -> {utic:{hm,pip,carba,glico,poli}, _uco_alcool_ml, _uco_pd,
          _uco_pip_u, _uco_carba_u, _uco_glico_u, _uco_poli_u}.
"""

from ._util import num, r1

_P6_STARTS = [14, 70, 125, 180, 235, 290, 345, 400, 455, 510, 565, 620]
_ATB_GROUPS = {
    'pip':   ['Piperacilina-tazobactam'],
    'carba': ['Meropenem', 'Imipenem', 'Ertapenem'],
    'glico': ['Vancomicina', 'Teicoplanina'],
    'poli':  ['Sulfato de Polimixina B', 'Sulfato de Polimixina E'],
}


def _sheet(provider, *names):
    tabs = provider.tabs()
    for n in names:
        if n in tabs:
            return provider.values(n)
    for n in names:
        for t in tabs:
            if t.startswith(n.split(' ')[0]):
                return provider.values(t)
    return None


def parse(provider, mes_idx, ano):
    res = {'fonte': 'cve_utic', 'mes': None}

    # Plan4 - HM alcool UCO
    hm = None
    uco_ml = uco_pd = None
    d4 = _sheet(provider, 'Plan4 - P.alcoolico e sabonete', 'Plan4')
    if d4:
        ridx = 15 + mes_idx
        if ridx < len(d4) and d4[ridx]:
            r = d4[ridx]
            uco_ml = num(r[6]) if len(r) > 6 else None
            uco_pd = num(r[8]) if len(r) > 8 else None
            hm = round(uco_ml / uco_pd, 1) if (uco_ml is not None and uco_pd) else None

    # Plan6 - DDDs UTIC (consumo) + unidades brutas
    consumo = {'pip': 0.0, 'carba': 0.0, 'glico': 0.0, 'poli': 0.0}
    unidades = {'pip': 0.0, 'carba': 0.0, 'glico': 0.0, 'poli': 0.0}
    d6 = _sheet(provider, 'Plan6 - DDD', 'Plan6')
    if d6:
        base = _P6_STARTS[mes_idx]
        for i in range(3, 41):
            ridx = base + i
            if ridx >= len(d6):
                break
            row = d6[ridx]
            if not row:
                continue
            nome = str(row[13]).strip() if len(row) > 13 and row[13] else ''
            if not nome:
                continue
            c = num(row[17]) if len(row) > 17 else 0
            u = num(row[16]) if len(row) > 16 else 0
            for grp, frags in _ATB_GROUPS.items():
                if any(f in nome for f in frags):
                    consumo[grp] += c
                    unidades[grp] += u

    res['utic'] = {'hm': hm, **{k: r1(v) for k, v in consumo.items()}}
    res['_uco_alcool_ml'] = uco_ml
    res['_uco_pd'] = uco_pd
    for grp in ('pip', 'carba', 'glico', 'poli'):
        res['_uco_' + grp + '_u'] = unidades[grp]
    return res
