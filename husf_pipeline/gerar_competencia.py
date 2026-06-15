#!/usr/bin/env python3
"""
gerar_competencia.py — Entrypoint do pipeline mensal HUSF.

Uso:
  python gerar_competencia.py --mes mai/26
  python gerar_competencia.py --mes mai/26 --dry-run
  python gerar_competencia.py --mes mai/26 --skip-r      # pula scripts R
  python gerar_competencia.py --seed-historico
  python gerar_competencia.py --seed-checklist
"""

import argparse, json, sys, subprocess, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import husf_pipeline.config as cfg
from husf_pipeline.parsers._util import XlsxProvider, parse_mes_arg, mes_label
from husf_pipeline.parsers import censo_mdr, censo_isc, diarreia, dots
from husf_pipeline.parsers import cve_mestre, cve_utic, dialise, controles
from husf_pipeline.parsers.controles import parse_alcool_enfermarias
from husf_pipeline.parsers import isolamentos
from husf_pipeline.parsers.alcool_uti import parse_alcool_uti
from husf_pipeline.core.merge import build_month
from husf_pipeline.core.report import print_report


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_yaml(path):
    try:
        import yaml
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"  ⚠  YAML nao encontrado: {path}. Campos manuais vazios.")
        return {}


def _load_prev_json():
    fname = cfg.DATA_JSON_PATTERN.format(n=cfg.DATA_JSON_VERSION)
    path = cfg.DASHBOARD_DIR / fname
    if not path.exists():
        sys.exit(f"ERRO: JSON anterior nao encontrado: {path}")
    with open(path, encoding='utf-8') as f:
        return json.load(f), path


def _save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Gravado: {path}")


