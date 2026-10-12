"""
cve_controles.py — parsers da Planilha Geral de Controles para preenchimento do CVE-SP.

Fontes → alvos (100% reconciliados contra o CVE manual, jan–mai):
  Dados UTI          → Plan2 device-days (UTI-1/UTI-2/UTIPE), Plan3 Neo (faixas A–E)
  Cirurgias limpas   → Plan1 col C (CL), Plan1B col D (total cirurgias)
  Checklist CVC      → Plan2 processo J/K/L (UTI-1←'Total UTI ADULTO'; UTI-2←'UTI Adulto C')
  Consumo mensal ATB → Plan6 col C (nº unidades UTIA = UTI A+B + UTI C)
  Dados UTI (texto)  → Plan4 ml álcool/sabonete (frascos × 500)
"""
import re, unicodedata

MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
         'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
FRASCO_ML = 500
CODE_ALIAS = {'cgeral': 'cgera'}   # Cirurgias limpas usa CGERAL; CVE usa CGERA

def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def norm(s):
    if s is None: return ''
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    s = s.replace('/', ' ').replace('.', ' ').replace(',', '.')
    return ' '.join(s.split())

def gkey(g):
    """Chave de nome genérico p/ Plan6 (base ampicilina/sulbactam colapsam)."""
    k = norm(g)
    if 'ampicilina-sulbactam' in k:
        k = k.replace('base ampicilina', '').replace('base sulbactam', '').strip()
    return k

# ── Dados UTI: denominadores de dispositivo (Plan2/Plan3) ──────────────────────

def dados_uti(S, mi):
    dU = S['Dados UTI']
    def g(col, row): return num(dU[f'{col}{row}'].value)
    r_ad, r_c, r_neo = 5+mi, 36+mi, 21+mi
    out = {}
    out['uti1']  = dict(vm=g('I',r_ad), ct=g('H',r_ad), sv=g('G',r_ad), pd=g('F',r_ad))
    out['uti2']  = dict(vm=g('E',r_c),  ct=g('D',r_c),  sv=g('C',r_c),  pd=g('B',r_c))
    out['utipe'] = dict(vm=g('T',r_ad), ct=g('S',r_ad), sv=g('R',r_ad), pd=g('Q',r_ad))
    bands = {'A':('B','C','D'),'B':('E','F','G'),'C':('H','I','J'),
             'D':('K','L','M'),'E':('N','O','P')}
    out['neo'] = {b: dict(pd=g(pc,r_neo), ct=g(cc,r_neo), vm=g(vc,r_neo))
                  for b,(pc,cc,vc) in bands.items()}
    return out

# ── Cirurgias limpas: denominadores cirúrgicos (Plan1/Plan1B) ──────────────────

def cirurgias(S, mes):
    cl = S['Cirurgias limpas']
    hdr = next((r for r in range(1, cl.max_row+1)
                if isinstance(cl.cell(row=r, column=4).value, str)
                and cl.cell(row=r, column=4).value.strip().upper() == mes.upper()), None)
    if hdr is None: return {}, {}
    left, right = {}, {}
    r = hdr+1
    while r < cl.max_row and not (isinstance(cl.cell(row=r,column=1).value, str)
                                  and 'ANO:' in str(cl.cell(row=r,column=1).value)):
        a, b = cl.cell(row=r,column=1).value, cl.cell(row=r,column=2).value
        d, e = cl.cell(row=r,column=4).value, cl.cell(row=r,column=5).value
        if isinstance(a,str) and num(b) is not None and a.strip().lower() not in ('especialidade cirúrgica','total'):
            k = norm(a); left[CODE_ALIAS.get(k, k)] = num(b)
        if isinstance(d,str) and num(e) is not None and d.strip().lower() not in ('especialidade cirúrgica','total'):
            right[norm(d)] = num(e)
        r += 1
        if r > hdr+45: break
    return left, right

# ── Consumo mensal ATB: nº unidades UTIA para Plan6 ────────────────────────────

