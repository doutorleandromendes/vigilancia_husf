"""
Parser: Competência da Visita Diária (vig_* no atb-sistema).

Substitui CINCO parsers de Google Sheets — censo_mdr, censo_isc, diarreia,
isolamentos e dots — por uma única chamada a:

    GET /vigilancia/api/competencia?inst=HUSF&mes=YYYY-MM&key=<VIG_API_KEY>

A API devolve a agregação crua (mesma função `compilar()` que alimenta a tela):
    cobertura: [{setor, nome, ordem, bloco, dias, pac_dia}]
    valores:   [{setor, item, bloco, rotulo, papel, unidade, ordem, n}]
    resumo:    {registros, retroativos, de, ate}

REGRA DO DENOMINADOR (diferente das planilhas): o pac-dia de um indicador soma
só os dias em que o BLOCO dele foi coletado. `cobertura` já vem quebrada por
setor × bloco justamente para isso. As planilhas dividiam pelo mês inteiro.
Em set/26 isso deu no mesmo (cobertura 26–30 dias de 30 em todo setor × bloco),
mas a regra importa em mês de cobertura parcial — ago/26, por exemplo, tem
19–25 dias e qualquer taxa calculada pelo mês inteiro sairia subestimada.

`papel` dos itens:
    incidente  → casos novos; viram densidade /1000 pac-dia
    prevalente → estoque diário (soma = paciente-dia); viram % ou DOT

ATENÇÃO: `isc_pos` está marcado como `incidente` no `vig_itens`, mas é coletado
como estoque diário (o paciente é marcado todo dia em que tem a ISC). A soma
mensal é portanto PACIENTE-DIA com ISC, não casos — e a taxa é prevalência
entre internados, não a taxa regulatória de ISC (casos / 100 cirurgias).
O `papel` da tabela deve ser corrigido para `prevalente`; até lá, não confie
nele para esse item.

As funções build_* devolvem exatamente o mesmo formato dos parsers antigos,
para que o core/merge.py NÃO precise mudar — exceto pelo acréscimo das duas
enfermarias ao `mdrMensal`, que exige dois pares de chave novos no loop do
merge.py.
"""
import json
import urllib.request

# ── setor (vig) -> chaves usadas no pipeline ──────────────────────────────────
# CM e CC entraram em set/26 (vigilância ativa de culturas, iniciada jul/26 nas
# duas enfermarias; o bloco mdr da grade diária só passou a cobri-las em
# setembro). Série nova, começa com um ponto.
SETOR_MDR  = {'uti_ab': 'ab', 'utic': 'uc', 'uti_neo': 'neo',
              'clinica_medica': 'cm', 'clinica_cirurgica': 'cc'}
SETOR_DIAR = {'clinica_medica': 'cm', 'clinica_cirurgica': 'cc', 'epm': 'epm',
              'uti_ab': 'utiab', 'utic': 'utic'}
SETOR_ISOL = {'clinica_medica': 'clinicaMedica', 'clinica_cirurgica': 'clinicaCirurgica',
              'epm': 'epm', 'apartamento': 'apartamento', 'uti_ab': 'utiAB',
              'utic': 'utic', 'uti_neo': 'utiNeo', 'pediatria': 'pediatria'}
SETOR_DOTS = {'uti_ab': 'utiab', 'utic': 'utic', 'clinica_medica': 'clin',
              'clinica_cirurgica': 'cir', 'apartamento': 'apto', 'epm': 'epm',
              'uti_neo': 'utineo'}

# ── população sob vigilância de ISC ───────────────────────────────────────────
# Decisão metodológica (08/10/2026): internação PS fica FORA — não é população
# cirúrgica. Maternidade fica DENTRO: cesárea é cirurgia.
#
# É uma LISTA DE INCLUSÃO de propósito. Com lista de exclusão, um setor novo
# que comece a coletar o bloco `isc` entraria no denominador sem ninguém
# perceber e derrubaria a taxa — foi exatamente esse o artefato que apareceu
# em set/26 quando o denominador passou de ~3000 para 3941 pac-dia.
# Setor com dado de ISC fora desta lista é reportado em `fora`, não absorvido.
#
# ALTERAR ESTA LISTA QUEBRA A SÉRIE. Se mudar, declare no painel.
ISC_SETORES = (
    'apartamento',
    'clinica_cirurgica',
    'clinica_medica',
    'epm',
    'maternidade',
    'pediatria',
    'uti_ab',
    'uti_neo',
    'utic',
)

