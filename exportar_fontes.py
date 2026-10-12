#!/usr/bin/env python3
"""
exportar_fontes.py — baixa em lote todas as fontes do pipeline HUSF.

  · As 5 Google Sheets (SHEET_IDS) -> exportadas como .xlsx via Drive API
  · Os 4 Excel locais (EXCEL_FILES) -> copiados como estão

Usa a MESMA service account do pipeline (config.CREDS_PATH), então não
precisa de OAuth novo. Requer que a Drive API esteja habilitada no projeto
e que o escopo drive.readonly seja pedido (feito aqui embaixo).

Uso, a partir da raiz do projeto (o diretório que contém husf_pipeline/):

    pip install google-api-python-client google-auth
    python3 exportar_fontes.py
    python3 exportar_fontes.py --out ~/Desktop/fontes --zip
"""

import argparse
import io
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

# ── importa o config do pipeline, rodando da raiz ou de dentro dele ──────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from husf_pipeline import config
except ImportError:
    try:
        import config  # rodando de dentro de husf_pipeline/
    except ImportError:
        sys.exit("erro: não achei o config.py — rode da raiz do projeto "
                 "(o diretório que contém husf_pipeline/)")

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def baixar_sheet(drive, file_id, destino):
    """Exporta uma Google Sheet como .xlsx. Retorna bytes gravados."""
    req = drive.files().export_media(fileId=file_id, mimeType=XLSX)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    data = buf.getvalue()

    # .xlsx é um zip: se não começa com 'PK', veio página de erro, não planilha
    if not data.startswith(b'PK'):
        raise RuntimeError(f"resposta não é xlsx ({len(data)} bytes) — "
                           f"cheque permissão da service account")
    destino.write_bytes(data)
    return len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path,
                    default=Path.home() / f"vig_fontes_{date.today():%Y%m%d}")
    ap.add_argument('--zip', action='store_true',
                    help='gera também um .zip com tudo, pra upload')
    ap.add_argument('--so-sheets', action='store_true',
                    help='pula os Excel locais')
    args = ap.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    print(f"destino: {out}\n")

    if not config.CREDS_PATH.exists():
        sys.exit(f"erro: credencial não encontrada em {config.CREDS_PATH}")

    creds = Credentials.from_service_account_file(
        str(config.CREDS_PATH), scopes=SCOPES)
    drive = build('drive', 'v3', credentials=creds, cache_discovery=False)

    ok, falhou = [], []

    # ── 1. Google Sheets ────────────────────────────────────────────────────
    print("── Google Sheets ──")
    for nome, fid in config.SHEET_IDS.items():
        destino = out / f"{nome}.xlsx"
        try:
            n = baixar_sheet(drive, fid, destino)
            print(f"  ✓ {nome:14s} {n/1024:8.1f} KB")
            ok.append(destino)
        except HttpError as e:
            code = getattr(e.resp, 'status', '?')
            dica = ''
            if code == 403:
                dica = '  (Drive API desabilitada no projeto? escopo?)'
            elif code == 404:
                dica = '  (service account não tem acesso a esse arquivo)'
            print(f"  ✗ {nome:14s} HTTP {code}{dica}")
            falhou.append(nome)
        except Exception as e:
            print(f"  ✗ {nome:14s} {e}")
            falhou.append(nome)

    # ── 2. Excel locais ─────────────────────────────────────────────────────
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

    # ── 3. zip opcional ─────────────────────────────────────────────────────
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