def consumo_atb(S, mes):
    atb = S['Consumo mensal ATB']
    up = mes.upper()
    hdr = next((r for r in range(1, atb.max_row+1)
                if isinstance(atb.cell(row=r, column=3).value, str)
                and 'MÊS DE REFER' in atb.cell(row=r, column=3).value.upper()
                and up in atb.cell(row=r, column=3).value.upper()), None)
    if hdr is None: return {}
    d = {}
    r = hdr+3
    while r < atb.max_row:
        a = atb.cell(row=r, column=1).value
        if isinstance(a,str) and 'ANO DE REFER' in a.upper(): break
        if isinstance(a,str) and a.strip() and a.strip().upper() != 'ANTIMICROBIANO POR NOME GENÉRICO':
            n = num(atb.cell(row=r, column=14).value) or 0   # N = UTI ADULTO A e B
            o = num(atb.cell(row=r, column=15).value) or 0   # O = UTI ADULTO C
            d[(gkey(a), norm(atb.cell(row=r, column=2).value))] = n + o
        r += 1
        if r > hdr+90: break
    return d

# ── Checklist CVC: processo J/K/L (Plan2) ──────────────────────────────────────

def checklist_cvc(S, mes):
    cc = S['Checklist CVC']
    hdr = None
    for r in range(1, cc.max_row+1):
        a, b = cc.cell(row=r, column=1).value, cc.cell(row=r, column=2).value
        if isinstance(a,str) and 'ANO' in a.upper() and isinstance(b,str) and b.strip().lower() == mes.lower():
            hdr = r; break
    if hdr is None: return {}
    def por_rotulo(alvo):
        for r in range(hdr, hdr+95):
            for col in (1, 2):
                v = cc.cell(row=r, column=col).value
                if isinstance(v,str) and v.strip().lower() == alvo.lower():
                    return [num(cc.cell(row=r, column=x).value) for x in (3,4,5)]
        return None
    def subtotal_apos(setor):
        start = next((r for r in range(hdr, hdr+95)
                      if isinstance(cc.cell(row=r,column=1).value, str)
                      and cc.cell(row=r,column=1).value.strip().lower() == setor.lower()), None)
        if start is None: return None
        for r in range(start+1, start+15):
            a, b = cc.cell(row=r,column=1).value, cc.cell(row=r,column=2).value
            if (a in (None,'')) and (b in (None,'')) and num(cc.cell(row=r,column=3).value) is not None:
                return [num(cc.cell(row=r, column=x).value) for x in (3,4,5)]
        return None
    return {'uti1': por_rotulo('Total UTI ADULTO'), 'uti2': subtotal_apos('UTI Adulto C')}

# ── Dados UTI (texto livre): álcool/sabonete em ml (Plan4) ─────────────────────

def alcool_sabonete(S, mi):
    dU = S['Dados UTI']
    b = str(dU.cell(row=5+mi, column=2).value or '')
    c = str(dU.cell(row=5+mi, column=3).value or '')
    def x500(v): return v*FRASCO_ML if v else None
    alc, _, sab = b.partition('Sabonete')
    m = re.search(r'A e B:\s*(\d+)\s*\+\s*(\d+)', alc); ad_alc = (int(m.group(1))+int(m.group(2))) if m else None
    m = re.search(r'A e B:\s*(\d+)', sab);              ad_sab = int(m.group(1)) if m else None
    alcp, _, sabp = c.partition('Sabonete')
    m = re.search(r'NEO\s*:?\s*(\d+)\s*\+\s*(\d+)', alcp); neo = (int(m.group(1))+int(m.group(2))) if m else None
    m = re.search(r'Ped\s*:?\s*(\d+)\s*\+\s*(\d+)', alcp); ped = (int(m.group(1))+int(m.group(2))) if m else None
    m = re.search(r'Neo\s*:?\s*(\d+)', sabp);              sneo = int(m.group(1)) if m else None
    m = re.search(r'Ped\s*:?\s*(\d+)', sabp);              sped = int(m.group(1)) if m else None
    return {'ad_alc':x500(ad_alc), 'ad_sab':x500(ad_sab),
            'ped_alc':x500(ped), 'ped_sab':x500(sped),
            'neo_alc':x500(neo), 'neo_sab':x500(sneo)}
