"""
Parser: CVE Mestre (arquivo .xlsx local) — o backbone.

Porta `parseCVE` do entrada_dados (HTML). Extrai do CVE mestre:
  - Plan2 'UTI': dispositivos e infecções de UTI A/B (linha UTI-1) e UTIC (UTI-2).
      bloco de janeiro em idx 30, passo 17 linhas; UTI-1 = +3, UTI-2 = +4.
      cols: pn(1)=pneumonia, ipcs_lab(2), iu(3)=ITU, vm(4)=VM-dias,
            ct(5)=CVC-dias, sv(6)=SVD-dias, pac_dia(7).
  - Plan3 'UTINeo': IPCS Neo somando faixas de peso (offsets 3..7).
      bloco jan idx 16, passo 15; cols pn(1), ipcs_lab(2), ipcs_clin(3),
      vm(4), ct(5), pac_dia(6). IPCS = (lab+clin)/CVC-dias *1000.
  - Plan4 'P.alcoolico': álcool/pac-dia do UTI Adulto COMBINADO (cols B/D)
      e do UCO (cols G/I) — guardados crus p/ derivar A/B.
  - Plan6 'DDD': DDDs do UTI Adulto COMBINADO (nome col 7, unidades col 10,
      taxa col 11). Guardados crus p/ derivar A/B por subtração do UCO.
  - Plan1 'ISC Especialidade': ISC cirurgias limpas (total + por equipe).
  - Plan1B 'ISC Cirurgia': ISC pós-cesariana.

UTI A/B de DDD/HM NÃO é definitivo aqui — é derivado em `derive_utiab()`
combinando este resultado com o do CVE UTI C (combinado − UCO).
"""

from ._util import num, r1, r2, calc_di, calc_tx

_P2_BASE, _P2_STEP = 30, 17
_P3_BASE, _P3_STEP = 16, 15
_P6_STARTS = [14, 70, 125, 180, 235, 290, 345, 400, 455, 510, 565, 620]

_PIP = ['Piperacilina-tazobactam']
_CARBA = ['Meropenem', 'Imipenem', 'Ertapenem']
_GLICO = ['Vancomicina', 'Teicoplanina']
_POLI = ['Sulfato de Polimixina B', 'Sulfato de Polimixina E']


def _rows(provider, *names):
    tabs = provider.tabs()
    for n in names:
        if n in tabs:
            return provider.values(n)
    for n in names:
        for t in tabs:
            if t.startswith(n.split(' ')[0]):
                return provider.values(t)
    return None


def _cell(row, i):
    return row[i] if row and i < len(row) else None


def parse(provider, mes_idx, ano):
    # ── Plan2 — UTI A/B e UTIC ────────────────────────────────────────
    d2 = _rows(provider, 'Plan2 - UTI', 'Plan2')
    b2 = _P2_BASE + mes_idx * _P2_STEP
    r_ab = d2[b2 + 3] if d2 and b2 + 3 < len(d2) else []
    r_uc = d2[b2 + 4] if d2 and b2 + 4 < len(d2) else []

    def unit(row):
        return {
            'pn': num(_cell(row, 1)), 'ipcs_lab': num(_cell(row, 2)),
            'iu': num(_cell(row, 3)), 'vm': num(_cell(row, 4)),
            'ct': num(_cell(row, 5)), 'sv': num(_cell(row, 6)),
            'pac_dia': num(_cell(row, 7)),
        }
    u1, u2 = unit(r_ab), unit(r_uc)

    # ── Plan3 — UTINeo (soma faixas de peso) ──────────────────────────
    d3 = _rows(provider, 'Plan3 - UTINeo', 'Plan3')
    b3 = _P3_BASE + mes_idx * _P3_STEP
    neo = {'pn': 0.0, 'ipcs_lab': 0.0, 'ipcs_clin': 0.0, 'vm': 0.0,
           'ct': 0.0, 'pac_dia': 0.0}
    if d3:
        cols = {'pn': 1, 'ipcs_lab': 2, 'ipcs_clin': 3, 'vm': 4, 'ct': 5, 'pac_dia': 6}
        for off in range(3, 8):
            nr = d3[b3 + off] if b3 + off < len(d3) else None
            if not nr:
                continue
            for f, c in cols.items():
                neo[f] += num(_cell(nr, c))

    # ── Plan4 — álcool combinado (UTI Adulto) e UCO ───────────────────
    d4 = _rows(provider, 'Plan4 - P.alcoolico e sabonete', 'Plan4')
    ra = d4[15 + mes_idx] if d4 and 15 + mes_idx < len(d4) else []
    alcool_adu = num(_cell(ra, 1))   # col B — UTI Adulto combinado (A/B + C)
    pd_adu = num(_cell(ra, 3))       # col D — pac-dia combinado

    # ── Plan6 — DDDs UTIA combinado (cru, p/ derivação) ───────────────
    d6 = _rows(provider, 'Plan6 - DDD', 'Plan6')
    units_comb = {'pip': 0.0, 'carba': 0.0, 'glico': 0.0, 'poli': 0.0}
    if d6:
        base = _P6_STARTS[mes_idx]
        groups = {'pip': _PIP, 'carba': _CARBA, 'glico': _GLICO, 'poli': _POLI}
        for i in range(3, 36):
            dr = d6[base + i] if base + i < len(d6) else None
            if not dr:
                break
            nome = dr[7] if len(dr) > 7 and isinstance(dr[7], str) else ''
            nome = nome.strip()
            if not nome:
                continue
            u_utia = num(_cell(dr, 10))   # unidades brutas DDD UTIA (combinado)
            for grp, frags in groups.items():
                if any(f in nome for f in frags):
                    units_comb[grp] += u_utia

    # ── Plan1 / Plan1B — ISC ──────────────────────────────────────────
    isc_limpas = _parse_isc_limpas(provider, mes_idx)
    isc_cesar = _parse_isc_cesar(provider, mes_idx)

    return {
        'fonte': 'cve_mestre', 'mes': None,
        # UTI A/B — dispositivos/infecções (definitivos do mestre)
        'ab': {
            'pav': calc_di(u1['pn'], u1['vm']),
            'itu': calc_di(u1['iu'], u1['sv']),
            'ipcs': calc_di(u1['ipcs_lab'], u1['ct']),
            'svd': calc_tx(u1['sv'], u1['pac_dia']),
            'cvc': calc_tx(u1['ct'], u1['pac_dia']),
            'tot': calc_tx(u1['vm'], u1['pac_dia']),
            'pac_dia': u1['pac_dia'],
        },
        # UTIC — dispositivos/infecções (do mestre; DDD/HM virão do CVE UTI C)
        'uc': {
            'pav': calc_di(u2['pn'], u2['vm']),
            'itu': calc_di(u2['iu'], u2['sv']),
            'ipcs': calc_di(u2['ipcs_lab'], u2['ct']),
            'svd': calc_tx(u2['sv'], u2['pac_dia']),
            'cvc': calc_tx(u2['ct'], u2['pac_dia']),
            'tot': calc_tx(u2['vm'], u2['pac_dia']),
            'pac_dia': u2['pac_dia'],
        },
        'neo': {
            'ipcs': calc_di(neo['ipcs_lab'] + neo['ipcs_clin'], neo['ct']),
            'ipcs_n':  round(neo['ipcs_lab'] + neo['ipcs_clin']),   # casos (p/ IC e g-chart)
            'ipcs_cd': round(neo['ct']),                            # cateter-dia (denominador)
        },
        'isc_limpas': isc_limpas,
        'isc_cesar': isc_cesar,
        # cru para derivar UTI A/B (combinado − UCO) em derive_utiab()
        '_comb': {'alcool_ml': alcool_adu, 'pd': pd_adu, 'units': units_comb},
    }


