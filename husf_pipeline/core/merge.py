"""
core/merge.py - Logica de acumulacao de series (porta appS/appISC do HTML).

Regras:
  - Series sao listas de dicts {p, v, c?} — c:1 = mes corrente.
  - Ao adicionar novo ponto: ponto anterior com c:1 perde o flag.
  - Dois pontos com mesmo label: o mais recente prevalece.
"""

from copy import deepcopy


def _demote(series):
    return [{k: v for k, v in pt.items() if k != 'c'} for pt in series]


def appS(series, label, value):
    """Acumula ponto {p, v} simples."""
    if value is None:
        return series
    base = _demote(deepcopy(series))
    base = [pt for pt in base if pt.get('p') != label]
    base.append({'p': label, 'v': value, 'c': 1})
    return base


def appISC(series, point):
    """Acumula ponto ISC (dict completo)."""
    base = _demote(deepcopy(series))
    base = [pt for pt in base if pt.get('p') != point['p']]
    pt = dict(point); pt['c'] = 1
    base.append(pt)
    return base


def appMDR(series, label, e=None, k=None, a=None, ps=None):
    """
    Acumula ponto MDR {p, e, k, a, ps?} — formato do JSON real.
    """
    base = _demote(deepcopy(series))
    base = [pt for pt in base if pt.get('p') != label]
    pt = {'p': label, 'e': e or 0, 'k': k or 0, 'a': a or 0}
    if ps is not None:
        pt['ps'] = ps
    pt['c'] = 1
    base.append(pt)
    return base


def appW(series, label, ward_point):
    """Acumula ponto de enfermaria {p, ac, itu, pneu, isc, pd, total}."""
    base = _demote(deepcopy(series))
    base = [pt for pt in base if pt.get('p') != label]
    pt = dict(ward_point); pt['p'] = label; pt['c'] = 1
    base.append(pt)
    return base


def append_checklist(series, label, chk_point):
    """Acumula ponto de checklist CVC."""
    base = _demote(deepcopy(series))
    base = [pt for pt in base if pt.get('p') != label]
    pt = dict(chk_point); pt['p'] = label; pt['c'] = 1
    base.append(pt)
    return base


