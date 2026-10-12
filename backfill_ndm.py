#!/usr/bin/env python3
"""
backfill_ndm.py — serie historica de NDM (jan-ago/26) a partir da planilha
geral de culturas, para dentro de data_iras.json -> mdrMensal[unidade].ndm

Regras (definidas 12/10/2026):
  METALO = uniao de MR='METALO' e CLASSE='METALO' (colunas disjuntas: duas
    convencoes de registro; CLASSE as vezes guarda MIC de polimixina).
  'METALO/KPC?' fica de fora.
  ORGANISMO PRIMEIRO: Pseudomonas metalo fica em Pseudomonas MR; Acinetobacter
    metalo fica em Acinetobacter. NDM aqui = Enterobacterales metalo.
  NOVO = PRIMEIRA DETECCAO NA INTERNACAO (por ATENDIMENTO), creditada a unidade
    onde ocorreu. Transferencia intra-hospitalar (inclusive P.S -> enfermaria)
    fica so no cumulativo da unidade de destino, sem novo.
  ADMISSAO NAO ENTRA: se a primeira deteccao da internacao foi swab de
    admissao, o caso e importado e nao gera novo em unidade nenhuma.
    'Rotina ou Admissao' so e preenchida em swab; amostra clinica vem vazia.

set/26+ pertence a vigilancia diaria e NAO e gravado aqui. O script so lista
set/26 pela mesma regra, para conferencia caso a caso com a grade.

  python3 backfill_ndm.py            # dry-run
  python3 backfill_ndm.py --aplicar  # grava em data_iras.json
"""
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict

import gspread
from husf_pipeline import config as cfg
from husf_pipeline.sheets.providers import make_providers
from husf_pipeline.parsers import censo_mdr, censo as censo_adm
from husf_pipeline.parsers._util import norm as _norm, find_month_tab, num

SHEET_ID = '10Ndg7JtP3fYxTFjbtRM____Tq77g6IAcki4DWYcSyrk'
ABA = '2026'
JSON = 'data_iras.json'
MESES = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
ATE_MES = 8
ORGS_FORA = ('PSEUDOMONAS', 'ACINETOBACTER')

CLINICA_UNIDADE = {
    'UTI-A': 'utiAB', 'UTI-B': 'utiAB', 'UIT-A': 'utiAB', 'UIT-B': 'utiAB',
    'UTI-C': 'utic',
    'UTI-NEO': 'utiNeo', 'UTINEO': 'utiNeo',
    'CM': 'clinicaMedica',
    'CC': 'clinicaCirurgica',
}