def _parse_isc_limpas(provider, mes_idx):
    d1 = _rows(provider, 'Plan1 - ISC Especialidade', 'Plan1')
    if not d1:
        return None
    bs = 7 + mes_idx * 15
    total = d1[bs + 13] if bs + 13 < len(d1) else []
    specs = []
    for off in range(2, 13):
        r = d1[bs + off] if bs + off < len(d1) else None
        if not r:
            continue
        spec = str(r[0]).strip() if r[0] else ''
        if spec:
            specs.append({'spec': spec, 'isc': num(_cell(r, 1)), 'cl': num(_cell(r, 2))})
    n, cl = num(_cell(total, 1)), num(_cell(total, 2))
    return {'n': n, 'cl': cl, 'taxa': round(n / cl * 100, 2) if cl else 0, 'specs': specs}


def _parse_isc_cesar(provider, mes_idx):
    d1b = _rows(provider, 'Plan1B - ISC Cirurgia', 'Plan1B')
    if not d1b:
        return None
    bs = 11 + mes_idx * 16
    for off in range(1, 15):
        r = d1b[bs + off] if bs + off < len(d1b) else None
        if not r:
            continue
        lbl = str(r[0]).lower() if r[0] else ''
        if 'cesarian' in lbl:
            isc, proc = num(_cell(r, 1)), num(_cell(r, 3))
            return {'isc': isc, 'proc': proc,
                    'taxa': round(isc / proc * 100, 2) if proc else 0}
    return None


def derive_utiab(mestre, utic, ab_pac_dia):
    """
    Deriva HM e DDDs de UTI A/B = (combinado do mestre − UCO do CVE UTI C),
    seguindo doUTICFill. Retorna dict {hm, pip, carba, glico, poli}.
    """
    comb = mestre['_comb']
    out = {}
    # HM álcool
    if comb['alcool_ml'] is not None and utic.get('_uco_alcool_ml') is not None and ab_pac_dia:
        out['hm'] = r1((comb['alcool_ml'] - utic['_uco_alcool_ml']) / ab_pac_dia)
    else:
        out['hm'] = None
    # DDDs por subtração de unidades brutas, /pac-dia *1000
    for grp in ('pip', 'carba', 'glico', 'poli'):
        u_comb = comb['units'].get(grp)
        u_uco = utic.get(f'_uco_{grp}_u')
        if u_comb is None or u_uco is None or not ab_pac_dia:
            out[grp] = None
        else:
            v = (u_comb - u_uco) / ab_pac_dia * 1000
            out[grp] = r1(max(v, 0.0))  # piso de segurança em 0
    return out
