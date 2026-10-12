"""
Parser: Planilha Geral de Controles - aba 'Checklist CVC'.

Estrutura (validada contra Planilha_Geral_de_controles_2026.xlsx):
  - Blocos mensais detectados pela linha onde col B = nome do mes em PT
    (JANEIRO, FEVEREIRO ...). Stride variavel (~95-100 linhas).
  - Dentro de cada bloco, setores em col A. Por setor, linhas de tipo de
    cateter (col B != 'TOTAL') acumulam os campos:
      C=2 liberados . D=3 preenchidos . E=4 conformes . F=5 inconformes
      G=6 falha preench. . H=7 nc_sitio . I=8 nc_maos . J=9 nc_param
      K=10 nc_degerm . L=11 nc_material . M=12 nc_puncao
  - UTI A/B = soma de 'UTI ADULTO A' + 'UTI ADULTO B'.
  - UTI Neo  = soma de 'UTI NEONATAL' + 'BERCARIO CUIDADOS INTERMEDIARIOS'.
  - Enfermarias: 'CLINICA CIRURGICA MISTA' e 'CLINICA MEDICA MISTA'.
  - Derivados: cobertura = preenchidos/liberados, conformidade = conformes/preenchidos.

parse(provider, mes_idx, ano) -> um mes, como antes.
parse_all_months(provider, ano, skip_empty=True) -> serie completa do arquivo
  (todos os meses encontrados), por setor. Meses sem coleta (lib==0 e
  preen==0) sao omitidos por padrao - representam "sem dado", nao "0%".
"""

import unicodedata
from ._util import num, r2

_MESES = ['JANEIRO','FEVEREIRO','MARCO','ABRIL','MAIO','JUNHO',
          'JULHO','AGOSTO','SETEMBRO','OUTUBRO','NOVEMBRO','DEZEMBRO']
_ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']

def _norm(s):
    if s is None: return ''
    s = str(s).strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    return s.upper()

_SECTOR_MAP = {
    'UTI ADULTO A':                         'utiAB',
    'UTI ADULTO B':                         'utiAB',
    'UTI ADULTO':                            'utiAB',  # 2024 jan-out: A/B nao split
    'UTI ADULTO C':                         'utiC',
    'UTI NEONATAL':                         'utiNeo',
    'BERCARIO CUIDADOS INTERMEDIARIOS':     'utiNeo',
    'CLINICA CIRURGICA MISTA':              'clinicaCirurgica',
    'CLINICA MEDICA MISTA':                 'clinicaMedica',
    'HEMODIALISE':                          'hd',
}

_FIELDS = ['lib','preen','conf','inconf','falha',
           'nc_sitio','nc_maos','nc_param','nc_degerm','nc_material','nc_puncao']
_COLS   = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

_KEYS = list(dict.fromkeys(_SECTOR_MAP.values()))


def _find_blocks(rows):
    """Lista (mes_idx, linha_inicio) de todos os blocos mensais, em ordem."""
    blocks = []
    for i, r in enumerate(rows):
        if r and len(r) > 1 and _norm(r[1]) in _MESES:
            blocks.append((_MESES.index(_norm(r[1])), i))
    blocks.sort(key=lambda x: x[1])
    return blocks


