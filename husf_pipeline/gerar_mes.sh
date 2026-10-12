#!/usr/bin/env bash
# gerar_mes.sh — roda a competência inteira do mês, em ordem:
#   1) dashboards (gerar_competencia.py)  2) CVE principal  3) CVE de diálise
#
# Uso:  ./gerar_mes.sh jun/26
#
# Requer as variáveis de ambiente do CVE (veja README_cve_pipeline.md):
#   CVE_CONTROLES, CVE_MESTRE, CVE_DIAL_MESTRE, CVE_OUT, CVE_SURA_URL, CVE_API_KEY
#   e CVE_SETOR_DIALISE = arquivo mensal do setor de hemodiálise.
set -euo pipefail

MES="${1:?uso: ./gerar_mes.sh jun/26}"
ROOT="$(cd "$(dirname "$0")" && pwd)"      # raiz do projeto (onde está husf_pipeline/)
cd "$ROOT"

echo "══════════════════════════════════════════════════════════════"
echo "  Competência ${MES}"
echo "══════════════════════════════════════════════════════════════"

echo "── 1/3  Dashboards (data_iras/sahe/stats.json) ────────────────"
python3 husf_pipeline/gerar_competencia.py --mes "$MES"

echo "── 2/3  CVE principal ─────────────────────────────────────────"
python3 husf_pipeline/gerar_cve.py --mes "$MES"

echo "── 3/3  CVE de diálise ────────────────────────────────────────"
if [[ -n "${CVE_SETOR_DIALISE:-}" ]]; then
  python3 husf_pipeline/gerar_cve.py --mes "$MES" --dialise --setor-dialise "$CVE_SETOR_DIALISE"
else
  echo "  ⚠  CVE_SETOR_DIALISE não definido — pulei o CVE de diálise."
fi

echo
echo "── Pronto. Próximos passos manuais ────────────────────────────"
echo "  • Dashboards:  cd \$DASHBOARD_DIR && git add data_iras.json data_sahe.json data_stats.json"
echo "                 git commit -m 'dados: ${MES}' && git push"
echo "  • CVE:         revise os *_auto.xlsx + diff_revisao*.csv e envie ao CVE-SP"
