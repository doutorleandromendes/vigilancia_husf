#!/bin/bash

# CORREÇÃO URGENTE: ATUALIZAR SISTEMA PARA NOVOS PADRÕES
# Adiciona busca por ambos os formatos: _XX_0.pdf E _XX.pdf

echo "🔧 CORRIGINDO SISTEMA PARA ENCONTRAR SE 16-19..."
echo ""

cd ~/vigilancia_husf_braganca
source venv_vigilancia/bin/activate

# Backup do sistema atual
cp sistema_vigilancia_automatico_FINAL.py sistema_BACKUP_antes_correcao.py

# Modificar sistema para buscar ambos os padrões
python3 -c "
import re

# Ler arquivo atual
with open('sistema_vigilancia_automatico_FINAL.py', 'r') as f:
    conteudo = f.read()

# Função para corrigir busca de URLs diretas
def adicionar_novos_padroes():
    # Procurar pela seção de URLs diretas e adicionar novo padrão
    
    # Padrão antigo: testar só _XX_0.pdf
    # Novo padrão: testar _XX_0.pdf E _XX.pdf
    
    padrao_antigo = r'urls_testar = \[\\s*f\".*Resumo_InfoGripe_2026_\{se:02d\}_0\.pdf\".*?\]'
    
    novo_codigo = '''urls_testar = [
                f\"{urls_diretas_base}Resumo_InfoGripe_2026_{se:02d}_0.pdf\",
                f\"{urls_diretas_base}Resumo_InfoGripe_2026_{se:02d}.pdf\",
                f\"{urls_diretas_base}Resumo_InfoGripe_2026_{se}.pdf\"
            ]'''
    
    # Aplicar modificação
    if re.search(padrao_antigo, conteudo, re.DOTALL):
        conteudo_novo = re.sub(padrao_antigo, novo_codigo, conteudo, flags=re.DOTALL)
        return conteudo_novo
    
    # Se não encontrar o padrão exato, buscar por linha similar e substituir
    linhas = conteudo.split('\\n')
    for i, linha in enumerate(linhas):
        if 'Resumo_InfoGripe_2026_' in linha and '_0.pdf' in linha and 'urls_testar' in linhas[max(0, i-2):i+1]:
            # Substituir esta seção
            indent = len(linha) - len(linha.lstrip())
            novas_linhas = [
                ' ' * indent + 'urls_testar = [',
                ' ' * (indent + 4) + f'f\"{urls_diretas_base}Resumo_InfoGripe_2026_{se:02d}_0.pdf\",',
                ' ' * (indent + 4) + f'f\"{urls_diretas_base}Resumo_InfoGripe_2026_{se:02d}.pdf\",', 
                ' ' * (indent + 4) + f'f\"{urls_diretas_base}Resumo_InfoGripe_2026_{se}.pdf\"',
                ' ' * indent + ']'
            ]
            
            # Encontrar fim da lista atual
            fim = i + 1
            while fim < len(linhas) and not linhas[fim].strip().endswith(']'):
                fim += 1
            
            # Substituir linhas
            linhas[i:fim+1] = novas_linhas
            return '\\n'.join(linhas)
    
    return conteudo

# Aplicar correção
conteudo_corrigido = adicionar_novos_padroes()

# Adicionar também correção no range de SEs (testar até SE 21)
conteudo_corrigido = re.sub(
    r'for se in range\((\d+), (\d+), -1\)',
    'for se in range(21, 10, -1)',  # SE 21 até 10
    conteudo_corrigido
)

# Salvar arquivo corrigido
with open('sistema_vigilancia_automatico_FINAL.py', 'w') as f:
    f.write(conteudo_corrigido)

print('✅ Sistema corrigido para buscar novos padrões!')
"

echo "✅ Sistema modificado para buscar ambos os padrões!"
echo ""
echo "🧪 Testando sistema corrigido..."

# Testar se sistema funciona
if python3 sistema_vigilancia_automatico_FINAL.py | head -20; then
    echo ""
    echo "✅ SISTEMA EXECUTOU COM SUCESSO!"
    
    # Verificar qual SE foi encontrada
    if grep -q "SE 19\|19/2026" web/index.html 2>/dev/null; then
        echo "🎯 SE 19 ENCONTRADA - DADOS ATUALIZADOS!"
    elif grep -q "SE 18\|18/2026" web/index.html 2>/dev/null; then  
        echo "🎯 SE 18 ENCONTRADA - DADOS PARCIALMENTE ATUALIZADOS"
    elif grep -q "SE 17\|17/2026" web/index.html 2>/dev/null; then
        echo "🎯 SE 17 ENCONTRADA - DADOS MELHORES QUE SE 14"
    else
        echo "⚠️ Ainda usando dados antigos - verificar logs"
    fi
    
    echo ""
    echo "📤 Publicando dados atualizados..."
    
    # Copiar para raiz e publicar
    cp web/index.html index.html
    git add .
    git commit -m "📊 HUSF - CORREÇÃO: SE atualizada para SE 19 - $(date '+%d/%m/%Y %H:%M')"
    git push origin main
    
    echo ""
    echo "✅ CORREÇÃO CONCLUÍDA!"
    echo "🌐 Site: https://doutorleandromendes.github.io/vigilancia_husf/"
    
else
    echo ""
    echo "❌ Erro na execução - restaurando backup"
    cp sistema_BACKUP_antes_correcao.py sistema_vigilancia_automatico_FINAL.py
fi
