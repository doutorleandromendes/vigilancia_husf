#!/usr/bin/env python3
"""
HUSF - Script de atualização automática
Chamado pelo GitHub Actions (vigilancia.yml)

Fonte primária:  Parquet SIVEP-Gripe 2026 (dados abertos, atualizado semanalmente)
Fallback:        CSV SIVEP-Gripe 2026 (mesmo conteúdo, maior)

Lógica:
  1. Descobre a URL do arquivo mais recente via portal de dados abertos
  2. Baixa somente as colunas necessárias (~15 MB vs 200 MB do CSV)
  3. Filtra as 4 SEs mais recentes com dados estáveis (>= 400 positivos)
  4. Calcula distribuição entre positivos por patógeno
  5. Calcula VPN com sensibilidades das meta-análises
  6. Gera index.html com cards colapsíveis
"""

import os
import re
import sys
import requests
import pyarrow.parquet as pq
import pandas as pd
from io import BytesIO
from datetime import datetime


# ── Parâmetros clínicos (fixos — baseados em meta-análises) ──────────────────

SENSIBILIDADES = {
    "COVID19":     0.70,   # Arshadi et al. 2022 — 60 estudos
    "INFLUENZA_A": 0.62,   # Chartrand et al. 2012 — 159 estudos
    "INFLUENZA_B": 0.58,   # Chartrand et al. 2012 — 159 estudos
    "VSR":         0.75,   # literatura disponível
    "RINOVIRUS":   0.50,   # estimativa conservadora
    "OUTROS":      0.65,
}
ESPECIFICIDADE  = 0.98
LIMIAR_LIBERAR  = 0.95   # VPN >= 95% → LIBERAR
LIMIAR_CAUTELA  = 0.90   # VPN >= 90% → CAUTELA
MIN_POSITIVOS   = 400    # mínimo de positivos para SE ser considerada estável

PATOGENOS_DISPLAY = [
    ("COVID19",     "COVID-19"),
    ("INFLUENZA_A", "Influenza A"),
    ("INFLUENZA_B", "Influenza B"),
    ("VSR",         "VSR"),
    ("RINOVIRUS",   "Rinovírus"),
    ("OUTROS",      "Outros vírus"),
]

# Colunas necessárias do Parquet (de 194 colunas, lemos apenas 14)
COLUNAS = [
    "SEM_PRI",
    "PCR_SARS2",
    "POS_PCRFLU", "TP_FLU_PCR",
    "PCR_VSR",
    "PCR_RINO",
    "PCR_ADENO", "PCR_METAP", "PCR_BOCA",
    "PCR_PARA1", "PCR_PARA2", "PCR_PARA3", "PCR_PARA4",
    "PCR_RESUL",
]


# ── Descoberta da URL ─────────────────────────────────────────────────────────

