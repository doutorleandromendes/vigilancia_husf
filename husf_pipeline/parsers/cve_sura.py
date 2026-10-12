"""
cve_sura.py — consome /atb/api/cve-numeradores e mapeia para os numeradores do CVE
(Plan2/Plan3 PN/IPCS/IU, Plan1/Plan1B ISC) e do CVE de diálise (HD ILAV/Bact por acesso).

Os dicionários marcados com  # ◀ CONFERIR  dependem da nomenclatura do SURA do HUSF.
"""
import json, unicodedata, urllib.request

# iras (SURA) -> campo do CVE
PN        = {'PAV','PAV/EVA'}
IPCS_LAB  = {'IPCSLab'}
IPCS_CLIN = {'IPCSClin'}
ITU       = {'ITU'}

# setor (SURA, tenant HUSF) -> unidade do Plan2                      # ◀ CONFERIR
SETOR_PLAN2 = {'UTI': 'uti1', 'UTI C': 'uti2', 'UTI Neo / Infantil': 'utipe'}
SETOR_NEO   = 'UTI Neo / Infantil'   # neonato=true → Plan3 por faixa

# código anotado no campo Etiol p/ ISC (ex. 'CNEURO') -> código Plan1  # ◀ CONFERIR
ETIOL_PLAN1 = {
    'cneuro':'NEUCI', 'cnc':'NEUCI',
    'ccard':'CCARD', 'ccardio':'CCARD',
    'cgeral':'CGERA', 'cger':'CGERA', 'cg':'CGERA',
    'cped':'CIRPE', 'cpediatrica':'CIRPE', 'ccipe':'CIRPE',
    'cvasc':'CIVAS', 'cvascular':'CIVAS',
    'gasci':'GASCI',
    'gineco':'GINEC', 'go':'GINEC', 'cginec':'GINEC',
    'corto':'ORTOP', 'ortopedia':'ORTOP',
    'cplast':'PLAST', 'cplastica':'PLAST',
    'ctorax':'TORAX',
    'curo':'UROCI', 'urologia':'UROCI',
}

# equipe responsável (SURA) -> código de especialidade do Plan1 (fallback)  # ◀ CONFERIR
EQUIPE_PLAN1 = {
    'cardiologia':'CCARD', 'cirurgia cardiaca':'CCARD',
    'cirurgia geral':'CGERA', 'clinica cirurgica':'CGERA',
    'cirurgia pediatrica':'CIRPE', 'pediatria cirurgica':'CIRPE',
    'cirurgia vascular':'CIVAS', 'vascular':'CIVAS',
    'gastro':'GASCI', 'gastrocirurgia':'GASCI',
    'ginecologia':'GINEC', 'ginecologia/obstetricia':'GINEC', 'go':'GINEC', 'obstetricia':'GINEC',
    'neurocirurgia':'NEUCI', 'neuro':'NEUCI',
    'ortopedia':'ORTOP',
    'cirurgia plastica':'PLAST', 'plastica':'PLAST',
    'toracica':'TORAX', 'cirurgia toracica':'TORAX',
    'urologia':'UROCI', 'uro':'UROCI',
}

# palavra-chave no texto livre `cirurgia` -> categoria do Plan1B     # ◀ CONFERIR
CIRURGIA_PLAN1B = [
    ('apendicect', 'Apendicectomia laparoscópica'),
    ('joelho', 'Artroplastia de joelho'),
    ('quadril', 'Artroplastia total de quadril'),
    ('colectomia', 'Colectomia laparoscópica'),
    ('colecist', 'Colecistectomia laparoscópica'),
    ('craniotomia', 'Craniotomia'),
    ('deriv', 'Derivação ventricular interna'),
    ('herni', 'Herniorrafia/hernioplastia laparoscópica'),
    ('histerect', 'Histerectomia laparoscópica'),
    ('mastect', 'Mastectomia'),
    ('mamoplast', 'Mamoplastia com implante mamário'),
    ('cesar', 'Parto cesariano'),
    ('revascular', 'Revascularização do miocárdio'),
]

def _n(s):
    if s is None: return ''
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode().lower()
    return ' '.join(s.split())

# ── Hemodiálise: classes IRAS do SURA -> colunas do CVE de diálise ─────────────
# acesso: CDL (cateter duplo lúmen) = temporário · PC = permanente · FAV = fístula
HD_ILAV = {'HD_ILAV_CDL':'temp', 'HD_ILAV_PC':'perm', 'HD_ILAV_FAV':'fist'}
HD_BACT = {'HD_Bact_CDL':'temp', 'HD_Bact_PC':'perm', 'HD_Bact_FAV':'fist'}
HD_GENERIC = {'(HD)ILAV', '(HD)ICS', '(HD)Bact'}   # sem acesso especificado → revisão

