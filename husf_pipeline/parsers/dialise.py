"""
Parser: CVE Diálise (arquivo .xlsx local).

Porta `parseCVEDialise`. Aba 'Hemodiálise', linhas 31..42 (0-idx) = Jan..Dez.
Taxas por acesso (cols 14..31):
  col 16 -> ILAV temp /1000 cat-dia      -> ilavTemp
  col 19 -> ILAV perm /1000 cat-dia      -> ilavPerm
  col 21 -> ILAV fístula /100 pac-mês    -> ilavFist
  col 24 -> Bacteremia temp /1000 cat-dia-> bactTemp
  col 27 -> Bacteremia perm /1000 cat-dia-> bactPerm
  col 29 -> Bacteremia fístula /100 pac-mês -> bactFist
  col 31 -> Vancomicina %                -> vanco

Totais combinando TODOS os acessos (temp+perm+fístula) — único denominador comum
é pac-mês (a fístula não tem cat-dia), portanto /100 pac-mês:
  ilav = (Nº temp+perm+fist) / (Nº pacientes total) * 100   [casos: cols 14,17,20; E: col 4]
  bact = (Nº temp+perm+fist) / (Nº pacientes total) * 100   [casos: cols 22,25,28]
Células de erro (#DIV/0!) -> None.

Saída -> {hd: {ilav, bact, ilavTemp, ilavPerm, ilavFist, bactTemp, bactPerm, bactFist, vanco}}.
"""

from ._util import num, r2

_BASE = 31  # linha 0-idx de Janeiro
_COLS = {'ilavTemp': 16, 'ilavPerm': 19, 'ilavFist': 21,
         'bactTemp': 24, 'bactPerm': 27, 'bactFist': 29, 'vanco': 31}
# numeradores (Nº) por acesso e total de pacientes (E), p/ os totais combinados
_ILAV_N = (14, 17, 20)   # O, R, U
_BACT_N = (22, 25, 28)   # W, Z, AC
_TOTAL_PAC = 4           # E (= B+C+D)


def _rows(provider):
    for n in ('Hemodiálise', 'Hemodialise'):
        if n in provider.tabs():
            return provider.values(n)
    raise ValueError("Aba 'Hemodiálise' não encontrada")


def parse(provider, mes_idx, ano):
    rows = _rows(provider)
    ridx = _BASE + mes_idx
    row = rows[ridx] if ridx < len(rows) else []
    hd = {}
    for field, col in _COLS.items():
        v = num(row[col], on_error=None) if row and col < len(row) else None
        hd[field] = r2(v)

    # totais combinados (todos os acessos) por 100 pac-mês
    def _cell(i):
        return num(row[i], on_error=0) if row and i < len(row) else 0
    pac = num(row[_TOTAL_PAC], on_error=None) if row and _TOTAL_PAC < len(row) else None
    if pac:
        hd['ilav'] = r2(sum(_cell(i) for i in _ILAV_N) / pac * 100)
        hd['bact'] = r2(sum(_cell(i) for i in _BACT_N) / pac * 100)
    else:
        hd['ilav'] = None
        hd['bact'] = None

    return {'fonte': 'cve_dialise', 'mes': None, 'hd': hd}