def build_month(prev_json, label, parsers_out, manual):
    """
    Constroi o JSON do novo mes.
    prev_json   : dict anterior
    label       : str 'mai/26'
    parsers_out : {fonte: resultado_do_parser}
    manual      : dict do YAML
    """
    d = deepcopy(prev_json)
    d['periodo'] = _label_to_periodo(label)

    cve   = parsers_out.get('cve_mestre', {})
    uticp = parsers_out.get('cve_utic',   {})
    dial  = parsers_out.get('cve_dialise',{})
    mdr   = parsers_out.get('censo_mdr',  {})
    iscp  = parsers_out.get('censo_isc',  {})
    diarr = parsers_out.get('diarreia',   {})
    dotsp = parsers_out.get('dots',       {})
    ctrl  = parsers_out.get('controles',  {})

    ab_pd = cve.get('ab', {}).get('pac_dia', 0) or 0
    uc_pd = cve.get('uc', {}).get('pac_dia', 0) or 0

    # DDDs UTI A/B (derivados: combinado - UTIC)
    deriv = {}
    if cve and uticp:
        from husf_pipeline.parsers.cve_mestre import derive_utiab
        deriv = derive_utiab(cve, uticp, ab_pd)

    def app(path, val):
        """app('utiAB.pav', 12.56) -> d['utiAB']['pav'] = appS(...)"""
        if val is None:
            return
        keys = path.split('.')
        node = d
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = appS(node.get(keys[-1], []), label, val)

    def man(key, default=None):
        return manual.get(key, default)

    # ── Global ────────────────────────────────────────────────────────────
    app('global.taxaIH', man('global_taxaIH'))

    # ── UTI A/B ───────────────────────────────────────────────────────────
    ab = cve.get('ab', {})
    for f in ('pav','itu','ipcs','svd','cvc','tot'):
        app(f'utiAB.{f}', ab.get(f))
    dts = dotsp.get('dots', {})
    def ddd(atb_key, unit):
        return (dts.get(atb_key) or {}).get(unit)

    # HM álcool: fonte primária = bags do SHL (Planilha de Controles 'Dados UTI')
    # ml = bags × 500; HM = ml / pac-dia (CVE Plan2). Ver alcool_uti.py.
    _au = parsers_out.get('controles_alcool_uti') or {}
    _ab_ml = (_au.get('utiAB') or {}).get(label)
    app('utiAB.hm', round(_ab_ml/ab_pd, 1) if _ab_ml and ab_pd else None)
    app('utiAB.dddPip',   ddd('pip','utiab'))
    app('utiAB.dddCarba', ddd('cbp','utiab'))
    app('utiAB.dddGlico', ddd('gpp','utiab'))
    app('utiAB.dddPoli',  ddd('pb','utiab'))

    ab_mdr = mdr.get('ab', {})
    d['utiAB']['mdr'] = appMDR(d['utiAB'].get('mdr', []), label,
        e=ab_mdr.get('esbl_r'), k=ab_mdr.get('kpc_r'),
        a=ab_mdr.get('acin_r'), ps=ab_mdr.get('pseu_r'))

    # ── UTI C ─────────────────────────────────────────────────────────────
    uc = cve.get('uc', {})
    utv = uticp.get('utic', {})
    for f in ('pav','itu','ipcs','svd','cvc','tot'):
        app(f'utic.{f}', uc.get(f))
    _uc_ml = (_au.get('utic') or {}).get(label)
    app('utic.hm', round(_uc_ml/uc_pd, 1) if _uc_ml and uc_pd else None)
    app('utic.dddPip',   ddd('pip','utic'))
    app('utic.dddCarba', ddd('cbp','utic'))
    app('utic.dddGlico', ddd('gpp','utic'))
    app('utic.dddPoli',  ddd('pb','utic'))

    uc_mdr = mdr.get('uc', {})
    d['utic']['mdr'] = appMDR(d['utic'].get('mdr', []), label,
        e=uc_mdr.get('esbl_r'), k=uc_mdr.get('kpc_r'),
        a=uc_mdr.get('acin_r'))

    # ── UTI Neo ───────────────────────────────────────────────────────────
    app('utiNeo.ipcs', cve.get('neo', {}).get('ipcs'))

    # ── Hemodiálise ───────────────────────────────────────────────────────
    hd = dial.get('hd', {})
    for f in ('ilavTemp','ilavPerm','ilavFist','bactTemp','bactPerm','bactFist','vanco'):
        app(f'hd.{f}', hd.get(f))

    # ── Diarreia ──────────────────────────────────────────────────────────
    dv = diarr.get('diarreia', {})
    for u in ('cm','cc','epm','utiab','utic'):
        app(f'diarreia.{u}', dv.get(u))

    # ── ISC ───────────────────────────────────────────────────────────────
    il = cve.get('isc_limpas')
    ic = cve.get('isc_cesar')
    ig = iscp.get('isc')
    if il:
        d['isc']['limpas'] = appISC(d['isc'].get('limpas', []),
            {'p': label, 'isc': il['n'], 'cl': il['cl'], 'taxa': il['taxa']})
    if ic:
        d['isc']['cesar'] = appISC(d['isc'].get('cesar', []),
            {'p': label, 'isc': ic['isc'], 'proc': ic['proc'], 'taxa': ic['taxa']})
    if ig:
        d['isc']['global'] = appISC(d['isc'].get('global', []),
            {'p': label, 'isc': ig['n'], 'pd': ig['pd'], 'taxa': ig['taxa']})

    # ── Álcool gel — enfermarias (ml/pac-dia) ──────────────────────────────────────
    # controles_alcool: {'clinicaMedica': 16.2, 'clinicaCirurgica': 28.7, 'epm': 45.3}
    _alcool = parsers_out.get('controles_alcool') or {}
    for wk in ('clinicaMedica', 'clinicaCirurgica', 'epm'):
        v = _alcool.get(wk)
        if v is not None:
            app(f'{wk}.hm', v)

    # ── DOTs ──────────────────────────────────────────────────────────────
    dts = dotsp.get('dots', {})
    units_d = ['utiab','utic','clin','cir','apto','epm','utineo']
    for atb in ('cef','pip','cbp','gpp','pb'):
        atb_d = dts.get(atb) or {}
        for u in units_d:
            app(f'dots.{atb}.{u}', atb_d.get(u))

    # ── MDR Institucional ─────────────────────────────────────────────────
    pd_inst = sum(mdr.get(u, {}).get('pd', 0) or 0 for u in ('ab','uc','neo'))
    def inst_rate(org_key):
        n = sum(mdr.get(u, {}).get(f'{org_key}_n', 0) or 0 for u in ('ab','uc','neo'))
        return round(n / pd_inst * 1000, 2) if pd_inst else 0
    d['mdrInst']['s'] = appMDR(d['mdrInst'].get('s', []), label,
        e=inst_rate('esbl'), k=inst_rate('kpc'), a=inst_rate('acin'))

    # ── MDR Mensal (para mdr_mensal.html) ─────────────────────────────────
    # Estrutura: mdrMensal[unit][org] = série {p,v,c}; mdrMensal[unit].pd = série;
    # mdrMensal[unit].counts[org] = array paralelo de contagens absolutas.
    d.setdefault('mdrMensal', {})
    for _ukey, _mkey in [('utiAB','ab'), ('utic','uc'), ('utiNeo','neo')]:
        _u = mdr.get(_mkey, {})
        if not _u:
            continue
        _mm = d['mdrMensal'].setdefault(_ukey, {})
        # normaliza séries legadas (listas de int puro → descarta, recomeça limpo)
        def _clean(seq):
            if not isinstance(seq, list): return []
            return [pt for pt in seq if isinstance(pt, dict)]
        for _org in ('esbl','kpc','acin','pseu'):
            _mm[_org] = appS(_clean(_mm.get(_org, [])), label, _u.get(f'{_org}_r'))
        _mm['pd'] = appS(_clean(_mm.get('pd', [])), label, _u.get('pd'))
        # counts: arrays paralelos de contagens absolutas, 1:1 com a série do organismo.
        # Reconstrói a partir da série (fonte da verdade) para garantir alinhamento
        # mesmo após limpeza de dados legados.
        _mm.setdefault('counts', {})
        for _org in ('esbl','kpc','acin','pseu'):
            _series = _mm.get(_org, [])
            _prev_counts = _mm['counts'].get(_org, [])
            _n_atual = int(_u.get(f'{_org}_n', 0) or 0)
            _new_counts = []
            for _i, _pt in enumerate(_series):
                if _pt.get('p') == label:
                    _new_counts.append(_n_atual)
                elif _i < len(_prev_counts) and isinstance(_prev_counts[_i], int):
                    _new_counts.append(_prev_counts[_i])
                else:
                    _new_counts.append(0)
            _mm['counts'][_org] = _new_counts

    # ── Enfermarias — contagens + taxaIH ─────────────────────────────────
    for wk in ('clinicaMedica','clinicaCirurgica','epm'):
        wp = man(wk)
        if not wp:
            continue
        total = sum(wp.get(k, 0) or 0 for k in ('ac','itu','pneu','isc'))
        pd_w  = wp.get('pd') or 0
        taxa  = round(total / pd_w * 100, 2) if pd_w else 0
        app(f'{wk}.taxaIH', taxa)
        d[wk]['infSeries'] = appW(
            d[wk].get('infSeries', []), label,
            {'ac': wp.get('ac',0), 'itu': wp.get('itu',0),
             'pneu': wp.get('pneu',0), 'isc': wp.get('isc',0),
             'pd': pd_w, 'total': total})

    # ── Checklist CVC ─────────────────────────────────────────────────────
    chk = ctrl.get('checklistCVC', {})
    for sk, sv in chk.items():
        d.setdefault('checklistCVC', {}).setdefault(sk, [])
        d['checklistCVC'][sk] = append_checklist(d['checklistCVC'][sk], label, sv)

    # ── SURA ──────────────────────────────────────────────────────────────
    sura = man('sura')
    if sura and isinstance(sura, dict):
        d.setdefault('sura', {})
        if not isinstance(d.get('sura'), dict):
            d['sura'] = {}
        serie = _demote(deepcopy(d['sura'].get('s', [])))
        serie = [pt for pt in serie if pt.get('p') != label]
        pt = dict(sura); pt.setdefault('obito', 0); pt['p'] = label; pt['c'] = 1
        serie.append(pt)
        d['sura']['s'] = serie

    # ── Isolamentos / Precauções de Contato ───────────────────────────────────
    # isol: {confirmados_total, confirmados_pc, novos_total, novos_pc}
    #   cada um: {ward: {n, pct}}
    _isol = parsers_out.get('isolamentos') or {}
    d.setdefault('isolamentos', {})
    for _metric in ('confirmados_total','confirmados_pc','novos_total','novos_pc'):
        d['isolamentos'].setdefault(_metric, {})
        for _ward, _vals in (_isol.get(_metric) or {}).items():
            _n   = _vals.get('n', 0) or 0
            _pct = _vals.get('pct')
            if _n == 0 and _pct is None: continue
            d['isolamentos'][_metric].setdefault(_ward, [])
            _ser = _demote(deepcopy(d['isolamentos'][_metric][_ward]))
            _ser = [pt for pt in _ser if pt.get('p') != label]
            _ser.append({'p': label, 'n': _n, 'pct': _pct, 'c': 1})
            d['isolamentos'][_metric][_ward] = _ser

    # ── Antibiograma ──────────────────────────────────────────────────────
    abio = man('abio')
    if abio:
        d['abio'] = abio

    # ── Status epidemiológico ─────────────────────────────────────────────
    for unit in ('global','utiAB','utic','utiNeo','clinicaMedica','clinicaCirurgica','epm','hd'):
        s = man(f'status_{unit}')
        if s and isinstance(d.get(unit), dict):
            d[unit]['status'] = s

    return d


def _label_to_periodo(label):
    _FULL = {'jan':'Janeiro','fev':'Fevereiro','mar':'Marco','abr':'Abril',
             'mai':'Maio','jun':'Junho','jul':'Julho','ago':'Agosto',
             'set':'Setembro','out':'Outubro','nov':'Novembro','dez':'Dezembro'}
    abbr, yy = label.split('/')
    return f"{_FULL[abbr]} 20{yy}"
