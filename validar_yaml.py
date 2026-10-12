#!/usr/bin/env python3
"""
VALIDADOR DE SINTAXE YAML
Verifica se o arquivo vigilancia_simples.yml está correto antes de usar
"""

import yaml
import sys

def validar_yaml(arquivo):
    """Valida sintaxe YAML"""
    
    print(f"🔍 VALIDANDO: {arquivo}")
    print("="*50)
    
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        print(f"📄 Arquivo lido: {len(conteudo)} caracteres")
        
        # Tentar fazer parse do YAML
        dados = yaml.safe_load(conteudo)
        
        print("✅ SINTAXE YAML: VÁLIDA")
        print("")
        
        # Verificar estrutura básica
        if 'name' in dados:
            print(f"📋 Nome: {dados['name']}")
        
        if 'on' in dados:
            print("📅 Triggers configurados:")
            if 'schedule' in dados['on']:
                for schedule in dados['on']['schedule']:
                    print(f"   ⏰ Cron: {schedule.get('cron', 'N/A')}")
            if 'workflow_dispatch' in dados['on']:
                print("   🔧 Manual execution: Habilitado")
        
        if 'jobs' in dados:
            print(f"🔧 Jobs: {len(dados['jobs'])}")
            for job_name, job_data in dados['jobs'].items():
                steps = job_data.get('steps', [])
                print(f"   📋 {job_name}: {len(steps)} steps")
        
        print("")
        print("🎯 VALIDAÇÃO COMPLETA: ✅ SUCESSO")
        print("📱 Arquivo está pronto para uso!")
        
        return True
        
    except yaml.YAMLError as e:
        print("❌ ERRO DE SINTAXE YAML:")
        print(f"   {str(e)}")
        
        # Tentar identificar linha do erro
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            print(f"   📍 Linha: {mark.line + 1}, Coluna: {mark.column + 1}")
        
        return False
        
    except Exception as e:
        print(f"❌ ERRO GERAL: {e}")
        return False

def verificar_problemas_comuns(arquivo):
    """Verifica problemas comuns em YAML"""
    
    print("\n🔍 VERIFICANDO PROBLEMAS COMUNS:")
    
    with open(arquivo, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    
    problemas = []
    
    for i, linha in enumerate(linhas, 1):
        # Verificar tabs
        if '\t' in linha:
            problemas.append(f"Linha {i}: Contém TAB (usar spaces)")
        
        # Verificar indentação inconsistente
        if linha.strip() and not linha.startswith(' ' * (len(linha) - len(linha.lstrip()))):
            if len(linha) - len(linha.lstrip()) % 2 != 0:
                problemas.append(f"Linha {i}: Indentação ímpar (usar múltiplos de 2)")
        
        # Verificar aspas não fechadas
        if linha.count('"') % 2 != 0:
            problemas.append(f"Linha {i}: Aspas duplas não fechadas")
        
        if linha.count("'") % 2 != 0:
            problemas.append(f"Linha {i}: Aspas simples não fechadas")
    
    if problemas:
        print("⚠️ PROBLEMAS ENCONTRADOS:")
        for problema in problemas:
            print(f"   • {problema}")
        return False
    else:
        print("✅ Nenhum problema comum detectado")
        return True

if __name__ == "__main__":
    arquivo = "vigilancia_simples.yml"
    
    print("🔧 VALIDADOR DE YAML - WORKFLOW GITHUB ACTIONS")
    print("="*60)
    print("")
    
    # Verificar se arquivo existe
    try:
        open(arquivo, 'r').close()
    except FileNotFoundError:
        print(f"❌ Arquivo {arquivo} não encontrado!")
        sys.exit(1)
    
    # Validar sintaxe
    yaml_ok = validar_yaml(arquivo)
    
    # Verificar problemas comuns
    problemas_ok = verificar_problemas_comuns(arquivo)
    
    print("\n" + "="*60)
    
    if yaml_ok and problemas_ok:
        print("🎉 ARQUIVO COMPLETAMENTE VÁLIDO!")
        print("✅ Pode ser usado sem problemas")
        print("")
        print("📱 COMANDOS PARA APLICAR:")
        print("   cp vigilancia_simples.yml .github/workflows/vigilancia.yml")
        print("   git add .github/workflows/vigilancia.yml")
        print("   git commit -m '✅ YAML validado e corrigido'")
        print("   git push origin main")
        
    else:
        print("❌ ARQUIVO TEM PROBLEMAS!")
        print("🔧 Precisa ser corrigido antes de usar")
        
    print("")
    print("🎯 Validação concluída!")
