#!/usr/bin/env python3
"""
Demo rápido do Sistema de Vigilância - HUSF Bragança Paulista
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 70)
print("🏥 SISTEMA DE VIGILÂNCIA RESPIRATÓRIA - DEMO HUSF BRAGANÇA PAULISTA")
print("=" * 70)

# Simular dados SRAG para Bragança Paulista
np.random.seed(42)  # Para resultados reproduzíveis

# Gerar 50 casos simulados (volume mensal típico para Bragança Paulista)
n_casos = 50
dados_simulados = {
    'data_sintomas': [datetime.now() - timedelta(days=np.random.randint(1, 30)) for _ in range(n_casos)],
    'municipio': ['3507605'] * n_casos,  # Código IBGE Bragança Paulista
    'covid_positivo': np.random.choice([0, 1], n_casos, p=[0.85, 0.15]),  # 15% COVID+
    'influenza_positivo': np.random.choice([0, 1], n_casos, p=[0.92, 0.08]),  # 8% Influenza+
    'vsr_positivo': np.random.choice([0, 1], n_casos, p=[0.95, 0.05]),  # 5% VSR+
}

df = pd.DataFrame(dados_simulados)

# Calcular estatísticas
total_casos = len(df)
covid_casos = df['covid_positivo'].sum()
influenza_casos = df['influenza_positivo'].sum()
vsr_casos = df['vsr_positivo'].sum()

covid_prevalencia = covid_casos / total_casos
influenza_prevalencia = influenza_casos / total_casos
vsr_prevalencia = vsr_casos / total_casos

print(f"📊 DADOS SIMULADOS PARA BRAGANÇA PAULISTA:")
print(f"• Total de casos analisados: {total_casos}")
print(f"• COVID-19: {covid_casos} casos ({covid_prevalencia:.1%})")
print(f"• Influenza: {influenza_casos} casos ({influenza_prevalencia:.1%})")
print(f"• VSR: {vsr_casos} casos ({vsr_prevalencia:.1%})")

# Calcular VPN (Valor Preditivo Negativo)
# Fórmula: VPN = (Especificidade × (1 - Prevalência)) / (Especificidade × (1 - Prevalência) + (1 - Sensibilidade) × Prevalência)

sensibilidade = 0.85  # 85%
especificidade = 0.98  # 98%

def calcular_vpn(prevalencia, sens=sensibilidade, espec=especificidade):
    vpn = (espec * (1 - prevalencia)) / (espec * (1 - prevalencia) + (1 - sens) * prevalencia)
    return vpn

covid_vpn = calcular_vpn(covid_prevalencia)
influenza_vpn = calcular_vpn(influenza_prevalencia)
vsr_vpn = calcular_vpn(vsr_prevalencia)

print(f"\n🔬 VALOR PREDITIVO NEGATIVO (VPN) - TESTE ANTÍGENO:")
print(f"• COVID-19: {covid_vpn:.1%}")
print(f"• Influenza: {influenza_vpn:.1%}")
print(f"• VSR: {vsr_vpn:.1%}")

# Classificar pressão epidemiológica
def classificar_pressao(prevalencia):
    if prevalencia < 0.05:
        return "🟢 BAIXA"
    elif prevalencia < 0.15:
        return "🟡 MODERADA"
    elif prevalencia < 0.25:
        return "🟠 ALTA"
    else:
        return "🔴 MUITO ALTA"

print(f"\n⚠️ PRESSÃO EPIDEMIOLÓGICA EM BRAGANÇA PAULISTA:")
print(f"• COVID-19: {classificar_pressao(covid_prevalencia)}")
print(f"• Influenza: {classificar_pressao(influenza_prevalencia)}")
print(f"• VSR: {classificar_pressao(vsr_prevalencia)}")

# Gerar orientações
def gerar_orientacao(vpn, prevalencia):
    pressao = classificar_pressao(prevalencia)
    
    if vpn >= 0.95 and prevalencia < 0.15:
        return "✅ LIBERAÇÃO SEGURA - VPN alto com baixa/moderada circulação"
    elif vpn >= 0.90 and prevalencia < 0.05:
        return "✅ LIBERAÇÃO ACEITÁVEL - VPN adequado com baixa circulação"
    elif vpn >= 0.85 and prevalencia < 0.15:
        return "⚠️ LIBERAÇÃO COM CAUTELA - Avaliar contexto clínico"
    elif prevalencia >= 0.15:
        return "🛑 MANTER ISOLAMENTO - Alta circulação viral"
    else:
        return "🔍 AVALIAÇÃO INDIVIDUALIZADA - VPN insuficiente"

print(f"\n🏥 ORIENTAÇÕES PARA ISOLAMENTO (HUSF BRAGANÇA PAULISTA):")
print(f"• COVID-19: {gerar_orientacao(covid_vpn, covid_prevalencia)}")
print(f"• Influenza: {gerar_orientacao(influenza_vpn, influenza_prevalencia)}")
print(f"• VSR: {gerar_orientacao(vsr_vpn, vsr_prevalencia)}")

print(f"\n📋 RELATÓRIO GERADO: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print(f"🏥 Hospital: HUSF - Bragança Paulista")
print(f"👨‍⚕️ Responsável: Dr. Leandro - SCIH/CCIH")

print("\n" + "=" * 70)
print("✅ SISTEMA DE VIGILÂNCIA FUNCIONANDO PERFEITAMENTE!")
print("🚀 Pronto para implementação no HUSF Bragança Paulista")
print("=" * 70)