# item (vig) -> chave de organismo do pipeline (usamos o INCIDENTE, '_novo')
MDR_ORG = {'mdr_esbl_novo': 'esbl', 'mdr_acin_novo': 'acin',
           'mdr_kpc_novo': 'kpc', 'mdr_pseu_novo': 'pseu'}

# ATB (prevalente: soma = paciente-dia em uso) -> chave DOT do pipeline.
# Cefepime (atb_cpm) não é exportado — paridade com o parser antigo.
DOT_ATB = {'atb_cro': 'cef', 'atb_ptz': 'pip', 'atb_mem': 'cbp',
           'atb_vte': 'gpp', 'atb_pmb': 'pb'}


def fetch(base_url, inst, mes, key=None, timeout=30):
    """mes no formato 'YYYY-MM'. Devolve o JSON cru da API."""
    url = (f'{base_url.rstrip("/")}/vigilancia/api/competencia'
           f'?inst={inst}&mes={mes}')
    if key:
        url += f'&key={key}'
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


# ── índices auxiliares ────────────────────────────────────────────────────────
def _pd_por_bloco(api):
    """{(setor, bloco): pac_dia} — denominador correto de cada bloco."""
    out = {}
    for c in api.get('cobertura', []):
        try:
            out[(c['setor'], c['bloco'])] = float(c['pac_dia'] or 0)
        except (TypeError, ValueError):
            out[(c['setor'], c['bloco'])] = 0.0
    return out


def _dias_por_bloco(api):
    return {(c['setor'], c['bloco']): int(c.get('dias') or 0)
            for c in api.get('cobertura', [])}


def _val(api):
    """{(setor, item): n}"""
    out = {}
    for v in api.get('valores', []):
        out[(v['setor'], v['item'])] = float(v['n'] or 0)
    return out


def _r2(x):
    return None if x is None else round(x, 2)


# ── censo_mdr ─────────────────────────────────────────────────────────────────
def build_censo_mdr(api):
    """Mesmo formato de parsers/censo_mdr.py: {'ab','uc','neo','cm','cc'} com pd,
    <org>_n (casos novos) e <org>_r (densidade /1000 pac-dia).

    'cm' e 'cc' são as enfermarias (série nova, set/26+). O merge.py só as
    consome se os pares de chave estiverem no loop do mdrMensal; o mdrInst
    continua somando ('ab','uc','neo') e NÃO deve absorvê-las — mudaria o
    denominador de uma série publicada no meio dela.
    """
    pd_, val = _pd_por_bloco(api), _val(api)
    out = {'fonte': 'vig_mdr', 'mes': None}
    for setor, key in SETOR_MDR.items():
        pd = pd_.get((setor, 'mdr'), 0.0)
        if not pd and not any(val.get((setor, i)) for i in MDR_ORG):
            # Setor sem bloco mdr coletado: omite a chave em vez de criar zeros.
            # Zero e "não coletado" são coisas diferentes e o painel precisa
            # distinguir — ver ago/26, em que só as 3 UTIs tinham o bloco.
            continue
        u = {'pd': pd}
        for item, org in MDR_ORG.items():
            n = val.get((setor, item), 0.0)
            u[f'{org}_n'] = n
            u[f'{org}_r'] = round(n / pd * 1000, 2) if pd else 0.0
        out[key] = u
    return out


# ── censo_isc ─────────────────────────────────────────────────────────────────
def build_censo_isc(api):
    """{'isc': {n, pd, taxa}, 'fora': [...]} — ISC somada SÓ nos setores de
    ISC_SETORES, numerador e denominador na mesma população.

    n   = paciente-dia com ISC (ver nota sobre `papel` no topo do módulo)
    pd  = pac-dia dos dias com coleta do bloco isc, nos mesmos setores
    taxa = n/pd*100 → prevalência de ISC entre internados

    `fora` lista setor com dado de ISC que não está em ISC_SETORES. Não é
    erro — é o aviso de que a população sob vigilância mudou e a decisão
    precisa ser revisada. Quem chama deve imprimir isso.
    """
    pd_, val = _pd_por_bloco(api), _val(api)
    incl = set(ISC_SETORES)

    n = sum(v for (s, i), v in val.items() if i == 'isc_pos' and s in incl)
    pd = sum(v for (s, b), v in pd_.items() if b == 'isc' and s in incl)

    fora = sorted({s for (s, b) in pd_ if b == 'isc' and s not in incl}
                  | {s for (s, i) in val if i == 'isc_pos' and s not in incl})

    return {'fonte': 'vig_isc', 'mes': None,
            'isc': {'n': round(n), 'pd': round(pd),
                    'taxa': round(n / pd * 100, 2) if pd else 0.0},
            'fora': fora}


