#!/usr/bin/env python3
"""
Teste de Conectividade - InfoGripe e Dados 2026
HUSF Bragança Paulista - Dr. Leandro

Verifica acesso às múltiplas fontes de dados epidemiológicos
"""

import requests
import json
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def testar_urls_infogripe():
    """Testar URLs do InfoGripe/Fiocruz"""
    
    print("\n" + "="*70)
    print("🔍 TESTANDO CONECTIVIDADE - FONTES DADOS 2026")
    print("="*70)
    
    urls_teste = [
        # GitLab Fiocruz - InfoGripe
        {
            'nome': 'GitLab Fiocruz - InfoGripe Principal',
            'url': 'https://gitlab.fiocruz.br/marcelo.gomes/infogripe/-/raw/master/Dados/InfoGripe/casos_br.csv',
            'tipo': 'CSV'
        },
        {
            'nome': 'GitLab Fiocruz - Casos por UF',
            'url': 'https://gitlab.fiocruz.br/marcelo.gomes/infogripe/-/raw/master/Dados/InfoGripe/casos_uf.csv',
            'tipo': 'CSV'
        },
        
        # Base dos Dados
        {
            'nome': 'Base dos Dados - InfoGripe',
            'url': 'https://basedosdados.org/dataset/736ad69a-5cb1-4e52-9a13-535d439853a6',
            'tipo': 'HTML'
        },
        
        # Site InfoGripe
        {
            'nome': 'Portal InfoGripe',
            'url': 'http://info.gripe.fiocruz.br/',
            'tipo': 'HTML'
        },
        
        # OpenDataSUS - SIVEP (para comparação)
        {
            'nome': 'OpenDataSUS - SIVEP 2024',
            'url': 'https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2024/INFLUD24-03-03-2025.csv',
            'tipo': 'CSV'
        },
        
        # GitHub - Dados SRAG
        {
            'nome': 'GitHub - SRAG Brasil',
            'url': 'https://raw.githubusercontent.com/belisards/srag_brasil/master/casos_uf.csv',
            'tipo': 'CSV'
        }
    ]
    
    resultados = []
    
    print(f"\n📡 Testando {len(urls_teste)} fontes de dados...")
    
    for i, fonte in enumerate(urls_teste, 1):
        print(f"\n[{i}/{len(urls_teste)}] {fonte['nome']}")
        print(f"    URL: {fonte['url']}")
        
        try:
            # Teste HEAD para verificar disponibilidade
            response = requests.head(fonte['url'], timeout=10, allow_redirects=True)
            status = response.status_code
            
            if status == 200:
                # Tentar fazer GET para verificar conteúdo
                response_get = requests.get(fonte['url'], timeout=15, stream=True)
                
                if response_get.status_code == 200:
                    # Verificar tamanho do conteúdo
                    content_length = response_get.headers.get('content-length', 'Desconhecido')
                    content_type = response_get.headers.get('content-type', 'Desconhecido')
                    
                    print(f"    ✅ DISPONÍVEL")
                    print(f"    📊 Tamanho: {content_length} bytes")
                    print(f"    🔧 Tipo: {content_type}")
                    
                    # Para CSVs, tentar ler algumas linhas
                    if fonte['tipo'] == 'CSV':
                        try:
                            content_preview = response_get.text[:500]  # Primeiros 500 caracteres
                            linhas = content_preview.split('\n')[:3]  # Primeiras 3 linhas
                            print(f"    📋 Preview:")
                            for linha in linhas:
                                if linha.strip():
                                    print(f"        {linha[:80]}{'...' if len(linha) > 80 else ''}")
                        except Exception as e:
                            print(f"    ⚠️ Erro no preview: {e}")
                    
                    resultados.append({
                        'nome': fonte['nome'],
                        'url': fonte['url'],
                        'status': 'DISPONÍVEL',
                        'tamanho': content_length,
                        'tipo_conteudo': content_type
                    })
                    
                else:
                    print(f"    ❌ ERRO GET: {response_get.status_code}")
                    resultados.append({
                        'nome': fonte['nome'],
                        'url': fonte['url'],
                        'status': f'ERRO_GET_{response_get.status_code}',
                        'tamanho': None,
                        'tipo_conteudo': None
                    })
            else:
                print(f"    ❌ ERRO HEAD: {status}")
                resultados.append({
                    'nome': fonte['nome'],
                    'url': fonte['url'],
                    'status': f'ERRO_HEAD_{status}',
                    'tamanho': None,
                    'tipo_conteudo': None
                })
                
        except requests.exceptions.Timeout:
            print(f"    ⏰ TIMEOUT")
            resultados.append({
                'nome': fonte['nome'],
                'url': fonte['url'],
                'status': 'TIMEOUT',
                'tamanho': None,
                'tipo_conteudo': None
            })
            
        except requests.exceptions.ConnectionError:
            print(f"    🔌 ERRO DE CONEXÃO")
            resultados.append({
                'nome': fonte['nome'],
                'url': fonte['url'],
                'status': 'ERRO_CONEXAO',
                'tamanho': None,
                'tipo_conteudo': None
            })
            
        except Exception as e:
            print(f"    ❌ ERRO: {e}")
            resultados.append({
                'nome': fonte['nome'],
                'url': fonte['url'],
                'status': f'ERRO: {e}',
                'tamanho': None,
                'tipo_conteudo': None
            })
    
    return resultados

