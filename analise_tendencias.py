#!/usr/bin/env python3
"""
Análise Avançada de Tendências Epidemiológicas
===============================================

Módulo para análise de tendências temporais, predição de VPN e 
alertas epidemiológicos automatizados.

Autor: Dr. Leandro (HUSF)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

@dataclass
class ParametrosModelagem:
    """Parâmetros para modelagem preditiva"""
    
    # Janelas temporais
    janela_tendencia: int = 28  # dias para análise de tendência
    janela_predicao: int = 14   # dias para predição
    janela_minima_dados: int = 14  # mínimo de dados para análise
    
    # Thresholds de alerta
    threshold_aumento_critico: float = 1.5  # 50% de aumento
    threshold_reducao_significativa: float = 0.7  # 30% de redução
    
    # Parâmetros do modelo
    n_estimators: int = 100
    random_state: int = 42
    test_size: float = 0.3


class AnalisadorTendencias:
    """Analisador de tendências epidemiológicas temporais"""
    
    def __init__(self, parametros: Optional[ParametrosModelagem] = None):
        self.parametros = parametros or ParametrosModelagem()
        self.modelos_treinados = {}
        self.historico_predicoes = {}
    
    def carregar_dados_historicos(self, diretorio: str = '/var/lib/vigilancia_respiratoria') -> pd.DataFrame:
        """Carrega dados históricos para análise de tendências"""
        
        try:
            dados_completos = []
            arquivos_json = Path(diretorio).glob('vigilancia_*.json')
            
            for arquivo in sorted(arquivos_json):
                with open(arquivo, 'r') as f:
                    dados = json.load(f)
                    
                    # Extrair informações relevantes
                    registro = {
                        'data_analise': pd.to_datetime(dados['data_analise']),
                        'total_casos': dados['total_casos_analisados'],
                        'covid19_positividade': dados['positividade'].get('covid19', 0),
                        'influenza_positividade': dados['positividade'].get('influenza', 0),
                        'vsr_positividade': dados['positividade'].get('vsr', 0),
                        'outros_positividade': dados['positividade'].get('outros', 0),
                        'covid19_vpn': dados['vpn_valores'].get('covid19', {}).get('vpn', 0),
                        'influenza_vpn': dados['vpn_valores'].get('influenza', {}).get('vpn', 0)
                    }
                    
                    dados_completos.append(registro)
            
            if dados_completos:
                df = pd.DataFrame(dados_completos)
                df = df.sort_values('data_analise')
                logger.info(f"Carregados {len(df)} registros históricos")
                return df
            else:
                logger.warning("Nenhum dado histórico encontrado")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Erro ao carregar dados históricos: {str(e)}")
            return pd.DataFrame()
    
    def calcular_tendencias(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """Calcula tendências para cada patógeno"""
        
        if df.empty or len(df) < self.parametros.janela_minima_dados:
            logger.warning("Dados insuficientes para análise de tendências")
            return {}
        
        tendencias = {}
        patogenos = ['covid19', 'influenza', 'vsr', 'outros']
        
        for patogeno in patogenos:
            col_positividade = f'{patogeno}_positividade'
            
            if col_positividade not in df.columns:
                continue
            
            # Filtrar dados não-nulos
            dados_patogeno = df[df[col_positividade].notna()].copy()
            
            if len(dados_patogeno) < self.parametros.janela_minima_dados:
                continue
            
            # Calcular tendência linear
            x = np.arange(len(dados_patogeno))
            y = dados_patogeno[col_positividade].values
            
            if np.all(y == 0):
                slope, intercept, r_value, p_value = 0, 0, 0, 1
            else:
                slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            
            # Calcular médias móveis
            dados_patogeno['ma_7d'] = dados_patogeno[col_positividade].rolling(window=min(7, len(dados_patogeno))).mean()
            dados_patogeno['ma_14d'] = dados_patogeno[col_positividade].rolling(window=min(14, len(dados_patogeno))).mean()
            
            # Classificar tendência
            if p_value < 0.05:  # Significativa
                if slope > 0.001:  # Aumento > 0.1% por período
                    tendencia_classe = "CRESCENTE"
                elif slope < -0.001:  # Redução > 0.1% por período
                    tendencia_classe = "DECRESCENTE"
                else:
                    tendencia_classe = "ESTÁVEL"
            else:
                tendencia_classe = "INDEFINIDA"
            
            # Detectar mudanças recentes
            if len(dados_patogeno) >= 14:
                media_recente = dados_patogeno[col_positividade].tail(7).mean()
                media_anterior = dados_patogeno[col_positividade].tail(14).head(7).mean()
                
                if media_anterior > 0:
                    variacao_recente = (media_recente - media_anterior) / media_anterior
                else:
                    variacao_recente = 0
            else:
                variacao_recente = 0
            
            # Alerta de mudança crítica
            alerta = None
            if variacao_recente > (self.parametros.threshold_aumento_critico - 1):
                alerta = "AUMENTO_CRITICO"
            elif variacao_recente < (self.parametros.threshold_reducao_significativa - 1):
                alerta = "REDUCAO_SIGNIFICATIVA"
            
            tendencias[patogeno] = {
                'slope': slope,
                'r_squared': r_value**2,
                'p_value': p_value,
                'tendencia_classe': tendencia_classe,
                'variacao_recente': variacao_recente,
                'media_7d': dados_patogeno['ma_7d'].iloc[-1] if not dados_patogeno['ma_7d'].isna().iloc[-1] else 0,
                'media_14d': dados_patogeno['ma_14d'].iloc[-1] if not dados_patogeno['ma_14d'].isna().iloc[-1] else 0,
                'alerta': alerta,
                'num_observacoes': len(dados_patogeno)
            }
        
        return tendencias
    
    def prever_vpn_futuro(self, df: pd.DataFrame, patogeno: str, dias_predicao: int = 7) -> Dict:
        """Prediz VPN futuro baseado em tendências de positividade"""
        
        col_positividade = f'{patogeno}_positividade'
        col_vpn = f'{patogeno}_vpn'
        
        if col_positividade not in df.columns or col_vpn not in df.columns:
            return {}
        
        # Filtrar dados válidos
        dados_validos = df[[col_positividade, col_vpn]].dropna()
        
        if len(dados_validos) < self.parametros.janela_minima_dados:
            logger.warning(f"Dados insuficientes para predição de VPN - {patogeno}")
            return {}
        
        try:
            # Preparar features
            X = dados_validos[[col_positividade]]
            y = dados_validos[col_vpn]
            
            # Treinar modelo se necessário
            if patogeno not in self.modelos_treinados:
                rf_model = RandomForestRegressor(
                    n_estimators=self.parametros.n_estimators,
                    random_state=self.parametros.random_state
                )
                rf_model.fit(X, y)
                self.modelos_treinados[patogeno] = rf_model
            
            modelo = self.modelos_treinados[patogeno]
            
            # Prever VPN baseado na positividade atual
            positividade_atual = dados_validos[col_positividade].iloc[-1]
            vpn_atual_previsto = modelo.predict([[positividade_atual]])[0]
            
            # Simular cenários de positividade futura
            positividade_min = max(0, positividade_atual * 0.5)
            positividade_max = min(1, positividade_atual * 2)
            
            cenarios_positividade = np.linspace(positividade_min, positividade_max, 10)
            vpn_cenarios = modelo.predict(cenarios_positividade.reshape(-1, 1))
            
            # Calcular métricas de qualidade do modelo
            y_pred = modelo.predict(X)
            r2 = r2_score(y, y_pred)
            mae = mean_absolute_error(y, y_pred)
            
            return {
                'vpn_atual_previsto': vpn_atual_previsto,
                'positividade_atual': positividade_atual,
                'cenarios': {
                    'positividade': cenarios_positividade.tolist(),
                    'vpn_previsto': vpn_cenarios.tolist()
                },
                'qualidade_modelo': {
                    'r2_score': r2,
                    'mae': mae
                },
                'dias_predicao': dias_predicao
            }
            
        except Exception as e:
            logger.error(f"Erro na predição de VPN para {patogeno}: {str(e)}")
            return {}
    
    def gerar_alertas_automaticos(self, tendencias: Dict, predicoes_vpn: Dict) -> List[Dict]:
        """Gera alertas automáticos baseados em tendências e predições"""
        
        alertas = []
        
        for patogeno, dados_tendencia in tendencias.items():
            # Alerta por tendência
            if dados_tendencia.get('alerta'):
                if dados_tendencia['alerta'] == 'AUMENTO_CRITICO':
                    alertas.append({
                        'tipo': 'AUMENTO_CRITICO',
                        'patogeno': patogeno,
                        'severidade': 'ALTA',
                        'mensagem': f"Aumento crítico de {dados_tendencia['variacao_recente']:.1%} na positividade de {patogeno}",
                        'recomendacao': "Reforçar medidas de isolamento precaucional",
                        'timestamp': datetime.now().isoformat()
                    })
                
                elif dados_tendencia['alerta'] == 'REDUCAO_SIGNIFICATIVA':
                    alertas.append({
                        'tipo': 'REDUCAO_SIGNIFICATIVA',
                        'patogeno': patogeno,
                        'severidade': 'BAIXA',
                        'mensagem': f"Redução significativa de {abs(dados_tendencia['variacao_recente']):.1%} na positividade de {patogeno}",
                        'recomendacao': "Considerar flexibilização gradual de protocolos",
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Alerta por VPN baixo predito
            if patogeno in predicoes_vpn:
                vpn_predito = predicoes_vpn[patogeno].get('vpn_atual_previsto', 0)
                if vpn_predito < 0.85:
                    alertas.append({
                        'tipo': 'VPN_BAIXO',
                        'patogeno': patogeno,
                        'severidade': 'MEDIA',
                        'mensagem': f"VPN predito baixo para {patogeno}: {vpn_predito:.1%}",
                        'recomendacao': "Considerar testes confirmatórios adicionais",
                        'timestamp': datetime.now().isoformat()
                    })
        
        return alertas
    
    def gerar_relatorio_tendencias(self, tendencias: Dict, predicoes_vpn: Dict, alertas: List[Dict]) -> str:
        """Gera relatório completo de análise de tendências"""
        
        relatorio = f"""
