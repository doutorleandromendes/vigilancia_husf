"""
Parser: DOTs de ATB HUSF.

Estrutura (validada contra DOTs_2026.xlsx):
  - Abas pivô por ATB: Tot_CTO(cef/ceftriaxona), Tot_PPTZ(pip), Tot_CBP(cbp),
    Tot_GPP(gpp), Tot_PB(pb).  [Tot_CPM/cefepime e a 7ª coluna UTINeo existem
    na planilha mas o GAS atual NÃO os exporta — mantemos paridade.]
  - Em cada aba: linha 0 = ATB, linha 1 = unidades, linhas 2..13 = JAN..DEZ.
      col 0 = mês · cols 1..7 = UTIAB, UTIC, Clinica, Cirurgia, Apto, EPM, UTINeo
  - Cefepime (Tot_CPM) NÃO é exportado, por decisão.  UTI Neo (col 7) É.
  - Meses sem dado vêm como '#DIV/0!' -> tratados como None (ausente), não 0.

Saída -> {dots: {cef:{utiab,...,utineo}, pip:{...}, ...}} (None se aba/mês ausente).
"""

from ._util import num, r2

_TABS = [('Tot_CTO', 'cef'), ('Tot_PPTZ', 'pip'), ('Tot_CBP', 'cbp'),
         ('Tot_GPP', 'gpp'), ('Tot_PB', 'pb')]
_UNITS = ['utiab', 'utic', 'clin', 'cir', 'apto', 'epm', 'utineo']


def parse(provider, mes_idx, ano):
    tabs = set(provider.tabs())
    dots = {}
    faltando = []
    for sheet, key in _TABS:
        if sheet not in tabs:
            dots[key] = None
            faltando.append(sheet)
            continue
        rows = provider.values(sheet)
        ridx = 2 + mes_idx
        if ridx >= len(rows) or not rows[ridx]:
            dots[key] = None
            continue
        row = rows[ridx]
        unit_data = {}
        any_val = False
        for i, uk in enumerate(_UNITS):
            v = num(row[i + 1], on_error=None) if i + 1 < len(row) else None
            unit_data[uk] = r2(v)
            if v is not None:
                any_val = True
        dots[key] = unit_data if any_val else None
    res = {'fonte': 'dots', 'mes': None, 'dots': dots}
    if faltando:
        res['_avisos'] = [f"abas DOT ausentes: {faltando}"]
    return res
