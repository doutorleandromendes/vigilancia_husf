#!/usr/bin/env python3
"""
Automação Semanal de Vigilância Respiratória
============================================

Script para automatização via cron job da extração e análise de dados 
epidemiológicos para orientação de isolamento respiratório.

Configurar no cron para execução quinzenal:
0 8 * * 1,4 /usr/bin/python3 /path/to/automacao_vigilancia.py

Autor: Dr. Leandro (HUSF)
"""

import sys
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import traceback
from datetime import datetime
import logging

# Adicionar o diretório do sistema ao path
sys.path.append(os.path.dirname(__file__))

from sistema_vigilancia_respiratoria import (
    SistemaVigilanciaRespiratoria, 
    ConfiguradorEpidemiologico
)

class AutomacaoVigilancia:
    """Automação do sistema de vigilância respiratória"""
    
    def __init__(self):
        # Configuração de logging para arquivos
        log_file = f'/var/log/vigilancia_respiratoria_{datetime.now().strftime("%Y%m")}.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Configuração do sistema
        self.config = ConfiguradorEpidemiologico(
            codigo_municipio="3543402",  # Campinas-SP
            nome_regiao="Região Metropolitana de Campinas - HUSF",
            limiar_baixa_circulacao=0.05,
            limiar_media_circulacao=0.15,
            limiar_alta_circulacao=0.25
        )
        
        # Configuração de email (configurar conforme necessário)
        self.smtp_config = {
            'servidor': 'smtp.gmail.com',  # Ajustar conforme servidor
            'porta': 587,
            'usuario': 'vigilancia.husf@gmail.com',  # Email de envio
            'senha': os.environ.get('EMAIL_PASSWORD', ''),  # Senha via variável de ambiente
            'destinatarios': [
                'leandro.ccih@husf.br',  # Dr. Leandro - CCIH
                'direcao.clinica@husf.br',  # Direção clínica
                'cti.chefia@husf.br'  # Chefia UTI
            ]
        }
        
    def executar_analise_automatizada(self) -> bool:
        """Executa análise automatizada completa"""
        
        try:
            self.logger.info("=== INICIANDO ANÁLISE AUTOMATIZADA DE VIGILÂNCIA RESPIRATÓRIA ===")
            
            # Inicializar sistema
            sistema = SistemaVigilanciaRespiratoria(self.config)
            
            # Executar análise
            resultados = sistema.executar_analise_completa()
            
            if not resultados:
                self.logger.error("Falha na obtenção de resultados da análise")
                return False
            
            # Gerar visualizações
            sistema.gerar_dashboard_visual(resultados)
            
            # Exportar resultados
            arquivo_json = sistema.exportar_resultados(resultados, 'json')
            arquivo_md = sistema.exportar_resultados(resultados, 'markdown')
            
            # Enviar por email
            sucesso_email = self._enviar_relatorio_por_email(resultados, arquivo_md, arquivo_json)
            
            # Arquivar dados históricos
            self._arquivar_dados_historicos(resultados, arquivo_json)
            
            self.logger.info("=== ANÁLISE AUTOMATIZADA CONCLUÍDA COM SUCESSO ===")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na análise automatizada: {str(e)}")
            self.logger.error(traceback.format_exc())
            self._enviar_alerta_erro(str(e))
            return False
    
    def _enviar_relatorio_por_email(self, resultados: dict, arquivo_md: str, arquivo_json: str) -> bool:
        """Envia relatório por email para a equipe"""
        
        if not self.smtp_config['senha']:
            self.logger.warning("Senha de email não configurada - pulando envio")
            return False
        
        try:
            # Criar mensagem
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['usuario']
            msg['To'] = ', '.join(self.smtp_config['destinatarios'])
            msg['Subject'] = f"[HUSF-CCIH] Relatório Vigilância Respiratória - {datetime.now().strftime('%d/%m/%Y')}"
            
            # Corpo do email
            corpo_email = f"""
Prezados colegas da equipe médica e direção clínica,

Segue relatório automático de vigilância respiratória para orientações sobre isolamento precaucional e liberação de pacientes suspeitos.

=== RESUMO EXECUTIVO ===

Período analisado: {resultados['periodo_dados']}
Região: {resultados['regiao']}
Total de casos analisados: {resultados['total_casos_analisados']}

POSITIVIDADE ATUAL:
"""
            
            for patogeno, taxa in resultados['positividade'].items():
                pressao = resultados['pressao_epidemiologica'].get(patogeno, 'N/A')
                corpo_email += f"• {patogeno.upper()}: {taxa:.1%} (Pressão: {pressao})\n"
            
            corpo_email += f"""

ORIENTAÇÕES PRINCIPAIS:
"""
            
            for patogeno, orientacao in resultados['orientacoes'].items():
                corpo_email += f"• {patogeno.upper()}: {orientacao}\n"
            
            corpo_email += f"""

Ver relatório completo em anexo para detalhes técnicos e metodologia.

---
Sistema de Vigilância Respiratória - HUSF
Responsável: Dr. Leandro (CCIH)
Gerado automaticamente em {datetime.now().strftime('%d/%m/%Y às %H:%M')}
"""
            
            msg.attach(MIMEText(corpo_email, 'plain', 'utf-8'))
            
            # Anexar relatório markdown
            with open(arquivo_md, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= relatorio_vigilancia_respiratoria.md'
                )
                msg.attach(part)
            
            # Anexar dashboard (se existir)
            dashboard_path = '/home/claude/dashboard_vigilancia_respiratoria.png'
            if os.path.exists(dashboard_path):
                with open(dashboard_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= dashboard_vigilancia_respiratoria.png'
                    )
                    msg.attach(part)
            
            # Enviar email
            server = smtplib.SMTP(self.smtp_config['servidor'], self.smtp_config['porta'])
            server.starttls()
            server.login(self.smtp_config['usuario'], self.smtp_config['senha'])
            text = msg.as_string()
            server.sendmail(self.smtp_config['usuario'], self.smtp_config['destinatarios'], text)
            server.quit()
            
            self.logger.info(f"Relatório enviado por email para {len(self.smtp_config['destinatarios'])} destinatários")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao enviar email: {str(e)}")
            return False
    
    def _enviar_alerta_erro(self, erro: str) -> None:
        """Envia alerta de erro por email"""
        
        if not self.smtp_config['senha']:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['usuario']
            msg['To'] = self.smtp_config['destinatarios'][0]  # Apenas Dr. Leandro
            msg['Subject'] = "[HUSF-CCIH] ERRO - Sistema Vigilância Respiratória"
            
            corpo = f"""
ALERTA: Falha no sistema de vigilância respiratória

Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
Erro: {erro}

Favor verificar logs do sistema para mais detalhes.

Sistema de Vigilância Respiratória - HUSF
"""
            
            msg.attach(MIMEText(corpo, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(self.smtp_config['servidor'], self.smtp_config['porta'])
            server.starttls()
            server.login(self.smtp_config['usuario'], self.smtp_config['senha'])
            server.sendmail(self.smtp_config['usuario'], [self.smtp_config['destinatarios'][0]], msg.as_string())
            server.quit()
            
            self.logger.info("Alerta de erro enviado")
            
        except Exception as e:
            self.logger.error(f"Erro ao enviar alerta: {str(e)}")
    
    def _arquivar_dados_historicos(self, resultados: dict, arquivo_json: str) -> None:
        """Arquiva dados históricos para análise de tendências"""
        
        try:
            # Criar diretório de arquivo se não existir
            arquivo_dir = '/var/lib/vigilancia_respiratoria'
            os.makedirs(arquivo_dir, exist_ok=True)
            
            # Copiar arquivo para diretório histórico
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            arquivo_historico = os.path.join(arquivo_dir, f'vigilancia_{timestamp}.json')
            
            import shutil
            shutil.copy2(arquivo_json, arquivo_historico)
            
            self.logger.info(f"Dados arquivados em: {arquivo_historico}")
            
            # Limpeza de arquivos antigos (manter apenas últimos 3 meses)
            self._limpar_arquivos_antigos(arquivo_dir)
            
        except Exception as e:
            self.logger.error(f"Erro ao arquivar dados: {str(e)}")
    
    def _limpar_arquivos_antigos(self, diretorio: str, dias_retencao: int = 90) -> None:
        """Remove arquivos mais antigos que X dias"""
        
        try:
            import glob
            from datetime import timedelta
            
            cutoff_date = datetime.now() - timedelta(days=dias_retencao)
            
            for arquivo in glob.glob(os.path.join(diretorio, 'vigilancia_*.json')):
                if os.path.getmtime(arquivo) < cutoff_date.timestamp():
                    os.remove(arquivo)
                    self.logger.info(f"Arquivo antigo removido: {arquivo}")
                    
        except Exception as e:
            self.logger.error(f"Erro na limpeza de arquivos: {str(e)}")


def main():
    """Função principal para execução via cron"""
    
    automacao = AutomacaoVigilancia()
    
    # Executar análise
    sucesso = automacao.executar_analise_automatizada()
    
    # Exit code para cron
    sys.exit(0 if sucesso else 1)


if __name__ == "__main__":
    main()