def _parse_block(rows, start, end):
    """Acumula um bloco mensal -> {sector_key: {campos + cobertura/conformidade}}.

    Salvaguardas estruturais (necessarias p/ arquivos 2024/2025):
    - Linhas de subtotal cujo rotulo (col B) COMECA com 'TOTAL' (ex: 'Total
      UTI ADULTO') sao ignoradas - senao duplicam a soma das linhas
      individuais ja contadas.
    - Se um cabecalho de setor (col A) SE REPETE dentro do bloco, isso indica
      uma segunda tabela colada (ex: resumo anual no bloco de dez/24) - o
      bloco e truncado no ponto da repeticao.
    """
    acc = {k: {f: 0.0 for f in _FIELDS} for k in _KEYS}
    cur = None
    seen_labels = set()
    for i in range(start, end):
        r = rows[i]
        if not r:
            continue
        a = _norm(r[0]) if r[0] else ''
        b = r[1]
        if a in _SECTOR_MAP:
            if a in seen_labels:
                break  # segunda tabela detectada - descarta o resto do bloco
            seen_labels.add(a)
            cur = _SECTOR_MAP[a]
            continue
        if cur and b and not _norm(b).startswith('TOTAL'):
            for f, ci in zip(_FIELDS, _COLS):
                if ci < len(r):
                    acc[cur][f] += num(r[ci])
        if a and a not in _SECTOR_MAP and a not in _MESES and not a.startswith('ANO'):
            if b is None:
                cur = None

    result = {}
    for key, vals in acc.items():
        lib, preen, conf = vals['lib'], vals['preen'], vals['conf']
        out = {f: round(v) for f, v in vals.items()}
        out['cobertura'] = r2(preen / lib * 100) if lib else None
        out['conformidade'] = r2(conf / preen * 100) if preen else None
        result[key] = out
    return result


def parse(provider, mes_idx, ano):
    """Parser mensal (uso normal do pipeline)."""
    rows = provider.values('Checklist CVC')
    blocks = _find_blocks(rows)
    blk = next((start for mi, start in blocks if mi == mes_idx), None)
    if blk is None:
        raise ValueError(f"Bloco do mes {mes_idx+1} nao encontrado no Checklist CVC")
    end = next((start for mi, start in blocks if mi != mes_idx and start > blk), len(rows))
    return {'fonte': 'controles', 'mes': None, 'checklistCVC': _parse_block(rows, blk, end)}


def parse_all_months(provider, ano, skip_empty=True):
    """
    Retorna {sector_key: [{'p':'jan/24', ...campos, cobertura, conformidade}, ...]}
    para TODOS os blocos mensais encontrados na planilha (tipicamente um ano).

    skip_empty=True (padrao): omite pontos onde lib==0 E preen==0 para aquele
    setor naquele mes - tratamos isso como "sem coleta", nao como "0%".
    """
    rows = provider.values('Checklist CVC')
    blocks = _find_blocks(rows)
    out = {k: [] for k in _KEYS}
    for idx, (mi, start) in enumerate(blocks):
        end = blocks[idx + 1][1] if idx + 1 < len(blocks) else len(rows)
        month = _parse_block(rows, start, end)
        label = f"{_ABBR[mi]}/{str(ano)[-2:]}"
        for sector, vals in month.items():
            if skip_empty and vals['lib'] == 0 and vals['preen'] == 0:
                continue
            pt = dict(vals)
            pt['p'] = label
            out[sector].append(pt)
    return out

# ── Consumo de álcool por enfermaria ──────────────────────────────────────────
# Aba: 'Consumo álcool UI'
# Estrutura: blocos mensais (col B = nome do mês), 7-8 linhas por bloco.
#   col A = setor · col B = pac/dia · col C = álcool (ml) · col D = ml/pac-dia
# 'Apto' e 'EPM' são combinados em 'epm' (total ml / total pd).
# 2024 não tem essa aba — série começa em jan/25.

_MESES_ALCOOL = ['JANEIRO','FEVEREIRO','MARCO','ABRIL','MAIO','JUNHO',
                 'JULHO','AGOSTO','SETEMBRO','OUTUBRO','NOVEMBRO','DEZEMBRO']

# Mapeamento: fragmento do nome normalizado -> chave do setor
_ALCOOL_MAP = [
    ('MEDICA',      'clinicaMedica'),
    ('CIRURGICA',   'clinicaCirurgica'),
    ('APTO',        '_apto'),   # combinado com EPM depois
    ('EPM',         '_epm'),
]


