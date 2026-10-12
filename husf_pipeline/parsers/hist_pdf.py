"""
Semeador histórico: série de IRAS das enfermarias (CM, CC, EPM).

Dado extraído dos boletins mensais CCIH (PDF Dez/24 e Dez/25).
Este módulo NÃO é chamado toda rodada — é executado UMA VEZ para semear
a série histórica antes de o pipeline mensal começar a acumulá-la.

Estrutura de saída: mesmo padrão appS do pipeline.
  {p:'jan/24', ac:2, itu:1, pneu:3, isc:6, pd:640, total:6}

Para integrar: gerar_competencia.py --seed-historico
"""

# ── Dados extraídos dos PDFs (não parsear novamente) ────────────────────────
# Ordem: jan..dez de cada ano
# Campos: ac=Inf.Acesso Central, itu=Inf.Urinária, pneu=Pneumonia,
#         isc=Inf.Sítio Cirúrgico, pd=pacientes-dia, total=Total infecções

_CM = {
    2024: dict(
        ac=  [2, 2, 3, 4, 3, 2, 4, 4, 3, 4, 3, 4],  # ← PDF dez/24 p.2 (2023→jan/24..dez/24 row)
        itu= [1, 1, 0, 1, 1, 1, 0, 1, 2, 3, 1, 1],
        pneu=[3, 4, 7, 8, 6, 5, 2, 4, 7, 8, 9,11],
        isc= [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # CM não tem ISC na tabela
        pd=  [640,635,717,682,720,695,695,652,632,670,592,663],
    ),
    2025: dict(
        ac=  [1, 2, 1, 2, 3, 3, 1, 2, 1, 2, 3, 5],  # ← PDF dez/25 p.2
        itu= [1, 1, 1, 2, 1, 0, 1, 1, 1, 0, 0, 1],
        pneu=[4, 7, 5, 6, 5, 7, 3, 5, 7, 9, 4, 6],
        isc= [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        pd=  [650,615,663,651,685,693,726,719,706,711,688,662],
    ),
}

_CC = {
    2024: dict(
        ac=  [4, 5, 7, 5, 8, 6, 8, 5, 6, 7, 5, 4],  # PDF dez/24 p.3
        itu= [3, 2, 3, 2, 4, 2, 4, 2, 3, 1, 2, 3],
        pneu=[7, 4, 5, 7, 9,12,10, 6, 8, 9,12,13],
        isc= [6, 3, 8, 6, 5, 6, 5, 7, 9,11,13,10],
        pd=  [817,782,864,837,878,835,857,775,820,800,738,760],
    ),
    2025: dict(
        ac=  [4, 6, 9, 6, 2, 1, 4, 4, 2, 4, 3, 4],  # PDF dez/25 p.3
        itu= [3, 4, 4, 6, 3, 2, 1, 0, 1, 2, 2, 0],
        pneu=[7, 8,10,12, 7,10, 9,12,10, 7,11, 7],
        isc= [9, 5, 6, 7,10,12,15,11,12,10, 8, 6],
        pd=  [737,667,769,747,788,795,832,840,801,836,799,791],
    ),
}

_EPM = {
    2024: dict(
        ac=  [2, 1, 2, 0, 1, 1, 2, 0, 1, 1, 1, 0],  # PDF dez/24 p.4
        itu= [0, 0, 1, 0, 1, 2, 1, 0, 1, 0, 0, 1],
        pneu=[1, 2, 3, 5, 2, 3, 3, 2, 1, 2, 0, 1],
        isc= [2, 3, 2, 3, 2, 1, 2, 3, 2, 1, 2, 1],
        pd=  [618,723,870,755,778,704,724,609,576,624,588,531],
    ),
    2025: dict(
        ac=  [1, 2, 0, 1, 2, 0, 1, 1, 0, 0, 0, 1],  # PDF dez/25 p.4
        itu= [0, 1, 1, 0, 1, 2, 1, 2, 1, 2, 0, 1],
        pneu=[2, 3, 2, 1, 3, 4, 3, 1, 1, 3, 1, 0],
        isc= [5, 3, 2, 1, 0, 1, 4, 2, 3, 1, 2, 1],
        pd=  [503,654,657,652,595,599,580,606,545,480,595,544],
    ),
}

_ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']


def _build_series(data_by_year):
    """Converte {ano: {campo: [jan..dez]}} -> lista de dicts {p, ac, itu, pneu, isc, pd, total}."""
    series = []
    for ano in sorted(data_by_year):
        d = data_by_year[ano]
        n_meses = len(d['pd'])
        for mi in range(n_meses):
            if d['pd'][mi] == 0:
                continue
            ac   = d['ac'][mi]
            itu  = d['itu'][mi]
            pneu = d['pneu'][mi]
            isc  = d['isc'][mi]
            pd   = d['pd'][mi]
            series.append({
                'p': f"{_ABBR[mi]}/{str(ano)[-2:]}",
                'ac': ac, 'itu': itu, 'pneu': pneu, 'isc': isc,
                'pd': pd,
                'total': ac + itu + pneu + isc,
            })
    return series


def get_historico():
    """Retorna {clinicaMedica, clinicaCirurgica, epm} com séries históricas 2024-2025."""
    return {
        'clinicaMedica':     _build_series(_CM),
        'clinicaCirurgica':  _build_series(_CC),
        'epm':               _build_series(_EPM),
    }
