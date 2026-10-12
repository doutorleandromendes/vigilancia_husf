"""
sheets/providers.py — Provedores ao vivo para as 4 planilhas Google Sheets.

Usa gspread com service account. Os IDs das planilhas ficam em config.py.
Interface idêntica a XlsxProvider (tabs() + values(tab)) — os parsers não
percebem a diferença.

Uso:
    from husf_pipeline.sheets.providers import make_providers
    provs = make_providers(config.SHEET_IDS, config.CREDS_PATH)
    # provs['censo_mdr'] é um provider pronto p/ passar aos parsers
"""

import gspread
from husf_pipeline.parsers._util import GSheetProvider


def make_providers(sheet_ids: dict, creds_path: str) -> dict:
    """
    sheet_ids: {'censo_mdr': 'ID...', 'censo_isc': 'ID...', ...}
    creds_path: caminho para o JSON da service account

    Retorna dict {fonte: GSheetProvider}.
    """
    gc = gspread.service_account(filename=creds_path)
    providers = {}
    for key, sid in sheet_ids.items():
        providers[key] = _LazyGSheetProvider(gc, sid)
    return providers


class _LazyGSheetProvider:
    """GSheetProvider com abertura preguiçosa da planilha (evita rate-limit na inicialização)."""

    def __init__(self, gc, spreadsheet_id):
        self._gc = gc
        self._sid = spreadsheet_id
        self._ss = None
        self._cache = {}

    def _open(self):
        if self._ss is None:
            self._ss = self._gc.open_by_key(self._sid)
        return self._ss

    def tabs(self):
        return [w.title for w in self._open().worksheets()]

    def values(self, tab):
        if tab not in self._cache:
            ws = self._open().worksheet(tab)
            self._cache[tab] = ws.get_all_values()
        return self._cache[tab]
