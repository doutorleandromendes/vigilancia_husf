"""
Parser: Censo-2026 (pacientes-dia por setor/mês).

Estrutura (validada contra Censo-2026.xlsx):
  - Aba única. Cabeçalho: col 0 = 'Setor atendimento'; cols seguintes = meses
    (Janeiro..Dezembro, PT-full). Uma linha por setor de atendimento.

Saída -> {'fonte':'censo', 'pd': {NOME_NORMALIZADO_DO_SETOR: pacientes-dia}}.
O consumo (enfermarias, taxa IH) escolhe os setores por nome normalizado.
"""
from ._util import num, norm, MESES_PT_FULL

# atalho: chave de enfermaria (YAML) -> nome do setor no Censo (normalizado)
WARD_CENSO = {
    'clinicaMedica':    'CLINICA MEDICA',
    'clinicaCirurgica': 'CLINICA CIRURGICA',
    'epm':              'ENFERMARIA PARTICULAR MISTA',
}


def parse(provider, mes_idx, ano):
    mes = norm(MESES_PT_FULL[mes_idx])   # ex.: 'MARCO' (norm remove acento)
    for tab in provider.tabs():
        rows = provider.values(tab)
        hdr_i = next((i for i, r in enumerate(rows)
                      if r and norm(r[0]) == 'SETOR ATENDIMENTO'), None)
        if hdr_i is None:
            continue
        col = next((j for j, v in enumerate(rows[hdr_i]) if norm(v) == mes), None)
        if col is None:
            raise ValueError(f"Coluna do mês {MESES_PT_FULL[mes_idx]} não achada no Censo")
        pd = {}
        for r in rows[hdr_i + 1:]:
            nome = norm(r[0]) if r and r[0] is not None else ''
            if not nome or nome == 'TOTAL':
                continue
            pd[nome] = num(r[col], on_error=None) if col < len(r) else None
        return {'fonte': 'censo', 'mes': None, 'pd': pd}
    raise ValueError("Censo: aba com 'Setor atendimento' não encontrada")