def testar_dados_sivep_alternativos():
    """Testar URLs alternativas do SIVEP para dados mais recentes"""
    
    print(f"\n🔍 TESTANDO DADOS SIVEP ALTERNATIVOS...")
    
    # URLs candidatas para dados mais recentes
    urls_sivep = [
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2025/INFLUD25.csv",
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2025/INFLUD25-03-03-2025.csv",
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2025/INFLUD25-12-31-2025.csv",
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-03-03-2026.csv",
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26.csv"
    ]
    
    for url in urls_sivep:
        print(f"\n📡 Testando: {url}")
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                print(f"    ✅ DISPONÍVEL!")
                print(f"    📊 Tamanho: {response.headers.get('content-length', 'Desconhecido')} bytes")
                print(f"    📅 Modificado: {response.headers.get('last-modified', 'Desconhecido')}")
                return url  # Retornar primeiro disponível
            else:
                print(f"    ❌ Status: {response.status_code}")
        except Exception as e:
            print(f"    ❌ Erro: {e}")
    
    print(f"\n⚠️ Nenhum arquivo SIVEP 2025/2026 encontrado")
    return None

def gerar_relatorio_conectividade(resultados):
    """Gerar relatório de conectividade"""
    
    print(f"\n" + "="*70)
    print("📊 RESUMO DE CONECTIVIDADE")
    print("="*70)
    
    disponivel = [r for r in resultados if r['status'] == 'DISPONÍVEL']
    total = len(resultados)
    
    print(f"\n✅ Fontes disponíveis: {len(disponivel)}/{total}")
    print(f"❌ Fontes com erro: {total - len(disponivel)}/{total}")
    
    if disponivel:
        print(f"\n🟢 FONTES FUNCIONANDO:")
        for fonte in disponivel:
            print(f"  ✓ {fonte['nome']}")
            print(f"    📊 Tamanho: {fonte['tamanho']} bytes")
    
    erros = [r for r in resultados if r['status'] != 'DISPONÍVEL']
    if erros:
        print(f"\n🔴 FONTES COM PROBLEMA:")
        for fonte in erros:
            print(f"  ✗ {fonte['nome']}: {fonte['status']}")
    
    # Recomendações
    print(f"\n💡 RECOMENDAÇÕES:")
    
    if len(disponivel) >= 3:
        print("  🎯 CENÁRIO IDEAL: Múltiplas fontes disponíveis")
        print("  📊 Sistema pode usar dados reais de 2026")
        print("  ✅ Implementar rotação automática entre fontes")
        
    elif len(disponivel) >= 1:
        print("  🟡 CENÁRIO FUNCIONAL: Pelo menos uma fonte disponível")
        print("  📊 Sistema pode funcionar com fonte backup")
        print("  ⚠️ Implementar monitoramento de falhas")
        
    else:
        print("  🔴 CENÁRIO CRÍTICO: Nenhuma fonte disponível")
        print("  📊 Sistema precisa usar dados simulados")
        print("  🚨 Implementar dados de fallback local")
    
    # Salvar relatório
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nome_arquivo = f"teste_conectividade_{timestamp}.json"
    
    relatorio_completo = {
        'timestamp': datetime.now().isoformat(),
        'total_fontes': total,
        'fontes_disponiveis': len(disponivel),
        'fontes_com_erro': len(erros),
        'resultados_detalhados': resultados
    }
    
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        json.dump(relatorio_completo, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Relatório salvo: {nome_arquivo}")
    
    return len(disponivel) > 0  # True se pelo menos uma fonte está disponível

def main():
    """Função principal"""
    
    print("🔬 TESTE DE CONECTIVIDADE - VIGILÂNCIA RESPIRATÓRIA")
    print("🏥 HUSF Bragança Paulista - Dr. Leandro")
    print(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    try:
        # Teste principal
        resultados = testar_urls_infogripe()
        
        # Teste SIVEP alternativo
        url_sivep_disponivel = testar_dados_sivep_alternativos()
        
        # Gerar relatório
        conectividade_ok = gerar_relatorio_conectividade(resultados)
        
        # Conclusões
        print(f"\n" + "="*70)
        print("🎯 CONCLUSÕES E PRÓXIMOS PASSOS")
        print("="*70)
        
        if conectividade_ok:
            print("✅ CONECTIVIDADE OK - Sistema pode usar dados reais")
            print("📊 Prosseguir com sistema de vigilância completo")
            print("🚀 Executar: python3 sistema_vigilancia_2026.py")
        else:
            print("⚠️ CONECTIVIDADE LIMITADA - Usar dados simulados")
            print("📊 Prosseguir com dados de fallback")
            print("🔄 Executar: python3 demo_sistema_vigilancia.py")
        
        if url_sivep_disponivel:
            print(f"💡 SIVEP disponível: {url_sivep_disponivel}")
        else:
            print("💡 SIVEP indisponível - focar no InfoGripe")
        
        print(f"\n📞 Suporte: Dr. Leandro - CCIH/SCIH HUSF")
        print("="*70)
        
    except Exception as e:
        logger.error(f"Erro no teste: {e}")
        print(f"\n❌ ERRO CRÍTICO: {e}")

if __name__ == "__main__":
    main()