def _run_rscript(script_name, cwd, timeout=180, label=''):
    """Roda um script R e retorna True se OK."""
    try:
        r = subprocess.run(
            ['Rscript', script_name],
            cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
        if r.returncode == 0:
            print(f"  OK  {script_name}" + (f" ({label})" if label else ''))
            return True
        else:
            msg = r.stderr.strip()
            print(f"  ERR {script_name}: {msg[:300] if msg else '(sem mensagem)'}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ERR {script_name}: timeout (>{timeout}s)")
        return False
    except FileNotFoundError:
        print(f"  ERR {script_name}: Rscript nao encontrado no PATH")
        return False
    except Exception as e:
        print(f"  ERR {script_name}: {e}")
        return False


# ── Scripts R ─────────────────────────────────────────────────────────────────

def run_r_scripts(label):
    """
    Roda os dois scripts R pos-pipeline e disponibiliza os outputs no repo:

    1. sahe_husf.R  →  data_sahe.json  (canais bootstrap P10-P90 + MK + zonas
                                         por mes; lido pelo dashboard via SAHE)

    2. husf_stats.R →  lis-portal/api/husf_stats_output.json  (tendencias DOT/
                        MDR, CUSUM, IC Poisson)  →  copiado para data_stats.json
                        no repo (lido pelo dashboard via STATS)

    Os dois arquivos de saida devem ser incluidos no commit mensal.
    """
    print("\n  Analise estatistica R...")

    # ── 1. SAHE: canais bootstrap por indicador de dispositivo ────────────────
    ok_sahe = _run_rscript('sahe_husf.R', cfg.DASHBOARD_DIR, timeout=300,
                           label='data_sahe.json')
    if not ok_sahe:
        print("     Execute manualmente: cd ~/vigilancia_husf_braganca && Rscript sahe_husf.R")

    # ── 2. husf_stats: tendencias DOT/MDR, CUSUM, Poisson ─────────────────────
    ok_stats = _run_rscript('husf_stats.R', cfg.DASHBOARD_DIR, timeout=300,
                            label='husf_stats_output.json')
    if ok_stats:
        src = cfg.STATS_OUTPUT_PATH          # definido em config.py
        dst = cfg.DASHBOARD_DIR / 'data_stats.json'
        if src and src.exists():
            shutil.copy2(src, dst)
            print(f"  OK  data_stats.json copiado do lis-portal")
        else:
            print(f"  ⚠  husf_stats_output.json nao encontrado em {src}")
            print(f"     Verifique STATS_OUTPUT_PATH em config.py")
    else:
        print("     Execute manualmente: Rscript husf_stats.R")


# ── Run mensal ────────────────────────────────────────────────────────────────

def run(mes_str, dry_run=False, skip_r=False):
    mes_idx, ano = parse_mes_arg(mes_str)
    label = mes_label(mes_idx, ano)
    print(f"\n==> Gerando competencia {label}\n")

    prev_json, prev_path = _load_prev_json()

    # Providers Google Sheets ao vivo
    print("  Conectando Google Sheets...")
    from husf_pipeline.sheets.providers import make_providers
    sp = make_providers(cfg.SHEET_IDS, str(cfg.CREDS_PATH))

    # Providers Excel locais
    xl = {k: XlsxProvider(str(v)) for k, v in cfg.EXCEL_FILES.items()}

    # Parsers
    out, errs = {}, []
    def rp(name, fn, prov):
        try:
            out[name] = fn(prov, mes_idx, ano)
            print(f"  OK  {name}")
        except Exception as e:
            print(f"  ERR {name}: {e}")
            errs.append(f"{name}: {e}")

    rp('censo_mdr',   censo_mdr.parse,   sp['censo_mdr'])
    rp('censo_isc',   censo_isc.parse,   sp['censo_isc'])
    rp('diarreia',    diarreia.parse,    sp['diarreia'])
    rp('dots',        dots.parse,        sp['dots'])
    rp('cve_mestre',  cve_mestre.parse,  xl['cve_mestre'])
    rp('cve_utic',    cve_utic.parse,    xl['cve_utic'])
    rp('cve_dialise', dialise.parse,     xl['cve_dialise'])
    rp('controles',   controles.parse,   xl['controles'])
    rp('isolamentos', isolamentos.parse, sp['isolamentos'])
    # Álcool das UTIs (bags do SHL na Planilha de Controles 'Dados UTI')
    try:
        out['controles_alcool_uti'] = parse_alcool_uti(
            str(cfg.EXCEL_FILES['controles']), ano)
        print('  OK  controles_alcool_uti')
    except Exception as e:
        out['controles_alcool_uti'] = {}
        print(f'  ERR controles_alcool_uti: {e}')
        errs.append(f'controles_alcool_uti: {e}')
    # Alcool gel das enfermarias — mesma planilha, parser separado
    try:
        _alc = parse_alcool_enfermarias(xl['controles'], mes_idx, ano)
        out['controles_alcool'] = _alc or {}
        print(f'  OK  controles_alcool')
    except Exception as e:
        out['controles_alcool'] = {}
        print(f'  ERR controles_alcool: {e}')
        errs.append(f'controles_alcool: {e}')

    yaml_path = cfg.MANUAL_DIR / f"{label.replace('/','')}.yaml"
    manual = _load_yaml(yaml_path)

    new_json = build_month(prev_json, label, out, manual)
    print_report(label, out, manual, warnings=errs)

    if dry_run:
        print("  Dry-run: JSON nao gravado, scripts R nao executados.")
        return

    _save_json(new_json, prev_path)

    if skip_r:
        print("\n  --skip-r: scripts R ignorados.")
        print("  Execute manualmente quando pronto:")
        print("    Rscript sahe_husf.R && Rscript husf_stats.R")
    else:
        run_r_scripts(label)

    print(f"\n  Proximo passo:")
    print(f"    cd ~/vigilancia_husf_braganca")
    print(f"    git add data_iras.json data_sahe.json data_stats.json")
    print(f"    git commit -m 'dados: {label}'")
    print(f"    git push")


# ── Seeds ─────────────────────────────────────────────────────────────────────

_MES_ORDER = {'jan':1,'fev':2,'mar':3,'abr':4,'mai':5,'jun':6,
              'jul':7,'ago':8,'set':9,'out':10,'nov':11,'dez':12}

def _label_key(lbl):
    if '/' in lbl:
        m, y = lbl.split('/')
        return (2000 + int(y), _MES_ORDER[m])
    return (int(lbl), 0)


def seed_checklist():
    """Semeia checklistCVC com serie historica completa (2024-2026)."""
    prev_json, prev_path = _load_prev_json()
    from husf_pipeline.parsers.controles import parse_all_months
    from copy import deepcopy

    d = deepcopy(prev_json)
    cur_pt = next((p for p in d.get('global', {}).get('taxaIH', []) if p.get('c')), None)
    cur_label = cur_pt['p'] if cur_pt else None
    print(f"  Competencia atual detectada: {cur_label or '(nenhuma)'}")

    files = dict(getattr(cfg, 'HIST_CONTROLES_FILES', {}))
    files[2026] = cfg.EXCEL_FILES['controles']

    combined = {}
    for ano, path in sorted(files.items()):
        prov = XlsxProvider(str(path))
        series = parse_all_months(prov, ano)
        for sector, pts in series.items():
            combined.setdefault(sector, [])
            for pt in pts:
                if cur_label and _label_key(pt['p']) >= _label_key(cur_label):
                    continue
                combined[sector].append(pt)
        print(f"  {ano}: OK")

    for sector, hist_pts in combined.items():
        d.setdefault('checklistCVC', {}).setdefault(sector, [])
        hist_pts.sort(key=lambda p: _label_key(p['p']))
        existing = {p['p'] for p in d['checklistCVC'][sector]}
        new_pts = [p for p in hist_pts if p['p'] not in existing]
        d['checklistCVC'][sector] = new_pts + d['checklistCVC'][sector]
        print(f"  checklistCVC.{sector}: +{len(new_pts)} pts "
              f"(total {len(d['checklistCVC'][sector])})")

    _save_json(d, prev_path)
    print("  Checklist CVC: serie historica semeada.")


def seed_alcool_historico():
    """
    Semeia serie historica de alcool gel das enfermarias (ml/pac-dia)
    a partir das Planilhas Gerais de Controles de 2025 e 2026.
    2024 nao tem a aba estruturada — serie comeca em jan/25.
    """
    prev_json, prev_path = _load_prev_json()
    from husf_pipeline.parsers.controles import parse_alcool_all_months
    from copy import deepcopy
    d = deepcopy(prev_json)

    cur_pt = next((p for p in d.get('global',{}).get('taxaIH',[]) if p.get('c')), None)
    cur_label = cur_pt['p'] if cur_pt else None
    print(f"  Competencia atual: {cur_label or '(nenhuma)'}")

    files = dict(getattr(cfg, 'HIST_CONTROLES_FILES', {}))
    files[2026] = cfg.EXCEL_FILES['controles']

    for ano, path in sorted(files.items()):
        prov = XlsxProvider(str(path))
        series = parse_alcool_all_months(prov, ano)
        if not series:
            print(f"  {ano}: sem aba Consumo alcool UI — ignorado")
            continue
        for sector, pts in series.items():
            d.setdefault(sector, {}).setdefault('hm', [])
            existing = {p['p'] for p in d[sector]['hm']}
            added = 0
            for pt in pts:
                if cur_label and _label_key(pt['p']) >= _label_key(cur_label):
                    continue
                if pt['p'] not in existing:
                    d[sector]['hm'].append(pt)
                    added += 1
            if added:
                print(f"  {ano} {sector}: +{added} pontos")
        print(f"  {ano}: OK ({path.name if hasattr(path,'name') else path})")

    _save_json(d, prev_path)
    print("  Alcool UI: serie historica semeada.")




def seed_alcool_uti():
    """
    Recalcula HM álcool das UTIs (A/B e C) a partir das bags do SHL
    (Planilha de Controles 'Dados UTI'), corrigindo o histórico.
    Fonte de pac-dia: CVE Plan2 (parser cve_mestre).
    """
    prev_json, prev_path = _load_prev_json()
    from husf_pipeline.parsers.alcool_uti import parse_alcool_uti
    from husf_pipeline.parsers import cve_mestre
    from husf_pipeline.parsers._util import XlsxProvider
    from copy import deepcopy

    d = deepcopy(prev_json)
    files = dict(getattr(cfg, 'HIST_CONTROLES_FILES', {}))
    files[2026] = cfg.EXCEL_FILES['controles']

    cur_pt = next((p for p in d.get('global',{}).get('taxaIH',[]) if p.get('c')), None)
    cur_label = cur_pt['p'] if cur_pt else None

    ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
    mestre_prov = XlsxProvider(str(cfg.EXCEL_FILES['cve_mestre']))

    fixes = {'utiAB': {}, 'utic': {}}
    for ano, path in sorted(files.items()):
        bags = parse_alcool_uti(str(path), ano)
        for mi in range(12):
            label = f"{ABBR[mi]}/{str(ano)[-2:]}"
            if cur_label and _label_key(label) > _label_key(cur_label):
                continue
            # pac-dia do CVE Plan2 — só disponível para 2026 (mestre atual)
            if ano == 2026:
                m = cve_mestre.parse(mestre_prov, mi, ano)
                ab_pd = m.get('ab',{}).get('pac_dia')
                uc_pd = m.get('uc',{}).get('pac_dia')
            else:
                ab_pd = uc_pd = None
            ab_ml = bags['utiAB'].get(label)
            uc_ml = bags['utic'].get(label)
            if ab_ml and ab_pd:
                fixes['utiAB'][label] = round(ab_ml/ab_pd, 1)
            if uc_ml and uc_pd:
                fixes['utic'][label] = round(uc_ml/uc_pd, 1)

    MO = {a:i+1 for i,a in enumerate(ABBR)}
    def lk(pt):
        p = pt['p']
        if '/' not in p: return (int(p), 0)
        m,y = p.split('/'); return (2000+int(y), MO[m])

    for unit in ('utiAB','utic'):
        series = d.setdefault(unit, {}).setdefault('hm', [])
        by_label = {pt['p']: pt for pt in series}
        for label, v in fixes[unit].items():
            if label in by_label:
                by_label[label]['v'] = v
            else:
                series.append({'p': label, 'v': v})
        series.sort(key=lk)
        print(f"  {unit}.hm corrigido: {[(p['p'],p['v']) for p in series if '/' in p['p']]}")

    _save_json(d, prev_path)
    print("  HM álcool UTIs recalculado das bags do SHL.")


def seed_isolamentos():
    """Semeia serie historica de isolamentos/precaucoes a partir do Sheets."""
    prev_json, prev_path = _load_prev_json()
    from husf_pipeline.parsers.isolamentos import parse_all_months
    from husf_pipeline.sheets.providers import make_providers
    from copy import deepcopy

    sp = make_providers(cfg.SHEET_IDS, str(cfg.CREDS_PATH))
    print("  Conectando Censo Isolamentos...")
    all_m = parse_all_months(sp['isolamentos'], 2026)

    cur_pt = next((p for p in prev_json.get('global',{}).get('taxaIH',[]) if p.get('c')), None)
    cur_label = cur_pt['p'] if cur_pt else None
    print(f"  Competencia atual: {cur_label or '(nenhuma)'}")

    d = deepcopy(prev_json)
    d.setdefault('isolamentos', {})

    added_total = 0
    for metric, ward_series in all_m.items():
        d['isolamentos'].setdefault(metric, {})
        for ward, pts in ward_series.items():
            d['isolamentos'][metric].setdefault(ward, [])
            existing = {p['p'] for p in d['isolamentos'][metric][ward]}
            new_pts = [p for p in pts
                       if p['p'] not in existing
                       and (not cur_label or _label_key(p['p']) < _label_key(cur_label))]
            for pt in new_pts:
                d['isolamentos'][metric][ward].append({'p': pt['p'], 'n': pt['n'], 'pct': pt['pct']})
            added_total += len(new_pts)
        print(f"  {metric}: OK")

    _save_json(d, prev_path)
    print(f"  Isolamentos: {added_total} pontos semeados no total.")

def seed_historico():
    """Semeia serie historica de IRAS das enfermarias (2024-2025, dos PDFs)."""
    prev_json, prev_path = _load_prev_json()
    from husf_pipeline.parsers.hist_pdf import get_historico
    from copy import deepcopy
    d = deepcopy(prev_json)
    for ward_key, series in get_historico().items():
        d.setdefault(ward_key, {}).setdefault('infSeries', [])
        existing = {p.get('p') for p in d[ward_key]['infSeries']}
        for pt in series:
            if pt['p'] not in existing:
                d[ward_key]['infSeries'].append(pt)
    _save_json(d, prev_path)
    print("  Historico de enfermarias semeado (2024-2025).")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description='Pipeline mensal HUSF')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--mes',             help='Competencia ex: mai/26')
    g.add_argument('--seed-historico',  action='store_true',
                   help='Semeia serie historica das enfermarias (uma vez)')
    g.add_argument('--seed-checklist',  action='store_true',
                   help='Semeia serie historica do checklist CVC (uma vez)')
    g.add_argument('--seed-alcool',      action='store_true',
                   help='Semeia serie historica de alcool das enfermarias (uma vez)')
    g.add_argument('--seed-isolamentos', action='store_true',
                   help='Semeia serie historica de isolamentos (uma vez)')
    g.add_argument('--seed-alcool-uti', action='store_true',
                   help='Recalcula HM álcool UTIs das bags do SHL (uma vez)')
    p.add_argument('--dry-run',  action='store_true',
                   help='Processa mas nao grava JSON nem roda R')
    p.add_argument('--skip-r',   action='store_true',
                   help='Pula os scripts R (util em testes)')
    args = p.parse_args()

    if args.seed_historico:
        seed_historico()
    elif args.seed_checklist:
        seed_checklist()
    elif args.seed_alcool:
        seed_alcool_historico()
    elif args.seed_isolamentos:
        seed_isolamentos()
    elif args.seed_alcool_uti:
        seed_alcool_uti()
    else:
        run(args.mes, dry_run=args.dry_run, skip_r=args.skip_r)


if __name__ == '__main__':
    main()
