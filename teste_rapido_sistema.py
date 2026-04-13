#!/usr/bin/env python3
"""
VERIFICAÇÃO RÁPIDA - SISTEMA VIGILÂNCIA HUSF
Teste rápido para verificar se sistema está funcionando
"""

import os
import subprocess
import sys
from datetime import datetime

def teste_rapido():
    """Teste rápido do sistema de vigilância"""
    
    print("⚡ TESTE RÁPIDO - SISTEMA VIGILÂNCIA HUSF")
    print("=" * 50)
    
    # 1. Verificar arquivo principal
    arquivo = "sistema_vigilancia_dinamico.py"
    if os.path.exists(arquivo):
        print(f"✅ Arquivo encontrado: {arquivo}")
    else:
        print(f"❌ Arquivo NÃO encontrado: {arquivo}")
        print("💡 Certifique-se de estar na pasta correta")
        return False
    
    # 2. Testar execução
    print("\n🔄 Testando execução...")
    try:
        # Executar sistema
        result = subprocess.run(
            [sys.executable, arquivo], 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Sistema executou sem erros")
            
            # Verificar saída
            print("\n📋 ÚLTIMAS LINHAS DA SAÍDA:")
            linhas_saida = result.stdout.strip().split('\n')[-5:]
            for linha in linhas_saida:
                print(f"   {linha}")
            
            # Verificar arquivo gerado
            if os.path.exists('web/index.html'):
                print("\n📱 ✅ Arquivo HTML gerado com sucesso")
                
                # Verificar tamanho
                size = os.path.getsize('web/index.html')
                print(f"   📊 Tamanho: {size:,} bytes")
                
                if size > 10000:  # Pelo menos 10KB
                    print("   ✅ Tamanho adequado")
                else:
                    print("   ⚠️ Arquivo muito pequeno")
                
                return True
            else:
                print("\n❌ Arquivo HTML NÃO foi gerado")
                return False
        else:
            print("❌ Sistema executou COM ERROS")
            print("\n🐛 ERROS ENCONTRADOS:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Sistema travou (timeout)")
        return False
    except Exception as e:
        print(f"❌ Erro na execução: {e}")
        return False

def verificar_dados_html():
    """Verificar dados no HTML gerado"""
    
    html_path = "web/index.html"
    if not os.path.exists(html_path):
        print("❌ Arquivo HTML não encontrado para análise")
        return
    
    print("\n🔍 ANALISANDO DADOS NO HTML...")
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Procurar indicadores chave
    indicadores = {
        'SE 11': 'SE 11' in html,
        'SE 12': 'SE 12' in html,
        'Março 2026': 'março' in html.lower() and '2026' in html,
        'Dr. Leandro': 'Dr. Leandro' in html,
        'VPNs calculados': '%' in html and 'VPN' in html
    }
    
    for nome, presente in indicadores.items():
        status = "✅" if presente else "❌"
        print(f"   {status} {nome}")
    
    # Data de geração
    if 'março' in html.lower():
        print("   ✅ Dados de março 2026 detectados")
    else:
        print("   ⚠️ Dados de março 2026 não detectados")

def main():
    """Execução principal"""
    
    print(f"🕐 Iniciado em: {datetime.now().strftime('%H:%M:%S')}")
    
    # Teste principal
    sucesso = teste_rapido()
    
    if sucesso:
        verificar_dados_html()
        print("\n🎉 RESULTADO: Sistema está FUNCIONANDO")
        print("📱 Acesse: https://doutorleandromendes.github.io/vigilancia_husf/")
    else:
        print("\n🚨 RESULTADO: Sistema tem PROBLEMAS")
        print("💡 Execute o diagnóstico completo para mais detalhes")
    
    print(f"\n⏰ Finalizado em: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