# ── diarreia ──────────────────────────────────────────────────────────────────
def build_diarreia(api):
    """{'diarreia': {cm, cc, epm, utiab, utic}} — densidade /1000 pac-dia dos
    casos NOVOS (as planilhas já traziam a taxa pronta)."""
    pd_, val = _pd_por_bloco(api), _val(api)
    d = {}
    for setor, key in SETOR_DIAR.items():
        pd = pd_.get((setor, 'diarreia'), 0.0)
        n = val.get((setor, 'diarreia_novo'), 0.0)
        d[key] = _r2(n / pd * 1000) if pd else None
    return {'fonte': 'vig_diarreia', 'mes': None, 'diarreia': d}


# ── isolamentos ───────────────────────────────────────────────────────────────
# novos_*      -> contagem de casos novos (incidente)
# confirmados_* -> paciente-dia confirmado (prevalente) e seu % sobre o pac-dia
_ISO_NOVO_PC  = ('iso_pc_mdr_novo', 'iso_pc_out_novo')
_ISO_NOVO_ALL = _ISO_NOVO_PC + ('iso_got_novo', 'iso_aero_novo', 'iso_srag_novo')
_ISO_CONF_PC  = ('iso_pc_mdr_conf', 'iso_pc_out_conf')
_ISO_CONF_ALL = _ISO_CONF_PC + ('iso_got_conf', 'iso_aero_conf', 'iso_srag_conf')


def build_isolamentos(api):
    """{metric: {ward: {n, pct}}} — mesmo formato de parsers/isolamentos.py."""
    pd_, val = _pd_por_bloco(api), _val(api)
    res = {m: {} for m in ('confirmados_total', 'confirmados_pc',
                           'novos_total', 'novos_pc')}
    for setor, ward in SETOR_ISOL.items():
        pd = pd_.get((setor, 'isolamento'), 0.0)

        def soma(itens):
            return sum(val.get((setor, i), 0.0) for i in itens)

        for metric, itens, is_conf in (
            ('novos_total',       _ISO_NOVO_ALL, False),
            ('novos_pc',          _ISO_NOVO_PC,  False),
            ('confirmados_total', _ISO_CONF_ALL, True),
            ('confirmados_pc',    _ISO_CONF_PC,  True),
        ):
            n = soma(itens)
            pct = _r2(n / pd * 100) if (is_conf and pd) else None
            if n or pct is not None:
                res[metric][ward] = {'n': int(round(n)), 'pct': pct}
    return res


# ── dots ──────────────────────────────────────────────────────────────────────
def build_dots(api):
    """{'dots': {cef:{utiab,...,utineo}, ...}} — DOT /1000 pac-dia.
    Os itens de ATB são prevalentes: a soma é paciente-dia em uso."""
    pd_, val = _pd_por_bloco(api), _val(api)
    dots = {}
    for item, key in DOT_ATB.items():
        unit = {}
        algum = False
        for setor, ukey in SETOR_DOTS.items():
            pd = pd_.get((setor, 'atb'), 0.0)
            n = val.get((setor, item))
            if pd and n is not None:
                unit[ukey] = _r2(n / pd * 1000)
                algum = True
            else:
                unit[ukey] = None
        dots[key] = unit if algum else None
    return {'fonte': 'vig_dots', 'mes': None, 'dots': dots}


# ── conveniência: tudo de uma vez ─────────────────────────────────────────────
def build_all(api):
    """Devolve os cinco resultados já no formato que o build_month espera."""
    return {
        'censo_mdr':   build_censo_mdr(api),
        'censo_isc':   build_censo_isc(api),
        'diarreia':    build_diarreia(api),
        'isolamentos': build_isolamentos(api),
        'dots':        build_dots(api),
    }


def cobertura_resumo(api):
    """Resumo de cobertura para o relatório: dias coletados por bloco."""
    dias = _dias_por_bloco(api)
    blocos = {}
    for (setor, bloco), d in dias.items():
        blocos.setdefault(bloco, []).append(d)
    return {b: {'setores': len(v), 'dias_min': min(v), 'dias_max': max(v)}
            for b, v in sorted(blocos.items())}
