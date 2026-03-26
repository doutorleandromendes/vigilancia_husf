#!/usr/bin/env python3
"""
Sistema de Vigilância Respiratória - HUSF Bragança Paulista
Extração de dados SIVEP-Gripe e cálculo de VPN para orientação de isolamento

Dr. Leandro - SCIH/CCIH
"""

import pandas as pd
import numpy as np
import requests
import json
import logging
import os
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ConfiguradorEpidemiologico:
    """Configurações epidemiológicas e de teste"""
    codigo_municipio: str = "3507605"  # Bragança Paulista-SP (IBGE)
    codigo_estado: str = "35"
    nome_regiao: str = "Bragança Paulista"
    sensibilidade_antigeno: float = 0.85
    especificidade_antigeno: float = 0.98
    limiar_baixa_circulacao: float = 0.05
    limiar_media_circulacao: float = 0.15
    limiar_alta_circulacao: float = 0.25
    janela_analise_dias: int = 14
    janela_tendencia_dias: int = 28

class ExtractorDadosEpidemiologicos:
    """Extrator de dados do SIVEP-Gripe via OpenDataSUS"""
    
    def __init__(self, config: ConfiguradorEpidemiologico):
        self.config = config
        self.url_base_srag = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG"
        self.timeout = 60
        
        # Criar diretórios necessários
        os.makedirs("dados", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        os.makedirs("relatorios", exist_ok=True)
    
    def obter_url_arquivo_atual(self, ano: int = None) -> str:
        """Gerar URL do arquivo SIVEP-Gripe mais recente"""
        if ano is None:
            ano = datetime.now().year
        
        # Nome padrão do arquivo (pode variar a data)
        # Exemplo: INFLUD25-03-03-2025.csv (INFLUD + ano + data de atualização)
        ano_abrev = str(ano)[-2:]  # Últimos 2 dígitos do ano
        
        # Para 2026, tentar algumas variações de nome
        possveis_nomes = [
            f"INFLUD{ano_abrev}-03-20-{ano}.csv",
            f"INFLUD{ano_abrev}-03-19-{ano}.csv", 
            f"INFLUD{ano_abrev}-03-18-{ano}.csv",
            f"INFLUD{ano_abrev}-{datetime.now().month:02d}-{datetime.now().day:02d}-{ano}.csv",
            f"INFLUD{ano_abrev}.csv"
        ]
        
        for nome in possveis_nomes:
            url = f"{self.url_base_srag}/{ano}/{nome}"
            try:
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"✓ Arquivo encontrado: {nome}")
                    return url
            except:
                continue
                
        # Fallback para nome genérico
        return f"{self.url_base_srag}/{ano}/INFLUD{ano_abrev}.csv"
    
    def baixar_dados_sivep(self, ano: int = None, forcar_download: bool = False) -> Optional[pd.DataFrame]:
        """Download dos dados SIVEP-Gripe"""
        
        if ano is None:
            ano = datetime.now().year
        
        arquivo_local = f"dados/sivep_srag_{ano}.csv"
        
        # Verificar se já existe arquivo local recente (menos de 7 dias)
        if os.path.exists(arquivo_local) and not forcar_download:
            mod_time = os.path.getmtime(arquivo_local)
            if (datetime.now().timestamp() - mod_time) < (7 * 24 * 3600):  # 7 dias
                logger.info(f"📁 Usando arquivo local: {arquivo_local}")
                try:
                    return pd.read_csv(arquivo_local, encoding='utf-8', low_memory=False)
                except:
                    logger.warning("Arquivo local corrompido, baixando novamente...")
        
        # Download do arquivo
        url = self.obter_url_arquivo_atual(ano)
        logger.info(f"📥 Baixando dados SIVEP-Gripe: {url}")
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Salvar arquivo local
            with open(arquivo_local, 'wb') as f:
                f.write(response.content)
            
            # Ler dados
            df = pd.read_csv(arquivo_local, encoding='utf-8', low_memory=False)
            
            logger.info(f"✓ Dados baixados: {len(df)} registros")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro no download: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao processar dados: {e}")
            return None
    
    def filtrar_dados_regiao(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filtrar dados para a região de interesse"""
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Filtrar por município (Bragança Paulista) 
        df_filtrado = df[df['CO_MUN_RES'] == self.config.codigo_municipio].copy()
        
        if df_filtrado.empty:
            # Se não encontrar dados do município específico, usar estado (SP)
            logger.warning(f"⚠️ Nenhum caso encontrado para Bragança Paulista (código {self.config.codigo_municipio})")
            df_filtrado = df[df['SG_UF'] == 'SP'].copy()
            logger.info(f"📊 Usando dados do estado de SP: {len(df_filtrado)} casos")
        
        # Filtrar por período (últimas X semanas)
        if 'DT_SIN_PRI' in df_filtrado.columns:
            try:
                df_filtrado['DT_SIN_PRI'] = pd.to_datetime(df_filtrado['DT_SIN_PRI'], errors='coerce')
                data_corte = datetime.now() - timedelta(days=self.config.janela_analise_dias)
                df_filtrado = df_filtrado[df_filtrado['DT_SIN_PRI'] >= data_corte]
            except:
                logger.warning("⚠️ Erro ao filtrar por data de sintomas")
        
        logger.info(f"✓ Dados filtrados: {len(df_filtrado)} casos na região")
        return df_filtrado

class CalculadorPressaoEpidemiologica:
    """Calculador de positividade e VPN por patógeno"""
    
    def __init__(self, config: ConfiguradorEpidemiologico):
        self.config = config
    
    def calcular_positividade_por_patogeno(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcular positividade por patógeno"""
        
        if df.empty:
            return {
                'COVID19': 0.0,
                'INFLUENZA': 0.0, 
                'VSR': 0.0,
                'OUTROS': 0.0
            }
        
        total_casos = len(df)
        positividade = {}
        
        # COVID-19: PCR_SARS2 == 1 OU CLASSI_FIN == 5
        covid_positivos = 0
        if 'PCR_SARS2' in df.columns:
            covid_positivos += len(df[df['PCR_SARS2'] == 1])
        if 'CLASSI_FIN' in df.columns:
            covid_positivos += len(df[df['CLASSI_FIN'] == 5])
        positividade['COVID19'] = covid_positivos / total_casos
        
        # Influenza: POS_PCRFLU == 1 OU CLASSI_FIN == 1  
        influenza_positivos = 0
        if 'POS_PCRFLU' in df.columns:
            influenza_positivos += len(df[df['POS_PCRFLU'] == 1])
        if 'CLASSI_FIN' in df.columns:
            influenza_positivos += len(df[df['CLASSI_FIN'] == 1])
        positividade['INFLUENZA'] = influenza_positivos / total_casos
        
        # VSR: PCR_VSR == 1
        vsr_positivos = 0
        if 'PCR_VSR' in df.columns:
            vsr_positivos = len(df[df['PCR_VSR'] == 1])
        positividade['VSR'] = vsr_positivos / total_casos
        
        # Outros vírus: CLASSI_FIN == 2
        outros_positivos = 0
        if 'CLASSI_FIN' in df.columns:
            outros_positivos = len(df[df['CLASSI_FIN'] == 2])
        positividade['OUTROS'] = outros_positivos / total_casos
        
        logger.info(f"📊 Positividade calculada para {total_casos} testes")
        return positividade
    
    def calcular_vpn(self, prevalencia: float) -> float:
        """Calcular Valor Preditivo Negativo"""
        sens = self.config.sensibilidade_antigeno
        espec = self.config.especificidade_antigeno
        
        # Fórmula VPN = (Espec × (1 - Prev)) / (Espec × (1 - Prev) + (1 - Sens) × Prev)
        vpn = (espec * (1 - prevalencia)) / (espec * (1 - prevalencia) + (1 - sens) * prevalencia)
        return vpn
    
    def classificar_pressao_epidemiologica(self, positividade: Dict[str, float]) -> Dict[str, str]:
        """Classificar pressão epidemiológica por patógeno"""
        
        classificacao = {}
        
        for patogeno, valor in positividade.items():
            if valor < self.config.limiar_baixa_circulacao:
                classificacao[patogeno] = "BAIXA"
            elif valor < self.config.limiar_media_circulacao:
                classificacao[patogeno] = "MODERADA"
            elif valor < self.config.limiar_alta_circulacao:
                classificacao[patogeno] = "ALTA"
            else:
                classificacao[patogeno] = "MUITO_ALTA"
        
        return classificacao

class OrientadorIsolamento:
    """Gerador de orientações de isolamento baseadas em VPN"""
    
    def __init__(self, config: ConfiguradorEpidemiologico):
        self.config = config
    
    def gerar_orientacao(self, vpn: float, pressao: str) -> str:
        """Gerar orientação de isolamento"""
        
        if vpn >= 0.95 and pressao in ["BAIXA", "MODERADA"]:
            return "LIBERAÇÃO SEGURA - VPN alto com baixa circulação"
        
        elif vpn >= 0.90 and pressao == "BAIXA":
            return "LIBERAÇÃO ACEITÁVEL - VPN adequado, circulação baixa"
        
        elif vpn >= 0.85 and pressao in ["BAIXA", "MODERADA"]:
            return "LIBERAÇÃO COM CAUTELA - Considerar contexto clínico individual"
        
        elif pressao in ["ALTA", "MUITO_ALTA"]:
            return "MANTER ISOLAMENTO - Alta circulação viral na região"
        
        else:
            return "AVALIAÇÃO INDIVIDUALIZADA - VPN insuficiente para decisão automática"

class SistemaVigilanciaRespiratoria:
    """Sistema principal de vigilância"""
    
    def __init__(self, arquivo_config: str = "configuracao_vigilancia.json"):
        # Carregar configuração
        with open(arquivo_config, 'r', encoding='utf-8') as f:
            self.config_json = json.load(f)
        
        # Configurar para HUSF Bragança Paulista
        config_husf = self.config_json['configuracoes_regionais']['husf_braganca']
        params = config_husf['parametros_epidemiologicos']
        
        self.config = ConfiguradorEpidemiologico(
            codigo_municipio=config_husf['codigo_municipio'],
            codigo_estado=config_husf['codigo_estado'],
            nome_regiao=config_husf['nome_regiao'],
            sensibilidade_antigeno=params['sensibilidade_antigeno'],
            especificidade_antigeno=params['especificidade_antigeno'],
            limiar_baixa_circulacao=params['limiar_baixa_circulacao'],
            limiar_media_circulacao=params['limiar_media_circulacao'],
            limiar_alta_circulacao=params['limiar_alta_circulacao'],
            janela_analise_dias=params['janela_analise_dias'],
            janela_tendencia_dias=params['janela_tendencia_dias']
        )
        
        self.extractor = ExtractorDadosEpidemiologicos(self.config)
        self.calculador = CalculadorPressaoEpidemiologica(self.config)
        self.orientador = OrientadorIsolamento(self.config)
    
    def executar_analise_completa(self) -> Dict:
        """Executar análise completa de vigilância"""
        
        logger.info("=== INICIANDO ANÁLISE DE VIGILÂNCIA RESPIRATÓRIA ===")
        
        # 1. Baixar dados SIVEP-Gripe
        df = self.extractor.baixar_dados_sivep()
        if df is None:
            logger.error("❌ Falha ao obter dados SIVEP-Gripe")
            return None
        
        # 2. Filtrar por região
        df_regiao = self.extractor.filtrar_dados_regiao(df)
        
        # 3. Calcular positividade
        positividade = self.calculador.calcular_positividade_por_patogeno(df_regiao)
        logger.info("Calculando VPN para cada patógeno...")
        
        # 4. Calcular VPN
        vpn_por_patogeno = {}
        for patogeno, prev in positividade.items():
            vpn_por_patogeno[patogeno] = self.calculador.calcular_vpn(prev)
        
        # 5. Classificar pressão epidemiológica
        pressao = self.calculador.classificar_pressao_epidemiologica(positividade)
        logger.info("Classificando pressão epidemiológica...")
        
        # 6. Gerar orientações
        orientacoes = {}
        for patogeno in positividade.keys():
            vpn = vpn_por_patogeno[patogeno]
            pressao_patogeno = pressao[patogeno]
            orientacoes[patogeno] = self.orientador.gerar_orientacao(vpn, pressao_patogeno)
        
        logger.info("Gerando orientações de isolamento...")
        
        # 7. Compilar resultados
        resultados = {
            'timestamp': datetime.now().isoformat(),
            'regiao': self.config.nome_regiao,
            'total_casos': len(df_regiao),
            'positividade': positividade,
            'vpn': vpn_por_patogeno,
            'pressao_epidemiologica': pressao,
            'orientacoes': orientacoes,
            'parametros': {
                'sensibilidade': self.config.sensibilidade_antigeno,
                'especificidade': self.config.especificidade_antigeno,
                'janela_analise_dias': self.config.janela_analise_dias
            }
        }
        
        logger.info("=== ANÁLISE CONCLUÍDA COM SUCESSO ===")
        return resultados
    
    def gerar_relatorio(self, resultados: Dict) -> str:
        """Gerar relatório formatado"""
        
        timestamp = datetime.fromisoformat(resultados['timestamp'])
        
        relatorio = f"""
# RELATÓRIO EPIDEMIOLÓGICO - ORIENTAÇÕES ISOLAMENTO RESPIRATÓRIO
## Período: {timestamp.strftime('%B/%Y')}
## Hospital: HUSF
## Responsável: Dr. Leandro - SCIH/CCIH

---

### PRESSÃO EPIDEMIOLÓGICA REGIONAL ({resultados['regiao']})

**Positividade por Patógeno (últimas {resultados['parametros']['janela_analise_dias']} dias):**
- **COVID19**: {resultados['positividade']['COVID19']:.1%}
- **INFLUENZA**: {resultados['positividade']['INFLUENZA']:.1%}  
- **VSR**: {resultados['positividade']['VSR']:.1%}
- **OUTROS**: {resultados['positividade']['OUTROS']:.1%}


### VALOR PREDITIVO NEGATIVO - TESTE DE ANTÍGENO

**Parâmetros utilizados:**
- Sensibilidade: {resultados['parametros']['sensibilidade']:.0%}
- Especificidade: {resultados['parametros']['especificidade']:.0%}

### ORIENTAÇÕES POR PATÓGENO

**COVID19**: {resultados['orientacoes']['COVID19']}

**INFLUENZA**: {resultados['orientacoes']['INFLUENZA']}

**VSR**: {resultados['orientacoes']['VSR']}

**OUTROS**: {resultados['orientacoes']['OUTROS']}


### RECOMENDAÇÕES GERAIS

1. **Isolamento Precaucional**: Manter até resultado de teste confirmatório em cenário de alta circulação viral
2. **Liberação com Teste Negativo**: Aplicar VPN conforme pressão epidemiológica local
3. **Monitoramento Contínuo**: Reavaliar orientações quinzenalmente baseado em dados atualizados

---
*Relatório gerado automaticamente em {timestamp.strftime('%d/%m/%Y %H:%M')}*
*Base: Dados OpenDataSUS (SIVEP-Gripe)*
        """
        
        return relatorio.strip()

def main():
    """Função principal"""
    
    try:
        # Inicializar sistema
        sistema = SistemaVigilanciaRespiratoria()
        
        # Executar análise
        resultados = sistema.executar_analise_completa()
        
        if resultados:
            # Gerar relatório
            relatorio = sistema.gerar_relatorio(resultados)
            
            # Salvar relatório
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            arquivo_relatorio = f"relatorios/vigilancia_respiratoria_{timestamp}.md"
            
            with open(arquivo_relatorio, 'w', encoding='utf-8') as f:
                f.write(relatorio)
            
            # Salvar dados JSON
            arquivo_dados = f"dados/resultados_vigilancia_{timestamp}.json"
            with open(arquivo_dados, 'w', encoding='utf-8') as f:
                json.dump(resultados, f, indent=2, ensure_ascii=False)
            
            # Exibir resumo
            print("\n" + "="*80)
            print("🏥 SISTEMA DE VIGILÂNCIA RESPIRATÓRIA - HUSF BRAGANÇA PAULISTA")
            print("="*80)
            
            print(f"\n📊 DADOS ANALISADOS:")
            print(f"• Total de casos: {resultados['total_casos']}")
            print(f"• Região: {resultados['regiao']}")
            print(f"• Período: Últimos {resultados['parametros']['janela_analise_dias']} dias")
            
            print(f"\n📈 POSITIVIDADE POR PATÓGENO:")
            for patogeno, valor in resultados['positividade'].items():
                print(f"• {patogeno}: {valor:.1%}")
            
            print(f"\n🔬 VALOR PREDITIVO NEGATIVO (VPN):")
            for patogeno, valor in resultados['vpn'].items():
                print(f"• {patogeno}: {valor:.1%}")
            
            print(f"\n⚠️ PRESSÃO EPIDEMIOLÓGICA:")
            for patogeno, pressao in resultados['pressao_epidemiologica'].items():
                emoji = {"BAIXA": "🟢", "MODERADA": "🟡", "ALTA": "🟠", "MUITO_ALTA": "🔴"}
                print(f"{emoji.get(pressao, '⚪')} {patogeno}: {pressao}")
            
            print(f"\n🏥 ORIENTAÇÕES DE ISOLAMENTO:")
            for patogeno, orientacao in resultados['orientacoes'].items():
                print(f"• {patogeno}: {orientacao}")
            
            print(f"\n📄 RELATÓRIO SALVO: {arquivo_relatorio}")
            print(f"📊 DADOS SALVOS: {arquivo_dados}")
            
            print("\n" + "="*80)
            print("✅ ANÁLISE CONCLUÍDA COM SUCESSO!")
            print("="*80)
            
        else:
            print("❌ Falha na análise. Verifique os logs.")
            
    except Exception as e:
        logger.error(f"❌ Erro no sistema: {e}")
        print(f"\n❌ ERRO: {e}")

if __name__ == "__main__":
    main()
