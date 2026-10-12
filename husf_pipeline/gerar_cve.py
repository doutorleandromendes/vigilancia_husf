#!/usr/bin/env python3
"""
gerar_cve.py — Entrypoint mensal do preenchimento do CVE-SP a partir das fontes.

Os caminhos das planilhas vêm do husf_pipeline/config.py (cfg.EXCEL_FILES), a mesma
fonte que o gerar_competencia.py usa. Variáveis de ambiente sobrepõem se definidas.

Uso:
  python gerar_cve.py --mes jul/26
  python gerar_cve.py --mes jul/26 --ate-agora
  python gerar_cve.py --mes jul/26 --dialise --setor-dialise CVE_hemodia_lise_JULHO.xlsx
  python gerar_cve.py --mes jul/26 --dry-run
"""
import argparse, csv, os, subprocess, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # raiz do projeto
from husf_pipeline.parsers import cve_controles as CC
from husf_pipeline.parsers import cve_sura as SURA
from husf_pipeline.core.cve_writer import build_cve, build_cve_dialise

# ── Config: caminhos do config.py do pipeline; env vars sobrepõem ──────────────
try:
    import husf_pipeline.config as cfg
    _EXCEL = {k: str(v) for k, v in getattr(cfg, 'EXCEL_FILES', {}).items()}
except Exception as _e:
    _EXCEL = {}
    print(f'  ⚠  não consegui importar husf_pipeline.config ({_e}); usando env vars.')

CONTROLES       = os.environ.get('CVE_CONTROLES')   or _EXCEL.get('controles')
CVE_MESTRE      = os.environ.get('CVE_MESTRE')      or _EXCEL.get('cve_mestre')
CVE_DIAL_MESTRE = os.environ.get('CVE_DIAL_MESTRE') or _EXCEL.get('cve_dialise')
OUT_DIR         = Path(os.environ.get('CVE_OUT', '.'))
SURA_URL        = os.environ.get('CVE_SURA_URL', 'https://app.lcmendes.med.br')
SURA_KEY        = os.environ.get('CVE_API_KEY')
INST            = os.environ.get('CVE_INST', 'HUSF')

ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']

def parse_mes(arg):
    """'jul/26' -> ('Julho', 2026, 7)"""
    a, _, yy = arg.lower().strip().partition('/')
    mi = ABBR.index(a[:3])
    return CC.MESES[mi], 2000 + int(yy), mi + 1

def _require(path, rotulo):
    if not path:
        sys.exit(f'ERRO: caminho de {rotulo} não encontrado (nem no config.py nem em env var).')
    if not Path(path).exists():
        sys.exit(f'ERRO: {rotulo} não existe no disco:\n  {path}')
    return path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mes', required=True, help='competência, ex.: jul/26')
    ap.add_argument('--ate-agora', action='store_true', help='preenche jan..mês (refresh)')
    ap.add_argument('--sura-url', default=SURA_URL)
    ap.add_argument('--sura-key', default=SURA_KEY)
    ap.add_argument('--sura-file', default=None, help='JSON local do endpoint (offline/teste)')
    ap.add_argument('--inst', default=INST)
    ap.add_argument('--no-sura', action='store_true', help='pula numeradores (só planilhas)')
    ap.add_argument('--dialise', action='store_true', help='preenche o CVE de diálise')
    ap.add_argument('--setor-dialise', default=None, help='arquivo mensal do setor de hemodiálise')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--recalc', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    mes, ano, mnum = parse_mes(args.mes)
    meses = CC.MESES[:mnum] if args.ate_agora else [mes]
    suf = args.mes.replace('/', '')
    default_name = f'PLANILHA_CVE_dialise_{suf}_auto.xlsx' if args.dialise else f'PLANILHA_CVE_HUSF_{suf}_auto.xlsx'
    out_path = Path(args.out) if args.out else OUT_DIR / default_name
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── SURA: busca o JSON bruto (uma vez), aplica o mapper conforme o modo ──
    merged = None
    if not args.no_sura:
        try:
            if args.sura_file:
                import json
                merged = json.load(open(args.sura_file, encoding='utf-8'))
            else:
                merged = {'iras_por_setor': [], 'isc_por_equipe': []}
                for m in meses:
                    mi = CC.MESES.index(m) + 1
                    j = SURA.fetch_sura(args.sura_url, args.inst, ano, mi, args.sura_key)
                    merged['iras_por_setor'] += j.get('iras_por_setor', [])
                    merged['isc_por_equipe'] += j.get('isc_por_equipe', [])
        except Exception as e:
            print(f'  ⚠  SURA indisponível ({e}). Seguindo sem numeradores.')

    if args.dialise:
        setor = _require(args.setor_dialise, 'arquivo do setor (--setor-dialise)')
        _require(CVE_DIAL_MESTRE, 'CVE diálise mestre (cfg.EXCEL_FILES["cve_dialise"])')
        hd = SURA.map_hd(merged) if merged else None
        diff = build_cve_dialise(setor, CVE_DIAL_MESTRE, str(out_path), meses, hd)
    else:
        _require(CONTROLES, 'Planilha de Controles (cfg.EXCEL_FILES["controles"])')
        _require(CVE_MESTRE, 'CVE mestre (cfg.EXCEL_FILES["cve_mestre"])')
        numeradores = SURA.map_numeradores(merged) if merged else None
        diff = build_cve(CONTROLES, CVE_MESTRE, str(out_path), meses, numeradores)

    # ── Relatório ──
    cnt = Counter(d[6] for d in diff)
    print(f'{args.mes}: {len(diff)} células  ->  ' + '  '.join(f'{k}={v}' for k, v in cnt.items()))
    div = [d for d in diff if d[6] in ('DIVERGE', 'PENDENTE')]
    if div:
        print(f'  ⚠  {len(div)} para revisar:')
        for d in div[:25]:
            print(f'     {d[0]:9} {d[1]:26} {d[2]:9} manual={d[3]}  auto={d[4]}  [{d[6]}]')

    if args.dry_run:
        out_path.unlink(missing_ok=True)
        print('  (dry-run: arquivo não gravado)')
        return

    diff_name = 'diff_revisao_dialise.csv' if args.dialise else 'diff_revisao_cve.csv'
    diff_path = OUT_DIR / diff_name
    with open(diff_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['mes','aba','celula','valor_antigo','valor_novo','fonte','status']); w.writerows(diff)
    print(f'  Gravado: {out_path}')
    print(f'  Diff:    {diff_path}')

    if args.recalc:
        rc = Path(__file__).parent / 'scripts' / 'recalc.py'
        if rc.exists():
            subprocess.run([sys.executable, str(rc), str(out_path)], check=False)
        else:
            print('  (recalc.py não encontrado; o Excel recalcula ao abrir)')

if __name__ == '__main__':
    main()
