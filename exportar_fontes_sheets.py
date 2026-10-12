#!/usr/bin/env python3
"""
exportar_fontes_sheets.py — mesma coisa que exportar_fontes.py, mas usando a
Sheets API (já habilitada no projeto) em vez da Drive API.

Lê todas as abas de cada planilha e remonta um .xlsx local com openpyxl.
Traz VALORES, não fórmulas nem formatação — que é exatamente o que os
parsers do pipeline consomem via provider.values(tab).

Uso, a partir da raiz do projeto:

    pip install google-api-python-client google-auth openpyxl
    python3 exportar_fontes_sheets.py --zip
"""

import argparse
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from husf_pipeline import config
except ImportError:
    try:
        import config
    except ImportError:
        sys.exit("erro: não achei o config.py — rode da raiz do projeto")

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openpyxl import Workbook

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
LOTE = 10          # abas por chamada de batchGet
_INVALIDO = re.compile(r'[\[\]:*?/\\]')


def _titulo_seguro(t, usados):
    """openpyxl: máximo 31 chars, sem []:*?/\\ e sem repetir."""
    s = _INVALIDO.sub('-', str(t))[:31] or 'aba'
    base, i = s, 2
    while s in usados:
        sufixo = f"~{i}"
        s = base[:31 - len(sufixo)] + sufixo
        i += 1
    usados.add(s)
    return s


def exportar(svc, file_id, destino):
    meta = svc.spreadsheets().get(
        spreadsheetId=file_id,
        fields='sheets.properties.title').execute()
    abas = [s['properties']['title'] for s in meta.get('sheets', [])]
    if not abas:
        raise RuntimeError('planilha sem abas')

    wb = Workbook()
    wb.remove(wb.active)
    usados = set()

    for i in range(0, len(abas), LOTE):
        pedaco = abas[i:i + LOTE]
        resp = svc.spreadsheets().values().batchGet(
            spreadsheetId=file_id,
            ranges=[f"'{a}'" for a in pedaco],
            valueRenderOption='UNFORMATTED_VALUE',
            dateTimeRenderOption='FORMATTED_STRING').execute()

        for aba, faixa in zip(pedaco, resp.get('valueRanges', [])):
            ws = wb.create_sheet(_titulo_seguro(aba, usados))
            for linha in faixa.get('values', []):
                ws.append([c if c != '' else None for c in linha])

    wb.save(destino)
    return destino.stat().st_size, len(abas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path,
                    default=Path.home() / f"vig_fontes_{date.today():%Y%m%d}")
    ap.add_argument('--zip', action='store_true')
    ap.add_argument('--so-sheets', action='store_true')
    args = ap.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    print(f"destino: {out}\n")

    if not config.CREDS_PATH.exists():
        sys.exit(f"erro: credencial não encontrada em {config.CREDS_PATH}")

    creds = Credentials.from_service_account_file(
        str(config.CREDS_PATH), scopes=SCOPES)
    svc = build('sheets', 'v4', credentials=creds, cache_discovery=False)

    ok, falhou = [], []

    print("── Google Sheets (via Sheets API) ──")
    for nome, fid in config.SHEET_IDS.items():
        destino = out / f"{nome}.xlsx"
        try:
            n, abas = exportar(svc, fid, destino)
            print(f"  ✓ {nome:14s} {n/1024:8.1f} KB   {abas:3d} abas")
            ok.append(destino)
        except HttpError as e:
            code = getattr(e.resp, 'status', '?')
            print(f"  ✗ {nome:14s} HTTP {code}")
            falhou.append(nome)
        except Exception as e:
            print(f"  ✗ {nome:14s} {e}")
            falhou.append(nome)

    if not args.so_sheets:
        print("\n── Excel locais ──")
        for nome, caminho in config.EXCEL_FILES.items():
            destino = out / f"{nome}{caminho.suffix}"
            if not caminho.exists():
                print(f"  ✗ {nome:14s} não encontrado: {caminho}")
                falhou.append(nome)
                continue
            shutil.copy2(caminho, destino)
            print(f"  ✓ {nome:14s} {destino.stat().st_size/1024:8.1f} KB")
            ok.append(destino)

    if args.zip and ok:
        zpath = out.with_suffix('.zip')
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in ok:
                z.write(f, f.name)
        print(f"\nzip: {zpath}  ({zpath.stat().st_size/1024/1024:.1f} MB)")

    print(f"\n{len(ok)} ok, {len(falhou)} falhou"
          + (f" — {', '.join(falhou)}" if falhou else ""))


if __name__ == '__main__':
    main()
