#!/usr/bin/env python3
"""
HUSF — Vigilância Respiratória — Script de atualização automática
Fonte: Parquet SIVEP-Gripe 2026 (dados abertos MS, atualizado semanalmente)

Arquitetura de três camadas:
  Nacional  → base estatística dos VPNs (maior poder)
  Regional  → RMC/Campinas (contexto epidemiológico da macrorregião)
  Local     → Bragança Paulista (notificações do município)
"""

import os, re, sys
import requests
import pyarrow.parquet as pq
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta


# ── Parâmetros clínicos ───────────────────────────────────────────────────────

SENSIBILIDADES = {
    "COVID19":     0.70,  # Arshadi et al. 2022 — 60 estudos
    "INFLUENZA_A": 0.62,  # Chartrand et al. 2012 — 159 estudos
    "INFLUENZA_B": 0.58,  # Chartrand et al. 2012 — 159 estudos
    "VSR":         0.75,  # literatura disponível
    "RINOVIRUS":   0.50,  # estimativa conservadora
    "OUTROS":      0.65,
}
ESPECIFICIDADE = 0.98
LIMIAR_LIBERAR = 0.95
LIMIAR_CAUTELA = 0.90
MIN_POSITIVOS  = 400   # mínimo para SE ser considerada estável

PATOGENOS_DISPLAY = [
    ("COVID19",     "COVID-19"),
    ("INFLUENZA_A", "Influenza A"),
    ("INFLUENZA_B", "Influenza B"),
    ("VSR",         "VSR"),
    ("RINOVIRUS",   "Rinovírus"),
    ("OUTROS",      "Outros vírus"),
]

COLUNAS = [
    "SEM_PRI", "CO_MUN_NOT",
    "PCR_SARS2", "POS_PCRFLU", "TP_FLU_PCR",
    "PCR_VSR", "PCR_RINO",
    "PCR_ADENO", "PCR_METAP", "PCR_BOCA",
    "PCR_PARA1", "PCR_PARA2", "PCR_PARA3", "PCR_PARA4",
    "PCR_RESUL",
]

# Bragança Paulista — IBGE 6 dígitos (CO_MUN_NOT)
COD_BP = "350760"

# Região Metropolitana de Campinas — municípios notificantes (CO_MUN_NOT)
# Inclui BP e todos os municípios da macrorregião de saúde de Campinas
CODS_RMC = {
    "350760": "Bragança Paulista",
    "350950": "Campinas",
    "350430": "Atibaia",
    "351550": "Holambra",
    "351630": "Hortolândia",
    "351880": "Indaiatuba",
    "352590": "Itatiba",
    "352800": "Jaguariúna",
    "354340": "Monte Mor",
    "354980": "Nova Odessa",
    "355350": "Paulínia",
    "355490": "Pedreira",
    "355720": "Santa Bárbara d'Oeste",
    "356020": "Santo Antônio de Posse",
    "356490": "Sumaré",
    "357080": "Valinhos",
    "357110": "Vinhedo",
    "357550": "Americana",
    "354750": "Morungaba",
    "354300": "Nazaré Paulista",
    "353050": "Joanópolis",
}


# ── Descoberta de URL ─────────────────────────────────────────────────────────

