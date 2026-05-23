#!/usr/bin/env python3
"""
INVESTIGAÇÃO URGENTE: ONDE ESTÃO OS DADOS SE 15-21?
Fiocruz pode ter mudado padrões de nomenclatura ou estrutura

Dr. Leandro Mendes - SCIH HUSF Bragança Paulista
"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from datetime import datetime, timedelta

def investigar_dados_perdidos():
    """Investigação completa para encontrar dados SE 15-21"""
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    })
    
    print("🔍 INVESTIGAÇÃO: DADOS PERDIDOS SE 15-21")
    print("="*60)
    print("")
    
    # 1. VERIFICAR MÚLTIPLOS PADRÕES DE NOMENCLATURA
    print("📋 1. TESTANDO NOVOS PADRÕES DE NOMENCLATURA:")
    print("")
    
    base_urls = [
        "https://agencia.fiocruz.br/sites/agencia.fiocruz.br/files/",
        "https://portal.fiocruz.br/sites/default/files/",
        "https://fiocruz.br/sites/default/files/"
    ]
    
    padroes_nome = [
        # Padrões antigos
        "Resumo_InfoGripe_2026_{se:02d}_0.pdf",
        "Resumo_InfoGripe_2026_{se}.pdf",
        # Possíveis novos padrões
        "Boletim_InfoGripe_2026_{se:02d}.pdf",
        "InfoGripe_Resumo_2026_{se:02d}.pdf",
        "InfoGripe_SE{se:02d}_2026.pdf",
        "Boletim_Semanal_InfoGripe_2026_{se:02d}.pdf",
        "InfoGripe_2026_SE_{se:02d}.pdf",
        "Resumo_InfoGripe_2026_Semana_{se:02d}.pdf"
    ]
    
    dados_encontrados = []
    
    for se in range(21, 14, -1):  # SE 21 até 15
        print(f"   🔍 Testando SE {se:02d}:")
        
        for base_url in base_urls:
            for padrao in padroes_nome:
                url = base_url + padrao.format(se=se)
                
                try:
                    response = session.head(url, timeout=8)
                    if response.status_code == 200:
                        size = int(response.headers.get('content-length', 0))
                        if size > 50000:  # > 50KB
                            print(f"      ✅ ENCONTRADO: SE {se:02d} - {url}")
                            dados_encontrados.append((se, url))
                            break
                except:
                    continue
            else:
                continue
            break
        else:
            print(f"      ❌ SE {se:02d}: Não encontrada")
        
        print("")
    
    print("="*60)
    
    # 2. SCRAPING AVANÇADO DAS PÁGINAS
    print("📋 2. SCRAPING AVANÇADO DE PÁGINAS FIOCRUZ:")
    print("")
    
    sites_investigar = [
        "https://agencia.fiocruz.br/noticias",
        "https://agencia.fiocruz.br",
        "https://portal.fiocruz.br/noticias",
        "https://fiocruz.br/noticias"
    ]
    
    pdfs_scraping = []
    
    for site in sites_investigar:
        try:
            print(f"   🌐 Investigando: {site}")
            response = session.get(site, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Buscar TODOS os links que mencionam InfoGripe
                links_infogripe = []
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    texto = link.get_text(strip=True).lower()
                    
                    if any(palavra in texto for palavra in ['infogripe', 'info gripe', 'boletim', 'epidemiológic']):
                        url_completa = urljoin(site, href)
                        links_infogripe.append((texto, url_completa))
                
                print(f"      📄 {len(links_infogripe)} links InfoGripe encontrados")
                
                # Analisar os links mais recentes
                for i, (texto, url) in enumerate(links_infogripe[:5]):
                    print(f"         {i+1}. {texto[:50]}... → {url}")
                    
                    # Se é PDF direto
                    if url.endswith('.pdf'):
                        se = extrair_se_url(url)
                        if se and se >= 15:
                            pdfs_scraping.append((se, url))
                    
                    # Se é página de notícia, investigar
                    elif 'noticia' in url or 'infogripe' in url:
                        pdfs_noticia = investigar_pagina_noticia(session, url)
                        pdfs_scraping.extend(pdfs_noticia)
                
            print("")
            
        except Exception as e:
            print(f"      ❌ Erro: {e}")
            print("")
    
    print("="*60)
    
    # 3. RESUMO DOS ACHADOS
    print("📋 3. RESUMO DOS ACHADOS:")
    print("")
    
    todos_dados = dados_encontrados + pdfs_scraping
    todos_dados = list(set(todos_dados))  # Remove duplicatas
    todos_dados.sort(reverse=True)  # Mais recente primeiro
    
    if todos_dados:
        print("   ✅ DADOS ENCONTRADOS:")
        for se, url in todos_dados:
            print(f"      SE {se:02d}: {url}")
        
        se_mais_recente = max(se for se, url in todos_dados)
        print(f"\n   🎯 SE MAIS RECENTE DISPONÍVEL: {se_mais_recente}")
        
        if se_mais_recente >= 18:
            print("   ✅ Dados relativamente atuais encontrados!")
        elif se_mais_recente >= 16:
            print("   ⚠️ Dados com defasagem moderada")
        else:
            print("   ❌ Dados muito defasados")
    else:
        print("   ❌ NENHUM DADO RECENTE ENCONTRADO")
        print("   🚨 POSSÍVEIS CAUSAS:")
        print("      • Fiocruz mudou estrutura completamente")
        print("      • Mudança de nomenclatura radical") 
        print("      • InfoGripe descontinuado")
        print("      • Dados migrados para novo sistema")
    
    print("")
    print("="*60)
    
    # 4. RECOMENDAÇÕES
    print("📋 4. RECOMENDAÇÕES URGENTES:")
    print("")
    
    if todos_dados:
        se_mais_recente = max(se for se, url in todos_dados)
        url_mais_recente = next(url for se, url in todos_dados if se == se_mais_recente)
        
        print(f"   🎯 ATUALIZAR SISTEMA PARA SE {se_mais_recente}")
        print(f"   📄 URL: {url_mais_recente}")
        
        # Detectar novo padrão
        novo_padrao = detectar_padrao_url(url_mais_recente)
        if novo_padrao:
            print(f"   🔧 NOVO PADRÃO DETECTADO: {novo_padrao}")
        
        print("")
        print("   📱 COMANDOS PARA TESTAR:")
        print(f"   wget '{url_mais_recente}' -O teste_se_{se_mais_recente}.pdf")
        print(f"   python3 -c \"import requests; r=requests.get('{url_mais_recente}'); print('Tamanho:', len(r.content), 'bytes')\"")
        
    else:
        print("   🆘 INVESTIGAÇÃO MANUAL NECESSÁRIA:")
        print("      1. Acessar https://agencia.fiocruz.br manualmente")
        print("      2. Procurar por 'InfoGripe' ou 'boletim epidemiológico'")
        print("      3. Verificar se InfoGripe foi substituído")
        print("      4. Contatar Fiocruz se necessário")
    
    return todos_dados

def extrair_se_url(url):
    """Extrai SE de uma URL usando múltiplos padrões"""
    padroes = [
        r'InfoGripe.*?2026.*?(\d{1,2})',
        r'2026.*?(\d{1,2}).*?\.pdf',
        r'SE.*?(\d{1,2})',
        r'semana.*?(\d{1,2})',
        r'_(\d{1,2})_0\.pdf',
        r'_(\d{1,2})\.pdf'
    ]
    
    for padrao in padroes:
        match = re.search(padrao, url, re.IGNORECASE)
        if match:
            se = int(match.group(1))
            if 1 <= se <= 53:
                return se
    return None

def investigar_pagina_noticia(session, url):
    """Investiga uma página de notícia específica"""
    pdfs = []
    
    try:
        response = session.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar links PDF na página
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                if href and href.endswith('.pdf') and 'infogripe' in href.lower():
                    url_pdf = urljoin(url, href)
                    se = extrair_se_url(url_pdf)
                    if se and se >= 15:
                        pdfs.append((se, url_pdf))
    except:
        pass
    
    return pdfs

def detectar_padrao_url(url):
    """Detecta padrão da URL para gerar template"""
    # Extrair SE da URL
    se = extrair_se_url(url)
    if se:
        # Criar template substituindo SE por placeholder
        padrao = re.sub(str(se).zfill(2), '{se:02d}', url)
        padrao = re.sub(str(se), '{se}', padrao)
        return padrao
    return None

if __name__ == "__main__":
    dados = investigar_dados_perdidos()
