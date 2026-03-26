#!/usr/bin/env python3
"""
Demonstração do Sistema de Vigilância Respiratória com Dados Simulados
======================================================================

Este script demonstra o funcionamento completo do sistema de vigilância
respiratória usando dados simulados que reproduzem cenários reais.

Autor: Dr. Leandro (HUSF)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
import sys
import os
from pathlib import Path

# Importar sistema de vigilância
from sistema_vigilancia_respiratoria import (
    ConfiguradorEpidemiologico,
    CalculadorPressaoEpidemiologica,
    OrientadorIsolamento
)

class GeradorDadosSimulados:
    """Gerador de dados SRAG simulados para demonstração"""
    
    def __init__(self):
        self.data_base = datetime.now() - timedelta(days=30)
    
    def gerar_dados_srag_simulados(self, num_casos: int = 500) -> pd.DataFrame:
        """Gera dados SRAG simulados baseados na estrutura real do SIVEP-Gripe"""
        
        np.random.seed(42)  # Para resultados reproduzíveis
        
        dados = []
        
        for i in range(num_casos):
            # Data aleatória nos últimos 30 dias
            dias_atras = np.random.randint(0, 30)
            data_sintomas = self.data_base + timedelta(days=dias_atras)
            
            # Simular resultados de PCR com prevalências realistas
            # COVID-19: ~15% de positividade
            covid_positivo = np.random.random() < 0.15
            
            # Influenza: ~8% de positividade
            influenza_positivo = np.random.random() < 0.08 and not covid_positivo
            
            # VSR: ~5% de positividade
            vsr_positivo = np.random.random() < 0.05 and not covid_positivo and not influenza_positivo
            
            # Outros vírus: ~3% de positividade
            outros_positivo = np.random.random() < 0.03 and not any([covid_positivo, influenza_positivo, vsr_positivo])
            
            # Resultados negativos
            pcr_resultado = '1' if any([covid_positivo, influenza_positivo, vsr_positivo, outros_positivo]) else '2'
            
            # Classificação final
            if covid_positivo:
                classi_fin = '5'  # SRAG por COVID-19
            elif influenza_positivo:
                classi_fin = '1'  # SRAG por influenza
            elif vsr_positivo or outros_positivo:
                classi_fin = '2'  # SRAG por outro vírus respiratório
            else:
                classi_fin = '4'  # SRAG não especificado
            
            registro = {
                'DT_SIN_PRI': data_sintomas.strftime('%d/%m/%Y'),
                'DT_NOTIFIC': (data_sintomas + timedelta(days=np.random.randint(1, 7))).strftime('%d/%m/%Y'),
                'CO_MUN_RES': '3543402',  # Campinas
                'SG_UF': '35',  # SP
                'PCR_RESUL': pcr_resultado,
                'PCR_SARS2': '1' if covid_positivo else '2',
                'POS_PCRFLU': '1' if influenza_positivo else '2',
                'PCR_VSR': '1' if vsr_positivo else '2',
                'CLASSI_FIN': classi_fin,
                'NU_IDADE_N': np.random.randint(18, 90),
                'CS_SEXO': np.random.choice(['1', '2']),  # M/F
                'EVOLUCAO': np.random.choice(['1', '2'], p=[0.85, 0.15])  # Cura/Óbito
            }
            
            dados.append(registro)
        
        df = pd.DataFrame(dados)
        df['DT_SIN_PRI'] = pd.to_datetime(df['DT_SIN_PRI'], format='%d/%m/%Y')
        
        return df


class DemonstradorSistema:
    """Demonstrador do sistema completo com dados simulados"""
    
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Configuração para HUSF
        self.config = ConfiguradorEpidemiologico(
            codigo_municipio="3543402",
            codigo_estado="35",
            nome_regiao="HUSF - Campinas (DEMONSTRAÇÃO)",
            sensibilidade_antigeno=0.85,
            especificidade_antigeno=0.98,
            limiar_baixa_circulacao=0.05,
            limiar_media_circulacao=0.15,
            limiar_alta_circulacao=0.25
        )
        
        self.gerador = GeradorDadosSimulados()
        self.calculador = CalculadorPressaoEpidemiologica(self.config)
        self.orientador = OrientadorIsolamento(self.config)
    
    def executar_demonstracao_completa(self) -> dict:
        """Executa demonstração completa do sistema"""
        
        self.logger.info("=== INICIANDO DEMONSTRAÇÃO DO SISTEMA DE VIGILÂNCIA ===")
        
        # 1. Gerar dados simulados
        self.logger.info("Gerando dados SRAG simulados...")
        dados_srag = self.gerador.gerar_dados_srag_simulados(500)
        self.logger.info(f"✓ {len(dados_srag)} casos simulados gerados")
        
        # 2. Calcular positividade
        self.logger.info("Calculando positividade por patógeno...")
        positividade = self.calculador.calcular_positividade_regional(dados_srag)
        
        if not positividade:
            self.logger.error("Falha no cálculo de positividade")
            return {}
        
        # 3. Calcular VPN
        self.logger.info("Calculando VPN para cada patógeno...")
        valores_vpn = {}
        for patogeno, taxa in positividade.items():
            valores_vpn[patogeno] = self.calculador.calcular_vpn_teste_antigenio(taxa)
        
        # 4. Classificar pressão epidemiológica
        self.logger.info("Classificando pressão epidemiológica...")
        pressao_epidemiologica = self.calculador.classificar_pressao_epidemiologica(positividade)
        
        # 5. Gerar orientações
        self.logger.info("Gerando orientações de isolamento...")
        orientacoes = self.orientador.gerar_orientacao_vpn(valores_vpn, pressao_epidemiologica)
        
        # 6. Estatísticas dos dados simulados
        stats_dados = {
            'total_casos': len(dados_srag),
            'periodo_inicio': dados_srag['DT_SIN_PRI'].min().strftime('%d/%m/%Y'),
            'periodo_fim': dados_srag['DT_SIN_PRI'].max().strftime('%d/%m/%Y'),
            'covid_casos': len(dados_srag[dados_srag['PCR_SARS2'] == '1']),
            'influenza_casos': len(dados_srag[dados_srag['POS_PCRFLU'] == '1']),
            'vsr_casos': len(dados_srag[dados_srag['PCR_VSR'] == '1']),
            'testados_pcr': len(dados_srag[dados_srag['PCR_RESUL'].isin(['1', '2'])])
        }
        
        # 7. Compilar resultados
        resultados = {
            'data_demonstracao': datetime.now().isoformat(),
            'tipo_dados': 'SIMULADOS',
            'configuracao': {
                'hospital': self.config.nome_regiao,
                'sensibilidade_teste': self.config.sensibilidade_antigeno,
                'especificidade_teste': self.config.especificidade_antigeno
            },
            'estatisticas_dados': stats_dados,
            'positividade': positividade,
            'vpn_valores': valores_vpn,
            'pressao_epidemiologica': pressao_epidemiologica,
            'orientacoes': orientacoes,
            'relatorio': self.orientador.gerar_relatorio_mensal(dados_srag, positividade, orientacoes)
        }
        
        self.logger.info("=== DEMONSTRAÇÃO CONCLUÍDA COM SUCESSO ===")
        return resultados
    
    def exibir_resultados(self, resultados: dict) -> None:
        """Exibe resultados da demonstração de forma organizada"""
        
        if not resultados:
            print("❌ Não há resultados para exibir")
            return
        
        print("\n" + "="*80)
        print("SISTEMA DE VIGILÂNCIA RESPIRATÓRIA - DEMONSTRAÇÃO")
        print("="*80)
        
        stats = resultados['estatisticas_dados']
        print(f"\n📊 DADOS ANALISADOS:")
        print(f"• Total de casos simulados: {stats['total_casos']}")
        print(f"• Período: {stats['periodo_inicio']} a {stats['periodo_fim']}")
        print(f"• Casos COVID-19: {stats['covid_casos']} ({stats['covid_casos']/stats['total_casos']*100:.1f}%)")
        print(f"• Casos Influenza: {stats['influenza_casos']} ({stats['influenza_casos']/stats['total_casos']*100:.1f}%)")
        print(f"• Casos VSR: {stats['vsr_casos']} ({stats['vsr_casos']/stats['total_casos']*100:.1f}%)")
        
        print(f"\n📈 POSITIVIDADE POR PATÓGENO:")
        for patogeno, taxa in resultados['positividade'].items():
            print(f"• {patogeno.upper()}: {taxa:.1%}")
        
        print(f"\n🔬 VALOR PREDITIVO NEGATIVO (VPN):")
        for patogeno, vpn_data in resultados['vpn_valores'].items():
            vpn = vpn_data['vpn']
            print(f"• {patogeno.upper()}: {vpn:.1%}")
        
        print(f"\n⚠️ PRESSÃO EPIDEMIOLÓGICA:")
        for patogeno, pressao in resultados['pressao_epidemiologica'].items():
            pressao_emoji = {'BAIXA': '🟢', 'MODERADA': '🟡', 'ALTA': '🟠', 'MUITO ALTA': '🔴'}
            emoji = pressao_emoji.get(pressao, '⚪')
            print(f"{emoji} {patogeno.upper()}: {pressao}")
        
        print(f"\n🏥 ORIENTAÇÕES DE ISOLAMENTO:")
        for patogeno, orientacao in resultados['orientacoes'].items():
            print(f"• {patogeno.upper()}: {orientacao}")
        
        print(f"\n📄 RELATÓRIO COMPLETO:")
        print(resultados['relatorio'])
    
    def salvar_resultados(self, resultados: dict) -> str:
        """Salva resultados da demonstração"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        arquivo = f'/home/claude/demonstracao_vigilancia_{timestamp}.json'
        
        try:
            with open(arquivo, 'w', encoding='utf-8') as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False, default=str)
            
            self.logger.info(f"✓ Resultados salvos em: {arquivo}")
            return arquivo
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar resultados: {e}")
            return ""
    
    def gerar_visualizacao_demo(self, resultados: dict) -> None:
        """Gera visualização dos resultados da demonstração"""
        
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            plt.style.use('seaborn-v0_8')
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # Cores padronizadas
            cores = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
            
            # 1. Positividade
            patogenos = list(resultados['positividade'].keys())
            positividades = [resultados['positividade'][p] * 100 for p in patogenos]
            
            bars1 = ax1.bar(patogenos, positividades, color=cores)
            ax1.set_title('Positividade por Patógeno (%)', fontweight='bold', fontsize=14)
            ax1.set_ylabel('Positividade (%)')
            ax1.tick_params(axis='x', rotation=45)
            
            # Adicionar valores nas barras
            for bar, val in zip(bars1, positividades):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{val:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            # 2. VPN
            vpn_valores = [resultados['vpn_valores'][p]['vpn'] * 100 for p in patogenos]
            
            bars2 = ax2.bar(patogenos, vpn_valores, color=['#FFB347', '#98D8E8', '#F7DC6F', '#BB8FCE'])
            ax2.set_title('Valor Preditivo Negativo (%)', fontweight='bold', fontsize=14)
            ax2.set_ylabel('VPN (%)')
            ax2.axhline(y=90, color='red', linestyle='--', alpha=0.7, label='Limiar 90%')
            ax2.axhline(y=95, color='green', linestyle='--', alpha=0.7, label='Limiar 95%')
            ax2.legend()
            ax2.tick_params(axis='x', rotation=45)
            ax2.set_ylim(80, 100)
            
            # Adicionar valores nas barras
            for bar, val in zip(bars2, vpn_valores):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{val:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            # 3. Pressão epidemiológica (heatmap)
            pressao_map = {'BAIXA': 1, 'MODERADA': 2, 'ALTA': 3, 'MUITO ALTA': 4}
            pressao_valores = [pressao_map.get(resultados['pressao_epidemiologica'][p], 0) for p in patogenos]
            
            im = ax3.imshow([pressao_valores], cmap='RdYlGn_r', aspect='auto')
            ax3.set_title('Pressão Epidemiológica', fontweight='bold', fontsize=14)
            ax3.set_xticks(range(len(patogenos)))
            ax3.set_xticklabels(patogenos, rotation=45)
            ax3.set_yticks([])
            
            # 4. Resumo estatístico
            ax4.axis('off')
            stats = resultados['estatisticas_dados']
            
            resumo_text = f"""
DEMONSTRAÇÃO - DADOS SIMULADOS

Total de casos: {stats['total_casos']}
Período: {stats['periodo_inicio']} a {stats['periodo_fim']}

CASOS POR PATÓGENO:
• COVID-19: {stats['covid_casos']} ({stats['covid_casos']/stats['total_casos']*100:.1f}%)
• Influenza: {stats['influenza_casos']} ({stats['influenza_casos']/stats['total_casos']*100:.1f}%)
• VSR: {stats['vsr_casos']} ({stats['vsr_casos']/stats['total_casos']*100:.1f}%)

PARÂMETROS DO TESTE:
• Sensibilidade: {resultados['configuracao']['sensibilidade_teste']:.0%}
• Especificidade: {resultados['configuracao']['especificidade_teste']:.0%}

Hospital: {resultados['configuracao']['hospital']}
"""
            
            ax4.text(0.05, 0.95, resumo_text, transform=ax4.transAxes, fontsize=11,
                    verticalalignment='top', fontfamily='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
            
            plt.suptitle('Sistema de Vigilância Respiratória - DEMONSTRAÇÃO', 
                        fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            # Salvar
            plt.savefig('/home/claude/demo_dashboard_vigilancia.png', dpi=300, bbox_inches='tight')
            self.logger.info("✓ Visualização salva: demo_dashboard_vigilancia.png")
            plt.close()
            
        except ImportError:
            self.logger.warning("Matplotlib não disponível - pulando visualização")
        except Exception as e:
            self.logger.error(f"Erro na visualização: {e}")


def main():
    """Função principal da demonstração"""
    
    print("="*80)
    print("DEMONSTRAÇÃO DO SISTEMA DE VIGILÂNCIA RESPIRATÓRIA")
    print("="*80)
    print("\nEste é um exemplo com dados simulados que reproduzem cenários reais")
    print("de análise epidemiológica para orientação de isolamento respiratório.\n")
    
    # Inicializar demonstrador
    demo = DemonstradorSistema()
    
    # Executar demonstração
    resultados = demo.executar_demonstracao_completa()
    
    if resultados:
        # Exibir resultados
        demo.exibir_resultados(resultados)
        
        # Salvar resultados
        arquivo = demo.salvar_resultados(resultados)
        
        # Gerar visualização
        demo.gerar_visualizacao_demo(resultados)
        
        print(f"\n✅ DEMONSTRAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"📁 Arquivo salvo: {Path(arquivo).name}")
        print(f"📊 Dashboard: demo_dashboard_vigilancia.png")
        
    else:
        print("❌ Falha na demonstração")


if __name__ == "__main__":
    main()