def map_hd(sura):
    """iras_por_setor do SURA -> numeradores HD por mês:
       {mes: {'ilav':{temp,perm,fist}, 'bact':{temp,perm,fist}, 'pendente':[...]}}"""
    out = {}
    def slot(m):
        return out.setdefault(m, {'ilav':{'temp':0,'perm':0,'fist':0},
                                  'bact':{'temp':0,'perm':0,'fist':0}, 'pendente':[]})
    for row in sura.get('iras_por_setor', []):
        iras = row.get('iras'); n = int(row['n']); m = int(row['mes'])
        if iras in HD_ILAV:   slot(m)['ilav'][HD_ILAV[iras]] += n
        elif iras in HD_BACT: slot(m)['bact'][HD_BACT[iras]] += n
        elif iras in HD_GENERIC:
            slot(m)['pendente'].append({'iras':iras, 'setor':row.get('setor'), 'n':n})
    return out

def fetch_sura(base_url, inst, ano, mes, key=None, timeout=20):
    url = f'{base_url.rstrip("/")}/atb/api/cve-numeradores?inst={inst}&ano={ano}&mes={mes}'
    if key: url += f'&key={key}'
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def map_numeradores(sura):
    """JSON do endpoint -> numeradores estruturados por competência-mês."""
    out = {}
    def slot(m):
        return out.setdefault(m, {
            'plan2': {u: {'pn':0,'ipcs':0,'iu':0} for u in ('uti1','uti2','utipe')},
            'plan3': {b: {'pn':0,'ipcs_lab':0,'ipcs_clin':0} for b in 'ABCDE'},
            'plan1': {}, 'plan1b': {}, 'plan1_pendente': [],
        })
    for row in sura.get('iras_por_setor', []):
        m = int(row['mes']); setor = row['setor']; iras = row['iras']; n = int(row['n'])
        neonato = bool(row.get('neonato')); faixa = row.get('faixa_peso')
        s = slot(m)
        if setor == SETOR_NEO and neonato and faixa in s['plan3']:
            if iras in PN:          s['plan3'][faixa]['pn']        += n
            elif iras in IPCS_LAB:  s['plan3'][faixa]['ipcs_lab']  += n
            elif iras in IPCS_CLIN: s['plan3'][faixa]['ipcs_clin'] += n
        else:
            u = SETOR_PLAN2.get(setor)
            if u:
                if setor == SETOR_NEO and not neonato: u = 'utipe'
                if iras in PN:         s['plan2'][u]['pn']   += n
                elif iras in IPCS_LAB: s['plan2'][u]['ipcs'] += n
                elif iras in ITU:      s['plan2'][u]['iu']   += n
    for row in sura.get('isc_por_equipe', []):
        m = int(row['mes']); n = int(row['n']); s = slot(m)
        cod = ETIOL_PLAN1.get(_n(row.get('etiol'))) or EQUIPE_PLAN1.get(_n(row.get('equipe')))
        if cod:
            s['plan1'][cod] = s['plan1'].get(cod, 0) + n
        else:
            s['plan1_pendente'].append({'etiol':row.get('etiol'),'equipe':row.get('equipe'),
                                        'cirurgia':row.get('cirurgia'),'n':n})
        cn = _n(row.get('cirurgia'))
        for kw, cat in CIRURGIA_PLAN1B:
            if kw in cn:
                d = s['plan1b'].setdefault(cat, {'incisional':0,'cavidade':0})
                d['incisional'] += n
                break
    return out


# ── Enfermarias (CM/CC/EPM) para os campos manuais do build_month ──────────────
# setor (SURA) -> chave da enfermaria no YAML                        # ◀ CONFERIR
SETOR_ENFERMARIA = {'Clínica Médica': 'clinicaMedica',
                    'Clínica Cirúrgica': 'clinicaCirurgica',
                    'EPM': 'epm'}
# iras (SURA) -> topografia da enfermaria (ac = IPCS/corrente)
IRAS_ENF = {'IPCSLab': 'ac', 'IPCSClin': 'ac', 'ITU': 'itu',
            'PAV': 'pneu', 'PAV/EVA': 'pneu', 'ISC': 'isc'}

def map_enfermarias(sura):
    """iras_por_setor do SURA -> {mes: {ward: {ac,itu,pneu,isc}}}. pd vem do Censo (à parte)."""
    out = {}
    for row in sura.get('iras_por_setor', []):
        ward = SETOR_ENFERMARIA.get(row.get('setor'))
        topo = IRAS_ENF.get(row.get('iras'))
        if not ward or not topo:
            continue
        m = int(row['mes']); n = int(row['n'])
        w = out.setdefault(m, {}).setdefault(ward, {'ac':0,'itu':0,'pneu':0,'isc':0})
        w[topo] += n
    return out
