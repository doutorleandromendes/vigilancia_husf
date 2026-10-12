"""
cve_dialise.py — parser do arquivo mensal do setor de hemodiálise (mesmo template do
CVE de diálise). Extrai SÓ denominadores + contagens do setor; os numeradores de IRAS
(O,R,U,W,Z,AC) são ignorados aqui — vêm do SURA (setor é muito falho nesses).

Aba 'Hemodiálise', linha do mês = 32 + mi (Janeiro=32 … Dezembro=43).
Colunas de input do setor:
  B=cat.temporário  C=cat.permanente  D=fístula       (nº pacientes / denominadores)
  F=hospitalização  H=CVC>3m  J=soroconversão  K=anti-HCV neg  M=mortalidade  AE=vancomicina
"""
import openpyxl

# campo -> índice de coluna (B=2 … AE=31)
SETOR_COLS = {'temp':2, 'perm':3, 'fist':4,
              'hosp':6, 'cvc3m':8, 'soro':10, 'hcvneg':11, 'obito':13, 'vanco':31}

def parse_hemodialise(setor_path, mi):
    """Retorna {campo: valor} da linha do mês mi (0-based) na aba Hemodiálise do setor."""
    wb = openpyxl.load_workbook(setor_path, read_only=True, data_only=True)
    ws = wb['Hemodiálise']
    row = 32 + mi
    vals = list(ws.iter_rows(min_row=row, max_row=row, values_only=True))[0]
    def col(idx): return vals[idx-1] if idx-1 < len(vals) else None
    out = {k: col(idx) for k, idx in SETOR_COLS.items()}
    wb.close()
    return out
