#!/usr/bin/env python3
"""
HUSF - Script de atualização automática
Chamado pelo GitHub Actions (vigilancia.yml)
Busca SE mais recente do InfoGripe, calcula VPNs e gera index.html
"""

import requests
import re
import os
from datetime import datetime
from io import BytesIO
import pdfplumber


# ── Configuração ──────────────────────────────────────────────────────────────

SENSIBILIDADES = {
    "COVID19":     0.70,   # Arshadi et al. 2022 (60 estudos)
    "INFLUENZA_A": 0.62,   # Chartrand et al. 2012 (159 estudos)
    "INFLUENZA_B": 0.58,   # Chartrand et al. 2012 (159 estudos)
    "VSR":         0.75,   # literatura disponível
    "RINOVIRUS":   0.50,   # estimativa conservadora
    "OUTROS":      0.65,
}
ESPECIFICIDADE = 0.98
LIMIAR_LIBERAR = 0.95   # VPN >= 95% -> LIBERAR
LIMIAR_CAUTELA = 0.90   # VPN >= 90% -> CAUTELA

BASE_URL = "https://agencia.fiocruz.br/sites/agencia.fiocruz.br/files/"

PATOGENOS = [
    ("COVID19",     "COVID-19"),
    ("INFLUENZA_A", "Influenza A"),
    ("INFLUENZA_B", "Influenza B"),
    ("VSR",         "VSR"),
    ("RINOVIRUS",   "Rinovírus"),
    ("OUTROS",      "Outros"),
]

# ── Funções ───────────────────────────────────────────────────────────────────

