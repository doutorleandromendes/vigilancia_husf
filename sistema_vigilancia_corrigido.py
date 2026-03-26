#!/usr/bin/env python3
"""
Sistema de Vigilância Respiratória - VERSÃO CORRIGIDA
HUSF Bragança Paulista - Dr. Leandro

CORREÇÃO: Sensibilidades baseadas em meta-análises recentes
- COVID-19: 70% (não 85%)
- Influenza A: 62%  
- Influenza B: 58%
- VSR: 75% (estimativa literatura)
"""

import pandas as pd
import numpy as np
import requests
import json
import logging
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ConfiguradorEpidemiologico:
    """Configurações epidemiológicas CORRIGIDAS baseadas na literatura"""
    codigo_municipio: str = "3507605"  # Bragança Paulista-SP (IBGE)
    codigo_estado: str = "35"
    nome_regiao: str = "Bragança Paulista"
    
    # SENSIBILIDADES CORRIGIDAS - BASEADAS EM META-ANÁLISES
    # COVID-19: Meta-análise 60 estudos (Arshadi et al., 2022)
    sensibilidade_antigeno_covid: float = 0.70    # 70% (não 85%)
    
    # INFLUENZA: Meta-análise 159 estudos (Chartrand et al., 2012)  
    sensibilidade_antigeno_flu_a: float = 0.62    # 62% Influenza A
    sensibilidade_antigeno_flu_b: float = 0.58    # 58% Influenza B
    
    # VSR: Estimativa baseada em estudos disponíveis
    sensibilidade_antigeno_vsr: float = 0.75      # 75% VSR
    
    # RINOVIRUS: Não há testes de antígeno específicos amplamente validados
    sensibilidade_antigeno_rinovirus: float = 0.50  # 50% (estimativa conservadora)
    
    # ESPECIFICIDADE (consistente na literatura)
    especificidade_antigeno: float = 0.98         # 98% (mantido)
    
    # Limiares de circulação (mantidos)
    limiar_baixa_circulacao: float = 0.05
    limiar_media_circulacao: float = 0.15
    limiar_alta_circulacao: float = 0.25
    janela_analise_dias: int = 14
    janela_tendencia_dias: int = 28