# ANÁLISE DE TENDÊNCIAS EPIDEMIOLÓGICAS
## Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

---

## TENDÊNCIAS POR PATÓGENO

"""
        
        for patogeno, dados in tendencias.items():
            relatorio += f"""
### {patogeno.upper()}

**Tendência geral**: {dados['tendência_classe']}  
**Variação recente (7 dias)**: {dados['variacao_recente']:.1%}  
**Média móvel 7 dias**: {dados['media_7d']:.1%}  
**Média móvel 14 dias**: {dados['media_14d']:.1%}  
**Significância estatística**: p = {dados['p_value']:.3f}  
**R²**: {dados['r_squared']:.3f}  

"""
            
            if dados.get('alerta'):
                relatorio += f"**⚠️ ALERTA**: {dados['alerta']}\n\n"
        
        # Predições VPN
        relatorio += "\n## PREDIÇÕES DE VPN\n\n"
        
        for patogeno, predicao in predicoes_vpn.items():
            if predicao:
                relatorio += f"""
### {patogeno.upper()}

**VPN atual predito**: {predicao['vpn_atual_previsto']:.1%}  
**Positividade atual**: {predicao['positividade_atual']:.1%}  
**Qualidade do modelo (R²)**: {predicao['qualidade_modelo']['r2_score']:.3f}  

