"""
Parser: Censo de Isolamentos/Precaucoes - aba 'Totais'.

Fonte: Google Sheets (SHEET_IDS['isolamentos']).
Blocos extraidos:
  confirmados_total  - pac-dia em qualquer PC/isolamento (%)
  novos_total        - casos novos em qualquer precaucao
  confirmados_pc     - pac-dia em PC Contato MDR+Outro (%)
  novos_pc           - casos novos em PC Contato
"""

from ._util import num, r2

_MESES_PT = ['Janeiro','Fevereiro','Marco','Abril','Maio','Junho',
             'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
_ABBR     = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']

_WARDS = [
    ('clinicaMedica',    1,  2),
    ('clinicaCirurgica', 3,  4),
    ('epm',              5,  6),
    ('apartamento',      7,  8),
    ('utiAB',            9,  10),
    ('utic',             11, 12),
    ('utiNeo',           13, 14),
    ('pediatria',        15, 16),
]


def _find_blocks(rows):
    result = {}
    for i, r in enumerate(rows):
        if not r or not r[0]: continue
        h = str(r[0]).strip()
        if 'Total Confirmad' in h:
            result['confirmados_total'] = i + 3
        elif 'Total Casos Nov' in h or 'Total Casos N' in h:
            result['novos_total'] = i + 3
        elif 'Confirmados' in h and 'PC Contat' in h:
            if 'confirmados_pc' not in result:
                result['confirmados_pc'] = i + 3
        elif ('Casos Novos' in h or 'Novos' in h) and 'PC Contat' in h:
            if 'novos_pc' not in result:
                result['novos_pc'] = i + 3
    return result


def _parse_row(row):
    out = {}
    if row is None:
        return out
    for key, cn, cp in _WARDS:
        try:
            n = int(float(str(row[cn]).replace(',','.'))) if cn < len(row) and row[cn] not in (None, '') else 0
        except (ValueError, TypeError):
            n = 0
        try:
            _praw = str(row[cp]).replace(',','.') if cp < len(row) and row[cp] not in (None, '', '\xb7') else None
            pct = round(float(_praw), 2) if _praw is not None else None
        except (ValueError, TypeError):
            pct = None
        if n > 0 or pct is not None:
            out[key] = {'n': n, 'pct': pct}
    return out


def parse(provider, mes_idx, ano):
    """Parser mensal padrao. Retorna {metric: {ward: {n, pct}}}."""
    rows = provider.values('Totais')
    blocks = _find_blocks(rows)
    result = {}
    for metric, start in blocks.items():
        ri = start + mes_idx
        row = rows[ri] if ri < len(rows) else None
        result[metric] = _parse_row(row)
    return result


def parse_all_months(provider, ano):
    """Serie completa. Retorna {metric: {ward: [{p, n, pct}]}}."""
    rows = provider.values('Totais')
    blocks = _find_blocks(rows)
    out = {}
    for metric, start in blocks.items():
        out[metric] = {w[0]: [] for w in _WARDS}
        for mi in range(12):
            ri = start + mi
            if ri >= len(rows): break
            row = rows[ri]
            ward_data = _parse_row(row)
            for key, vals in ward_data.items():
                if vals.get('n', 0) > 0:
                    out[metric][key].append({'p': f"{_ABBR[mi]}/{str(ano)[-2:]}", **vals})
    return out