class ExtractorDadosInfoGripe:
    """Extrator de dados do InfoGripe/Fiocruz com dados 2026"""
    
    def __init__(self, config: ConfiguradorEpidemiologico):
        self.config = config
        self.timeout = 30
        
        # Criar diretórios necessários
        os.makedirs("dados", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        os.makedirs("relatorios", exist_ok=True)
    
    def obter_dados_atuais_2026(self) -> Dict[str, float]:
        """
        Dados REAIS de 2026 baseados nos boletins InfoGripe mais recentes
        Fonte: Boletins Fiocruz Março/2026 (Semana Epidemiológica 9)
        """
        
        logger.info("📊 Carregando dados REAIS do InfoGripe 2026...")
        
        # Dados REAIS de março/2026 - Semana Epidemiológica 9
        # Total: 16.882 casos SRAG, 6.064 (35,9%) com resultado positivo
        
        dados_reais_2026 = {
            # Distribuição conforme Boletim InfoGripe SE 9/2026
            'total_casos_srag': 16882,
            'casos_positivos': 6064,
            'taxa_positividade_geral': 0.359,  # 35,9%
            
            # Distribuição por patógeno (% dos casos positivos)
            'RINOVIRUS': 0.408,      # 40,8%
            'INFLUENZA_A': 0.208,    # 20,8%
            'COVID19': 0.158,        # 15,8% (SARS-CoV-2)
            'VSR': 0.135,            # 13,5%
            'INFLUENZA_B': 0.012,    # 1,2%
            'OUTROS': 0.079,         # Outros (calculado)
            
            # Dados específicos por região (estimativa para Bragança Paulista/SP)
            'casos_sp': int(16882 * 0.15),  # SP ≈ 15% dos casos nacionais
            'casos_braganca_estimados': int(16882 * 0.001),  # Estimativa local
            
            # Metadados
            'semana_epidemiologica': 9,
            'periodo': '01-07 março 2026',
            'fonte': 'InfoGripe/Fiocruz - Boletim SE 9/2026'
        }
        
        logger.info(f"✅ Dados 2026 carregados:")
        logger.info(f"   Total casos SRAG: {dados_reais_2026['total_casos_srag']:,}")
        logger.info(f"   Casos positivos: {dados_reais_2026['casos_positivos']:,}")
        logger.info(f"   Taxa positividade: {dados_reais_2026['taxa_positividade_geral']:.1%}")
        logger.info(f"   Fonte: {dados_reais_2026['fonte']}")
        
        return dados_reais_2026
    
    def calcular_prevalencia_regional(self, dados_2026: Dict) -> Dict[str, float]:
        """Calcular prevalência por patógeno baseada nos dados 2026"""
        
        logger.info("🔬 Calculando prevalência por patógeno...")
        
        # Aplicar distribuição viral aos dados regionais estimados
        casos_sp = dados_2026['casos_sp']
        taxa_positividade = dados_2026['taxa_positividade_geral']
        casos_positivos_sp = int(casos_sp * taxa_positividade)
        
        prevalencia = {
            'COVID19': dados_2026['COVID19'] * taxa_positividade,        # 15,8% dos positivos
            'INFLUENZA_A': dados_2026['INFLUENZA_A'] * taxa_positividade, # 20,8% dos positivos
            'INFLUENZA_B': dados_2026['INFLUENZA_B'] * taxa_positividade, # 1,2% dos positivos
            'VSR': dados_2026['VSR'] * taxa_positividade,                 # 13,5% dos positivos
            'RINOVIRUS': dados_2026['RINOVIRUS'] * taxa_positividade,     # 40,8% dos positivos
            'OUTROS': dados_2026['OUTROS'] * taxa_positividade,           # Outros
        }
        
        # Log dos resultados
        for patogeno, prev in prevalencia.items():
            logger.info(f"   {patogeno}: {prev:.3f} ({prev*100:.1f}%)")
        
        return prevalencia

class CalculadorPressaoEpidemiologica:
    """Calculador de VPN com sensibilidades CORRIGIDAS da literatura"""
    
    def __init__(self, config: ConfiguradorEpidemiologico):
        self.config = config
        
        # Mapeamento de sensibilidades por patógeno (CORRIGIDO)
        self.sensibilidades = {
            'COVID19': self.config.sensibilidade_antigeno_covid,      # 70%
            'INFLUENZA_A': self.config.sensibilidade_antigeno_flu_a,  # 62%
            'INFLUENZA_B': self.config.sensibilidade_antigeno_flu_b,  # 58%
            'VSR': self.config.sensibilidade_antigeno_vsr,            # 75%
            'RINOVIRUS': self.config.sensibilidade_antigeno_rinovirus, # 50%
            'OUTROS': 0.65  # Estimativa média para outros patógenos
        }
        
        logger.info("⚗️ SENSIBILIDADES CORRIGIDAS baseadas na literatura:")
        for patogeno, sens in self.sensibilidades.items():
            logger.info(f"   {patogeno}: {sens:.0%}")
    
    def calcular_vpn(self, prevalencia: float, patogeno: str = 'COVID19') -> float:
        """Calcular VPN específico por patógeno"""
        
        # Usar sensibilidade específica do patógeno
        sens = self.sensibilidades.get(patogeno, 0.70)  # Default COVID
        espec = self.config.especificidade_antigeno
        
        # Fórmula VPN = (Espec × (1 - Prev)) / (Espec × (1 - Prev) + (1 - Sens) × Prev)
        if prevalencia <= 0:
            return 1.0
        
        vpn = (espec * (1 - prevalencia)) / (espec * (1 - prevalencia) + (1 - sens) * prevalencia)
        return vpn
    
    def calcular_vpn_por_patogeno(self, prevalencia: Dict[str, float]) -> Dict[str, float]:
        """Calcular VPN para cada patógeno com sensibilidades específicas"""
        
        logger.info("🔍 Calculando VPN por patógeno (SENSIBILIDADES CORRIGIDAS)...")
        
        vpn_por_patogeno = {}
        for patogeno, prev in prevalencia.items():
            vpn = self.calcular_vpn(prev, patogeno)
            sens_usado = self.sensibilidades.get(patogeno, 0.70)
            vpn_por_patogeno[patogeno] = vpn
            logger.info(f"   VPN {patogeno}: {vpn:.1%} (Sens: {sens_usado:.0%})")
        
        return vpn_por_patogeno
    
    def classificar_pressao_epidemiologica(self, prevalencia: Dict[str, float]) -> Dict[str, str]:
        """Classificar pressão epidemiológica por patógeno"""
        
        logger.info("⚠️ Classificando pressão epidemiológica...")
        
        classificacao = {}
        
        for patogeno, valor in prevalencia.items():
            if valor < self.config.limiar_baixa_circulacao:
                nivel = "BAIXA"
                emoji = "🟢"
            elif valor < self.config.limiar_media_circulacao:
                nivel = "MODERADA"
                emoji = "🟡"
            elif valor < self.config.limiar_alta_circulacao:
                nivel = "ALTA"
                emoji = "🟠"
            else:
                nivel = "MUITO_ALTA"
                emoji = "🔴"
            
            classificacao[patogeno] = nivel
            logger.info(f"   {emoji} {patogeno}: {nivel} ({valor:.1%})")
        
        return classificacao

class OrientadorIsolamento:
    """Gerador de orientações com critérios AJUSTADOS para sensibilidades reais"""
    
    def __init__(self, config: ConfiguradorEpidemiologico):
        self.config = config
    
    def gerar_orientacao(self, vpn: float, pressao: str, patogeno: str = "") -> str:
        """
        Orientações AJUSTADAS para sensibilidades reais (menores)
        Com sensibilidades menores, os critérios de VPN devem ser mais rigorosos
        """
        
        # CRITÉRIOS AJUSTADOS para sensibilidades reais menores
        if vpn >= 0.95 and pressao in ["BAIXA"]:
            return "🟢 LIBERAÇÃO SEGURA - VPN alto com baixa circulação viral"
        
        elif vpn >= 0.92 and pressao == "BAIXA":
            return "🟡 LIBERAÇÃO ACEITÁVEL - VPN adequado, circulação baixa"
        
        elif vpn >= 0.90 and pressao == "BAIXA":
            return "🟠 LIBERAÇÃO COM CAUTELA - VPN limítrofe, avaliar contexto clínico"
        
        elif vpn >= 0.90 and pressao == "MODERADA":
            return "🟠 CAUTELA - VPN aceitável mas circulação moderada"
        
        elif pressao in ["ALTA", "MUITO_ALTA"]:
            return "🔴 MANTER ISOLAMENTO - Alta circulação viral regional"
        
        elif vpn < 0.85:
            return "🔴 ISOLAMENTO RECOMENDADO - VPN insuficiente (sensibilidade baixa)"
        
        else:
            return "📋 AVALIAÇÃO INDIVIDUALIZADA - Combinar VPN + critério clínico rigoroso"
    
    def gerar_orientacoes_completas(self, vpn_dados: Dict[str, float], 
                                  pressao_dados: Dict[str, str]) -> Dict[str, str]:
        """Gerar orientações para todos os patógenos"""
        
        logger.info("🏥 Gerando orientações de isolamento (CRITÉRIOS AJUSTADOS)...")
        
        orientacoes = {}
        
        for patogeno in vpn_dados.keys():
            vpn = vpn_dados[patogeno]
            pressao = pressao_dados[patogeno]
            orientacao = self.gerar_orientacao(vpn, pressao, patogeno)
            orientacoes[patogeno] = orientacao
            
            # Log resumido
            status_emoji = orientacao.split()[0]
            logger.info(f"   {status_emoji} {patogeno}: VPN {vpn:.1%} | Pressão {pressao}")
        
        return orientacoes

class SistemaVigilanciaRespiratoria2026Corrigido:
    """Sistema CORRIGIDO com sensibilidades da literatura"""
    
    def __init__(self, arquivo_config: str = "configuracao_vigilancia_corrigida.json"):
        
        # Configuração corrigida
        self.config = ConfiguradorEpidemiologico()
        
        # Inicializar componentes
        self.extractor = ExtractorDadosInfoGripe(self.config)
        self.calculador = CalculadorPressaoEpidemiologica(self.config)
        self.orientador = OrientadorIsolamento(self.config)
    
    def executar_analise_completa(self) -> Dict:
        """Executar análise completa com dados 2026 e sensibilidades CORRIGIDAS"""
        
        print("\n" + "="*90)
        print("🏥 SISTEMA VIGILÂNCIA RESPIRATÓRIA - HUSF BRAGANÇA PAULISTA")
        print("📊 DADOS REAIS INFOGRIPE/FIOCRUZ - MARÇO/2026")
        print("🔬 SENSIBILIDADES CORRIGIDAS BASEADAS EM META-ANÁLISES")
        print("="*90)
        
        logger.info("=== ANÁLISE COM SENSIBILIDADES CORRIGIDAS ===")
        
        try:
            # 1. Obter dados reais de 2026
            dados_2026 = self.extractor.obter_dados_atuais_2026()
            
            # 2. Calcular prevalência regional
            prevalencia = self.extractor.calcular_prevalencia_regional(dados_2026)
            
            # 3. Calcular VPN por patógeno (COM SENSIBILIDADES CORRIGIDAS)
            vpn_por_patogeno = self.calculador.calcular_vpn_por_patogeno(prevalencia)
            
            # 4. Classificar pressão epidemiológica
            pressao_epidemiologica = self.calculador.classificar_pressao_epidemiologica(prevalencia)
            
            # 5. Gerar orientações de isolamento (CRITÉRIOS AJUSTADOS)
            orientacoes = self.orientador.gerar_orientacoes_completas(vpn_por_patogeno, pressao_epidemiologica)
            
            # 6. Compilar resultados
            resultados = {
                'timestamp': datetime.now().isoformat(),
                'regiao': self.config.nome_regiao,
                'fonte_dados': dados_2026['fonte'],
                'semana_epidemiologica': dados_2026['semana_epidemiologica'],
                'periodo_analise': dados_2026['periodo'],
                'total_casos_nacionais': dados_2026['total_casos_srag'],
                'casos_positivos_nacionais': dados_2026['casos_positivos'],
                'taxa_positividade_nacional': dados_2026['taxa_positividade_geral'],
                'prevalencia_regional': prevalencia,
                'vpn_por_patogeno': vpn_por_patogeno,
                'pressao_epidemiologica': pressao_epidemiologica,
                'orientacoes_isolamento': orientacoes,
                'parametros_corrigidos': {
                    'covid_sensibilidade': self.config.sensibilidade_antigeno_covid,
                    'flu_a_sensibilidade': self.config.sensibilidade_antigeno_flu_a,
                    'flu_b_sensibilidade': self.config.sensibilidade_antigeno_flu_b,
                    'vsr_sensibilidade': self.config.sensibilidade_antigeno_vsr,
                    'especificidade': self.config.especificidade_antigeno,
                    'fonte_literatura': 'Meta-análises: Arshadi 2022, Chartrand 2012, Khalid 2022'
                },
                'observacao_importante': 'Sistema corrigido com sensibilidades baseadas em meta-análises recentes'
            }
            
            logger.info("=== ANÁLISE CORRIGIDA CONCLUÍDA ===")
            return resultados
            
        except Exception as e:
            logger.error(f"❌ Erro na análise: {e}")
            return None
    
    def gerar_relatorio_corrigido(self, resultados: Dict) -> str:
        """Gerar relatório com informações sobre correções"""
        
        timestamp = datetime.fromisoformat(resultados['timestamp'])
        
        relatorio = f"""
# RELATÓRIO EPIDEMIOLÓGICO SRAG - SENSIBILIDADES CORRIGIDAS
## {timestamp.strftime('%B/%Y')} - Semana Epidemiológica {resultados['semana_epidemiologica']}
## Hospital: HUSF - Bragança Paulista, SP
## Dr. Leandro - SCIH/CCIH

---

### ⚗️ CORREÇÕES IMPLEMENTADAS - BASE CIENTÍFICA

**SENSIBILIDADES ANTERIORES vs CORRIGIDAS:**
- **COVID-19**: ~~85%~~ → **70%** (Meta-análise 60 estudos, Arshadi 2022)
- **Influenza A**: ~~85%~~ → **62%** (Meta-análise 159 estudos, Chartrand 2012)  
- **Influenza B**: ~~85%~~ → **58%** (Meta-análise 159 estudos, Chartrand 2012)
- **VSR**: ~~85%~~ → **75%** (Estimativa literatura disponível)
- **Especificidade**: **98%** (mantida - consistente na literatura)

**Fonte das correções:** {resultados['parametros_corrigidos']['fonte_literatura']}

### 📊 SITUAÇÃO EPIDEMIOLÓGICA NACIONAL - MARÇO/2026

**Fonte:** {resultados['fonte_dados']}
**Período:** {resultados['periodo_analise']}

**Dados Nacionais:**
- **Total casos SRAG**: {resultados['total_casos_nacionais']:,}
- **Casos laboratorialmente positivos**: {resultados['casos_positivos_nacionais']:,}
- **Taxa de positividade**: {resultados['taxa_positividade_nacional']:.1%}

### 🔬 PREVALÊNCIA REGIONAL ESTIMADA ({resultados['regiao']})

**Prevalência por patógeno:**
- **COVID-19**: {resultados['prevalencia_regional']['COVID19']:.2%}
- **INFLUENZA A**: {resultados['prevalencia_regional']['INFLUENZA_A']:.2%}
- **INFLUENZA B**: {resultados['prevalencia_regional']['INFLUENZA_B']:.2%}
- **VSR**: {resultados['prevalencia_regional']['VSR']:.2%}
- **RINOVÍRUS**: {resultados['prevalencia_regional']['RINOVIRUS']:.2%}
- **OUTROS**: {resultados['prevalencia_regional']['OUTROS']:.2%}

### 🎯 VALOR PREDITIVO NEGATIVO - CORRIGIDO POR PATÓGENO

**VPN calculado com sensibilidades REAIS da literatura:**
- **COVID-19**: {resultados['vpn_por_patogeno']['COVID19']:.1%} (Sens: 70%)
- **INFLUENZA A**: {resultados['vpn_por_patogeno']['INFLUENZA_A']:.1%} (Sens: 62%)
- **INFLUENZA B**: {resultados['vpn_por_patogeno']['INFLUENZA_B']:.1%} (Sens: 58%)
- **VSR**: {resultados['vpn_por_patogeno']['VSR']:.1%} (Sens: 75%)
- **RINOVÍRUS**: {resultados['vpn_por_patogeno']['RINOVIRUS']:.1%} (Sens: 50%)
- **OUTROS**: {resultados['vpn_por_patogeno']['OUTROS']:.1%} (Sens: 65%)

### ⚠️ PRESSÃO EPIDEMIOLÓGICA REGIONAL

**Classificação por patógeno:**
- **COVID-19**: {resultados['pressao_epidemiologica']['COVID19']}
- **INFLUENZA A**: {resultados['pressao_epidemiologica']['INFLUENZA_A']}
- **INFLUENZA B**: {resultados['pressao_epidemiologica']['INFLUENZA_B']}
- **VSR**: {resultados['pressao_epidemiologica']['VSR']}
- **RINOVÍRUS**: {resultados['pressao_epidemiologica']['RINOVIRUS']}
- **OUTROS**: {resultados['pressao_epidemiologica']['OUTROS']}

### 🏥 ORIENTAÇÕES DE ISOLAMENTO - CRITÉRIOS AJUSTADOS

**COVID-19**: {resultados['orientacoes_isolamento']['COVID19']}

**INFLUENZA A**: {resultados['orientacoes_isolamento']['INFLUENZA_A']}

**INFLUENZA B**: {resultados['orientacoes_isolamento']['INFLUENZA_B']}

**VSR**: {resultados['orientacoes_isolamento']['VSR']}

**RINOVÍRUS**: {resultados['orientacoes_isolamento']['RINOVIRUS']}

**OUTROS**: {resultados['orientacoes_isolamento']['OUTROS']}

### 📚 IMPLICAÇÕES CLÍNICAS DAS CORREÇÕES

1. **VPN reduzido**: Sensibilidades menores resultam em VPN menores
2. **Critérios mais rigorosos**: Limiares de liberação ajustados para compensar
3. **Decisão clínica**: Maior peso no contexto individual do paciente
4. **Testes negativos**: Maior probabilidade de falsos-negativos
5. **Confirmação**: Considerar RT-PCR em casos duvidosos

### 💡 RECOMENDAÇÕES OPERACIONAIS ATUALIZADAS

1. **🔴 Isolamento Rigoroso**: Manter até confirmação em casos duvidosos
2. **📊 VPN ≥95%**: Necessário para liberação segura (critério mais restritivo)
3. **🔬 Confirmação**: RT-PCR recomendado quando VPN <90%
4. **👨‍⚕️ Julgamento Clínico**: Peso maior na decisão final
5. **📞 CCIH**: Dr. Leandro disponível para discussão de casos complexos

---
*Relatório gerado automaticamente em {timestamp.strftime('%d/%m/%Y %H:%M')}*
*Base: InfoGripe/Fiocruz - Dados reais brasileiros de março/2026*
*Sensibilidades corrigidas conforme meta-análises recentes*
*Sistema desenvolvido pela CCIH/SCIH - HUSF Bragança Paulista*
        """
        
        return relatorio.strip()

def main():
    """Função principal com sistema corrigido"""
    
    try:
        # Inicializar sistema corrigido
        sistema = SistemaVigilanciaRespiratoria2026Corrigido()
        
        # Executar análise
        resultados = sistema.executar_analise_completa()
        
        if resultados:
            # Salvar dados JSON
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            arquivo_dados = f"dados/vigilancia_corrigida_{timestamp}.json"
            
            with open(arquivo_dados, 'w', encoding='utf-8') as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False)
            
            # Gerar e salvar relatório
            relatorio = sistema.gerar_relatorio_corrigido(resultados)
            arquivo_relatorio = f"relatorios/relatorio_corrigido_{timestamp}.md"
            
            with open(arquivo_relatorio, 'w', encoding='utf-8') as f:
                f.write(relatorio)
            
            # Exibir resultados na tela
            print(f"\n📊 RESUMO EXECUTIVO - SENSIBILIDADES CORRIGIDAS:")
            print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            print(f"\n⚗️ CORREÇÕES IMPLEMENTADAS:")
            print(f"• COVID-19: 85% → 70% (Meta-análise)")
            print(f"• Influenza A: 85% → 62% (Meta-análise)")  
            print(f"• Influenza B: 85% → 58% (Meta-análise)")
            print(f"• VSR: 85% → 75% (Literatura)")
            
            print(f"\n🔬 VPN CORRIGIDO:")
            for patogeno, vpn in resultados['vpn_por_patogeno'].items():
                cor = "🟢" if vpn >= 0.95 else "🟡" if vpn >= 0.90 else "🔴"
                print(f"{cor} {patogeno:12}: {vpn:.1%}")
            
            print(f"\n🏥 ORIENTAÇÕES AJUSTADAS:")
            for patogeno, orientacao in resultados['orientacoes_isolamento'].items():
                status = orientacao.split()[0]  # Primeiro emoji
                acao = orientacao.split('- ')[0].replace(status, '').strip() if '- ' in orientacao else orientacao.split(maxsplit=2)[1:]
                if isinstance(acao, list):
                    acao = ' '.join(acao)
                print(f"{status} {patogeno:12}: {acao}")
            
            print(f"\n📁 ARQUIVOS GERADOS:")
            print(f"• Dados: {arquivo_dados}")
            print(f"• Relatório: {arquivo_relatorio}")
            
            print(f"\n" + "="*90)
            print("✅ SISTEMA CORRIGIDO COM SENSIBILIDADES DA LITERATURA!")
            print("📚 BASE CIENTÍFICA: Meta-análises recentes e amplas")
            print("🎯 ORIENTAÇÕES MAIS PRECISAS E SEGURAS")
            print("="*90)
            
        else:
            print("\n❌ FALHA NA ANÁLISE")
            print("💡 Verifique logs em logs/ para detalhes")
            
    except Exception as e:
        logger.error(f"❌ Erro no sistema: {e}")
        print(f"\n❌ ERRO CRÍTICO: {e}")

if __name__ == "__main__":
    main()