def descobrir_url_atual():
    """
    Consulta o portal de dados abertos para encontrar a URL
    do arquivo SIVEP-Gripe 2026 mais recente.
    Tenta: API CKAN → scraping da página → força-bruta por data.
    """
    print("Buscando URL do arquivo SIVEP-Gripe 2026 mais recente...")

    # 1. API CKAN
    try:
        r = requests.get(
            "https://dadosabertos.saude.gov.br/api/3/action/package_show",
            params={"id": "srag-2019-a-2026"},
            timeout=15,
        )
        if r.status_code == 200:
            resources = r.json()["result"]["resources"]
            candidatos = []
            for res in resources:
                name = res.get("name", "")
                url  = res.get("url", "")
                if "2026" in name and "parquet" in name.lower():
                    candidatos.append((res.get("last_modified", ""), url))
                elif "2026" in name and "csv" in name.lower():
                    candidatos.append((res.get("last_modified", "") + "_csv", url))
            if candidatos:
                candidatos.sort(reverse=True)
                url = candidatos[0][1]
                print(f"  URL via API CKAN: {url.split('/')[-1]}")
                return url
    except Exception as e:
        print(f"  API CKAN falhou: {e}")

    # 2. Scraping da página do portal
    try:
        r = requests.get(
            "https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026",
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code == 200:
            # Procurar links para parquet de 2026
            parquets = re.findall(
                r'https://s3[^"\']+2026/INFLUD26[^"\']+\.parquet', r.text
            )
            if parquets:
                url = sorted(parquets)[-1]  # mais recente pela ordenação da data no nome
                print(f"  URL via scraping: {url.split('/')[-1]}")
                return url
            # Fallback: CSV
            csvs = re.findall(
                r'https://s3[^"\']+2026/INFLUD26[^"\']+\.csv', r.text
            )
            if csvs:
                url = sorted(csvs)[-1]
                print(f"  URL CSV via scraping: {url.split('/')[-1]}")
                return url
    except Exception as e:
        print(f"  Scraping falhou: {e}")

    # 3. Força-bruta por data (semanas para trás a partir de hoje)
    base = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/"
    hoje = datetime.now()
    for dias in range(0, 14):
        from datetime import timedelta
        d = hoje - timedelta(days=dias)
        for ext in ["parquet", "csv"]:
            fname = f"INFLUD26-{d.day:02d}-{d.month:02d}-{d.year}.{ext}"
            url = base + fname
            try:
                resp = requests.head(url, timeout=8)
                if resp.status_code == 200:
                    size_mb = int(resp.headers.get("content-length", 0)) / 1e6
                    print(f"  URL por força-bruta: {fname} ({size_mb:.0f} MB)")
                    return url
            except Exception:
                continue

    print("  ERRO: não foi possível descobrir a URL do arquivo atual.")
    return None


# ── Download e leitura ────────────────────────────────────────────────────────

def baixar_parquet(url):
    """Baixa o arquivo e retorna DataFrame com apenas as colunas necessárias."""
    print(f"Baixando {url.split('/')[-1]}...")
    r = requests.get(url, timeout=120,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    tamanho_mb = len(r.content) / 1e6
    print(f"  Baixado: {tamanho_mb:.1f} MB")

    if url.endswith(".parquet"):
        df = pq.read_table(BytesIO(r.content), columns=COLUNAS).to_pandas()
    else:
        # CSV fallback — ler só as colunas necessárias
        df = pd.read_csv(
            BytesIO(r.content),
            sep=";",
            usecols=COLUNAS,
            encoding="latin-1",
            dtype=str,
            low_memory=False,
        )

    print(f"  Linhas: {len(df):,} | Colunas lidas: {len(df.columns)}")
    return df


# ── Cálculo epidemiológico ────────────────────────────────────────────────────

def selecionar_ses_estaveis(df):
    """
    Retorna as 4 SEs mais recentes com >= MIN_POSITIVOS positivos confirmados.
    SEs muito recentes têm dados incompletos pelo atraso de digitação.
    """
    ses_com_positivos = (
        df[df["PCR_RESUL"] == "1"]
        .groupby("SEM_PRI").size()
        .reset_index(name="n_pos")
        .query(f"n_pos >= {MIN_POSITIVOS}")
        .sort_values("SEM_PRI")
    )
    ultimas4 = ses_com_positivos["SEM_PRI"].tolist()[-4:]
    return ultimas4


def calcular_prevalencias(df, ses):
    """
    Calcula a distribuição entre os positivos identificados nas SEs selecionadas.
    Método idêntico ao InfoGripe: proporção entre positivos por patógeno.
    """
    d = df[df["SEM_PRI"].isin(ses)].copy()

    def pos(col):
        return int((d[col] == "1").sum())

    flu_pos = d["POS_PCRFLU"] == "1"
    flu_b   = flu_pos & (d["TP_FLU_PCR"] == "2")

    contagens = {
        "COVID19":     pos("PCR_SARS2"),
        "INFLUENZA_A": int(flu_pos.sum()) - int(flu_b.sum()),
        "INFLUENZA_B": int(flu_b.sum()),
        "VSR":         pos("PCR_VSR"),
        "RINOVIRUS":   pos("PCR_RINO"),
        "OUTROS":      (pos("PCR_ADENO") + pos("PCR_METAP") +
                        pos("PCR_BOCA") + pos("PCR_PARA1") +
                        pos("PCR_PARA2") + pos("PCR_PARA3") + pos("PCR_PARA4")),
    }

    total = sum(contagens.values()) or 1
    prevalencias = {k: v / total for k, v in contagens.items()}
    return prevalencias, contagens, total


def calcular_vpn(prev, patogeno):
    sens = SENSIBILIDADES.get(patogeno, 0.65)
    num  = ESPECIFICIDADE * (1 - prev)
    den  = (1 - sens) * prev + ESPECIFICIDADE * (1 - prev)
    return num / den if den > 0 else 0


# ── Geração do HTML ───────────────────────────────────────────────────────────

def gerar_card(patogeno, nome_display, vpn, prev):
    if vpn >= LIMIAR_LIBERAR:
        card_cls = "liberar"
        vpn_cls  = "vpn-verde"
        ori_cls  = "orientacao-verde"
        icone    = "fas fa-check-circle"
        texto    = "LIBERAR ISOLAMENTO COM ANTÍGENO NEGATIVO"
    elif vpn >= LIMIAR_CAUTELA:
        card_cls = "cautela"
        vpn_cls  = "vpn-amarelo"
        ori_cls  = "orientacao-amarelo"
        icone    = "fas fa-exclamation-triangle"
        texto    = "CAUTELA — AVALIAR CLINICAMENTE"
    else:
        card_cls = "rtpcr"
        vpn_cls  = "vpn-vermelho"
        ori_cls  = "orientacao-vermelho"
        icone    = "fas fa-times-circle"
        texto    = "RT-PCR RECOMENDADO"

    return f"""
        <div class="card-patogeno {card_cls}">
          <div class="patogeno-header">
            <div class="patogeno-nome">{nome_display}</div>
            <div class="vpn-badge {vpn_cls}">VPN {vpn:.0%}</div>
          </div>
          <div class="orientacao {ori_cls}">
            <i class="{icone}"></i> {texto}
          </div>
          <div class="prevalencia-info">
            Positividade regional (4 sem.): {prev:.1%}
          </div>
        </div>"""


def gerar_html(ses_usadas, prevalencias, vpns, contagens, total_pos, timestamp):
    cards = "".join(
        gerar_card(p, n, vpns[p], prevalencias.get(p, 0))
        for p, n in PATOGENOS_DISPLAY
        if p in vpns
    )

    # Card colapsível 1 — positividade dinâmica
    badges = "".join(
        f'<span class="badge-pathogen">{n}: {prevalencias.get(p,0):.1%}</span>'
        for p, n in PATOGENOS_DISPLAY
    )
    se_range = f"SE {ses_usadas[0]}–{ses_usadas[-1]}/2026"

    # Card colapsível 2 — base científica (hardcoded, não muda)
    base_cientifica = """
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
          <li>Fonte: SIVEP-Gripe dados abertos (atualizado semanalmente)</li>
          <li>Atualização automática via GitHub Actions (a cada 15 dias)</li>
        </ul>"""

    css = """
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
              font-size:.82rem;margin-bottom:10px;
              display:flex;flex-wrap:wrap;gap:6px;align-items:center}
    .info-bar strong{color:#2c3e50}
    .criterio-box{background:#fff;border-radius:10px;padding:12px 14px;
                  margin-bottom:10px;font-size:.8rem}
    .criterio-row{display:flex;align-items:center;margin:4px 0}
    .dot{width:11px;height:11px;border-radius:50%;margin-right:8px;flex-shrink:0}
    .card-patogeno{background:#fff;margin:8px 0;border-radius:12px;
                   padding:14px;box-shadow:0 3px 12px rgba(0,0,0,.18);
                   border-left:5px solid #ddd}
    .liberar{border-left-color:#28a745}
    .cautela{border-left-color:#ffc107}
    .rtpcr  {border-left-color:#dc3545}
    .patogeno-header{display:flex;justify-content:space-between;
                     align-items:center;margin-bottom:8px}
    .patogeno-nome{font-weight:700;font-size:1.05rem;color:#2c3e50}
    .vpn-badge{padding:5px 11px;border-radius:20px;font-weight:700;
               color:#fff;font-size:.88rem}
    .vpn-verde  {background:#28a745}
    .vpn-amarelo{background:#ffc107;color:#000}
    .vpn-vermelho{background:#dc3545}
    .orientacao{font-weight:600;font-size:.84rem;margin-bottom:3px}
    .orientacao-verde  {color:#28a745}
    .orientacao-amarelo{color:#d39e00}
    .orientacao-vermelho{color:#dc3545}
    .prevalencia-info{font-size:.74rem;color:#6c757d;margin-top:3px}
    .collapsible{background:#fff;border-radius:10px;margin:10px 0;overflow:hidden}
    .coll-header{padding:11px 14px;cursor:pointer;
                 display:flex;justify-content:space-between;align-items:center;
                 font-weight:600;font-size:.83rem;color:#2c3e50;background:#f8f9fa;
                 border:none;width:100%;text-align:left}
    .coll-header i.fa-chevron-down{transition:transform .25s}
    .coll-content{display:none;padding:12px 14px;font-size:.79rem}
    .coll-content.open{display:block}
    .badge-pathogen{display:inline-block;padding:3px 8px;border-radius:10px;
                    margin:2px;font-size:.74rem;background:#e9ecef;color:#495057}
    .footer{text-align:center;color:rgba(255,255,255,.65);
            font-size:.68rem;margin:14px 0 20px;line-height:1.6}
    h6{color:#fff;margin:14px 0 6px;font-weight:700;font-size:.9rem}
    """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>HUSF — Vigilância Respiratória {se_range}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <h1>Hospital Universitário São Francisco</h1>
    <p>Vigilância de SG/SRAG — Bragança Paulista, SP</p>
    <p>Dr. Leandro Mendes — Médico Infectologista e Epidemiologista — SCIH</p>
  </div>

  <div class="info-bar">
    <strong>Dados:</strong> SIVEP-Gripe (dados abertos) &nbsp;|&nbsp;
    <strong>Período:</strong> {se_range} &nbsp;|&nbsp;
    <strong>Positivos analisados:</strong> {total_pos:,} &nbsp;|&nbsp;
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

  <h6>Orientações de Liberação de Isolamento</h6>
  {cards}

  <div class="collapsible">
    <button class="coll-header" onclick="toggle('posit')">
      <span><i class="fas fa-chart-bar" style="margin-right:6px"></i>
        Taxa de Positividade por Patógeno ({se_range})</span>
      <i class="fas fa-chevron-down" id="icon-posit"></i>
    </button>
    <div class="coll-content" id="posit">
      <p style="color:#6c757d;margin-bottom:8px;font-size:.78rem">
        Distribuição entre casos positivos confirmados por laboratório —
        4 semanas mais recentes com dados estáveis. Fonte: SIVEP-Gripe/MS.
      </p>
      {badges}
    </div>
  </div>

  <div class="collapsible">
    <button class="coll-header" onclick="toggle('base')">
      <span><i class="fas fa-flask" style="margin-right:6px"></i>
        Base Científica e Parâmetros do Sistema</span>
      <i class="fas fa-chevron-down" id="icon-base"></i>
    </button>
    <div class="coll-content" id="base">
      {base_cientifica}
    </div>
  </div>

  <div class="footer">
    Sistema automático de vigilância epidemiológica<br>
    HUSF — Bragança Paulista &nbsp;|&nbsp; {se_range}
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


# ── Verificação de atualização necessária ─────────────────────────────────────

def se_atual_no_site():
    """Lê a SE mais recente do index.html atual. Retorna '00' se não existir."""
    if not os.path.exists("index.html"):
        return "00"
    try:
        with open("index.html", encoding="utf-8") as f:
            html = f.read()
        m = re.search(r"SE\s+(\d+)[–-](\d+)/2026", html)
        return m.group(2) if m else "00"
    except Exception:
        return "00"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("HUSF — Vigilância Respiratória — Atualização automática")
    print("=" * 60)

    # 1. Descobrir URL
    url = descobrir_url_atual()
    if not url:
        print("ERRO: impossível prosseguir sem URL.", file=sys.stderr)
        sys.exit(1)

    # 2. Baixar e ler dados
    df = baixar_parquet(url)

    # 3. Selecionar SEs estáveis
    ses = selecionar_ses_estaveis(df)
    if len(ses) < 2:
        print("AVISO: menos de 2 SEs estáveis encontradas. Usando todas disponíveis.")
        ses = sorted(df["SEM_PRI"].dropna().unique())[-4:]

    se_mais_recente = ses[-1]
    se_site         = se_atual_no_site()

    print(f"\nSE mais recente nos dados: {se_mais_recente}")
    print(f"SE atual no site:           {se_site}")

    if se_mais_recente <= se_site:
        print("Site já está atualizado. Nada a fazer.")
        return

    print(f"Atualizando: SE {se_site} → SE {se_mais_recente}")
    print(f"SEs usadas no cálculo: {ses}")

    # 4. Calcular epidemiologia
    prevalencias, contagens, total_pos = calcular_prevalencias(df, ses)

    print(f"\nTotal positivos analisados: {total_pos:,}")
    print("Distribuição entre positivos:")
    for k, v in sorted(contagens.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} ({prevalencias[k]:.1%})")

    # 5. Calcular VPNs
    vpns = {p: calcular_vpn(prevalencias[p], p) for p in prevalencias}

    print("\nVPNs calculados:")
    for p, n in PATOGENOS_DISPLAY:
        if p in vpns:
            vpn   = vpns[p]
            prev  = prevalencias[p]
            status = "LIBERAR" if vpn >= LIMIAR_LIBERAR else "CAUTELA" if vpn >= LIMIAR_CAUTELA else "RTPCR"
            print(f"  [{status}] {n}: VPN {vpn:.1%} (prev {prev:.1%})")

    # 6. Gerar HTML
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    html = gerar_html(ses, prevalencias, vpns, contagens, total_pos, timestamp)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nindex.html gerado com sucesso ({len(html):,} bytes)")
    print("Pronto para commit e push.")


if __name__ == "__main__":
    main()