def descobrir_url():
    print("Buscando arquivo SIVEP-Gripe 2026 mais recente...")
    base = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/"

    # 1. API CKAN
    try:
        r = requests.get(
            "https://dadosabertos.saude.gov.br/api/3/action/package_show",
            params={"id": "srag-2019-a-2026"}, timeout=15,
        )
        if r.status_code == 200:
            res = r.json()["result"]["resources"]
            cands = [
                (x.get("last_modified", ""), x["url"]) for x in res
                if "2026" in x.get("name", "") and x.get("url", "").endswith(".parquet")
            ]
            if cands:
                url = sorted(cands, reverse=True)[0][1]
                print(f"  API CKAN: {url.split('/')[-1]}")
                return url
    except Exception as e:
        print(f"  API CKAN falhou: {e}")

    # 2. Scraping da página
    try:
        r = requests.get(
            "https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026",
            timeout=15, headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code == 200:
            urls = re.findall(r'https://s3[^"\']+2026/INFLUD26[^"\']+\.parquet', r.text)
            if urls:
                url = sorted(urls)[-1]
                print(f"  Scraping: {url.split('/')[-1]}")
                return url
            urls_csv = re.findall(r'https://s3[^"\']+2026/INFLUD26[^"\']+\.csv', r.text)
            if urls_csv:
                url = sorted(urls_csv)[-1]
                print(f"  Scraping CSV: {url.split('/')[-1]}")
                return url
    except Exception as e:
        print(f"  Scraping falhou: {e}")

    # 3. Força-bruta por data
    hoje = datetime.now()
    for dias in range(0, 15):
        d = hoje - timedelta(days=dias)
        for ext in ["parquet", "csv"]:
            fname = f"INFLUD26-{d.day:02d}-{d.month:02d}-{d.year}.{ext}"
            url = base + fname
            try:
                resp = requests.head(url, timeout=8)
                if resp.status_code == 200:
                    mb = int(resp.headers.get("content-length", 0)) / 1e6
                    print(f"  Força-bruta: {fname} ({mb:.0f} MB)")
                    return url
            except Exception:
                continue

    print("  ERRO: nenhuma URL encontrada.")
    return None


# ── Download ──────────────────────────────────────────────────────────────────

def baixar(url):
    print(f"Baixando {url.split('/')[-1]}...")
    r = requests.get(url, timeout=180, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    print(f"  {len(r.content)/1e6:.1f} MB")

    if url.endswith(".parquet"):
        df = pq.read_table(BytesIO(r.content), columns=COLUNAS).to_pandas()
    else:
        df = pd.read_csv(
            BytesIO(r.content), sep=";",
            usecols=COLUNAS, encoding="latin-1", dtype=str, low_memory=False,
        )
    print(f"  {len(df):,} linhas")
    return df


# ── Funções epidemiológicas ───────────────────────────────────────────────────

def contagem_patogenos(d):
    """Conta positivos por patógeno num DataFrame filtrado."""
    flu   = d["POS_PCRFLU"] == "1"
    flu_b = flu & (d["TP_FLU_PCR"] == "2")
    def pos(col): return int((d[col] == "1").sum())
    return {
        "COVID19":     pos("PCR_SARS2"),
        "INFLUENZA_A": int(flu.sum()) - int(flu_b.sum()),
        "INFLUENZA_B": int(flu_b.sum()),
        "VSR":         pos("PCR_VSR"),
        "RINOVIRUS":   pos("PCR_RINO"),
        "OUTROS":      sum(pos(c) for c in [
                           "PCR_ADENO", "PCR_METAP", "PCR_BOCA",
                           "PCR_PARA1", "PCR_PARA2", "PCR_PARA3", "PCR_PARA4"]),
    }


def ses_estaveis(df):
    """4 SEs nacionais mais recentes com >= MIN_POSITIVOS positivos."""
    counts = (
        df[df["PCR_RESUL"] == "1"]
        .groupby("SEM_PRI").size()
        .reset_index(name="n")
        .query(f"n >= {MIN_POSITIVOS}")
        .sort_values("SEM_PRI")
    )
    return counts["SEM_PRI"].tolist()[-4:]


def calcular_vpn(prev, patogeno):
    s = SENSIBILIDADES.get(patogeno, 0.65)
    n = ESPECIFICIDADE * (1 - prev)
    d = (1 - s) * prev + ESPECIFICIDADE * (1 - prev)
    return n / d if d > 0 else 0


def camada_stats(df_subset, ses4):
    """Retorna dict com cumulativo e últimas 4 SEs para qualquer subset."""
    # Cumulativo
    c_all = contagem_patogenos(df_subset)
    cum = {
        "total":      len(df_subset),
        "positivos":  int((df_subset["PCR_RESUL"] == "1").sum()),
        "aguardando": int((df_subset["PCR_RESUL"] == "5").sum()),
        "patogenos":  {k: v for k, v in c_all.items() if v > 0},
    }
    # Últimas 4 SEs
    sub4 = df_subset[df_subset["SEM_PRI"].isin(ses4)]
    c4   = contagem_patogenos(sub4)
    total4 = sum(c4.values()) or 1
    sem4 = {
        "total":      len(sub4),
        "positivos":  int((sub4["PCR_RESUL"] == "1").sum()),
        "aguardando": int((sub4["PCR_RESUL"] == "5").sum()),
        "patogenos":  {k: v for k, v in c4.items() if v > 0},
        "prevalencias": {k: v / total4 for k, v in c4.items()},
    }
    return {"cumulativo": cum, "ultimas4": sem4}


# ── Geração do HTML ───────────────────────────────────────────────────────────

CSS = """
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;
     background:linear-gradient(135deg,#667eea,#764ba2);
     margin:0;padding:10px;min-height:100vh}
.wrap{max-width:600px;margin:0 auto}
.header{background:linear-gradient(135deg,#2c3e50,#34495e);color:#fff;
        padding:18px;border-radius:14px;text-align:center;
        margin-bottom:12px;box-shadow:0 4px 20px rgba(0,0,0,.3)}
.header h1{margin:0;font-size:1.25rem;font-weight:700}
.header p{margin:4px 0 0;font-size:.82rem;opacity:.85}
.info-bar{background:#fff;border-radius:10px;padding:10px 14px;
          font-size:.8rem;margin-bottom:10px;color:#495057}
.criterio-box{background:#fff;border-radius:10px;padding:12px 14px;
              margin-bottom:10px;font-size:.8rem}
.criterio-row{display:flex;align-items:center;margin:4px 0}
.dot{width:11px;height:11px;border-radius:50%;margin-right:8px;flex-shrink:0}
.card-vpn{background:#fff;margin:8px 0;border-radius:12px;padding:14px;
          box-shadow:0 3px 12px rgba(0,0,0,.18);border-left:5px solid #ddd}
.liberar{border-left-color:#28a745}
.cautela{border-left-color:#ffc107}
.rtpcr  {border-left-color:#dc3545}
.pat-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.pat-nome{font-weight:700;font-size:1.05rem;color:#2c3e50}
.vpn-badge{padding:5px 11px;border-radius:20px;font-weight:700;color:#fff;font-size:.88rem}
.vpn-verde   {background:#28a745}
.vpn-amarelo {background:#ffc107;color:#000}
.vpn-vermelho{background:#dc3545}
.orientacao{font-weight:600;font-size:.84rem;margin-bottom:3px}
.ori-verde   {color:#28a745}
.ori-amarelo {color:#d39e00}
.ori-vermelho{color:#dc3545}
.prev-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}
.prev-chip{font-size:.72rem;padding:2px 7px;border-radius:8px;
           background:#f0f0f0;color:#555}
.collapsible{background:#fff;border-radius:10px;margin:10px 0;overflow:hidden}
.coll-btn{padding:11px 14px;cursor:pointer;width:100%;text-align:left;border:none;
          background:#f8f9fa;display:flex;justify-content:space-between;
          align-items:center;font-weight:600;font-size:.83rem;color:#2c3e50}
.coll-btn i.fa-chevron-down{transition:transform .25s}
.coll-content{display:none;padding:12px 14px;font-size:.79rem}
.coll-content.open{display:block}
.escala-tabs{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.tab{padding:4px 10px;border-radius:8px;font-size:.76rem;font-weight:600;
     background:#e9ecef;color:#495057;cursor:pointer;border:none}
.tab.ativo{background:#2c3e50;color:#fff}
.escala-panel{display:none}.escala-panel.ativo{display:block}
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px}
.stat-box{background:#f8f9fa;border-radius:8px;padding:8px 10px;text-align:center}
.stat-num{font-size:1.1rem;font-weight:700;color:#2c3e50}
.stat-lbl{font-size:.68rem;color:#6c757d;margin-top:1px}
.badge-p{display:inline-block;padding:2px 7px;border-radius:8px;
         margin:2px;font-size:.73rem;background:#dee2e6;color:#495057}
.sem4-title{font-weight:700;font-size:.78rem;color:#2c3e50;
            margin:8px 0 4px;padding-top:8px;border-top:1px solid #eee}
.aviso{font-size:.72rem;color:#888;margin-top:8px;padding-top:6px;
       border-top:1px solid #eee;line-height:1.4}
h6.st{color:#fff;margin:14px 0 6px;font-weight:700;font-size:.9rem}
.footer{text-align:center;color:rgba(255,255,255,.65);
        font-size:.68rem;margin:14px 0 20px;line-height:1.6}
"""


def card_vpn(patogeno, nome, vpn, prev_nac, prev_reg):
    if vpn >= LIMIAR_LIBERAR:
        cc, vc, oc = "liberar", "vpn-verde", "ori-verde"
        ic, tx = "fas fa-check-circle", "LIBERAR ISOLAMENTO COM ANTÍGENO NEGATIVO"
    elif vpn >= LIMIAR_CAUTELA:
        cc, vc, oc = "cautela", "vpn-amarelo", "ori-amarelo"
        ic, tx = "fas fa-exclamation-triangle", "CAUTELA — AVALIAR CLINICAMENTE"
    else:
        cc, vc, oc = "rtpcr", "vpn-vermelho", "ori-vermelho"
        ic, tx = "fas fa-times-circle", "RT-PCR RECOMENDADO"

    chip_reg = (
        f'<span class="prev-chip">Regional {prev_reg:.1%}</span>'
        if prev_reg is not None else ""
    )

    return f"""
<div class="card-vpn {cc}">
  <div class="pat-header">
    <div class="pat-nome">{nome}</div>
    <div class="vpn-badge {vc}">VPN {vpn:.0%}</div>
  </div>
  <div class="orientacao {oc}"><i class="{ic}"></i> {tx}</div>
  <div class="prev-row">
    <span class="prev-chip">Nacional {prev_nac:.1%}</span>
    {chip_reg}
  </div>
</div>"""


def painel_escala(stats, label_ses4, escala_id, nome_escala, aviso_txt=None):
    """Gera o HTML de um painel de escala (local/regional/nacional)."""
    cum  = stats["cumulativo"]
    sem4 = stats["ultimas4"]

    def badges(dct):
        if not dct:
            return '<span style="color:#aaa;font-size:.74rem">sem positivos identificados</span>'
        return "".join(
            f'<span class="badge-p">{k}: {v}</span>'
            for k, v in sorted(dct.items(), key=lambda x: -x[1])
        )

    # Positividade das últimas 4 SEs
    prev4 = sem4.get("prevalencias", {})
    badges4 = "".join(
        f'<span class="badge-p">{k}: {v:.1%}</span>'
        for k, v in sorted(prev4.items(), key=lambda x: -x[1])
        if v > 0
    ) or '<span style="color:#aaa;font-size:.74rem">sem positivos identificados</span>'

    aviso_html = (
        f'<div class="aviso"><i class="fas fa-info-circle"></i> {aviso_txt}</div>'
        if aviso_txt else ""
    )

    return f"""
<div class="escala-panel" id="panel-{escala_id}">
  <div class="stat-grid">
    <div class="stat-box">
      <div class="stat-num">{cum['total']}</div>
      <div class="stat-lbl">Notificações 2026</div>
    </div>
    <div class="stat-box">
      <div class="stat-num">{cum['positivos']}</div>
      <div class="stat-lbl">Positivos 2026</div>
    </div>
    <div class="stat-box">
      <div class="stat-num">{cum['aguardando']}</div>
      <div class="stat-lbl">Aguardando</div>
    </div>
  </div>
  <div style="font-size:.76rem;font-weight:600;color:#495057;margin-bottom:4px">
    Patógenos identificados (cumulativo 2026):
  </div>
  {badges(cum['patogenos'])}

  <div class="sem4-title">
    <i class="fas fa-clock" style="margin-right:4px"></i>
    Últimas 4 SEs ({label_ses4}) — {sem4['total']} notificações,
    {sem4['positivos']} positivos
  </div>
  {badges4}
  {aviso_html}
</div>"""


def gerar_html(ses, prev_nac, vpns, stats_nac, stats_reg, stats_loc, timestamp):
    se_label  = f"SE {ses[0]}–{ses[-1]}/2026"
    ses_label = f"{ses[0]}–{ses[-1]}"

    cards_vpn = "".join(
        card_vpn(
            p, n, vpns[p],
            prev_nac.get(p, 0),
            stats_reg["ultimas4"]["prevalencias"].get(p),
        )
        for p, n in PATOGENOS_DISPLAY if p in vpns
    )

    painel_loc = painel_escala(
        stats_loc, ses_label, "local", "Local",
        aviso_txt=(
            "Casos notificados em Bragança Paulista (SIVEP-Gripe/MS). "
            "O SIVEP-Gripe registra internações por SRAG; volume pequeno "
            "para municípios de médio porte é esperado."
        ),
    )
    painel_reg = painel_escala(
        stats_reg, ses_label, "regional", "Regional",
        aviso_txt=(
            "Região Metropolitana de Campinas — macrorregião de referência do HUSF. "
            "21 municípios, incluindo Bragança Paulista."
        ),
    )
    painel_nac = painel_escala(
        stats_nac, ses_label, "nacional", "Nacional",
        aviso_txt="Base nacional — usada para o cálculo dos VPNs por maior poder estatístico.",
    )

    total_nac = stats_nac["cumulativo"]["positivos"]

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>HUSF — Vigilância Respiratória {se_label}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<div class="header">
  <h1>Hospital Universitário São Francisco</h1>
  <p>Vigilância de SG/SRAG — Bragança Paulista, SP</p>
  <p>Dr. Leandro Mendes — Médico Infectologista e Epidemiologista — SCIH</p>
</div>

<div class="info-bar">
  <strong>Fonte:</strong> SIVEP-Gripe (dados abertos/MS) &nbsp;·&nbsp;
  <strong>Período:</strong> {se_label} &nbsp;·&nbsp;
  <strong>Positivos nacionais:</strong> {total_nac:,} &nbsp;·&nbsp;
  <strong>Atualizado:</strong> {timestamp}
</div>

<div class="criterio-box">
  <strong style="font-size:.84rem">Critério — VPN do teste de antígeno:</strong>
  <div class="criterio-row" style="margin-top:6px">
    <div class="dot" style="background:#28a745"></div>
    <span><strong>&ge; 95%</strong> &rarr; Liberar isolamento com antígeno negativo</span>
  </div>
  <div class="criterio-row">
    <div class="dot" style="background:#ffc107"></div>
    <span><strong>90–95%</strong> &rarr; Cautela — avaliar clinicamente</span>
  </div>
  <div class="criterio-row">
    <div class="dot" style="background:#dc3545"></div>
    <span><strong>&lt; 90%</strong> &rarr; RT-PCR recomendado</span>
  </div>
</div>

<h6 class="st">Orientações de Liberação de Isolamento</h6>
{cards_vpn}

<div class="collapsible">
  <button class="coll-btn" onclick="tog('ctx')">
    <span><i class="fas fa-chart-bar" style="margin-right:6px"></i>
      Contexto Epidemiológico ({se_label})</span>
    <i class="fas fa-chevron-down" id="icon-ctx"></i>
  </button>
  <div class="coll-content" id="ctx">
    <div class="escala-tabs">
      <button class="tab ativo" onclick="tab('local')">
        <i class="fas fa-hospital" style="margin-right:4px"></i>Local
      </button>
      <button class="tab" onclick="tab('regional')">
        <i class="fas fa-map-marker-alt" style="margin-right:4px"></i>Regional
      </button>
      <button class="tab" onclick="tab('nacional')">
        <i class="fas fa-globe-americas" style="margin-right:4px"></i>Nacional
      </button>
    </div>
    {painel_loc}
    {painel_reg}
    {painel_nac}
  </div>
</div>

<div class="collapsible">
  <button class="coll-btn" onclick="tog('base')">
    <span><i class="fas fa-flask" style="margin-right:6px"></i>
      Base Científica e Parâmetros</span>
    <i class="fas fa-chevron-down" id="icon-base"></i>
  </button>
  <div class="coll-content" id="base">
    <strong>Sensibilidades dos testes (meta-análises):</strong>
    <ul style="margin:6px 0 10px;padding-left:20px">
      <li>COVID-19: 70% — Arshadi et al., 2022 (60 estudos)</li>
      <li>Influenza A: 62% — Chartrand et al., 2012 (159 estudos)</li>
      <li>Influenza B: 58% — Chartrand et al., 2012 (159 estudos)</li>
      <li>VSR: 75% — literatura disponível</li>
      <li>Rinovírus: 50% — estimativa conservadora</li>
      <li>Outros vírus: 65% — estimativa</li>
    </ul>
    <strong>Parâmetros do sistema HUSF:</strong>
    <ul style="margin:6px 0 0;padding-left:20px">
      <li>Especificidade: 98% (todos os testes)</li>
      <li>Critério de liberação: VPN &ge; 95%</li>
      <li>VPN calculado com dados nacionais (maior poder estatístico)</li>
      <li>Fonte: SIVEP-Gripe dados abertos — atualizado semanalmente pelo MS</li>
      <li>Atualização automática via GitHub Actions (a cada 15 dias)</li>
    </ul>
  </div>
</div>

<div class="footer">
  Sistema automático de vigilância epidemiológica<br>
  HUSF — Bragança Paulista &nbsp;|&nbsp; {se_label}
</div>

</div>
<script>
function tog(id){{
  var c=document.getElementById(id);
  var i=document.getElementById("icon-"+id);
  c.classList.toggle("open");
  i.style.transform=c.classList.contains("open")?"rotate(180deg)":"";
}}
var _tab="local";
function tab(id){{
  document.getElementById("panel-"+_tab).classList.remove("ativo");
  document.querySelectorAll(".tab").forEach(function(t){{t.classList.remove("ativo");}});
  document.getElementById("panel-"+id).classList.add("ativo");
  event.target.closest(".tab").classList.add("ativo");
  _tab=id;
}}
document.getElementById("panel-local").classList.add("ativo");
</script>
</body>
</html>"""


# ── Estado atual do site ──────────────────────────────────────────────────────

def se_site():
    if not os.path.exists("index.html"):
        return "00"
    try:
        with open("index.html", encoding="utf-8") as f:
            html = f.read()
        m = re.search(r"SE\s+(\d+)[–\-](\d+)/2026", html)
        return m.group(2) if m else "00"
    except Exception:
        return "00"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("HUSF — Vigilância Respiratória — Atualização automática")
    print("=" * 60)

    url = descobrir_url()
    if not url:
        print("ERRO: impossível prosseguir sem URL.", file=sys.stderr)
        sys.exit(1)

    df = baixar(url)

    # SEs estáveis para o cálculo nacional
    ses = ses_estaveis(df)
    if len(ses) < 2:
        ses = sorted(df["SEM_PRI"].dropna().unique())[-4:]

    se_nova  = ses[-1]
    se_atual = se_site()

    print(f"\nSE mais recente:  {se_nova}")
    print(f"SE no site atual: {se_atual}")

    if se_nova <= se_atual:
        print("Site já atualizado. Nada a fazer.")
        return

    print(f"Atualizando SE {se_atual} → SE {se_nova}")
    print(f"SEs usadas: {ses}")

    # ── Camada nacional (base dos VPNs)
    conts_nac, total_nac = None, None
    c_nac  = contagem_patogenos(df[df["SEM_PRI"].isin(ses)])
    total_nac = sum(c_nac.values()) or 1
    prev_nac  = {k: v / total_nac for k, v in c_nac.items()}
    vpns      = {p: calcular_vpn(prev_nac[p], p) for p in prev_nac}
    stats_nac = camada_stats(df, ses)

    print(f"\nNacional — {total_nac:,} positivos nas 4 SEs")
    for p, n in PATOGENOS_DISPLAY:
        if p in vpns:
            st = ("LIBERAR" if vpns[p] >= LIMIAR_LIBERAR
                  else "CAUTELA" if vpns[p] >= LIMIAR_CAUTELA else "RTPCR")
            print(f"  [{st}] {n}: {vpns[p]:.0%} VPN (prev {prev_nac[p]:.1%})")

    # ── Camada regional (RMC)
    df_reg  = df[df["CO_MUN_NOT"].isin(CODS_RMC.keys())].copy()
    stats_reg = camada_stats(df_reg, ses)
    reg4_pos = stats_reg["ultimas4"]["positivos"]
    print(f"\nRegional (RMC) — {stats_reg['cumulativo']['positivos']:,} positivos cumulativos, "
          f"{reg4_pos} nas 4 SEs")

    # ── Camada local (Bragança Paulista)
    df_loc  = df[df["CO_MUN_NOT"] == COD_BP].copy()
    stats_loc = camada_stats(df_loc, ses)
    print(f"Local (BP) — {stats_loc['cumulativo']['positivos']} positivos cumulativos, "
          f"{stats_loc['ultimas4']['positivos']} nas 4 SEs")

    # ── Gerar HTML
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    html = gerar_html(ses, prev_nac, vpns, stats_nac, stats_reg, stats_loc, timestamp)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nindex.html gerado: {len(html):,} bytes")
    print("Pronto para commit e push.")


if __name__ == "__main__":
    main()