"""
        
        # Alertas automáticos
        if alertas:
            relatorio += "\n## 🚨 ALERTAS AUTOMÁTICOS\n\n"
            
            for alerta in alertas:
                severidade_emoji = {'ALTA': '🔴', 'MEDIA': '🟡', 'BAIXA': '🟢'}
                emoji = severidade_emoji.get(alerta['severidade'], '⚪')
                
                relatorio += f"""
{emoji} **{alerta['tipo']}** - {alerta['patogeno'].upper()}  
*Severidade*: {alerta['severidade']}  
*Mensagem*: {alerta['mensagem']}  
*Recomendação*: {alerta['recomendacao']}  

"""
        
        relatorio += f"""
---
*Análise gerada automaticamente pelo Sistema de Vigilância Respiratória - HUSF*  
*Responsável: Dr. Leandro - CCIH*
"""
        
        return relatorio
    
    def criar_graficos_tendencias(self, df: pd.DataFrame, salvar_como: str = '/home/claude/tendencias_epidemiologicas.png') -> None:
        """Cria gráficos de tendências temporais"""
        
        if df.empty:
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        patogenos = ['covid19', 'influenza', 'vsr', 'outros']
        cores = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
        
        for i, (patogeno, cor) in enumerate(zip(patogenos, cores)):
            row, col = i // 2, i % 2
            ax = axes[row, col]
            
            col_positividade = f'{patogeno}_positividade'
            
            if col_positividade in df.columns:
                # Dados válidos
                dados_validos = df[df[col_positividade].notna()]
                
                if not dados_validos.empty:
                    # Gráfico principal
                    ax.plot(dados_validos['data_analise'], dados_validos[col_positividade] * 100, 
                           color=cor, linewidth=2, marker='o', markersize=4, label='Positividade')
                    
                    # Média móvel
                    if len(dados_validos) >= 7:
                        ma_7d = dados_validos[col_positividade].rolling(window=7).mean()
                        ax.plot(dados_validos['data_analise'], ma_7d * 100, 
                               color=cor, linestyle='--', alpha=0.7, label='Média móvel 7d')
                    
                    # Linha de tendência
                    if len(dados_validos) >= 3:
                        x_numeric = np.arange(len(dados_validos))
                        z = np.polyfit(x_numeric, dados_validos[col_positividade] * 100, 1)
                        p = np.poly1d(z)
                        ax.plot(dados_validos['data_analise'], p(x_numeric), 
                               color='red', linestyle=':', alpha=0.8, label='Tendência')
            
            ax.set_title(f'{patogeno.upper()} - Positividade Temporal', fontweight='bold')
            ax.set_ylabel('Positividade (%)')
            ax.tick_params(axis='x', rotation=45)
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.suptitle('Análise de Tendências Epidemiológicas - HUSF', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(salvar_como, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Gráficos de tendências salvos em: {salvar_como}")


class SistemaInteligentePreditivo:
    """Sistema integrado de análise preditiva para vigilância respiratória"""
    
    def __init__(self, parametros: Optional[ParametrosModelagem] = None):
        self.analisador = AnalisadorTendencias(parametros)
        self.parametros = parametros or ParametrosModelagem()
    
    def executar_analise_preditiva_completa(self) -> Dict:
        """Executa análise preditiva completa"""
        
        logger.info("Iniciando análise preditiva epidemiológica...")
        
        # Carregar dados históricos
        df_historico = self.analisador.carregar_dados_historicos()
        
        if df_historico.empty:
            logger.warning("Sem dados históricos suficientes para análise preditiva")
            return {
                'erro': 'Dados históricos insuficientes',
                'recomendacao': 'Aguardar acúmulo de mais dados (mínimo 14 dias)'
            }
        
        # Calcular tendências
        tendencias = self.analisador.calcular_tendencias(df_historico)
        
        # Fazer predições de VPN
        predicoes_vpn = {}
        for patogeno in ['covid19', 'influenza', 'vsr', 'outros']:
            predicao = self.analisador.prever_vpn_futuro(df_historico, patogeno)
            if predicao:
                predicoes_vpn[patogeno] = predicao
        
        # Gerar alertas
        alertas = self.analisador.gerar_alertas_automaticos(tendencias, predicoes_vpn)
        
        # Gerar relatório
        relatorio = self.analisador.gerar_relatorio_tendencias(tendencias, predicoes_vpn, alertas)
        
        # Criar gráficos
        self.analisador.criar_graficos_tendencias(df_historico)
        
        resultado_completo = {
            'timestamp': datetime.now().isoformat(),
            'dados_analisados': len(df_historico),
            'periodo_analise': f"{df_historico['data_analise'].min().strftime('%d/%m/%Y')} a {df_historico['data_analise'].max().strftime('%d/%m/%Y')}",
            'tendencias': tendencias,
            'predicoes_vpn': predicoes_vpn,
            'alertas': alertas,
            'relatorio': relatorio,
            'qualidade_analise': {
                'dados_suficientes': len(df_historico) >= self.parametros.janela_minima_dados,
                'periodo_minimo': (df_historico['data_analise'].max() - df_historico['data_analise'].min()).days >= self.parametros.janela_minima_dados
            }
        }
        
        logger.info(f"Análise preditiva concluída: {len(alertas)} alertas gerados")
        return resultado_completo


# Exemplo de uso
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    # Inicializar sistema preditivo
    sistema = SistemaInteligentePreditivo()
    
    # Executar análise
    resultado = sistema.executar_analise_preditiva_completa()
    
    if 'erro' not in resultado:
        print("\n" + "="*60)
        print("ANÁLISE PREDITIVA EPIDEMIOLÓGICA")
        print("="*60)
        
        print(f"Período analisado: {resultado['periodo_analise']}")
        print(f"Total de dados: {resultado['dados_analisados']} registros")
        print(f"Alertas gerados: {len(resultado['alertas'])}")
        
        if resultado['alertas']:
            print("\n🚨 ALERTAS PRIORITÁRIOS:")
            for alerta in resultado['alertas']:
                print(f"• {alerta['tipo']} - {alerta['patogeno'].upper()}: {alerta['mensagem']}")
        
        print("\n" + resultado['relatorio'])
        
        # Salvar resultado
        with open('/home/claude/analise_preditiva_result.json', 'w') as f:
            json.dump(resultado, f, indent=2, default=str)
        
        print(f"\nResultados salvos em: analise_preditiva_result.json")
    else:
        print(f"Erro na análise: {resultado['erro']}")
        print(f"Recomendação: {resultado['recomendacao']}")
