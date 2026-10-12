"""
config.py — Caminhos, IDs e constantes do pipeline HUSF.

Edite este arquivo para apontar para seus arquivos locais e IDs das planilhas.
Os IDs das planilhas ficam aqui (não na credencial), pois não são segredos.
"""

from pathlib import Path

# ── Raiz do projeto ───────────────────────────────────────────────────────────
ROOT = Path(__file__).parent

# ── Credencial da service account (NUNCA no git) ──────────────────────────────
CREDS_PATH = ROOT / 'credentials' / 'husf-pipeline-sa.json'

# ── IDs das planilhas Google Sheets ──────────────────────────────────────────
# Encontre o ID na URL: docs.google.com/spreadsheets/d/<ID>/edit
SHEET_IDS = {
    'censo_mdr':  '1BPKPjFfgPlSyiHdwUAuGhjIUU-hV3iVe-ltbEx6m07U',
    'censo_isc':  '1FIAfc_83MVeYCfgQd7KmXXkXLOyxQNBbW2ur5Hk3alc',
    'diarreia':   '1mLhOq_pUMAaicj5Lhun_I6KyzJBL7aE02x68XHvzz24',
    'dots':       '1KnoUogJ1SrIQ-jexLruat6JfWNHvq6bUZF4Z5IQVPEA',
    'isolamentos':'1dEkDRsfH7j9yvZmhUIlkj400GyO_z73P4W1Iks5hRj4',
    'censo': '1IPxP-IjMD4lgBUXvjB0tDM6RJKzmWojpZhAnAMMz65Q'
}

# ── Arquivos Excel locais ─────────────────────────────────────────────────────
# Ajuste os caminhos para onde você mantém esses arquivos
EXCEL_DIR = Path('/Users/leandromendes/Library/CloudStorage/GoogleDrive-delfos28@gmail.com/Meu Drive/lcmendes@berkeley.edu 2024-05-23 13:32/HUSF/Indicadores_Mestre')

EXCEL_FILES = {
    'cve_mestre':   EXCEL_DIR / 'PLANILHA CVE HUSF mestre2026.xlsx',
    'cve_utic':     EXCEL_DIR / 'CVE UTI C.xlsx',
    'cve_dialise':  EXCEL_DIR / 'PLANILHA CVE Dialise mestre2026.xlsx',
    'controles':    EXCEL_DIR / 'Planilha Geral de controles 2026.xlsx',
}

# ── Repositório do dashboard (onde o data_iras_N.json vive) ──────────────────
DASHBOARD_DIR = Path.home() / 'vigilancia_husf_braganca'
DATA_JSON_PATTERN = 'data_iras.json'   # {n} = número da versão atual

# Versão atual do JSON (incrementar ao mudar schema):
DATA_JSON_VERSION = 8

# ── Diretório de manuais ──────────────────────────────────────────────────────
MANUAL_DIR = ROOT / 'manual'

HIST_CONTROLES_FILES = {
    2024: EXCEL_DIR / 'Planilha Geral de controles 2024.xlsx',
    2025: EXCEL_DIR / 'Planilha Geral de controles 2025.xlsx',
}

# ── Scripts R e outputs estatísticos ─────────────────────────────────────────
# Caminho onde husf_stats.R grava o output (antes de ser copiado pro repo)
STATS_OUTPUT_PATH = Path.home() / 'lis-portal' / 'api' / 'husf_stats_output.json'
