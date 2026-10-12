"""
core/report.py — Relatório de preenchimento da rodada.

Imprime o que entrou, o que ficou None/ausente, e alertas clínicos óbvios.
"""

from datetime import datetime


def _fmt(v):
    if v is None:
        return '—'
    if isinstance(v, float):
        return f'{v:.2f}'
    return str(v)


def print_report(label, parsers_out, manual, warnings=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"\n{'='*60}")
    print(f"  HUSF Pipeline · competência {label} · {now}")
    print(f"{'='*60}")

    # ── Parsers ──────────────────────────────────────────────────────────
    print("\n📋 FONTES PROCESSADAS")
    fonte_labels = {
        'cve_mestre':  'CVE Mestre',
        'cve_utic':    'CVE UTI C',
        'cve_dialise': 'CVE Diálise',
        'censo_mdr':   'Censo MDR',
        'censo_isc':   'Censo ISC',
        'diarreia':    'Censo Diarreia',
        'dots':        'DOTs ATB',
        'controles':   'Checklist CVC',
    }
    for key, name in fonte_labels.items():
        status = '✅' if key in parsers_out else '⚠️  AUSENTE'
        print(f"  {status}  {name}")

    # ── Manual ───────────────────────────────────────────────────────────
    print("\n📝 CAMPOS MANUAIS")
    manual_fields = [
        ('global_taxaIH',      'Taxa IH Global'),
        ('status_global',      'Status epidemiológico Global'),
        ('status_utiAB',       'Status UTI A/B'),
        ('status_utic',        'Status UTI C'),
        ('status_utiNeo',      'Status UTI Neo'),
        ('status_clinicaMedica','Status Clínica Médica'),
        ('status_clinicaCirurgica','Status Clínica Cirúrgica'),
        ('status_epm',         'Status EPM'),
        ('status_hd',          'Status Hemodiálise'),
        ('clinicaMedica',      'Enfermaria CM (contagens)'),
        ('clinicaCirurgica',   'Enfermaria CC (contagens)'),
        ('epm',                'Enfermaria EPM (contagens)'),
        ('sura',               'SURA'),
        ('abio',               'Antibiograma'),
    ]
    pending = []
    for key, name in manual_fields:
        v = manual.get(key)
        if v is None or v == '':
            print(f"  ⚠️  {name:35s} — pendente")
            pending.append(name)
        else:
            print(f"  ✅  {name:35s} = {_fmt(v) if not isinstance(v, dict) else '(preenchido)'}")

    # ── Avisos dos parsers ────────────────────────────────────────────────
    all_warnings = list(warnings or [])
    for res in parsers_out.values():
        if isinstance(res, dict):
            all_warnings.extend(res.get('_avisos', []))

    if all_warnings:
        print("\n⚠️  AVISOS")
        for w in all_warnings:
            print(f"  • {w}")

    # ── Resumo ────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    if pending:
        print(f"  {len(pending)} campo(s) pendente(s). Edite manual/{label.replace('/','')}.yaml")
    else:
        print("  Todos os campos preenchidos. Pronto para commit.")
    print(f"{'='*60}\n")