def se_teorica_atual():
    hoje = datetime.now()
    inicio_2026 = datetime(2026, 1, 5)
    dias = (hoje - inicio_2026).days
    return min(52, max(1, dias // 7 + 1))


def se_atual_no_site():
    """Lê a SE que está no index.html atual, retorna 0 se não existir."""
    if not os.path.exists("index.html"):
        return 0
    try:
        with open("index.html", encoding="utf-8") as f:
            html = f.read()
        match = re.search(r"SE\s+(\d+)/2026", html)
        return int(match.group(1)) if match else 0
    except Exception:
        return 0


def buscar_se_mais_recente():
    """Retorna (numero_se, url_pdf) da SE mais recente disponível."""
    se_max = int(se_teorica_atual())
    for se in range(se_max, max(1, se_max - 12), -1):
        for url in [
            f"{BASE_URL}Resumo_InfoGripe_2026_{se:02d}.pdf",
            f"{BASE_URL}Resumo_InfoGripe_2026_{se:02d}_0.pdf",
        ]:
            try:
                r = requests.head(url, timeout=10)
                if r.status_code == 200:
                    size = int(r.headers.get("content-length", 0))
                    if size > 50000:
                        print(f"SE {se} encontrada: {url}")
                        return se, url
            except Exception:
                continue
    return 0, ""


def extrair_prevalencias(pdf_bytes):
    """Extrai prevalências do PDF. Retorna dict com valores padrão se falhar."""
    defaults = {
        "COVID19":     0.03,
        "INFLUENZA_A": 0.25,
        "INFLUENZA_B": 0.05,
        "VSR":         0.40,
        "RINOVIRUS":   0.25,
        "OUTROS":      0.02,
    }
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            texto = "\n".join(
                p.extract_text() or "" for p in pdf.pages
            )

        linhas = texto.split("\n")
        for i, linha in enumerate(linhas):
            if "4 ltimas semanas" in linha.lower() or "4 últimas semanas" in linha.lower():
                bloco = " ".join(linhas[i: i + 15])
                padroes = {
                    "INFLUENZA_A": r"influenza\s+a[^0-9]*?(\d+[,.]?\d*)\s*%",
                    "INFLUENZA_B": r"influenza\s+b[^0-9]*?(\d+[,.]?\d*)\s*%",
                    "VSR":         r"sincicial[^0-9]*?(\d+[,.]?\d*)\s*%",
                    "RINOVIRUS":   r"rinov[^0-9]*?(\d+[,.]?\d*)\s*%",
                    "COVID19":     r"covid[^0-9]*?(\d+[,.]?\d*)\s*%",
                }
                for pat_name, pattern in padroes.items():
                    m = re.search(pattern, bloco, re.IGNORECASE)
                    if m:
                        val = float(m.group(1).replace(",", ".")) / 100
                        defaults[pat_name] = val
                        print(f"  {pat_name}: {val:.1%}")
                break
    except Exception as e:
        print(f"Aviso: extração de dados falhou ({e}), usando defaults")
    return defaults


def calcular_vpn(prev, sens):
    num = ESPECIFICIDADE * (1 - prev)
    den = (1 - sens) * prev + ESPECIFICIDADE * (1 - prev)
    return num / den if den > 0 else 0


def gerar_card(patogeno, nome, vpn, prev):
    if vpn >= LIMIAR_LIBERAR:
        card_class, vpn_class, ori_class = "liberar", "vpn-verde", "orientacao-verde"
        icone = "fas fa-check-circle"
        orientacao = "LIBERAR ISOLAMENTO COM ANTÍGENO NEGATIVO"
    elif vpn >= LIMIAR_CAUTELA:
        card_class, vpn_class, ori_class = "cautela", "vpn-amarelo", "orientacao-amarelo"
        icone = "fas fa-exclamation-triangle"
        orientacao = "CAUTELA - AVALIAR CLINICAMENTE"
    else:
        card_class, vpn_class, ori_class = "rtpcr", "vpn-vermelho", "orientacao-vermelho"
        icone = "fas fa-times-circle"
        orientacao = "RT-PCR RECOMENDADO"

    return f"""
        <div class="card-patogeno {card_class}">
            <div class="patogeno-header">
                <div class="patogeno-nome">{nome}</div>
                <div class="vpn-badge {vpn_class}">VPN {vpn:.0%}</div>
            </div>
            <div class="orientacao {ori_class}">
                <i class="{icone}"></i> {orientacao}
            </div>
            <div class="prevalencia-info">Positividade regional: {prev:.1%}</div>
        </div>"""


def gerar_html(se_num, prevalencias, vpns, timestamp):
    cards = "".join(
        gerar_card(p, n, vpns[p], prevalencias.get(p, 0))
        for p, n in PATOGENOS
        if p in vpns
    )

    badges_positividade = "".join(
        f'<span class="badge-pathogen">{nome}: {prevalencias.get(p, 0):.1%}</span>'
        for p, nome in PATOGENOS
    )

    css = """
    body{font-family:system-ui,-apple-system,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);padding:10px;margin:0;min-height:100vh}
    .card-patogeno{background:#fff;margin:8px 0;border-radius:12px;padding:15px;box-shadow:0 3px 15px rgba(0,0,0,.2);border-left:5px solid #ddd}
    .liberar{border-left-color:#28a745}.cautela{border-left-color:#ffc107}.rtpcr{border-left-color:#dc3545}
    .patogeno-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
    .patogeno-nome{font-weight:700;font-size:1.1rem;color:#2c3e50}
    .vpn-badge{padding:6px 12px;border-radius:20px;font-weight:700;color:#fff;font-size:.9rem}
    .vpn-verde{background:#28a745}.vpn-amarelo{background:#ffc107;color:#000}.vpn-vermelho{background:#dc3545}
    .orientacao{font-weight:600;font-size:.85rem;margin-bottom:4px}
    .orientacao-verde{color:#28a745}.orientacao-amarelo{color:#d39e00}.orientacao-vermelho{color:#dc3545}
    .prevalencia-info{font-size:.75rem;color:#6c757d;margin-top:4px}
    .header-automatico{background:linear-gradient(135deg,#2c3e50,#34495e);color:#fff;padding:20px;border-radius:15px;text-align:center;margin-bottom:15px;box-shadow:0 4px 20px rgba(0,0,0,.3)}
    .criterio-box{background:#fff;border-radius:10px;padding:12px 15px;margin:10px 0;font-size:.8rem}
    .criterio-item{display:flex;align-items:center;margin:4px 0}
    .dot{width:12px;height:12px;border-radius:50%;margin-right:8px;flex-shrink:0}
    .collapsible-section{background:#fff;border-radius:10px;margin:10px 0;overflow:hidden}
    .collapsible-header{padding:12px 15px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:.85rem;color:#2c3e50;background:#f8f9fa}
    .collapsible-content{display:none;padding:12px 15px;font-size:.8rem}
    .collapsible-content.open{display:block}
    .badge-pathogen{display:inline-block;padding:3px 8px;border-radius:10px;margin:2px;font-size:.75rem;background:#e9ecef;color:#495057}
    """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HUSF - Vigilância Respiratória SE {se_num}/2026</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="container-fluid" style="max-width:600px;margin:0 auto">

<div class="header-automatico">
<h1 style="margin:0;font-size:1.3rem;font-weight:700">Hospital Universitário São Francisco</h1>
<p style="margin:4px 0 0;font-size:.85rem;opacity:.9">Vigilância de SG/SRAG - Bragança Paulista, SP</p>
<p style="margin:4px 0 0;font-size:.8rem;opacity:.8">Dr. Leandro Mendes - Médico Infectologista e Epidemiologista - SCIH</p>
</div>

<div class="alert alert-info" style="border-radius:10px;font-size:.85rem;padding:10px 15px">
<strong>SE {se_num}/2026</strong> &nbsp;|&nbsp; Fonte: InfoGripe/Fiocruz &nbsp;|&nbsp; Atualizado: {timestamp}
</div>

<div class="criterio-box">
<strong style="font-size:.85rem">Critério de decisão (VPN do teste de antígeno):</strong>
<div class="criterio-item" style="margin-top:6px"><div class="dot" style="background:#28a745"></div><span><strong>&ge;95%</strong> &rarr; Liberar isolamento com antígeno negativo</span></div>
<div class="criterio-item"><div class="dot" style="background:#ffc107"></div><span><strong>90-95%</strong> &rarr; Cautela - avaliar clinicamente</span></div>
<div class="criterio-item"><div class="dot" style="background:#dc3545"></div><span><strong>&lt;90%</strong> &rarr; RT-PCR recomendado</span></div>
</div>

<h6 style="color:#fff;margin:15px 0 8px;font-weight:700">Orientações de Liberação de Isolamento</h6>
{cards}

<div class="collapsible-section">
<div class="collapsible-header" onclick="toggle('positividade')">
<span><i class="fas fa-chart-bar" style="margin-right:6px"></i>Taxa de Positividade por Patógeno (SE {se_num}/2026)</span>
<i class="fas fa-chevron-down" id="icon-positividade"></i>
</div>
<div class="collapsible-content" id="positividade">
<p style="color:#6c757d;margin-bottom:8px">Distribuição entre casos positivos - 4 últimas semanas (InfoGripe/Fiocruz):</p>
{badges_positividade}
</div>
</div>

<div class="collapsible-section">
<div class="collapsible-header" onclick="toggle('base-cientifica')">
<span><i class="fas fa-flask" style="margin-right:6px"></i>Base Científica e Parâmetros do Sistema</span>
<i class="fas fa-chevron-down" id="icon-base-cientifica"></i>
</div>
<div class="collapsible-content" id="base-cientifica">
<strong>Sensibilidades dos testes (meta-análises):</strong>
<ul style="margin:6px 0 10px;padding-left:20px">
<li>COVID-19: 70% (Arshadi et al., 2022 - 60 estudos)</li>
<li>Influenza A: 62% (Chartrand et al., 2012 - 159 estudos)</li>
<li>Influenza B: 58% (Chartrand et al., 2012 - 159 estudos)</li>
<li>VSR: 75% (literatura disponível)</li>
<li>Rinovírus: 50% (estimativa conservadora)</li>
<li>Outros: 65% (estimativa)</li>
</ul>
<strong>Parâmetros do sistema HUSF:</strong>
<ul style="margin:6px 0 0;padding-left:20px">
<li>Especificidade: 98% (todos os testes)</li>
<li>Critério de liberação: VPN &ge; 95%</li>
<li>Fonte epidemiológica: InfoGripe/Fiocruz</li>
<li>Atualização: automática a cada 15 dias (GitHub Actions)</li>
</ul>
</div>
</div>

<div style="text-align:center;color:rgba(255,255,255,.7);font-size:.7rem;margin:15px 0;padding-bottom:20px">
Sistema automático de vigilância epidemiológica<br>
HUSF - Bragança Paulista &nbsp;|&nbsp; SE {se_num}/2026
</div>

</div>
<script>
function toggle(id){{
var c=document.getElementById(id);
var i=document.getElementById("icon-"+id);
c.classList.toggle("open");
i.style.transform=c.classList.contains("open")?"rotate(180deg)":"";
}}
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("HUSF - Verificando atualizações...")

    se_site = se_atual_no_site()
    print(f"SE atual no site: {se_site}")

    se_nova, pdf_url = buscar_se_mais_recente()
    print(f"SE mais recente disponível: {se_nova}")

    if se_nova == 0:
        print("Nenhuma SE encontrada. Nada a fazer.")
        return

    if se_nova <= se_site:
        print(f"Site já está na SE {se_site}. Nada a atualizar.")
        return

    print(f"Atualizando SE {se_site} -> {se_nova}...")

    # Download PDF
    r = requests.get(pdf_url, timeout=60)
    print(f"PDF baixado: {len(r.content):,} bytes")

    # Extrair dados
    print("Extraindo prevalências...")
    prevalencias = extrair_prevalencias(r.content)

    # Calcular VPNs
    vpns = {
        p: calcular_vpn(prevalencias[p], SENSIBILIDADES[p])
        for p in SENSIBILIDADES
    }

    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    html = gerar_html(se_nova, prevalencias, vpns, timestamp)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nindex.html gerado para SE {se_nova}/2026")
    print("Resumo VPNs:")
    nomes = dict(PATOGENOS)
    for p, vpn in vpns.items():
        status = "OK" if vpn >= LIMIAR_LIBERAR else "CAUTELA" if vpn >= LIMIAR_CAUTELA else "RTPCR"
        print(f"  [{status}] {nomes.get(p, p)}: {vpn:.0%} (prev {prevalencias.get(p, 0):.1%})")


if __name__ == "__main__":
    main()
