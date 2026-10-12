"""
Parser: Censo Diarreia HUSF.

Estrutura (validada contra Censo_Diarreia_2026_HUSF.xlsx):
  - Aba 'Totais'. Procura o cabeçalho 'Tabela 3' na col 0.
  - Logo abaixo, header de colunas e uma linha por mês (nome em inglês):
      Mês(0) · CM(1) · CC(2) · EPM(3) · Apto(4, ignorado) · UTIAB(5) · UTIC(6) · Pediatria(7)
    Os valores já são taxas (/1000 pac-dia).

Saída -> {diarreia: {cm, cc, epm, utiab, utic}}.
"""

from ._util import num, norm, MESES_EN, MESES_PT_FULL, r2


def parse(provider, mes_idx, ano):
    rows = provider.values('Totais')

    t3 = next((i for i, r in enumerate(rows)
               if r and 'TABELA 3' in norm(r[0])), -1)
    if t3 < 0:
        raise ValueError("'Tabela 3' não encontrada na aba Totais")

    alvo = {norm(MESES_EN[mes_idx]), norm(MESES_PT_FULL[mes_idx])}
    row = None
    for j in range(t3, min(t3 + 20, len(rows))):
        if rows[j] and norm(rows[j][0]) in alvo:
            row = rows[j]
            break
    if row is None:
        raise ValueError(f"Mês {MESES_EN[mes_idx]} não encontrado na Tabela 3")

    def g(i):
        return r2(num(row[i])) if i < len(row) else None

    return {'fonte': 'diarreia', 'mes': None,
            'diarreia': {'cm': g(1), 'cc': g(2), 'epm': g(3),
                         'utiab': g(5), 'utic': g(6)}}
