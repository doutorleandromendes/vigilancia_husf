"""
Parser: Censo MDRs HUSF.

Estrutura (validada contra Censo_MDRs_HUSF_2026.xlsx):
  - Uma aba por mês (JAN..DEZ).
  - Header em 3 linhas: 'UTI AB' col 0, 'UTIC' col 12, 'UTI Neo' col 24.
  - Por organismo, duas colunas: Cumulativo e Novo (incidente).
      ESBL cum=+1 novo=+2 · Acineto cum=+3 novo=+4 · KPC cum=+5 novo=+6
      Pseudo cum=+7 novo=+8 · Paciente-dia=+9
  - Linha 'Total' (col 0) com as somas do mês; a linha seguinte 'Di' traz as
    densidades /1000 pac-dia. Usamos 'Novo' (incidência) + densidade.

Saída -> dict por unidade com contagens incidentes e taxas /1000 pac-dia.
"""

from ._util import find_month_tab, num, norm

# offset de coluna de cada unidade dentro da linha Total/Di
_UNIT_OFFSET = {'ab': 0, 'uc': 12, 'neo': 24}
# (chave_saida, offset_da_contagem_NOVO, offset_da_densidade)
_ORG = {'esbl': 2, 'acin': 4, 'kpc': 6, 'pseu': 8}


def parse(provider, mes_idx, ano):
    tab = find_month_tab(provider, mes_idx)
    rows = provider.values(tab)

    tot_idx = next((i for i, r in enumerate(rows)
                    if r and norm(r[0]) == 'TOTAL'), -1)
    if tot_idx < 0:
        raise ValueError(f"Linha 'Total' não encontrada na aba {tab}")
    tot = rows[tot_idx]
    di = rows[tot_idx + 1] if tot_idx + 1 < len(rows) else []

    def cell(row, i):
        return row[i] if i < len(row) else None

    def rate(n, pd):
        return round(n / pd * 1000, 2) if pd else 0.0

    out = {}
    for unit, base in _UNIT_OFFSET.items():
        pd = num(cell(tot, base + 9))
        u = {'pd': pd}
        for org, off in _ORG.items():
            n = num(cell(tot, base + off))
            d = num(cell(di, base + off)) if di else 0.0
            u[f'{org}_n'] = n
            u[f'{org}_r'] = d if d else rate(n, pd)
        out[unit] = u
    return {'fonte': 'censo_mdr', 'mes': None, 'ab': out['ab'],
            'uc': out['uc'], 'neo': out['neo']}
