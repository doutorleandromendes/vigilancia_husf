#!/usr/bin/env python3
"""
Instalador e Configurador do Sistema de Vigilância Respiratória
==============================================================

Script para instalação automática e configuração inicial do sistema
de vigilância respiratória para orientação de isolamento.

Uso:
    sudo python3 setup_vigilancia.py --hospital HUSF_CAMPINAS
    python3 setup_vigilancia.py --configurar-email
    python3 setup_vigilancia.py --testar-sistema

Autor: Dr. Leandro (HUSF)
"""

import os
import sys
import json
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime
import shutil

class InstaladorVigilancia:
    """Instalador e configurador do sistema de vigilância"""
    
    def __init__(self):
        self.diretorio_base = Path(__file__).parent
        self.diretorio_sistema = Path('/opt/vigilancia_respiratoria')
        self.diretorio_dados = Path('/var/lib/vigilancia_respiratoria')
        self.diretorio_logs = Path('/var/log/vigilancia_respiratoria')
        self.config_file = Path('/etc/vigilancia_respiratoria.json')
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
    
    def verificar_requisitos(self) -> bool:
        """Verifica se os requisitos do sistema estão atendidos"""
        
        self.logger.info("Verificando requisitos do sistema...")
        
        # Verificar Python >= 3.8
        if sys.version_info < (3, 8):
            self.logger.error("Python >= 3.8 é necessário")
            return False
        
        # Verificar se é Linux/Unix
        if os.name != 'posix':
            self.logger.warning("Sistema testado apenas em Linux/Unix")
        
        # Verificar permissões
        if os.geteuid() != 0:
            self.logger.warning("Executar como root para instalação completa")
            self.logger.info("Continuando com instalação limitada...")
        
        return True
    
    def instalar_dependencias(self) -> bool:
        """Instala dependências Python necessárias"""
        
        self.logger.info("Instalando dependências Python...")
        
        dependencias = [
            'pandas>=1.5.0',
            'numpy>=1.21.0',
            'scipy>=1.9.0', 
            'scikit-learn>=1.1.0',
            'matplotlib>=3.5.0',
            'seaborn>=0.11.0',
            'requests>=2.28.0',
            'jupyter>=1.0.0'
        ]
        
        try:
            for dep in dependencias:
                self.logger.info(f"Instalando {dep}...")
                subprocess.run([sys.executable, '-m', 'pip', 'install', dep], 
                             check=True, capture_output=True)
            
            self.logger.info("Dependências instaladas com sucesso")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Erro ao instalar dependências: {e}")
            return False
    
    def criar_estrutura_diretorios(self) -> bool:
        """Cria estrutura de diretórios necessária"""
        
        self.logger.info("Criando estrutura de diretórios...")
        
        diretorios = [
            self.diretorio_sistema,
            self.diretorio_dados,
            self.diretorio_logs,
            self.diretorio_sistema / 'scripts',
            self.diretorio_sistema / 'config',
            self.diretorio_sistema / 'relatorios'
        ]
        
        try:
            for diretorio in diretorios:
                diretorio.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Diretório criado: {diretorio}")
            
            # Ajustar permissões se root
            if os.geteuid() == 0:
                os.system(f"chown -R nobody:nobody {self.diretorio_dados}")
                os.system(f"chmod -R 755 {self.diretorio_dados}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao criar diretórios: {e}")
            return False
    
    def copiar_arquivos_sistema(self) -> bool:
        """Copia arquivos do sistema para diretório de instalação"""
        
        self.logger.info("Copiando arquivos do sistema...")
        
        arquivos_sistema = [
            'sistema_vigilancia_respiratoria.py',
            'automacao_vigilancia.py',
            'analise_tendencias.py',
            'configuracao_vigilancia.json'
        ]
        
        try:
            for arquivo in arquivos_sistema:
                origem = self.diretorio_base / arquivo
                destino = self.diretorio_sistema / 'scripts' / arquivo
                
                if origem.exists():
                    shutil.copy2(origem, destino)
                    self.logger.info(f"Copiado: {arquivo}")
                else:
                    self.logger.warning(f"Arquivo não encontrado: {arquivo}")
            
            # Tornar scripts executáveis
            os.system(f"chmod +x {self.diretorio_sistema}/scripts/*.py")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao copiar arquivos: {e}")
            return False
    
    def configurar_hospital(self, codigo_hospital: str) -> bool:
        """Configura sistema para hospital específico"""
        
        self.logger.info(f"Configurando sistema para: {codigo_hospital}")
        
        # Carregar configurações
        config_origem = self.diretorio_base / 'configuracao_vigilancia.json'
        
        try:
            with open(config_origem, 'r', encoding='utf-8') as f:
                configuracoes = json.load(f)
            
            # Buscar configuração do hospital
            config_hospital = configuracoes['configuracoes_regionais'].get(codigo_hospital.lower())
            
            if not config_hospital:
                self.logger.error(f"Configuração não encontrada para: {codigo_hospital}")
                self.logger.info("Hospitais disponíveis:")
                for codigo in configuracoes['configuracoes_regionais'].keys():
                    self.logger.info(f"  - {codigo}")
                return False
            
            # Criar configuração ativa
            config_ativa = {
                'hospital_selecionado': codigo_hospital.lower(),
                'configuracao': config_hospital,
                'parametros_globais': configuracoes['parametros_globais'],
                'mapeamento_patogenos': configuracoes['mapeamento_patogenos'],
                'templates_relatorios': configuracoes['templates_relatorios']
            }
            
            # Salvar configuração
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_ativa, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Sistema configurado para: {config_hospital['nome_instituicao']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na configuração: {e}")
            return False
    
    def configurar_cron(self) -> bool:
        """Configura tarefas automatizadas no cron"""
        
        if os.geteuid() != 0:
            self.logger.warning("Root necessário para configurar cron")
            return False
        
        self.logger.info("Configurando tarefas automáticas...")
        
        try:
            # Script principal - segundas e quintas às 08:00
            cron_principal = f"0 8 * * 1,4 {sys.executable} {self.diretorio_sistema}/scripts/automacao_vigilancia.py"
            
            # Análise de tendências - terças às 09:00
            cron_tendencias = f"0 9 * * 2 {sys.executable} {self.diretorio_sistema}/scripts/analise_tendencias.py"
            
            # Limpeza - domingos às 02:00
            cron_limpeza = f"0 2 * * 0 find {self.diretorio_dados} -type f -mtime +90 -delete"
            
            # Adicionar ao cron
            cron_entries = [cron_principal, cron_tendencias, cron_limpeza]
            
            with open('/tmp/vigilancia_cron', 'w') as f:
                f.write("# Sistema de Vigilância Respiratória\n")
                for entry in cron_entries:
                    f.write(f"{entry}\n")
            
            # Instalar no cron
            os.system("crontab /tmp/vigilancia_cron")
            os.remove('/tmp/vigilancia_cron')
            
            self.logger.info("Tarefas automáticas configuradas")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao configurar cron: {e}")
            return False
    
    def configurar_email(self) -> bool:
        """Configuração interativa de email"""
        
        self.logger.info("Configuração de email...")
        
        if not self.config_file.exists():
            self.logger.error("Sistema não configurado. Execute primeiro --hospital")
            return False
        
        try:
            # Carregar configuração atual
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print("\n=== CONFIGURAÇÃO DE EMAIL ===")
            print("Para receber relatórios automáticos por email.")
            print("Deixe em branco para pular a configuração.\n")
            
            # Coletar informações
            servidor = input("Servidor SMTP [smtp.gmail.com]: ") or "smtp.gmail.com"
            porta = int(input("Porta SMTP [587]: ") or 587)
            usuario = input("Email de envio: ")
            
            if usuario:
                import getpass
                senha = getpass.getpass("Senha (não será exibida): ")
                
                destinatarios = []
                print("\nDestinários (Enter vazio para finalizar):")
                while True:
                    email = input("Email destinatário: ")
                    if not email:
                        break
                    destinatarios.append(email)
                
                # Atualizar configuração
                config['configuracao']['configuracao_email'] = {
                    'servidor_smtp': servidor,
                    'porta': porta,
                    'usuario': usuario,
                    'senha': senha,  # Em produção, usar variável de ambiente
                    'destinatarios': destinatarios
                }
                
                # Salvar
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.logger.info("Configuração de email salva")
                print("\n⚠️  IMPORTANTE: Por segurança, configure a senha como variável de ambiente:")
                print(f"export EMAIL_PASSWORD='{senha}'")
                print("E remova a senha do arquivo de configuração.")
                
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na configuração de email: {e}")
            return False
    
    def testar_sistema(self) -> bool:
        """Testa funcionamento básico do sistema"""
        
        self.logger.info("Testando sistema...")
        
        if not self.config_file.exists():
            self.logger.error("Sistema não configurado")
            return False
        
        try:
            # Teste de importação
            sys.path.append(str(self.diretorio_sistema / 'scripts'))
            
            from sistema_vigilancia_respiratoria import SistemaVigilanciaRespiratoria, ConfiguradorEpidemiologico
            
            # Carregar config
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            hospital_config = config_data['configuracao']
            
            # Criar configurador
            config = ConfiguradorEpidemiologico(
                codigo_municipio=hospital_config['codigo_municipio'],
                codigo_estado=hospital_config['codigo_estado'],
                nome_regiao=hospital_config['nome_regiao']
            )
            
            # Teste básico
            sistema = SistemaVigilanciaRespiratoria(config)
            
            self.logger.info("✓ Importações OK")
            self.logger.info("✓ Configuração OK")
            self.logger.info("✓ Sistema funcional")
            
            return True
            
        except ImportError as e:
            self.logger.error(f"Erro de importação: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Erro no teste: {e}")
            return False
    
    def instalar_completo(self, hospital: str) -> bool:
        """Instalação completa do sistema"""
        
        self.logger.info("=== INICIANDO INSTALAÇÃO COMPLETA ===")
        
        etapas = [
            ("Verificando requisitos", self.verificar_requisitos),
            ("Instalando dependências", self.instalar_dependencias),
            ("Criando diretórios", self.criar_estrutura_diretorios),
            ("Copiando arquivos", self.copiar_arquivos_sistema),
            ("Configurando hospital", lambda: self.configurar_hospital(hospital)),
            ("Configurando cron", self.configurar_cron),
            ("Testando sistema", self.testar_sistema)
        ]
        
        for nome_etapa, funcao_etapa in etapas:
            self.logger.info(f"➤ {nome_etapa}...")
            
            if not funcao_etapa():
                self.logger.error(f"Falha na etapa: {nome_etapa}")
                return False
        
        self.logger.info("=== INSTALAÇÃO CONCLUÍDA COM SUCESSO ===")
        self.logger.info(f"Sistema instalado em: {self.diretorio_sistema}")
        self.logger.info(f"Configuração: {self.config_file}")
        self.logger.info("Execute --configurar-email para configurar envio de relatórios")
        
        return True
    
    def gerar_documentacao(self) -> bool:
        """Gera documentação de uso do sistema"""
        
        doc = f"""
# Sistema de Vigilância Respiratória - Documentação

## Instalação
```bash
sudo python3 setup_vigilancia.py --hospital husf_campinas
python3 setup_vigilancia.py --configurar-email
```

## Arquivos Principais
- **Sistema principal**: {self.diretorio_sistema}/scripts/sistema_vigilancia_respiratoria.py  
- **Automação**: {self.diretorio_sistema}/scripts/automacao_vigilancia.py  
- **Análise de tendências**: {self.diretorio_sistema}/scripts/analise_tendencias.py  
- **Configuração**: {self.config_file}  

## Diretórios
- **Dados**: {self.diretorio_dados}  
- **Logs**: {self.diretorio_logs}  
- **Relatórios**: {self.diretorio_sistema}/relatorios  

## Uso Manual
```bash
# Análise única
cd {self.diretorio_sistema}/scripts
python3 sistema_vigilancia_respiratoria.py

# Análise com tendências
python3 analise_tendencias.py
```

## Automação
O sistema executa automaticamente:
- **Segundas e quintas às 08:00**: Análise principal + relatórios
- **Terças às 09:00**: Análise de tendências
- **Domingos às 02:00**: Limpeza de dados antigos

## Configuração
Edite o arquivo de configuração em: {self.config_file}

## Logs
Verifique logs em: {self.diretorio_logs}/

## Suporte
Dr. Leandro - CCIH HUSF
Email: leandro.ccih@husf.br

---
Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}
"""
        
        try:
            doc_file = self.diretorio_sistema / 'README.md'
            with open(doc_file, 'w', encoding='utf-8') as f:
                f.write(doc)
            
            self.logger.info(f"Documentação salva em: {doc_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar documentação: {e}")
            return False


def main():
    """Função principal"""
    
    parser = argparse.ArgumentParser(description='Instalador Sistema Vigilância Respiratória')
    parser.add_argument('--hospital', help='Código do hospital (ex: husf_campinas)')
    parser.add_argument('--configurar-email', action='store_true', help='Configurar envio de emails')
    parser.add_argument('--testar-sistema', action='store_true', help='Testar funcionamento')
    parser.add_argument('--gerar-docs', action='store_true', help='Gerar documentação')
    
    args = parser.parse_args()
    
    instalador = InstaladorVigilancia()
    
    if args.hospital:
        sucesso = instalador.instalar_completo(args.hospital)
        if sucesso:
            instalador.gerar_documentacao()
    
    elif args.configurar_email:
        instalador.configurar_email()
    
    elif args.testar_sistema:
        instalador.testar_sistema()
    
    elif args.gerar_docs:
        instalador.gerar_documentacao()
    
    else:
        parser.print_help()
        print("\nExemplos de uso:")
        print("  sudo python3 setup_vigilancia.py --hospital husf_campinas")
        print("  python3 setup_vigilancia.py --configurar-email")
        print("  python3 setup_vigilancia.py --testar-sistema")


if __name__ == "__main__":
    main()