def _parse_alcool_block(rows, start, end):
    """
    Extrai {clinicaMedica, clinicaCirurgica, epm} em ml/pac-dia de um bloco
    mensal da aba 'Consumo álcool UI'.
    Apto + EPM são somados em 'epm'.
    Retorna None em vez de 0 se o bloco estiver vazio (coleta não realizada).
    """
    acc = {}   # chave -> {'ml': float, 'pd': float}

    for i in range(start + 1, end):   # +1 pula linha de cabeçalho de colunas
        r = rows[i]
        if not r or not r[0]:
            continue
        a = _norm(r[0])
        try:
            pd  = float(str(r[1]).replace(',','.')) if r[1] not in (None, '') else None
            ml  = float(str(r[2]).replace(',','.')) if r[2] not in (None, '') else None
        except (ValueError, TypeError):
            continue
        if pd is None or pd <= 0 or ml is None or ml <= 0:
            continue
        for frag, key in _ALCOOL_MAP:
            if frag in a:
                acc.setdefault(key, {'ml': 0.0, 'pd': 0.0})
                acc[key]['ml'] += ml
                acc[key]['pd'] += pd
                break

    result = {}
    for key in ('clinicaMedica', 'clinicaCirurgica'):
        if key in acc and acc[key]['pd'] > 0:
            result[key] = round(acc[key]['ml'] / acc[key]['pd'], 1)
        else:
            result[key] = None

    # combina Apto + EPM
    ml_epm = (acc.get('_apto', {}).get('ml', 0) +
              acc.get('_epm',  {}).get('ml', 0))
    pd_epm = (acc.get('_apto', {}).get('pd', 0) +
              acc.get('_epm',  {}).get('pd', 0))
    result['epm'] = round(ml_epm / pd_epm, 1) if pd_epm > 0 else None

    return result


def _find_alcool_blocks(rows):
    """Localiza blocos mensais na aba 'Consumo álcool UI'."""
    blocks = []
    for i, r in enumerate(rows):
        if not r or not r[1]:
            continue
        b = _norm(str(r[1]))
        for mi, m in enumerate(_MESES_ALCOOL):
            if _norm(m) == b:
                blocks.append((mi, i))
                break
    blocks.sort(key=lambda x: x[1])
    return blocks


def parse_alcool_enfermarias(provider, mes_idx, ano):
    """
    Extrai consumo de álcool gel (ml/pac-dia) das enfermarias para um mês.
    Retorna dict {clinicaMedica, clinicaCirurgica, epm} ou None se a aba não existir.
    Valores None indicam que a coleta não foi realizada naquele mês.
    """
    if 'Consumo álcool UI' not in provider.tabs():
        return None   # 2024 não tem essa aba
    rows = provider.values('Consumo álcool UI')
    blocks = _find_alcool_blocks(rows)
    blk = next((start for mi, start in blocks if mi == mes_idx), None)
    if blk is None:
        return None
    end = next((start for mi, start in blocks if start > blk), len(rows))
    return _parse_alcool_block(rows, blk, end)


def parse_alcool_all_months(provider, ano):
    """
    Extrai série histórica completa de consumo de álcool das enfermarias.
    Retorna {clinicaMedica: [{p, v}, ...], clinicaCirurgica: [...], epm: [...]}.
    Meses sem coleta (todos None) são omitidos.
    """
    if 'Consumo álcool UI' not in provider.tabs():
        return {}
    rows = provider.values('Consumo álcool UI')
    blocks = _find_alcool_blocks(rows)
    ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
    out = {'clinicaMedica': [], 'clinicaCirurgica': [], 'epm': []}

    for idx, (mi, start) in enumerate(blocks):
        end = blocks[idx + 1][1] if idx + 1 < len(blocks) else len(rows)
        mes_data = _parse_alcool_block(rows, start, end)
        label = f"{ABBR[mi]}/{str(ano)[-2:]}"
        for sector in out:
            v = mes_data.get(sector)
            if v is not None:
                out[sector].append({'p': label, 'v': v})
    return out