def chave(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip().upper()


def dia(s):
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', str(s).strip())
    return (int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


# Denominador do backfill. Tres bases de pac-dia convivem em 2026 (medido 12/10):
#   Censo administrativo ............ 100%  (todos os pacientes, todos os dias)
#   censo_mdr (planilha MDR, UTIs) ... ~95%  (praticamente mes cheio)
#   vigilancia diaria (set/26+) ...... ~95%  (26-30/30 dias, retroativos inclusos)
#   censo_isc / diarreia / isol. ..... ~65%  (aparentemente so dias uteis)
# Incidencia NAO e imune a cobertura (o caso conta 1x, o pac-dia encolhe), entao
# o backfill usa a base mais proxima da vigilancia atual:
#   UTIs  -> censo_mdr (mesma fonte da serie MDR ja publicada)
#   enfermarias -> Censo administrativo (~5% da vigilancia; censo_isc daria ~1,5x)
UTI_MDR = {'utiAB': 'ab', 'utic': 'uc', 'utiNeo': 'neo'}
ENF_CENSO = {'clinicaCirurgica': 'CLINICA CIRURGICA', 'clinicaMedica': 'CLINICA MEDICA'}
ISC_GRUPO = {'clinicaCirurgica': 'CLINICA CIRURGICA', 'clinicaMedica': 'CLINICA MEDICA',
             'utiAB': 'UTIAB', 'utic': 'UTIC'}


def _soma_isc(sp, mi, grupo):
    rows = sp['censo_isc'].values(find_month_tab(sp['censo_isc'], mi))
    hdr = rows[1] if len(rows) > 1 else []
    j = next((i for i, h in enumerate(hdr) if chave(h) == grupo), None)
    if j is None:
        return None
    tot = 0.0
    for r in rows[3:]:
        if r and chave(r[0]).startswith('TOTAL'):
            break
        if r and str(r[0]).strip().isdigit() and j + 2 < len(r):
            tot += num(r[j + 2]) or 0
    return tot


def denominador(sp, u, mes):
    """(pac_dia, fonte, alternativa_censo_isc)"""
    mi = mes - 1
    alt = _soma_isc(sp, mi, ISC_GRUPO[u]) if u in ISC_GRUPO else None
    if u in UTI_MDR:
        return censo_mdr.parse(sp['censo_mdr'], mi, 2026)[UTI_MDR[u]]['pd'], 'censo_mdr', alt
    if u in ENF_CENSO:
        return censo_adm.parse(sp['censo'], mi, 2026)['pd'].get(_norm(ENF_CENSO[u])), 'censo', alt
    return None, None, alt


def main():
    aplicar = '--aplicar' in sys.argv

    gc = gspread.service_account(filename=str(cfg.CREDS_PATH))
    rows = gc.open_by_key(SHEET_ID).worksheet(ABA).get_all_values()
    hdr, dados = rows[0], [r for r in rows[1:] if any(str(c).strip() for c in r)]
    col = {chave(h): j for j, h in enumerate(hdr)}
    def C(r, n):
        j = col.get(n)
        return r[j] if j is not None and j < len(r) else ''

    # Todas as deteccoes elegiveis, INCLUSIVE admissao: ela e necessaria para
    # saber qual foi a primeira deteccao da internacao.
    descartes = defaultdict(int)
    det = []   # (atendimento, data, clinica, eh_admissao, material)
    for r in dados:
        mr, cl = chave(C(r, 'MR')), chave(C(r, 'CLASSE'))
        if 'METALO/KPC' in cl:
            descartes['METALO/KPC? (duvida)'] += 1; continue
        if 'METALO' not in (mr, cl):
            continue
        org = chave(C(r, 'MICRORGANISMO'))
        if any(o in org for o in ORGS_FORA):
            descartes['organismo fica em pseu/acin'] += 1; continue
        at, d = str(C(r, 'ATENDIMENTO')).strip(), dia(C(r, 'DATA'))
        if not at or not d:
            descartes['sem atendimento ou data'] += 1; continue
        det.append((at, d, chave(C(r, 'CLINICA')),
                    chave(C(r, 'ROTINA OU ADMISSAO')) == 'ADMISSAO',
                    chave(C(r, 'MATERIAL'))))

    # primeira deteccao por internacao; empate no mesmo dia -> admissao primeiro
    primeiro = {}
    for at, d, cli, adm, mat in det:
        k_ = (d, 0 if adm else 1)
        if at not in primeiro or k_ < primeiro[at][0]:
            primeiro[at] = (k_, cli, adm, mat)

    serie = defaultdict(lambda: defaultdict(int))
    fora, set26 = defaultdict(int), []
    for at, ((d, _), cli, adm, mat) in primeiro.items():
        ano, mes, dd = d
        if adm:
            descartes['1a deteccao em swab de admissao (importado)'] += 1; continue
        if ano != 2026:
            continue
        u = CLINICA_UNIDADE.get(cli)
        if mes == 9:
            set26.append((dd, cli, u, mat))
        if mes > ATE_MES:
            continue
        if u:
            serie[u][mes] += 1
        else:
            fora[cli] += 1

    print(f'{len(det)} deteccoes elegiveis -> {len(primeiro)} internacoes')
    for k_, v in sorted(descartes.items()):
        print(f'  descartado: {k_}: {v}')
    print(f'  novo fora do mdrMensal (jan-ago): {dict(fora)}\n')

    d = json.load(open(JSON, encoding='utf-8'))
    mm = d.setdefault('mdrMensal', {})

    sp = make_providers(cfg.SHEET_IDS, str(cfg.CREDS_PATH))
    print('unidade            mes      n   pac-dia   densidade   [fonte do pac-dia]')
    plano, faltam = [], []
    for u in sorted(serie):
        pdser = {p.get('p'): p.get('v') for p in (mm.get(u) or {}).get('pd', [])}
        for mes in sorted(serie[u]):
            lab, n = f'{MESES[mes-1]}/26', serie[u][mes]
            pd, fonte, alt = pdser.get(lab), 'mdrMensal', None
            if not pd:
                pd, fonte, alt = denominador(sp, u, mes)
            if pd:
                v = round(n / pd * 1000, 2)
                cmp_ = ''
                if alt:
                    cmp_ = f'   (censo_isc {alt:.0f} -> {n/alt*1000:.2f})'
                print(f'  {u:<17} {lab:<7} {n:>3}   {pd:>7.0f}   {v:>8.2f}   [{fonte}]{cmp_}')
                plano.append((u, lab, n, pd, v, fonte))
            else:
                print(f'  {u:<17} {lab:<7} {n:>3}   {"—":>7}   {"—":>8}   <-- sem pac-dia')
                faltam.append((u, lab, n))

    print('\nset/26 pela mesma regra — conferir caso a caso com a grade diaria:')
    for dd, cli, u, mat in sorted(set26):
        print(f'   {dd:02d}/09  {cli:<7} -> {u or "(fora do painel)":<18} {mat}')

    if faltam:
        print('\nSem denominador de vigilancia:')
        for u, lab, n in faltam:
            print(f'   - {u} {lab}: {n} caso(s)')

    if not aplicar:
        print('\nDRY-RUN. Para gravar:  python3 backfill_ndm.py --aplicar')
        return
    if faltam:
        sys.exit('\nABORTADO: ha pontos sem pac-dia; resolver a fonte antes de gravar.')

    shutil.copy(JSON, JSON + '.bak')
    for u, lab, n, pd, v, fonte in plano:
        node = mm.setdefault(u, {})
        s = [p for p in node.get('ndm', []) if p.get('p') != lab]
        s.append({'p': lab, 'v': v, 'pd': pd, 'pdFonte': fonte})
        s.sort(key=lambda p: (int(p['p'].split('/')[1]), MESES.index(p['p'].split('/')[0])))
        node['ndm'] = s
        antigos = {p['p']: c for p, c in zip(node.get('ndm', []), (node.get('counts', {}).get('ndm') or []))}
        antigos[lab] = n
        node.setdefault('counts', {})['ndm'] = [antigos.get(p['p'], 0) for p in s]
    json.dump(d, open(JSON, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'\nGRAVADO em {JSON} ({len(plano)} pontos). Backup: {JSON}.bak')


if __name__ == '__main__':
    main()
