"""
status.py — endemicidade SIMPLES para taxas brutas de IH (enfermarias + global).
Canal endêmico sobre a série histórica + tendência do ano vigente, SEPARADOS.

Vocabulário (igual ao formulário de entrada):
  classify -> 'endemic' | 'alert' | 'exceptional'
    endemic     : atual ≤ μ + σ
    alert       : μ + σ < atual ≤ μ + 2σ   (alerta supraendêmico)
    exceptional : atual > μ + 2σ            (atividade excepcional)
  trend    -> 'subindo' | 'estável' | 'descendo'  (declive dos pontos do ano vigente)

μ, σ do histórico (todos os pontos MENOS o corrente). Poucos pontos (<4) → 'endemic'.
UTIs e HD NÃO usam isto (têm análise própria robusta).
"""
from statistics import mean, pstdev


def _vals(serie):
    return [p['v'] for p in serie if isinstance(p.get('v'), (int, float))]


def classify(serie):
    pts = _vals(serie)
    if len(pts) < 4:
        return 'endemic'
    atual = pts[-1]
    base = pts[:-1]
    mu = mean(base)
    sd = pstdev(base) or 0.0
    if atual > mu + 2 * sd:
        return 'exceptional'
    if atual > mu + sd:
        return 'alert'
    return 'endemic'


def trend(serie, sufixo_ano):
    """Declive simples dos pontos cujo 'p' termina em sufixo_ano (ex.: '/26')."""
    ano = [p['v'] for p in serie
           if isinstance(p.get('v'), (int, float)) and str(p.get('p', '')).endswith(sufixo_ano)]
    if len(ano) < 3:
        return '—'
    n = len(ano); xs = list(range(n))
    den = n * sum(i * i for i in xs) - sum(xs) ** 2
    if den == 0:
        return 'estável'
    slope = (n * sum(i * v for i, v in zip(xs, ano)) - sum(xs) * sum(ano)) / den
    return 'subindo' if slope > 0.05 else ('descendo' if slope < -0.05 else 'estável')
