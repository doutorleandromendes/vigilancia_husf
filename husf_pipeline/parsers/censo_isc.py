"""
Parser: Censo ISC HUSF (vigilância global / "negativa").

Estrutura (validada contra Censo_ISC_2026_HUSF.xlsx):
  - Uma aba por mês (em inglês: January..December) + aba 'Template'.
  - Header (linha 2): Dia(0), depois grupos de 3 por setor:
      [ISC+(1), ISC-(2), Pac-dia(3)] · [4,5,6] · [7,8,9] · [10,11,12] ...
    (Clínica, Internação, UTIAB, UTIC).
  - Linhas de dados: col 0 = dia (1..31). Soma-se ISC+ e Pac-dia de todos os
    grupos, em todos os dias, até a primeira linha sem dia / 'Total'.

Saída -> {isc: {n, pd, taxa}} (taxa = ISC+/pac-dia * 100).
"""

from ._util import find_month_tab, num, norm


def parse(provider, mes_idx, ano):
    tab = find_month_tab(provider, mes_idx)
    rows = provider.values(tab)

    # primeira linha de dados: col 0 numérico entre 1 e 31
    start = -1
    for i, r in enumerate(rows):
        if not r:
            continue
        v = r[0]
        if isinstance(v, (int, float)) and 1 <= v <= 31:
            start = i
            break
        if isinstance(v, str) and v.strip().isdigit() and 1 <= int(v) <= 31:
            start = i
            break
    if start < 0:
        raise ValueError(f"Dados diários não encontrados na aba {tab}")

    total_isc = 0.0
    total_pd = 0.0
    for r in rows[start:]:
        if not r:
            break
        dia = r[0]
        if dia is None or dia == '' or norm(dia) == 'TOTAL':
            break
        # trios a partir da col 1: ISC+(c), ISC-(c+1), Pac-dia(c+2)
        c = 1
        while c < len(r):
            total_isc += num(r[c])
            if c + 2 < len(r):
                total_pd += num(r[c + 2])
            c += 3

    taxa = round(total_isc / total_pd * 100, 2) if total_pd else 0.0
    return {'fonte': 'censo_isc', 'mes': None,
            'isc': {'n': round(total_isc), 'pd': round(total_pd), 'taxa': taxa}}
