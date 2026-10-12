"""
manual_auto.py — monta os campos "manuais" do build_month que já existem nas fontes.

build(out, ano, mes_idx) -> dict pronto p/ mesclar no `manual`:
  clinicaMedica / clinicaCirurgica / epm : {ac,itu,pneu,isc,pd}
      numeradores ← SURA (map_enfermarias) · pd ← Censo
  global_taxaIH : (Σ IrAS confirmadas, exceto HD e PS) / (Σ pac-dia dos setores
      vigiados no Censo) × 100

SURA por HTTP (env CVE_SURA_URL / CVE_API_KEY / CVE_INST) — ou passe sura_json p/ teste.
"""
import os
from husf_pipeline.parsers import cve_sura
from husf_pipeline.parsers._util import norm
from husf_pipeline.parsers.censo import WARD_CENSO
from husf_pipeline.core import status as _status

ABBR = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
# unidades que usam a endemicidade SIMPLES (UTIs/HD têm análise própria)
STATUS_SIMPLES = ('global', 'clinicaMedica', 'clinicaCirurgica', 'epm')

# Setores VIGIADOS p/ o denominador da Taxa IH Global (nomes do Censo, normalizados).
# Exclui PS ('INTERNAÇÃO P.S.'), Hemodiálise, Psiquiatria, Hospital Dia, Ambulatório.
VIGIADOS_CENSO = [norm(s) for s in (
    'Apartamento', 'Baixo Risco-Neo', 'Clinica Cirurgica', 'Clinica Medica',
    'Clinica Obstetrica', 'Clinica Pediatrica', 'Cuidados Intermediarios-Neo',
    'Enfermaria Particular Mista', 'UTI Adulto A SUS', 'UTI Adulto B SUS',
    'UTI Adulto C', 'UTI Infantil', 'UTI Neonatal')]

# Setores do SURA excluídos do numerador da Taxa IH Global.
SURA_EXCLUI_TAXA = {'Hemodiálise', 'PS'}


def _fetch(ano, mes_idx):
    url  = os.environ.get('CVE_SURA_URL', 'https://app.lcmendes.med.br')
    key  = os.environ.get('CVE_API_KEY')
    inst = os.environ.get('CVE_INST', 'HUSF')
    return cve_sura.fetch_sura(url, inst, ano, mes_idx + 1, key)


def build(out, ano, mes_idx, prev_json=None, sura_json=None):
    if sura_json is None:
        sura_json = _fetch(ano, mes_idx)
    m = mes_idx + 1
    pd = (out.get('censo') or {}).get('pd', {})
    auto = {}

    # Enfermarias: numeradores (SURA) + pd (Censo)
    # Enfermarias: numeradores (SURA) + pd (Censo).
    # Ausência de IrAS no SURA ≠ pendente: se o setor tem pac-dia no Censo, é 0 infecção.
    enf = cve_sura.map_enfermarias(sura_json).get(m, {})
    for w, censo_nome in WARD_CENSO.items():
        pd_w = pd.get(norm(censo_nome))
        if pd_w is None:
            continue   # sem pac-dia no Censo → setor não vigiado neste mês
        topos = enf.get(w, {'ac': 0, 'itu': 0, 'pneu': 0, 'isc': 0})
        auto[w] = {**topos, 'pd': pd_w}

    # Taxa IH Global
    num = sum(int(r['n']) for r in sura_json.get('iras_por_setor', [])
              if int(r['mes']) == m and r.get('setor') not in SURA_EXCLUI_TAXA)
    den = sum(pd.get(s) or 0 for s in VIGIADOS_CENSO)
    if den:
        auto['global_taxaIH'] = round(num / den * 100, 2)

    # SURA (adesão ao parecer) — bloco 'adesao' do endpoint
    ad = next((r for r in sura_json.get('adesao', []) if int(r['mes']) == m), None)
    if ad:
        auto['sura'] = {k: ad.get(k, 0) for k in
                        ('sol', 'neg', 'mantido', 'semAtb', 'troca', 'alta', 'obito')}

    # Status epidemiológico SIMPLES (canal + tendência) — global + enfermarias
    if prev_json is not None:
        suf = f"/{ano % 100:02d}"
        label = f"{ABBR[mes_idx]}{suf}"
        # valor corrente de taxaIH por unidade
        cur = {'global': auto.get('global_taxaIH')}
        for w in ('clinicaMedica', 'clinicaCirurgica', 'epm'):
            blk = auto.get(w)
            if blk and blk.get('pd'):
                tot = (blk['ac'] or 0) + (blk['itu'] or 0) + (blk['pneu'] or 0) + (blk['isc'] or 0)
                cur[w] = round(tot / blk['pd'] * 100, 2)
        for unit in STATUS_SIMPLES:
            v = cur.get(unit)
            if v is None:
                continue
            hist = (prev_json.get(unit) or {}).get('taxaIH', []) or []
            serie = list(hist) + [{'p': label, 'v': v}]
            auto[f'status_{unit}'] = _status.classify(serie)
            auto[f'statusTrend_{unit}'] = _status.trend(serie, suf)

    return auto
